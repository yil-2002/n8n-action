import os
import asyncio
import threading
import tempfile
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, ContentType
from aiogram.utils import executor
from shazamio import Shazam

# ─── Config ───────────────────────────────────────────────────────────────────

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT      = int(os.getenv("PORT", 8000))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")

# ─── Bot ──────────────────────────────────────────────────────────────────────

bot    = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp     = Dispatcher(bot)
shazam = Shazam()

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

# ─── Handlers ─────────────────────────────────────────────────────────────────

@dp.message_handler(commands=["start"])
async def cmd_start(message: Message):
    await message.answer(
        "🎵 <b>Shazam Bot</b>\n\n"
        "Audio yoki video yuboring — qo'shiqni bir zumda topaman!\n\n"
        "📤 <b>Qabul qilinadi:</b>\n"
        "• 🎵 Audio xabar\n"
        "• 🎤 Ovozli xabar (voice)\n"
        "• 🎬 Video (musiqali)\n"
        "• 📎 Audio/video fayl\n\n"
        "⚡️ Yuboring, topamiz!"
    )

@dp.message_handler(commands=["help"])
async def cmd_help(message: Message):
    await message.answer(
        "ℹ️ <b>Yordam</b>\n\n"
        "1. Audio, voice yoki video yuboring\n"
        "2. Bot avtomatik qo'shiqni taniydi\n"
        "3. Ijrochi, nomi, albom va yilini ko'rsatadi\n\n"
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
    await download_and_recognize(message, message.video.file_id, "mp4")

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
    if message.text.startswith("/"):
        return
    await message.answer("🎵 Audio yoki video yuboring!\n/help — yordam")

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
        allowed_updates=["message"]
    )
