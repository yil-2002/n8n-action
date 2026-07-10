FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --upgrade pip setuptools wheel

RUN pip install --no-cache-dir shazamio

RUN pip install --no-cache-dir \
    aiogram \
    yt-dlp \
    asyncpg \
    aiofiles \
    python-dotenv

COPY . .

RUN mkdir -p downloads

CMD ["python", "bot.py"]


