# 🎵 Shazam Telegram Bot

YouTube, Instagram va TikTok videolaridagi musiqani avtomatik aniqlab, videoni yuklab beruvchi bot.

## ⚡ Imkoniyatlar

- 🎵 Shazam orqali musiqa aniqlash (qo'shiq nomi, artist, album)
- 📥 YouTube, Instagram Reels, TikTok videolarini yuklab olish
- 📤 Videoni to'g'ridan-to'g'ri Telegram ga yuborish
- 🚀 Async arxitektura (tez ishlaydi)

## 🛠 O'rnatish

### 1. Talablar
- Python 3.11+
- ffmpeg
- Telegram Bot Token (@BotFather)

### 2. Klonlash
```bash
git clone https://github.com/YOUR_USERNAME/shazam-bot.git
cd shazam-bot
```

### 3. Virtual muhit
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 4. Kutubxonalarni o'rnatish
```bash
pip install -r requirements.txt
```

### 5. .env fayl yaratish
```bash
cp .env.example .env
# .env faylni tahrirlang va BOT_TOKEN ni qo'shing
```

### 6. ffmpeg o'rnatish
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# MacOS
brew install ffmpeg

# Windows - https://ffmpeg.org/download.html
```

### 7. Ishga tushirish
```bash
python bot.py
```

## 🐳 Docker bilan

```bash
cp .env.example .env
# BOT_TOKEN ni .env ga qo'shing

docker-compose up -d
```

## 📁 Loyiha tuzilmasi

```
shazam_bot/
├── bot.py              # Asosiy bot fayli
├── downloader.py       # yt-dlp video/audio yuklab olish
├── shazam_finder.py    # ShazamIO musiqa aniqlash
├── utils.py            # Yordamchi funksiyalar
├── requirements.txt    # Python kutubxonalari
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## ⚠️ Muhim eslatmalar

- **Instagram**: Private postlar uchun `cookies.txt` kerak bo'lishi mumkin
- **Fayl hajmi**: Telegram 50MB gacha video qabul qiladi
- **TikTok**: Ba'zan VPN kerak bo'lishi mumkin

## 📝 Instagram Cookies (ixtiyoriy)

Private Instagram reels uchun:
1. Chrome extension: "Get cookies.txt LOCALLY" o'rnating
2. instagram.com ga kiring
3. Cookies ni eksport qiling → `cookies.txt` sifatida saqlang
4. Bot papkasiga qo'ying

## 🤝 Hissa qo'shish

Pull request lar qabul qilinadi!
