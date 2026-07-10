import asyncio
import os
import uuid
import logging
import yt_dlp

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# yt-dlp konfiguratsiyasi - Instagram cookies kerak bo'lishi mumkin
YDL_OPTS_VIDEO = {
    "format": "best[ext=mp4][filesize<50M]/best[filesize<50M]/best",
    "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
    "quiet": True,
    "no_warnings": True,
    "extract_flat": False,
    # Instagram/TikTok uchun
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        )
    },
}

YDL_OPTS_AUDIO = {
    "format": "bestaudio/best",
    "outtmpl": f"{DOWNLOAD_DIR}/audio_%(id)s.%(ext)s",
    "quiet": True,
    "no_warnings": True,
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "128",
    }],
}


async def download_video(url: str) -> str | None:
    """Video yuklab olish va path qaytarish"""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _download_video_sync, url)
        return result
    except Exception as e:
        logger.error(f"Video yuklab olishda xato: {e}")
        return None


def _download_video_sync(url: str) -> str | None:
    """Sinxron video yuklash"""
    opts = YDL_OPTS_VIDEO.copy()

    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            if info:
                # Fayl nomini aniqlash
                filename = ydl.prepare_filename(info)
                # .mp4 kengaytmasini tekshirish
                if not filename.endswith(".mp4"):
                    mp4_name = filename.rsplit(".", 1)[0] + ".mp4"
                    if os.path.exists(mp4_name):
                        return mp4_name
                if os.path.exists(filename):
                    return filename
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"yt-dlp xatosi: {e}")
            return None
    return None


async def extract_audio(video_path: str) -> str | None:
    """Videodan audio ajratib olish (Shazam uchun)"""
    try:
        audio_path = video_path.rsplit(".", 1)[0] + "_audio.mp3"

        cmd = [
            "ffmpeg", "-i", video_path,
            "-vn",                    # video yo'q
            "-acodec", "mp3",
            "-ar", "44100",           # sample rate
            "-ab", "128k",            # bitrate
            "-t", "30",               # faqat 30 soniya (Shazam uchun yetarli)
            "-y",                     # overwrite
            audio_path,
            "-loglevel", "quiet"
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()

        if os.path.exists(audio_path):
            return audio_path
        return None

    except Exception as e:
        logger.error(f"Audio ajratishda xato: {e}")
        return None
