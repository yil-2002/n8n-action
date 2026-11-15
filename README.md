# 🎬 Rasmdan video — Telegram bot (n8n + fal.ai + Supabase)

Foydalanuvchi mashina yoki portret rasmini yuboradi, 20 000 so'm to'laydi va tayyor shablon bo'yicha
5–6 soniyalik AI video oladi. Hammasi n8n'da avtomatik ishlaydi.

## Tuzilma

```
config/      templates.json, settings.json, texts.json  — shablonlar, sozlamalar, bot matnlari (manba)
sql/         001_schema.sql, 002_seed.sql               — Supabase uchun
workflows/   VB1..VB5 *.json                            — n8n'ga import
scripts/     build.py                                   — config + kod -> workflows/ va seed SQL
deploy/      docker-compose.yml, tunnel.sh, .env.example — VPS: n8n + Cloudflare quick tunnel
tests/       logic.test.js, sql_flow.py
docs/        01-mvp-workflow.md (arxitektura), 02-setup.md (o'rnatish + test rejasi)
```

## Bosqichlar

| # | Bosqich | Holat |
|---|---------|-------|
| 1 | MVP: bot + mashina + 2 shablon + fal.ai | 🟢 kod tayyor, VPS'da sinash kerak |
| 2 | Shablon sinovi (20–30 rasm) | ⏳ |
| 3 | To'lov: Click / Payme | ⏳ |
| 4 | Admin: `/stats`, `/broadcast`, shablon boshqaruvi | ⏳ |
| 5 | Portret + moderatsiya + rozilik + oldin/keyin to'plami | ⏳ |
| 6 | Ishga tushirish | ⏳ |

Boshlash: [docs/02-setup.md](docs/02-setup.md)
