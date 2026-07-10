import os
import asyncio
import threading
import tempfile
import re
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, ContentType, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from shazamio import Shazam
import yt_dlp

# ─── Config ───────────────────────────────────────────────────────────────────

BOT_TOKEN   = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "ovoz_media_bot")  # o'zingizning bot username
PORT        = int(os.getenv("PORT", 8000))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")

# ─── Bot ──────────────────────────────────────────────────────────────────────

bot     = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp      = Dispatcher(bot, storage=storage)
shazam  = Shazam()

# URL pattern
URL_PATTERN = re.compile(
    r'https?://[^\s]+'
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

async def recognize_file(file_path: str) -> str:
    try:
        result = await shazam.recognize(file_path)
        track  = result.get("track")
        if not track:
            return "❌ Qo'shiq tanilmadi. Boshqa audio yuboring."

        title    = track.get("title",    "Noma'lum")
        subtitle = track.get("subtitle", "Noma'lum")
        genre    = track.get("genres", {}).get("primary", "")
        url      = track.get("url", "")

        sections = track.get("sections", [])
        album = ""
        year  = ""
        for section in sections:
            for meta in section.get("metadata", []):
                if meta.get("title") == "Album":
                    album = meta.get("text", "")
                if meta.get("title") == "Released":
                    year = meta.get("text", "")

        text = (
            f"🎵 <b>Qo'shiq topildi!</b>\n\n"
            f"🎤 <b>Ijrochi:</b> {subtitle}\n"
            f"🎼 <b>Nomi:</b> {title}\n"
        )
        if album:
            text += f"💿 <b>Albom:</b> {album}\n"
        if year:
            text += f"📅 <b>Yil:</b> {year}\n"
        if genre:
            text += f"🎸 <b>Janr:</b> {genre}\n"
        if url:
            text += f"\n🔗 <a href='{url}'>Shazam'da ochish</a>"

        return text

    except Exception as e:
        return f"❌ Xatolik yuz berdi: {str(e)}"


async def download_and_recognize(message: Message, file_id: str, ext: str):
    await message.answer("🔍 <b>Qo'shiq izlanmoqda...</b>")
    tmp_path = None
    try:
        file = await bot.get_file(file_id)
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp_path = tmp.name
        await bot.download_file(file.file_path, tmp_path)
        result = await recognize_file(tmp_path)
        await message.answer(result, disable_web_page_preview=False)
    except Exception as e:
        await message.answer(f"❌ Fayl yuklanmadi: {str(e)}")
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def is_youtube(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url

def is_instagram(url: str) -> bool:
    return "instagram.com" in url

COOKIES_FILE = os.getenv("COOKIES_FILE", "/app/cookies.txt")

# Invidious public instancelar (YouTube proxy)
INVIDIOUS_INSTANCES = [
    "https://invidious.nerdvpn.de",
    "https://inv.nadeko.net",
    "https://invidious.privacyredirect.com",
    "https://yt.cdaut.de",
]

def get_youtube_id(url: str) -> str | None:
    """YouTube URL dan video ID olish"""
    patterns = [
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


async def get_invidious_stream(video_id: str) -> tuple[str, str, str, int] | None:
    """Invidious API orqali stream URL olish — (stream_url, title, author, duration)"""
    import aiohttp as _aiohttp
    for instance in INVIDIOUS_INSTANCES:
        try:
            api_url = f"{instance}/api/v1/videos/{video_id}"
            async with _aiohttp.ClientSession(timeout=_aiohttp.ClientTimeout(total=10)) as sess:
                async with sess.get(api_url) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()

            title    = data.get("title", "Video")
            author   = data.get("author", "")
            duration = data.get("lengthSeconds", 0)

            # Eng yaxshi mp4 stream tanlash (360p yoki 720p)
            formats = data.get("formatStreams", [])
            chosen  = None
            for q in ["720p", "480p", "360p", "240p"]:
                for f in formats:
                    if f.get("quality") == q and f.get("container") == "mp4":
                        chosen = f
                        break
                if chosen:
                    break
            if not chosen and formats:
                chosen = formats[-1]

            if chosen:
                stream_url = chosen.get("url", "")
                if stream_url:
                    return stream_url, title, author, duration
        except Exception:
            continue
    return None


def base_ydl_opts(url: str) -> dict:
    """Har bir platforma uchun umumiy yt-dlp sozlamalar"""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE

    if is_instagram(url):
        opts.update({
            "extractor_args": {
                "instagram": {"include_ads": False}
            },
        })

    return opts


def download_video_sync(url: str, output_path: str) -> dict:
    """yt-dlp orqali video yuklash (sync, thread ichida)"""
    opts = base_ydl_opts(url)
    opts.update({
        "outtmpl": output_path,
        "format": "best[ext=mp4][filesize<50M]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
    })
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info


def download_audio_sync(url: str, output_path: str) -> dict:
    """yt-dlp orqali faqat audio yuklash (sync, thread ichida)"""
    opts = base_ydl_opts(url)
    opts.update({
        "outtmpl": output_path,
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    })
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info


async def process_url(message: Message, url: str):
    """URL dan video yuklab, Telegram ga yuborish"""
    status_msg = await message.answer("⏳ <b>Video yuklanmoqda...</b>")

    tmp_dir  = tempfile.mkdtemp()
    vid_path = os.path.join(tmp_dir, "video.%(ext)s")
    actual_file = None
    title    = "Video"
    duration = 0

    try:
        # YouTube uchun avval Invidious sinab ko'r
        if is_youtube(url):
            video_id = get_youtube_id(url)
            if video_id:
                await status_msg.edit_text("⏳ <b>YouTube video yuklanmoqda...</b>")
                invidious = await get_invidious_stream(video_id)
                if invidious:
                    stream_url, title, author, duration = invidious
                    # Stream URL dan to'g'ridan yuklash
                    out_file = os.path.join(tmp_dir, "video.mp4")
                    import aiohttp as _aiohttp
                    async with _aiohttp.ClientSession() as sess:
                        async with sess.get(stream_url, timeout=_aiohttp.ClientTimeout(total=120)) as resp:
                            if resp.status == 200:
                                with open(out_file, "wb") as f:
                                    async for chunk in resp.content.iter_chunked(1024 * 64):
                                        f.write(chunk)
                                actual_file = out_file

        # Invidious ishlamasa yoki boshqa platform — yt-dlp
        if not actual_file:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, download_video_sync, url, vid_path
            )
            if info:
                title    = info.get("title", "Video")
                duration = info.get("duration", 0)
            for f in os.listdir(tmp_dir):
                full = os.path.join(tmp_dir, f)
                if os.path.isfile(full) and not full.endswith(".part"):
                    actual_file = full
                    break

        if not actual_file:
            await status_msg.edit_text("❌ Video yuklab bo'lmadi.")
            return

        file_size = os.path.getsize(actual_file)
        if file_size > 50 * 1024 * 1024:
            await status_msg.edit_text("❌ Video hajmi 50MB dan katta, yuborib bo'lmaydi.")
            return

        await status_msg.delete()

        with open(actual_file, "rb") as vf:
            await message.answer_video(
                vf,
                caption=f"❤️ @{BOT_USERNAME} orqali yuklab olindi 🚀📥",
                supports_streaming=True,
            )

        shazam_kb = InlineKeyboardMarkup()
        shazam_kb.add(
            InlineKeyboardButton("🎵 Musiqani topish (Shazam)", callback_data=f"shazam_url:{url}")
        )
        await message.answer("👇 Videodagi musiqani topish uchun:", reply_markup=shazam_kb)

    except yt_dlp.utils.DownloadError as e:
        err = str(e)
        if "Sign in" in err or "bot" in err.lower():
            await status_msg.edit_text(
                "❌ <b>YouTube bu linkni blokladi.</b>\n\n"
                "YouTube Shorts yoki boshqa platformadan urinib ko'ring."
            )
        elif "instagram" in err.lower() or "login" in err.lower():
            await status_msg.edit_text(
                "❌ <b>Instagram private video.</b>\n\n"
                "Faqat public (ochiq) Instagram postlarni yuklab olish mumkin."
            )
        else:
            await status_msg.edit_text(f"❌ Yuklab bolmadi: {err[:250]}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik: {str(e)[:200]}")
    finally:
        # Temp fayllarni tozalash
        import shutil
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass


async def process_url_audio_shazam(message: Message, url: str):
    """URL dan audio yuklab, Shazam bilan aniqlash va mp3 yuborish"""
    status_msg = await message.answer("🔍 <b>Musiqa aniqlanmoqda...</b>")

    tmp_dir  = tempfile.mkdtemp()
    aud_path = os.path.join(tmp_dir, "audio")
    actual_file = None
    info = None

    try:
        # YouTube uchun Invidious orqali video yuklab, ffmpeg bilan mp3 ga aylantir
        if is_youtube(url):
            video_id = get_youtube_id(url)
            if video_id:
                invidious = await get_invidious_stream(video_id)
                if invidious:
                    stream_url, yt_title, yt_author, yt_dur = invidious
                    tmp_mp4 = os.path.join(tmp_dir, "video.mp4")
                    tmp_mp3 = os.path.join(tmp_dir, "audio.mp3")
                    import aiohttp as _aiohttp
                    async with _aiohttp.ClientSession() as sess:
                        async with sess.get(stream_url, timeout=_aiohttp.ClientTimeout(total=120)) as resp:
                            if resp.status == 200:
                                with open(tmp_mp4, "wb") as f:
                                    async for chunk in resp.content.iter_chunked(1024 * 64):
                                        f.write(chunk)
                    # ffmpeg bilan mp3 ga aylantir
                    import subprocess
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", tmp_mp4, "-vn",
                         "-acodec", "libmp3lame", "-q:a", "2", tmp_mp3],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    if os.path.exists(tmp_mp3):
                        actual_file = tmp_mp3
                        info = {"title": yt_title, "uploader": yt_author, "duration": yt_dur}

        # Fallback: yt-dlp
        if not actual_file:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, download_audio_sync, url, aud_path
            )
            for f in os.listdir(tmp_dir):
                if f.endswith(".mp3"):
                    actual_file = os.path.join(tmp_dir, f)
                    break
            if not actual_file:
                for f in os.listdir(tmp_dir):
                    full = os.path.join(tmp_dir, f)
                    if os.path.isfile(full) and not full.endswith(".part"):
                        actual_file = full
                        break

        if not actual_file:
            await status_msg.edit_text("❌ Audio yuklab bo'lmadi.")
            return

        # Shazam bilan aniqlash
        shazam_result = await recognize_file(actual_file)

        title    = ""
        subtitle = ""
        try:
            raw   = await shazam.recognize(actual_file)
            track = raw.get("track", {})
            title    = track.get("title", "")
            subtitle = track.get("subtitle", "")
        except Exception:
            pass

        performer   = subtitle or (info.get("uploader", "") if info else "")
        track_title = title    or (info.get("title", "Audio") if info else "Audio")
        duration    = int(info.get("duration", 0)) if info else 0

        file_size = os.path.getsize(actual_file)

        await status_msg.delete()

        await message.answer(shazam_result, disable_web_page_preview=False)

        if file_size <= 50 * 1024 * 1024:
            with open(actual_file, "rb") as af:
                await message.answer_audio(
                    af,
                    title=track_title,
                    performer=performer,
                    duration=duration,
                    caption=f"📥 @{BOT_USERNAME} orqali yuklab olindi!",
                )
        else:
            await message.answer("❌ Audio hajmi 50MB dan katta, yuborib bo'lmadi.")

    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik: {str(e)[:200]}")
    finally:
        import shutil
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass

