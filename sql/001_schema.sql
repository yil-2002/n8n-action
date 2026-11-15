-- =============================================================
-- Rasmdan video bot — baza sxemasi (Supabase / Postgres 15+)
-- Supabase: SQL Editor -> shu faylni to'liq ishga tushiring.
-- Qayta ishga tushirish xavfsiz (IF NOT EXISTS).
-- =============================================================

-- ---------- users ----------
CREATE TABLE IF NOT EXISTS users (
  telegram_id        bigint PRIMARY KEY,
  username           text,
  first_name         text,
  lang               text NOT NULL DEFAULT 'uz' CHECK (lang IN ('uz', 'ru')),
  state              text NOT NULL DEFAULT 'idle',      -- idle | awaiting_photo
  selected_template  text,
  total_orders       int  NOT NULL DEFAULT 0,
  created_at         timestamptz NOT NULL DEFAULT now(),
  last_seen_at       timestamptz NOT NULL DEFAULT now()
);

-- ---------- templates ----------
CREATE TABLE IF NOT EXISTS templates (
  id               text PRIMARY KEY,                     -- car_night_city
  category         text NOT NULL CHECK (category IN ('car', 'portrait')),
  name_uz          text NOT NULL,
  name_ru          text,
  prompt           text NOT NULL,
  negative_prompt  text,                                 -- NULL -> settings.default_negative_prompt
  duration         int  NOT NULL DEFAULT 5,              -- soniya; model o'ziga mos qiymatga yaxlitlanadi
  active           boolean NOT NULL DEFAULT true,
  sample_file_id   text,                                 -- namuna video (Telegram file_id)
  sort_order       int  NOT NULL DEFAULT 100,
  created_at       timestamptz NOT NULL DEFAULT now()
);

-- ---------- orders ----------
CREATE TABLE IF NOT EXISTS orders (
  id               bigserial PRIMARY KEY,
  user_id          bigint NOT NULL REFERENCES users (telegram_id),
  template_id      text   NOT NULL REFERENCES templates (id),
  photo_file_id    text   NOT NULL,
  photo_width      int,
  photo_height     int,
  image_url        text,                                 -- 5-bosqich: Supabase Storage'dagi asl rasm
  status           text   NOT NULL DEFAULT 'awaiting_payment'
                   CHECK (status IN ('awaiting_payment', 'paid', 'generating', 'done', 'failed', 'refunded')),
  payment_id       text,
  amount_uzs       int    NOT NULL DEFAULT 0,
  model            text,
  fal_request_id   text,
  status_url       text,
  response_url     text,
  attempt          int    NOT NULL DEFAULT 0,            -- fal.ai'ga necha marta yuborildi (shu generatsiya uchun)
  gen_started_at   timestamptz,
  submitted_at     timestamptz,
  done_at          timestamptz,
  failed_at        timestamptz,
  video_url        text,
  video_file_id    text,
  prev_video_url   text,                                 -- qayta yaratishdan oldingi video
  regen_used       boolean NOT NULL DEFAULT false,
  api_cost_usd     numeric(10, 4) NOT NULL DEFAULT 0,
  error_text       text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

-- Bir foydalanuvchida bir vaqtda faqat 1 ta faol buyurtma (baza darajasida kafolat)
CREATE UNIQUE INDEX IF NOT EXISTS orders_one_active_per_user
  ON orders (user_id) WHERE status IN ('awaiting_payment', 'paid', 'generating');
CREATE INDEX IF NOT EXISTS orders_fal_request_id_idx ON orders (fal_request_id);
CREATE INDEX IF NOT EXISTS orders_status_idx ON orders (status);
CREATE INDEX IF NOT EXISTS orders_created_at_idx ON orders (created_at);

-- ---------- settings (kod yozmasdan o'zgartiriladigan sozlamalar) ----------
CREATE TABLE IF NOT EXISTS settings (
  key    text PRIMARY KEY,
  value  text NOT NULL,
  note   text
);

-- ---------- bot_texts ----------
CREATE TABLE IF NOT EXISTS bot_texts (
  key  text PRIMARY KEY,
  uz   text NOT NULL,
  ru   text
);

-- ---------- updated_at trigger ----------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS orders_updated_at ON orders;
CREATE TRIGGER orders_updated_at BEFORE UPDATE ON orders
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------- Xavfsizlik ----------
-- Supabase'ning ochiq REST API'si (anon/authenticated) bu jadvallarni ko'rmasin.
-- n8n "postgres" (egasi) sifatida ulanadi va RLS uni cheklamaydi.
ALTER TABLE users     ENABLE ROW LEVEL SECURITY;
ALTER TABLE templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders    ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings  ENABLE ROW LEVEL SECURITY;
ALTER TABLE bot_texts ENABLE ROW LEVEL SECURITY;
