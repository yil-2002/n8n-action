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

def base_ydl_opts(url: str) -> dict:
    """Har bir platforma uchun umumiy yt-dlp sozlamalar"""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        # Bot detection bypass
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    if is_youtube(url):
        opts.update({
            "extractor_args": {
                "youtube": {
                    "player_client": ["ios", "web_creator"],
                    "skip": ["dash", "hls"],
                }
            },
            "age_limit": 99,
        })

    if is_instagram(url):
        opts.update({
            # Instagram public video uchun
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

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(
            None, download_video_sync, url, vid_path
        )

        # Yuklangan faylni topish
        actual_file = None
        for f in os.listdir(tmp_dir):
            full = os.path.join(tmp_dir, f)
            if os.path.isfile(full):
                actual_file = full
                break

        if not actual_file:
            await status_msg.edit_text("❌ Video yuklab bo'lmadi.")
            return

        file_size = os.path.getsize(actual_file)
        # Telegram 50MB limit
        if file_size > 50 * 1024 * 1024:
            await status_msg.edit_text(
                "❌ Video hajmi 50MB dan katta, yuborib bo'lmaydi."
            )
            return

        title    = info.get("title", "Video") if info else "Video"
        duration = info.get("duration", 0) if info else 0

        # Shazam uchun inline tugma
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🎵 Musiqa topish", callback_data=f"shazam_local:{actual_file}"))

        await status_msg.delete()

        with open(actual_file, "rb") as vf:
            await message.answer_video(
                vf,
                caption=f"❤️ @{BOT_USERNAME} orqali yuklab olindi 🚀📥",
                supports_streaming=True,
            )

        # Shazam tugmasi alohida xabar sifatida
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

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(
            None, download_audio_sync, url, aud_path
        )

        # mp3 faylni topish
        actual_file = None
        for f in os.listdir(tmp_dir):
            if f.endswith(".mp3"):
                actual_file = os.path.join(tmp_dir, f)
                break

        if not actual_file:
            for f in os.listdir(tmp_dir):
                full = os.path.join(tmp_dir, f)
                if os.path.isfile(full):
                    actual_file = full
                    break

        if not actual_file:
            await status_msg.edit_text("❌ Audio yuklab bo'lmadi.")
            return

        # Shazam bilan aniqlash
        shazam_result = await recognize_file(actual_file)

        # Ijrochi va nom Shazam natijasidan olish
        title    = ""
        subtitle = ""
        try:
            raw = await shazam.recognize(actual_file)
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

        # Shazam natijasini yubor
        await message.answer(shazam_result, disable_web_page_preview=False)

        # mp3 faylni audio sifatida yubor (50MB limit)
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
