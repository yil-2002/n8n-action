import asyncio
import logging
from shazamio import Shazam

logger = logging.getLogger(__name__)


async def find_music(audio_path: str) -> dict | None:
    """
    ShazamIO yordamida musiqani aniqlash
    Returns: {'title': ..., 'artist': ..., 'album': ..., 'year': ...}
    """
    if not audio_path:
        return None

    try:
        shazam = Shazam()
        result = await shazam.recognize(audio_path)

        if not result or "track" not in result:
            logger.info("Musiqa topilmadi")
            return None

        track = result["track"]

        # Ma'lumotlarni olish
        song_info = {
            "title": track.get("title", "Noma'lum"),
            "artist": track.get("subtitle", "Noma'lum"),
            "album": None,
            "year": None,
            "genre": None,
            "cover_url": None,
            "shazam_url": track.get("url", None),
        }

        # Metadata bo'limlaridan qo'shimcha ma'lumot
        sections = track.get("sections", [])
        for section in sections:
            if section.get("type") == "SONG":
                metadata = section.get("metadata", [])
                for meta in metadata:
                    title = meta.get("title", "").lower()
                    text = meta.get("text", "")
                    if "album" in title:
                        song_info["album"] = text
                    elif "released" in title or "year" in title:
                        song_info["year"] = text
                    elif "genre" in title:
                        song_info["genre"] = text

        # Cover rasm URL
        images = track.get("images", {})
        song_info["cover_url"] = images.get("coverarthq") or images.get("coverart")

        logger.info(f"Musiqa topildi: {song_info['title']} - {song_info['artist']}")
        return song_info

    except Exception as e:
        logger.error(f"Shazam xatosi: {e}")
        return None
