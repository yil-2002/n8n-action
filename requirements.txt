FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --upgrade pip

COPY requirements.txt .

RUN pip install --no-cache-dir \
    aiogram \
    yt-dlp \
    aiohttp \
    asyncpg \
    aiofiles \
    python-dotenv

RUN pip install --no-cache-dir shazamio --no-deps
RUN pip install --no-cache-dir aiohttp requests

COPY . .

RUN mkdir -p downloads

CMD ["python", "bot.py"]

