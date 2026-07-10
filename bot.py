import asyncio
import os
import logging

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from downloader import download_video, extract_audio
from shazam_finder import find_music
from utils import is_valid_url, cleanup_files, get_platform
from database import init_db, upsert_user, save_request, get_stats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN   = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")   # https://YOUR-APP.onrender.com
PORT        = int(os.getenv("PORT", 8080))

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message):
    await upsert_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    await message.answer(
        "👋 Salom! Men *Shazam Bot*man\n\n"
        "📎 YouTube, Instagram yoki TikTok videosi linkini yuboring\n"
        "🎵 Men musiqani aniqlab, videoni yuklab beraman!\n\n"
        "✅ *Qo'llab-quvvatlanadigan platformalar:*\n"
        "• YouTube / YouTube Shorts\n"
        "• Instagram Reels\n"
        "• TikTok",
        parse_mode="Markdown",
    )


@dp.message(Command("stats"))
async def stats_handler(message: Message):
    stats = await get_stats()
    await message.answer(
        f"📊 *Statistika:*\n\n"
        f"👤 Foydalanuvchilar: {stats['total_users']}\n"
        f"📥 Jami so'rovlar: {stats['total_requests']}\n"
        f"✅ Muvaffaqiyatli: {stats['success_requests']}",
        parse_mode="Markdown",
    )


@dp.message(F.text)
async def handle_link(message: Message):
    url = message.text.strip()

    await upsert_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )

    if not is_valid_url(url):
        await message.answer("❌ Iltimos, to'g'ri video link yuboring!")
        return

    platform = get_platform(url)
    if not platform:
        await message.answer(
            "❌ Faqat YouTube, Instagram va TikTok linklari qabul qilinadi!"
        )
        return

    status_msg = await message.answer(f"⏳ {platform} dan video yuklanmoqda...")
    video_path = audio_path = None
    song_info  = None

    try:
        await status_msg.edit_text(f"📥 {platform} dan video yuklanmoqda...")
        video_path = await download_video(url)

        if not video_path:
            await status_msg.edit_text("❌ Video yuklab bo'lmadi. Linkni tekshiring.")
            await save_request(message.from_user.id, platform, url, status="failed")
            return

        await status_msg.edit_text("🎵 Audio ajratilmoqda...")
        audio_path = await extract_audio(video_path)

        await status_msg.edit_text("🔍 Musiqa aniqlanmoqda...")
        song_info = await find_music(audio_path)

        if song_info:
            caption = (
                f"✅ *Musiqa topildi!*\n\n"
                f"🎵 *Qo'shiq:* {song_info.get('title', 'Nomalum')}\n"
                f"🎤 *Artist:* {song_info.get('artist', 'Nomalum')}\n"
                f"💿 *Album:* {song_info.get('album', 'Nomalum')}\n"
                f"📅 *Yil:* {song_info.get('year', 'Nomalum')}\n\n"
                f"📱 *Platforma:* {platform}"
            )
        else:
            caption = (
                f"⚠️ *Musiqa aniqlanmadi*\n\n"
                f"📱 *Platforma:* {platform}"
            )

        await status_msg.edit_text("📤 Video yuborilmoqda...")

        with open(video_path, "rb") as vf:
            await message.answer_video(
                video=types.BufferedInputFile(vf.read(), filename="video.mp4"),
                caption=caption,
                parse_mode="Markdown",
            )

        await status_msg.delete()

        await save_request(
            message.from_user.id, platform, url,
            song_title=song_info.get("title") if song_info else None,
            song_artist=song_info.get("artist") if song_info else None,
        )

    except Exception as e:
        logger.error(f"Xato: {e}")
        await status_msg.edit_text(f"❌ Xato yuz berdi: {str(e)}")
        await save_request(message.from_user.id, platform, url, status="failed")

    finally:
        cleanup_files([video_path, audio_path])


async def health(request):
    return web.Response(text="OK", status=200)


async def on_startup(app):
    await init_db()
    webhook_path = f"/webhook/{BOT_TOKEN}"
    await bot.set_webhook(f"{WEBHOOK_URL}{webhook_path}")
    logger.info(f"Webhook set: {WEBHOOK_URL}{webhook_path}")


async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()


def build_app():
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/ping",   health)
    app.router.add_get("/",       health)

    webhook_path = f"/webhook/{BOT_TOKEN}"
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=webhook_path)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app


if __name__ == "__main__":
    app = build_app()
    web.run_app(app, host="0.0.0.0", port=PORT)