# ─── Handlers ─────────────────────────────────────────────────────────────────

@dp.message_handler(commands=["start"])
async def cmd_start(message: Message):
    await message.answer(
        "🎵 <b>Shazam Bot</b>\n\n"
        "Audio, video yoki havola yuboring — qo'shiqni bir zumda topaman!\n\n"
        "📤 <b>Qabul qilinadi:</b>\n"
        "• 🎵 Audio xabar\n"
        "• 🎤 Ovozli xabar (voice)\n"
        "• 🎬 Video (musiqali)\n"
        "• 📎 Audio/video fayl\n"
        "• 🔗 TikTok / YouTube / Instagram havolasi\n\n"
        "⚡️ Yuboring, topamiz!"
    )

@dp.message_handler(commands=["help"])
async def cmd_help(message: Message):
    await message.answer(
        "ℹ️ <b>Yordam</b>\n\n"
        "1. Audio, voice yoki video yuboring\n"
        "2. Yoki TikTok/YouTube/Instagram linkini yuboring\n"
        "3. Bot avtomatik qo'shiqni taniydi\n"
        "4. Ijrochi, nomi, albom va yilini ko'rsatadi\n\n"
        "❗️ <b>Eslatma:</b> Fon shovqini kam bo'lgan audio yaxshiroq taniladi."
    )

