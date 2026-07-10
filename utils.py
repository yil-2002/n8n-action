import os
import re
import logging

logger = logging.getLogger(__name__)

PLATFORM_PATTERNS = {
    "YouTube": [
        r"(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)",
    ],
    "Instagram": [
        r"(instagram\.com/reel/|instagram\.com/p/|instagram\.com/tv/)",
    ],
    "TikTok": [
        r"(tiktok\.com/@.+/video/|vm\.tiktok\.com/|vt\.tiktok\.com/)",
    ],
}


def is_valid_url(text: str) -> bool:
    """URL ekanligini tekshirish"""
    url_pattern = re.compile(
        r"https?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return bool(url_pattern.match(text.strip()))


def get_platform(url: str) -> str | None:
    """Platforma nomini aniqlash"""
    for platform, patterns in PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return platform
    return None


def cleanup_files(file_paths: list):
    """Vaqtinchalik fayllarni o'chirish"""
    for path in file_paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
                logger.debug(f"O'chirildi: {path}")
            except Exception as e:
                logger.warning(f"Faylni o'chirishda xato {path}: {e}")


def format_file_size(size_bytes: int) -> str:
    """Fayl hajmini o'qilishi oson formatda"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    return f"{size_bytes / 1024 ** 3:.1f} GB"
