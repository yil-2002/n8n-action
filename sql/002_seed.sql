-- AVTOMATIK yaratilgan: python3 scripts/build.py  (qo'lda tahrirlamang)
-- Manba: config/templates.json, config/settings.json, config/texts.json
-- Mavjud qatorlar O'ZGARTIRILMAYDI (ON CONFLICT DO NOTHING) — Supabase'dagi tahrirlaringiz saqlanadi.
-- Majburan yangilash uchun: pastdagi DO NOTHING ni DO UPDATE ... ga almashtiring yoki qatorni o'chirib qayta ishga tushiring.

INSERT INTO templates (id, category, name_uz, name_ru, prompt, negative_prompt, duration, active, sample_file_id, sort_order) VALUES
  ('car_night_city', 'car', '🌃 Night City', NULL, 'Cinematic shot of this exact car driving slowly through a neon-lit city street at night, wet asphalt reflections, smooth camera tracking from the side, realistic lighting, keep the car''s design, color and wheels unchanged.', NULL, 5, true, NULL, 10),
  ('car_orbit', 'car', '🔄 360° aylanish', NULL, 'Smooth slow orbit camera move around this exact car parked in a premium studio with soft light, glossy reflections, car stays still, design and color unchanged.', NULL, 5, true, NULL, 20),
  ('car_desert', 'car', '🏜 Cho''l', NULL, 'This exact car driving fast along a desert road at golden hour, dust trail behind the wheels, low-angle tracking camera, cinematic, car design unchanged.', NULL, 5, false, NULL, 30),
  ('car_rain', 'car', '🌧 Yomg''ir', NULL, 'This exact car parked under heavy rain at night, headlights turn on, raindrops on the body, slow push-in camera, moody cinematic lighting.', NULL, 5, false, NULL, 40),
  ('portrait_cinematic', 'portrait', '🎬 Kino kadri', NULL, 'The person slowly turns their head toward the camera and smiles softly, gentle wind in the hair, cinematic shallow depth of field, natural face, identity unchanged.', NULL, 5, false, NULL, 50),
  ('portrait_golden', 'portrait', '🌅 Oltin soat', NULL, 'The person stands in warm golden-hour sunlight, light breeze, slow camera push-in, calm natural expression, identity unchanged.', NULL, 5, false, NULL, 60)
ON CONFLICT (id) DO NOTHING;

INSERT INTO settings (key, value, note) VALUES
  ('price_uzs', '20000', 'Buyurtma narxi, so''m'),
  ('enabled_categories', 'car', 'Vergul bilan: car,portrait'),
  ('sample_video_file_id', '', '/start dagi namuna video. Admin botga video yuborsa, bot file_id ni qaytaradi'),
  ('default_negative_prompt', 'distorted face, extra limbs, warped car body, changed logo, text, watermark, blurry, flicker', 'Shablonda negative_prompt bo''sh bo''lsa ishlatiladi (faqat Kling qo''llaydi)'),
  ('min_image_side', '720', 'Rasmning qisqa tomoni kamida necha px'),
  ('max_attempts', '2', 'fal.ai''ga necha marta yuborish (1 = qayta urinishsiz)'),
  ('gen_timeout_min', '5', 'Bitta urinish uchun timeout, daqiqa')
ON CONFLICT (key) DO NOTHING;

INSERT INTO bot_texts (key, uz, ru) VALUES
  ('start', '👋 Assalomu alaykum!

📸 Rasmingizni yuboring — sun''iy intellekt uni <b>5–6 soniyalik kinematik videoga</b> aylantiradi.

🚗 Mashina yoki 👤 portret
🎨 Tayyor uslublar
🔁 Har bir buyurtmaga 1 marta bepul qayta yaratish

💰 Narxi: <b>{price} so''m</b>', NULL),
  ('btn_start', '🚀 Boshlash', NULL),
  ('btn_menu', '🎬 Video yaratish', NULL),
  ('btn_back', '⬅️ Orqaga', NULL),
  ('choose_category', 'Nimani jonlantiramiz? 👇', NULL),
  ('btn_cat_car', '🚗 Mashina', NULL),
  ('btn_cat_portrait', '👤 Portret', NULL),
  ('choose_template', '🎨 Uslubni tanlang:', NULL),
  ('template_caption', '<b>{name}</b>', NULL),
  ('btn_choose', '✅ Tanlash', NULL),
  ('no_templates', 'Bu bo''limda hozircha uslublar yo''q. Tez orada qo''shiladi!', NULL),
  ('template_unavailable', 'Bu uslub hozir mavjud emas. Boshqasini tanlang 👇', NULL),
  ('send_photo_car', '✅ Uslub: <b>{name}</b>

📷 Endi mashinangiz rasmini yuboring.

💡 Yaxshi natija uchun:
• Mashina to''liq kadrga tushsin
• Yorug'' joyda, yon yoki old-yon tomondan
• Rasm aniq, kamida 720px bo''lsin', NULL),
  ('send_photo_portrait', '✅ Uslub: <b>{name}</b>

📷 Endi portret rasmingizni yuboring.

⚠️ <b>Faqat o''zingizning rasmingizni yuklang.</b>

💡 Yuz aniq ko''rinsin, yorug'' joyda, kameraga qarab.', NULL),
  ('err_need_template', 'Avval uslubni tanlang 👇', NULL),
  ('err_not_image', '❌ Bu rasm emas. Iltimos, JPG yoki PNG rasm yuboring.', NULL),
  ('err_small', '❌ Rasm juda kichik ({w}×{h}). Kamida {min}px bo''lgan rasm yuboring.', NULL),
  ('err_too_big', '❌ Fayl juda katta — 20 MB dan oshmasin.', NULL),
  ('err_active_order', '⏳ Sizda hali tugallanmagan buyurtma bor. U tayyor bo''lgach, yangisini boshlashingiz mumkin.', NULL),
  ('generating', '🎬 Video tayyorlanmoqda… Odatda 1–3 daqiqa.
Tayyor bo''lishi bilan shu yerga yuboramiz.', NULL),
  ('done', '✨ Videongiz tayyor!', NULL),
  ('btn_regen', '🔁 Qayta yaratish (1 marta bepul)', NULL),
  ('btn_new', '➕ Yana buyurtma', NULL),
  ('regen_unavailable', 'Qayta yaratish imkoniyati allaqachon ishlatilgan yoki sizda boshqa faol buyurtma bor.', NULL),
  ('err_generation', '😔 Kechirasiz, videoni yaratishda xatolik yuz berdi. Biz bu haqda xabardormiz va tez orada siz bilan bog''lanamiz.', NULL),
  ('help', 'Video yaratish uchun pastdagi tugmani bosing 👇', NULL),
  ('not_open', '🚧 Bot hozir sinov rejimida. Tez orada hamma uchun ochiladi!', NULL),
  ('admin_file_id', 'file_id:
<code>{file_id}</code>', NULL),
  ('admin_failed', '🚨 <b>Buyurtma #{order_id} — xato</b>
Foydalanuvchi: {user}
Shablon: {template}
Urinishlar: {attempt}
Xato: <code>{error}</code>', NULL),
  ('admin_delivery_failed', '🚨 <b>Buyurtma #{order_id}</b>: video tayyor, lekin Telegram''ga yuborib bo''lmadi.
{video_url}
<code>{error}</code>', NULL)
ON CONFLICT (key) DO NOTHING;