@dp.message_handler(content_types=ContentType.AUDIO)
async def handle_audio(message: Message):
    audio = message.audio
    ext   = "mp3"
    if audio.file_name and "." in audio.file_name:
        ext = audio.file_name.rsplit(".", 1)[-1].lower()
    await download_and_recognize(message, audio.file_id, ext)

@dp.message_handler(content_types=ContentType.VOICE)
async def handle_voice(message: Message):
    await download_and_recognize(message, message.voice.file_id, "ogg")

@dp.message_handler(content_types=ContentType.VIDEO)
async def handle_video(message: Message):
    # Avval video yuborib, keyin shazam tugmasi
    video = message.video
    await message.answer("🔍 <b>Qo'shiq izlanmoqda...</b>")
    tmp_path = None
    try:
        file = await bot.get_file(video.file_id)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
        await bot.download_file(file.file_path, tmp_path)
        result = await recognize_file(tmp_path)
        await message.answer(result, disable_web_page_preview=False)
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

@dp.message_handler(content_types=ContentType.VIDEO_NOTE)
async def handle_video_note(message: Message):
    await download_and_recognize(message, message.video_note.file_id, "mp4")

@dp.message_handler(content_types=ContentType.DOCUMENT)
async def handle_document(message: Message):
    doc  = message.document
    name = doc.file_name or "file"
    ext  = name.rsplit(".", 1)[-1].lower() if "." in name else "mp3"
    allowed = {"mp3","mp4","ogg","wav","flac","aac","m4a","mov","avi","mkv","webm","opus"}
    if ext not in allowed:
        await message.answer("❌ Faqat audio yoki video fayllarni yuboring!")
        return
    await download_and_recognize(message, doc.file_id, ext)

