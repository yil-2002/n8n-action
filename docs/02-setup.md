# O'rnatish va test (MVP)

## 1. Supabase

1. Yangi loyiha yarating (region: Frankfurt `eu-central-1` — O'zbekistonga eng yaqini).
2. **SQL Editor** → `sql/001_schema.sql` ni to'liq ishga tushiring, keyin `sql/002_seed.sql` ni.
3. **Connect** → **Session pooler** ma'lumotlarini oling. Direct connection faqat IPv6 orqali ishlaydi, ko'p VPS'larda ulanmaydi.
   - Host: `aws-0-<region>.pooler.supabase.com`, Port: `5432`
   - User: `postgres.<project-ref>`, Database: `postgres`, parol — loyiha paroli

## 2. VPS: n8n + Cloudflare quick tunnel

```bash
git clone https://github.com/yil-2002/n8n-action && cd n8n-action/deploy
cp .env.example .env
nano .env            # TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, FAL_KEY, FAL_WEBHOOK_SECRET, N8N_ENCRYPTION_KEY
docker compose up -d
chmod +x tunnel.sh && ./tunnel.sh      # URL'ni topadi, .env ga yozadi, n8n'ni qayta ishga tushiradi
```

Tunnel qayta ishga tushsa URL o'zgaradi. Buni avtomatik tiklash uchun cron qo'shing (`crontab -e`):

```
*/2 * * * * /root/n8n-action/deploy/tunnel.sh >> /var/log/vb-tunnel.log 2>&1
```

> ⚠️ **Quick tunnel haqida.** Cloudflare quick tunnel'lar faqat sinov uchun mo'ljallangan, uptime kafolati
> yo'q. URL har restartda almashadi. Shunday paytda bot ~1–2 daqiqa javob bermaydi, yarim yo'lda qolgan
> buyurtmalarni esa watchdog fal.ai'dan o'zi olib yetkazadi. Pullik ishga tushirishdan oldin (3–6-bosqich)
> **named tunnel**ga o'tishni tavsiya qilaman. U bepul, faqat Cloudflare'ga ulangan o'z domeningiz kerak
> (~$10/yil). URL doimiy bo'ladi va `tunnel.sh` kerak bo'lmaydi.

n8n'ga kirish: `.env` dagi `N8N_EDITOR_BASE_URL` manzili. Birinchi kirishda admin akkaunt yaratiladi.

## 3. n8n'da sozlash

**Credentials** (Overview → Credentials → Create):
- **Postgres** — nomi aynan `Supabase Postgres`. Ma'lumotlar 1-bo'limdagi pooler'dan, SSL: `require`.
- **Telegram API** — nomi `Telegram Bot`, bot tokeni (faqat Telegram Trigger uchun).

**Import** (Workflows → ⋯ → Import from File). Quyidagi tartibda import qiling:
1. `VB5_error-handler.json`
2. `VB2_process-order.json`
3. `VB3_fal-result.json`
4. `VB4_watchdog.json`
5. `VB1_bot-main.json`

**Import'dan keyin:**
1. Har bir workflow'dagi Postgres va Telegram node'larida credential tanlanganini tekshiring.
2. **Execute Workflow** node'larida maqsadli workflow'ni ro'yxatdan tanlang:
   - VB1 → `Run process-order` → **VB2 process-order**
   - VB3 → `Run process-order` → **VB2 process-order**
   - VB4 → `Run process-order` → **VB2**, `Run fal-result` → **VB3 fal-result**
3. VB1–VB4 da: **Settings → Error workflow** → **VB5 error-handler**.
4. **Beshala workflow'ni ham Publish / Active qiling.** n8n 2.x boshqa workflow'dan chaqirilganda uning publish qilingan versiyasini ishlatadi, shuning uchun VB2 va VB5 ham publish qilingan bo'lishi kerak. Har bir o'zgarishdan keyin qayta publish qiling.
5. Tekshiruv: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo` buyrug'i tunnel URL'ini ko'rsatishi kerak.

**Namuna videolar:** admin sifatida botga video yuboring, bot `file_id` ni qaytaradi. Uni Supabase'da
`settings.sample_video_file_id` ga (/start uchun) yoki `templates.sample_file_id` ga qo'ying.

## 4. Test rejasi (MVP)

| # | Ssenariy | Qanday | Kutilgan natija |
|---|----------|--------|-----------------|
| 1 | Muvaffaqiyatli oqim | /start → Boshlash → Mashina → Night City → yaxshi rasm | "Tayyorlanmoqda" xabari, 1–3 daqiqada video + 2 tugma; `orders.status=done`, `video_file_id` va `api_cost_usd` to'lgan |
| 2 | Qayta yaratish | 1-dan keyin 🔁 | Eski xabardan 🔁 tugmasi yo'qoladi, yangi video keladi, unda 🔁 yo'q; `regen_used=true`, `prev_video_url` saqlangan |
| 3 | Kichik rasm | 600×400 rasm | "Rasm juda kichik (600×400)…" |
| 4 | Rasm emas | PDF fayl yuborish | "Bu rasm emas…" |
| 5 | Shablonsiz rasm | /start'dan keyin darhol rasm | "Avval uslubni tanlang" + kategoriyalar |
| 6 | Faol buyurtma | Video tayyorlanayotganda yana uslub tanlab rasm yuborish | "Sizda hali tugallanmagan buyurtma bor" |
| 7 | fal.ai xatosi | `.env` da `FAL_MODEL=fal-ai/notexist` → restart → buyurtma | Watchdog ~1 daqiqa ichida 1 marta qayta yuboradi, keyin `failed`; foydalanuvchiga uzr, admin'ga xabar |
| 8 | Webhook yo'qoldi | n8n'da VB3 ni vaqtincha o'chiring → buyurtma → VB3 ni yoqing | 1–2 daqiqada watchdog natijani o'zi oladi va video yetkaziladi |
| 9 | Timeout | Supabase'da `settings.gen_timeout_min=1` → buyurtma | 1 daqiqadan keyin qayta urinish, yana kechiksa `failed` + admin xabari (keyin `5` ga qaytaring) |
| 10 | Tunnel almashdi | `docker compose restart cloudflared && ./tunnel.sh` | Yangi URL, bot yana javob beradi (`getWebhookInfo`) |
| 11 | Begona foydalanuvchi | Boshqa akkauntdan /start | "Bot hozir sinov rejimida" |
| 12 | Model almashtirish | `FAL_MODEL=…hailuo-2.3…`, `FAL_COST_PER_VIDEO_USD=0.28` | 6 soniyalik video |

To'lov testlari (muvaffaqiyatli, bekor qilingan, qaytarish) 3-bosqichda qo'shiladi.

## 5. Avtomatik testlar (n8n'siz)

```bash
node tests/logic.test.js            # Code node'lari mantig'i
# bo'sh test bazasida (ishlab turgan bazada EMAS):
psql -f sql/001_schema.sql && psql -f sql/002_seed.sql && python3 tests/sql_flow.py
```

## 6. O'zgartirish kiritish

Workflow'lar `scripts/build.py` dan yasaladi. Kodni o'zgartirgach `python3 scripts/build.py` ni ishga
tushiring va qayta import qiling. Boshqa yo'l: n8n'da bevosita tahrirlab, Export qilib, `workflows/` ga saqlash.
Bu holda `build.py` ham yangilanishi kerak, aks holda keyingi generatsiya o'zgarishlaringizni o'chirib yuboradi.
