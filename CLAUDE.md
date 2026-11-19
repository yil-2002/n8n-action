# Shazam Telegram Bot (n8n-action)

aiogram 2.x Telegram bot: YouTube/Instagram/TikTok havolasidan video yuklaydi (yt-dlp) va musiqani aniqlaydi (shazamio). Async arxitektura, Docker/Procfile orqali deploy.

## Fayllar
- `bot.py` — handlerlar va ishga tushirish
- `downloader.py` — yt-dlp yuklash
- `shazam_finder.py` — musiqa aniqlash
- `database.py` — DB (`DATABASE_URL`)
- `utils.py` — yordamchilar

## Buyruqlar
- Lokal: `pip install -r requirements.txt && python bot.py` (ffmpeg kerak)
- Sintaksis tekshiruvi: `python -m compileall -q .`

## Qoidalar
- Maxfiy qiymatlar faqat env o'zgaruvchilarida (`.env.example` ga qarang). `cookies.txt` va tokenlarni hech qachon commit qilmang.
- aiogram 2.23.1 ga bog'langan; v3 ga o'tish alohida, so'ralgan ishda.
- yt-dlp tez-tez buziladi: yuklash xatosi bo'lsa avval yt-dlp ni yangilang.
- Kod va commit'lar inglizcha, foydalanuvchiga javob o'zbekcha.
