// Code node'lari mantig'ining testi (n8n'siz):  node tests/logic.test.js
const fs = require('fs');
const wf = (f) => JSON.parse(fs.readFileSync('workflows/' + f));
const code = (w, name) => w.nodes.find((n) => n.name === name).parameters.jsCode;
const texts = {}; for (const [k, v] of Object.entries(JSON.parse(fs.readFileSync('config/texts.json')))) if (!k.startsWith('_')) texts[k] = v.uz;
const settings = {}; for (const [k, v] of Object.entries(JSON.parse(fs.readFileSync('config/settings.json')))) settings[k] = v.value;
const env = { ADMIN_CHAT_ID: '1', ALLOWED_USER_IDS: '7', BOT_PUBLIC: 'false', FAL_MODEL: 'fal-ai/kling-video/v2.5-turbo/pro/image-to-video', WEBHOOK_URL: 'https://abc.trycloudflare.com/', FAL_WEBHOOK_SECRET: 's3', TELEGRAM_BOT_TOKEN: 'T' };
async function run(js, input, nodes = {}, helpers = {}) {
  const items = input.map((j) => ({ json: j }));
  const $ = (n) => ({ first: () => ({ json: nodes[n] }), itemMatching: () => ({ json: nodes[n] }) });
  const fn = new Function('$input', '$', '$env', 'return (async function(){' + js + '}).call(this)');
  return fn.call({ helpers }, { first: () => items[0], all: () => items }, $, env);
}
let bad = 0; const ok = (name, c) => { console.log((c ? 'OK   ' : 'FAIL ') + name); if (!c) bad++; };
(async () => {
  const w1 = wf('VB1_bot-main.json');
  const norm = (u) => run(code(w1, 'Normalize'), [u]);
  const from = { id: 1, username: 'adm', first_name: 'A' }, chat = { id: 1, type: 'private' };
  let n = (await norm({ message: { from, chat, text: '/start', message_id: 1 } }))[0].json;
  ok('Normalize: /start', n.kind === 'text' && n.text === '/start');
  n = (await norm({ message: { from, chat, message_id: 2, photo: [{ file_id: 's', width: 320, height: 240 }, { file_id: 'L', width: 1280, height: 960 }] } }))[0].json;
  ok('Normalize: eng katta rasm tanlanadi', n.photo.file_id === 'L');
  ok('Normalize: guruh chatlari e\'tiborsiz', (await norm({ message: { from, chat: { id: -5, type: 'group' }, text: 'x' } })).length === 0);

  const router = async (nn, ctx) => (await run(code(w1, 'Router'), [{ texts, settings, state: 'idle', selected_template: null, lang: 'uz', ...ctx }], { Normalize: { chat_id: nn.user_id, cb_id: null, cb_data: '', kind: 'text', text: '', ...nn } })).map((i) => i.json);
  let r = await router({ user_id: 1, text: '/start' });
  ok('Router: /start narx bilan', r[0].method === 'sendMessage' && r[0].payload.text.includes('20 000 so\'m'));
  r = await router({ user_id: 1, text: '/start' }, { settings: { ...settings, sample_video_file_id: 'VID' } });
  ok('Router: /start namuna video bilan', r[0].method === 'sendVideo' && r[0].payload.video === 'VID');
  r = await router({ user_id: 99, text: '/start' });
  ok('Router: begona foydalanuvchi -> sinov rejimi', r.length === 1 && r[0].payload.text === texts.not_open);
  r = await router({ user_id: 7, text: '/start' });
  ok('Router: ALLOWED_USER_IDS ishlaydi', r[0].payload.text.includes('Assalomu'));
  r = await router({ user_id: 1, kind: 'callback', cb_id: 'q', cb_data: 'menu' });
  ok('Router: callback ack + kategoriyalar', r[0].method === 'answerCallbackQuery' && r[1].payload.reply_markup.inline_keyboard.length === 1);
  r = await router({ user_id: 1, kind: 'callback', cb_id: 'q', cb_data: 'cat:portrait' });
  ok('Router: o\'chirilgan kategoriya -> menyu', r[1].route === 'reply' && r[1].payload.text === texts.choose_category);
  r = await router({ user_id: 1, kind: 'callback', cb_id: 'q', cb_data: 'cat:car' });
  ok('Router: cat:car -> list_templates', r[1].route === 'list_templates' && r[1].category === 'car');
  r = await router({ user_id: 1, kind: 'callback', cb_id: 'q', cb_data: 'regen:42', cb_message_id: 9 });
  ok('Router: regen', r[1].route === 'regen' && r[1].order_id === 42);
  const photo = (w, h) => ({ user_id: 1, kind: 'photo', photo: { file_id: 'P', width: w, height: h } });
  r = await router(photo(1280, 960));
  ok('Router: shablonsiz rasm -> avval uslub', r[0].payload.text === texts.err_need_template);
  const aw = { state: 'awaiting_photo', selected_template: 'car_orbit' };
  r = await router(photo(640, 480), aw);
  ok('Router: kichik rasm rad etildi', r[0].payload.text.includes('640×480') && r[0].payload.text.includes('720'));
  r = await router(photo(1280, 960), aw);
  ok('Router: yaxshi rasm -> create_order', r[0].route === 'create_order' && r[0].file_id === 'P' && r[0].template_id === 'car_orbit');
  r = await router({ user_id: 1, kind: 'document', doc: { file_id: 'D', mime_type: 'application/pdf', file_size: 10 } }, aw);
  ok('Router: PDF rad etildi', r[0].payload.text === texts.err_not_image);
  r = await router({ user_id: 1, kind: 'document', doc: { file_id: 'D', mime_type: 'image/png', file_size: 10 } }, aw);
  ok('Router: PNG fayl qabul qilindi', r[0].route === 'create_order' && r[0].file_id === 'D');
  r = await router({ user_id: 1, kind: 'video', video_file_id: 'V<1>' });
  ok('Router: admin video -> file_id (HTML escape)', r[0].payload.text.includes('V&lt;1&gt;'));

  const w2 = wf('VB2_process-order.json');
  const dec = async (o) => (await run(code(w2, 'Decide'), [{ id: 1, status: 'generating', attempt: 0, error: '', settings, ...o }]))[0]?.json.action;
  ok('Decide: yangi -> submit', (await dec({})) === 'submit');
  ok('Decide: 1 xato -> retry', (await dec({ attempt: 1, error: 'x' })) === 'submit');
  ok('Decide: 2 xato -> fail', (await dec({ attempt: 2, error: 'x' })) === 'fail');
  ok('Decide: done -> skip', (await dec({ status: 'done', error: 'x' })) === 'skip');

  const jpg = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 1, 2, 3]);
  const build = async (model, dur = 5) => { env.FAL_MODEL = model; return (await run(code(w2, 'Build fal request'), [{}], { Decide: { id: 5, prompt: 'P', negative_prompt: 'N', duration: dur } }, { getBinaryDataBuffer: async () => jpg }))[0].json; };
  let b = await build('fal-ai/kling-video/v2.5-turbo/pro/image-to-video');
  ok('fal: Kling body', b.body.duration === '5' && b.body.negative_prompt === 'N' && b.body.image_url.startsWith('data:image/jpeg;base64,'));
  const hook = decodeURIComponent(b.url.split('fal_webhook=')[1]);
  ok('fal: webhook URL to\'g\'ri', b.url.startsWith('https://queue.fal.run/fal-ai/kling-video/v2.5-turbo/pro/image-to-video?fal_webhook=') && hook === 'https://abc.trycloudflare.com/webhook/fal-result?secret=s3');
  b = await build('fal-ai/minimax/hailuo-2.3/standard/image-to-video');
  ok('fal: Hailuo body (6s, negative yo\'q)', b.body.duration === '6' && !('negative_prompt' in b.body) && b.body.prompt_optimizer === false);

  const w3 = wf('VB3_fal-result.json');
  const fr = async (j) => (await run(code(w3, 'Normalize'), [j])).map((i) => i.json);
  let x = await fr({ headers: {}, query: { secret: 's3' }, body: { request_id: 'R', status: 'OK', payload: { video: { url: 'http://v.mp4' } } } });
  ok('fal-result: OK webhook', x[0].ok === true && x[0].video_url === 'http://v.mp4');
  x = await fr({ headers: {}, query: { secret: 'bad' }, body: { request_id: 'R', status: 'OK', payload: { video: { url: 'u' } } } });
  ok('fal-result: noto\'g\'ri secret rad etildi', x.length === 0);
  x = await fr({ headers: {}, query: { secret: 's3' }, body: { request_id: 'R', status: 'ERROR', error: 'Invalid status code: 422', payload: { detail: [{ msg: 'bad image' }] } } });
  ok('fal-result: ERROR webhook', x[0].ok === false && x[0].error.includes('422'));
  x = await fr({ request_id: 'R', status: 'OK', payload: { video: { url: 'u' } } });
  ok('fal-result: watchdog\'dan (secret shart emas)', x[0].ok === true);
  console.log(bad ? `NATIJA: ${bad} ta xato` : 'NATIJA: hammasi o\'tdi'); process.exit(bad ? 1 : 0);
})();
