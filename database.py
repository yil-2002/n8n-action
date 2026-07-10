import os
import asyncpg
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")


async def get_db():
    """PostgreSQL ulanish"""
    return await asyncpg.connect(DATABASE_URL)


async def init_db():
    """Jadvallarni yaratish"""
    conn = await get_db()
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                last_active TIMESTAMP DEFAULT NOW(),
                total_requests INT DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id),
                platform TEXT,
                url TEXT,
                song_title TEXT,
                song_artist TEXT,
                status TEXT DEFAULT 'success',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        logger.info("✅ Database jadvallari tayyor")
    finally:
        await conn.close()


async def upsert_user(user_id: int, username: str, first_name: str):
    """Foydalanuvchini qo'shish yoki yangilash"""
    conn = await get_db()
    try:
        await conn.execute("""
            INSERT INTO users (id, username, first_name, last_active, total_requests)
            VALUES ($1, $2, $3, NOW(), 1)
            ON CONFLICT (id) DO UPDATE
            SET username = $2,
                first_name = $3,
                last_active = NOW(),
                total_requests = users.total_requests + 1
        """, user_id, username, first_name)
    finally:
        await conn.close()


async def save_request(user_id: int, platform: str, url: str,
                       song_title: str = None, song_artist: str = None,
                       status: str = "success"):
    """So'rovni saqlash"""
    conn = await get_db()
    try:
        await conn.execute("""
            INSERT INTO requests (user_id, platform, url, song_title, song_artist, status)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, user_id, platform, url, song_title, song_artist, status)
    finally:
        await conn.close()


async def get_stats():
    """Umumiy statistika"""
    conn = await get_db()
    try:
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
        total_requests = await conn.fetchval("SELECT COUNT(*) FROM requests")
        success_requests = await conn.fetchval(
            "SELECT COUNT(*) FROM requests WHERE status = 'success'"
        )
        return {
            "total_users": total_users,
            "total_requests": total_requests,
            "success_requests": success_requests,
        }
    finally:
        await conn.close()