@dp.message_handler(content_types=ContentType.TEXT)
async def handle_text(message: Message):
    text = message.text or ""

    if text.startswith("/"):
        return

    # URL borligini tekshirish
    match = URL_PATTERN.search(text)
    if match:
        url = match.group(0)
        await process_url(message, url)
        return

    await message.answer("🎵 Audio, video yoki havola yuboring!\n/help — yordam")


# ─── Callback: Shazam tugmasi (URL orqali) ────────────────────────────────────

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("shazam_url:"))
async def callback_shazam_url(call: types.CallbackQuery):
    await call.answer("🔍 Musiqa izlanmoqda...")
    url = call.data[len("shazam_url:"):]
    await process_url_audio_shazam(call.message, url)


# ─── Health check (alohida thread) ────────────────────────────────────────────

def run_health_server():
    async def health(request):
        return web.Response(text="OK")

    async def _start():
        app = web.Application()
        app.router.add_get("/", health)
        app.router.add_get("/health", health)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        print(f"🌐 Health check: http://0.0.0.0:{PORT}")
        while True:
            await asyncio.sleep(3600)

    asyncio.run(_start())

# ─── Startup & Main ───────────────────────────────────────────────────────────

async def on_startup(dp):
    print("🎵 Shazam Bot ishga tushdi!")

if __name__ == "__main__":
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    executor.start_polling(
        dp,
        on_startup=on_startup,
        skip_updates=True,
        allowed_updates=["message", "callback_query"]
    )
