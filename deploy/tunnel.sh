#!/usr/bin/env bash
# Cloudflare quick tunnel'ning joriy URL'ini topadi. URL o'zgargan bo'lsa:
#   1) .env dagi WEBHOOK_URL / N8N_EDITOR_BASE_URL ni yangilaydi
#   2) n8n'ni qayta yaratadi -> faol workflow'lar Telegram webhook'ini yangi URL'ga o'zi qayta o'rnatadi
#   3) Telegram getWebhookInfo bilan tekshiradi
#
# Cron (har 2 daqiqada, tunnel o'zi qayta ishga tushsa ham bot tiklanadi):
#   */2 * * * * /path/to/deploy/tunnel.sh >> /var/log/vb-tunnel.log 2>&1
set -euo pipefail
cd "$(dirname "$0")"

url=""
for _ in $(seq 1 30); do
  url=$(docker compose logs cloudflared 2>&1 | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1 || true)
  [ -n "$url" ] && break
  sleep 2
done
if [ -z "$url" ]; then
  echo "$(date -Is) Tunnel URL topilmadi. 'docker compose logs cloudflared' ni tekshiring." >&2
  exit 1
fi

current=$(grep -E '^WEBHOOK_URL=' .env | cut -d= -f2- || true)
if [ "$current" = "$url/" ]; then
  echo "$(date -Is) URL o'zgarmagan: $url"
  exit 0
fi

sed -i '/^WEBHOOK_URL=/d;/^N8N_EDITOR_BASE_URL=/d' .env
printf 'WEBHOOK_URL=%s/\nN8N_EDITOR_BASE_URL=%s/\n' "$url" "$url" >> .env
docker compose up -d --force-recreate n8n
echo "$(date -Is) Yangi URL: $url  (n8n qayta ishga tushirildi)"

token=$(grep -E '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2- || true)
if [ -n "$token" ]; then
  sleep 25
  echo "Telegram webhook:"
  curl -s "https://api.telegram.org/bot${token}/getWebhookInfo" | grep -oE '"url":"[^"]*"' || true
fi
