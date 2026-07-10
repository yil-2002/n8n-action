import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from downloader import download_video, extract_audio
from shazam_finder import find_music
from utils import is_valid_url, cleanup_files, get_platform

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "👋 Salom! Men **Shazam Bot**man\n\n"
        "📎 YouTube, Instagram yoki TikTok videosi linkini yuboring\n"
        "🎵 Men musiqani aniqlab, videoni yuklab beraman!\n\n"
        "✅ Qo'llab-quvvatlanadigan platformalar:\n"
        "• YouTube / YouTube Shorts\n"
        "• Instagram Reels\n"
        "• TikTok",
        parse_mode="Markdown"
    )


@dp.message(F.text)
async def handle_link(message: Message):
    url = message.text.strip()

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

    video_path = None
    audio_path = None

    try:
        # 1. Video yuklab olish
        await status_msg.edit_text(f"📥 {platform} dan video yuklanmoqda...")
        video_path = await download_video(url)

        if not video_path:
            await status_msg.edit_text("❌ Video yuklab bo'lmadi. Link to'g'riligini tekshiring.")
            return

        # 2. Audio chiqarish
        await status_msg.edit_text("🎵 Audio ajratilmoqda...")
        audio_path = await extract_audio(video_path)

        # 3. Shazam orqali musiqa aniqlash
        await status_msg.edit_text("🔍 Musiqa aniqlanmoqda...")
        song_info = await find_music(audio_path)

        # 4. Natijani yuborish
        if song_info:
            caption = (
                f"✅ *Musiqa topildi!*\n\n"
                f"🎵 *Qo'shiq:* {song_info.get('title', 'Noma\'lum')}\n"
                f"🎤 *Artist:* {song_info.get('artist', 'Noma\'lum')}\n"
                f"💿 *Album:* {song_info.get('album', 'Noma\'lum')}\n"
                f"📅 *Yil:* {song_info.get('year', 'Noma\'lum')}\n\n"
                f"📱 *Platforma:* {platform}"
            )
        else:
            caption = (
                f"⚠️ *Musiqa aniqlanmadi*\n\n"
                f"📱 *Platforma:* {platform}\n"
                f"Video yuborilmoqda..."
            )

        await status_msg.edit_text("📤 Video yuborilmoqda...")

        # 5. Video yuborish
        with open(video_path, "rb") as video_file:
            await message.answer_video(
                video=types.BufferedInputFile(
                    video_file.read(),
                    filename=os.path.basename(video_path)
                ),
                caption=caption,
                parse_mode="Markdown"
            )

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Xato: {e}")
        await status_msg.edit_text(f"❌ Xato yuz berdi: {str(e)}")

    finally:
        cleanup_files([video_path, audio_path])


async def main():
    logger.info("Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
