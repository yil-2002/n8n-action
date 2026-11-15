#!/usr/bin/env python3
"""
Generator: config/*.json + quyidagi tavsiflardan quyidagilarni yasaydi:
  sql/002_seed.sql          — shablonlar, sozlamalar, bot matnlari
  workflows/VB*.json        — n8n'ga import qilinadigan workflow'lar

Ishga tushirish:  python3 scripts/build.py
"""
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRED_PG = {"postgres": {"id": "supabase-postgres", "name": "Supabase Postgres"}}
CRED_TG = {"telegramApi": {"id": "telegram-bot", "name": "Telegram Bot"}}


def uid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "vb/" + seed))


# ---------------------------------------------------------------------------
# Workflow builder
# ---------------------------------------------------------------------------
class WF:
    def __init__(self, name: str):
        self.name = name
        self.nodes = []
        self.conns = {}

    def add(self, name, type_, ver, params, pos, **extra):
        node = {
            "parameters": params,
            "id": uid(self.name + "/" + name),
            "name": name,
            "type": type_,
            "typeVersion": ver,
            "position": list(pos),
        }
        node.update(extra)
        self.nodes.append(node)
        return name

    def link(self, a, b, out=0):
        main = self.conns.setdefault(a, {"main": []})["main"]
        while len(main) <= out:
            main.append([])
        main[out].append({"node": b, "type": "main", "index": 0})

    def chain(self, *names):
        for a, b in zip(names, names[1:]):
            self.link(a, b)

    def dump(self, path: Path):
        names = [n["name"] for n in self.nodes]
        assert len(names) == len(set(names)), f"duplicate node names in {self.name}"
        for a, c in self.conns.items():
            assert a in names, a
            for outs in c["main"]:
                for t in outs:
                    assert t["node"] in names, t["node"]
        data = {
            "name": self.name,
            "nodes": self.nodes,
            "connections": self.conns,
            "settings": {"executionOrder": "v1", "saveManualExecutions": True},
            "pinData": {},
            "active": False,
            "meta": {"templateCredsSetupCompleted": False},
            "tags": [],
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # --- node helpers -------------------------------------------------------
    def code(self, name, js, pos, each=False):
        p = {"jsCode": js.strip() + "\n"}
        if each:
            p["mode"] = "runOnceForEachItem"
        return self.add(name, "n8n-nodes-base.code", 2, p, pos)

    def pg(self, name, query, params_expr, pos, always=False):
        p = {"operation": "executeQuery", "query": query.strip(), "options": {}}
        if params_expr:
            p["options"]["queryReplacement"] = "={{ " + params_expr + " }}"
        extra = {"credentials": CRED_PG}
        if always:
            extra["alwaysOutputData"] = True
        return self.add(name, "n8n-nodes-base.postgres", 2.6, p, pos, **extra)

    def http(self, name, method, url, pos, body=None, headers=None, file=False,
             full=False, never=False, batch=False, timeout=None, on_error=None):
        p = {"method": method, "url": url, "options": {}}
        if headers:
            p["sendHeaders"] = True
            p["headerParameters"] = {"parameters": [{"name": k, "value": v} for k, v in headers]}
        if body:
            p["sendBody"] = True
            p["specifyBody"] = "json"
            p["jsonBody"] = body
        resp = {}
        if file:
            resp.update({"responseFormat": "file", "outputPropertyName": "data"})
        if full:
            resp["fullResponse"] = True
        if never:
            resp["neverError"] = True
        if resp:
            p["options"]["response"] = {"response": resp}
        if batch:
            p["options"]["batching"] = {"batch": {"batchSize": 1, "batchInterval": 100}}
        if timeout:
            p["options"]["timeout"] = timeout
        extra = {}
        if on_error:
            extra["onError"] = on_error
        return self.add(name, "n8n-nodes-base.httpRequest", 4.2, p, pos, **extra)

    def tg_send(self, name, pos):
        """Universal Telegram Bot API chaqiruvi: kirish {method, payload}."""
        return self.http(
            name, "POST",
            "={{ 'https://api.telegram.org/bot' + $env.TELEGRAM_BOT_TOKEN + '/' + $json.method }}",
            pos, body="={{ JSON.stringify($json.payload) }}", never=True, batch=True)

    def iff(self, name, bool_expr, pos):
        p = {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{
                    "id": uid(self.name + "/" + name + "/c"),
                    "leftValue": "={{ " + bool_expr + " }}",
                    "rightValue": "",
                    "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                }],
                "combinator": "and",
            },
            "options": {},
        }
        return self.add(name, "n8n-nodes-base.if", 2.2, p, pos)

    def switch(self, name, field_expr, keys, pos):
        values = []
        for k in keys:
            values.append({
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                    "conditions": [{
                        "id": uid(self.name + "/" + name + "/" + k),
                        "leftValue": "={{ " + field_expr + " }}",
                        "rightValue": k,
                        "operator": {"type": "string", "operation": "equals"},
                    }],
                    "combinator": "and",
                },
                "renameOutput": True,
                "outputKey": k,
            })
        return self.add(name, "n8n-nodes-base.switch", 3.2, {"rules": {"values": values}, "options": {}}, pos)

    def sub_trigger(self, name, pos):
        return self.add(name, "n8n-nodes-base.executeWorkflowTrigger", 1.1,
                        {"inputSource": "passthrough"}, pos)

    def exec_wf(self, name, target, pos):
        p = {
            "workflowId": {"__rl": True, "value": "", "mode": "list", "cachedResultName": target},
            "mode": "each",
            "options": {"waitForSubWorkflow": False},
        }
        return self.add(name, "n8n-nodes-base.executeWorkflow", 1.2, p, pos)


# ---------------------------------------------------------------------------
# Umumiy JS bo'laklari
# ---------------------------------------------------------------------------
JS_T = r"""
const t = (k, v = {}) => String(T[k] ?? k).replace(/\{(\w+)\}/g, (m, x) => (v[x] ?? m));
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
"""

SQL_TEXTS = """(SELECT jsonb_object_agg(b.key, CASE WHEN u.lang = 'ru' AND coalesce(b.ru, '') <> '' THEN b.ru ELSE b.uz END) FROM bot_texts b)"""

WF_PROCESS = "VB2 process-order"
WF_RESULT = "VB3 fal-result"

# ===========================================================================
# VB1 bot-main
# ===========================================================================
def build_bot_main() -> WF:
    w = WF("VB1 bot-main")
    w.add("Telegram Trigger", "n8n-nodes-base.telegramTrigger", 1.2,
          {"updates": ["message", "callback_query"], "additionalFields": {}},
          (0, 300), credentials=CRED_TG, webhookId=uid("tg-trigger"))

    w.code("Normalize", r"""
// Telegram update -> bitta tekis obyekt
const u = $input.first().json;
const m = u.message;
const cq = u.callback_query;
const msg = m || cq?.message;
const from = m?.from || cq?.from;
if (!msg || !from || msg.chat?.type !== 'private') return [];

const out = {
  chat_id: msg.chat.id,
  user_id: from.id,
  username: from.username || null,
  first_name: from.first_name || null,
  kind: 'text',
  text: m?.text || '',
  cb_id: cq?.id || null,
  cb_data: cq?.data || '',
  cb_message_id: cq?.message?.message_id || null,
  photo: null,
  doc: null,
  video_file_id: null,
};
if (cq) {
  out.kind = 'callback';
} else if (m.photo?.length) {
  const p = m.photo.reduce((a, b) => (b.width * b.height > a.width * a.height ? b : a));
  out.kind = 'photo';
  out.photo = { file_id: p.file_id, width: p.width, height: p.height };
} else if (m.document) {
  out.kind = 'document';
  out.doc = { file_id: m.document.file_id, mime_type: m.document.mime_type || '', file_size: m.document.file_size || 0 };
} else if (m.video || m.animation) {
  out.kind = 'video';
  out.video_file_id = (m.video || m.animation).file_id;
}
return [{ json: out }];
""", (220, 300))

    w.pg("Context", f"""
WITH u AS (
  INSERT INTO users (telegram_id, username, first_name)
  VALUES ($1, $2, $3)
  ON CONFLICT (telegram_id) DO UPDATE
    SET username = EXCLUDED.username, first_name = EXCLUDED.first_name, last_seen_at = now()
  RETURNING telegram_id, lang, state, selected_template
)
SELECT u.*,
  {SQL_TEXTS} AS texts,
  (SELECT jsonb_object_agg(key, value) FROM settings) AS settings
FROM u
""", "[ $json.user_id, $json.username, $json.first_name ]", (440, 300))

    w.code("Router", r"""
const n = $('Normalize').first().json;
const ctx = $input.first().json;
const T = ctx.texts || {};
const S = ctx.settings || {};
""" + JS_T + r"""
const chat_id = n.chat_id;
const out = [];
const call = (method, payload) => out.push({ json: { route: 'reply', method, payload } });
const say = (text, rows) => call('sendMessage', {
  chat_id, text, parse_mode: 'HTML',
  ...(rows ? { reply_markup: { inline_keyboard: rows } } : {}),
});
const go = (route, extra = {}) => out.push({ json: { route, chat_id, user_id: n.user_id, ...extra } });

if (n.cb_id) call('answerCallbackQuery', { callback_query_id: n.cb_id });

// --- MVP: kirish cheklovi ---
const isAdmin = String(n.user_id) === String($env.ADMIN_CHAT_ID);
const allowed = String($env.ALLOWED_USER_IDS || '').split(',').map((s) => s.trim()).filter(Boolean);
const isPublic = String($env.BOT_PUBLIC || 'false') === 'true';
if (!isPublic && !isAdmin && !allowed.includes(String(n.user_id))) {
  say(t('not_open'));
  return out;
}

const price = String(S.price_uzs || '0').replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
const cats = String(S.enabled_categories || 'car').split(',').map((s) => s.trim()).filter(Boolean);
const minSide = Number(S.min_image_side || 720);
const showCategories = () =>
  say(t('choose_category'), cats.map((c) => [{ text: t('btn_cat_' + c), callback_data: 'cat:' + c }]));
const d = n.cb_data;

if (n.kind === 'text' && /^\/start\b/.test(n.text)) {
  const caption = t('start', { price });
  const rows = [[{ text: t('btn_start'), callback_data: 'menu' }]];
  if (S.sample_video_file_id) {
    call('sendVideo', { chat_id, video: S.sample_video_file_id, caption, parse_mode: 'HTML', reply_markup: { inline_keyboard: rows } });
  } else {
    say(caption, rows);
  }
} else if (d === 'menu' || d === 'new') {
  showCategories();
} else if (d.startsWith('cat:')) {
  const c = d.slice(4);
  if (cats.includes(c)) go('list_templates', { category: c });
  else showCategories();
} else if (d.startsWith('tpl:')) {
  go('select_template', { template_id: d.slice(4) });
} else if (d.startsWith('regen:')) {
  go('regen', { order_id: Number(d.slice(6)), cb_message_id: n.cb_message_id });
} else if (n.kind === 'photo' || n.kind === 'document') {
  if (ctx.state !== 'awaiting_photo' || !ctx.selected_template) {
    say(t('err_need_template'));
    showCategories();
  } else if (n.kind === 'document' && !/^image\/(jpeg|png|webp)$/i.test(n.doc.mime_type)) {
    say(t('err_not_image'));
  } else if (n.kind === 'document' && n.doc.file_size > 20 * 1024 * 1024) {
    say(t('err_too_big'));
  } else if (n.kind === 'photo' && Math.min(n.photo.width, n.photo.height) < minSide) {
    say(t('err_small', { w: n.photo.width, h: n.photo.height, min: minSide }));
  } else {
    const img = n.kind === 'photo' ? n.photo : { file_id: n.doc.file_id, width: null, height: null };
    go('create_order', { template_id: ctx.selected_template, file_id: img.file_id, width: img.width, height: img.height });
  }
} else if (n.kind === 'video' && isAdmin) {
  say(t('admin_file_id', { file_id: esc(n.video_file_id) }));
} else if (!n.cb_id) {
  say(t('help'), [[{ text: t('btn_menu'), callback_data: 'menu' }]]);
}
return out;
""", (660, 300))

    w.switch("Route", "$json.route",
             ["reply", "list_templates", "select_template", "create_order", "regen"], (880, 300))
    w.tg_send("Send TG", (1760, 300))

    # --- list_templates ---
    w.pg("Templates", """
SELECT id,
       coalesce(CASE WHEN $2 = 'ru' THEN name_ru END, name_uz) AS name,
       sample_file_id
FROM templates
WHERE category = $1 AND active
ORDER BY sort_order, id
""", "[ $json.category, $('Context').first().json.lang ]", (1100, 0), always=True)
    w.code("Build template list", r"""
const ctx = $('Context').first().json;
const chat_id = $('Normalize').first().json.chat_id;
const T = ctx.texts || {};
""" + JS_T + r"""
const rows = $input.all().map((i) => i.json).filter((r) => r.id);
const out = [];
const send = (method, payload) => out.push({ json: { method, payload: { chat_id, parse_mode: 'HTML', ...payload } } });
const back = [{ text: t('btn_back'), callback_data: 'menu' }];

if (!rows.length) {
  send('sendMessage', { text: t('no_templates'), reply_markup: { inline_keyboard: [back] } });
  return out;
}
const buttons = [];
for (const r of rows) {
  const btn = { text: t('btn_choose') + ' — ' + r.name, callback_data: 'tpl:' + r.id };
  if (r.sample_file_id) {
    send('sendVideo', { video: r.sample_file_id, caption: t('template_caption', { name: esc(r.name) }), reply_markup: { inline_keyboard: [[btn]] } });
  } else {
    buttons.push([btn]);
  }
}
buttons.push(back);
send('sendMessage', { text: t('choose_template'), reply_markup: { inline_keyboard: buttons } });
return out;
""", (1320, 0))

    # --- select_template ---
    w.pg("Set template", """
WITH t AS (
  SELECT id, category, coalesce(CASE WHEN $3 = 'ru' THEN name_ru END, name_uz) AS name
  FROM templates WHERE id = $2 AND active
), u AS (
  UPDATE users SET state = 'awaiting_photo', selected_template = $2
  WHERE telegram_id = $1 AND EXISTS (SELECT 1 FROM t)
  RETURNING telegram_id
)
SELECT category, name FROM t
""", "[ $json.user_id, $json.template_id, $('Context').first().json.lang ]", (1100, 200), always=True)
    w.code("Build ask photo", r"""
const ctx = $('Context').first().json;
const chat_id = $('Normalize').first().json.chat_id;
const T = ctx.texts || {};
""" + JS_T + r"""
const r = $input.first().json;
const text = r.category ? t('send_photo_' + r.category, { name: esc(r.name) }) : t('template_unavailable');
const markup = r.category ? undefined : { inline_keyboard: [[{ text: t('btn_back'), callback_data: 'menu' }]] };
return [{ json: { method: 'sendMessage', payload: { chat_id, text, parse_mode: 'HTML', ...(markup ? { reply_markup: markup } : {}) } } }];
""", (1320, 200))

    # --- create_order ---
    w.pg("Create order", """
WITH ok AS (
  SELECT 1 FROM templates WHERE id = $2 AND active
), busy AS (
  SELECT 1 FROM orders WHERE user_id = $1 AND status IN ('awaiting_payment', 'paid', 'generating')
), ins AS (
  INSERT INTO orders (user_id, template_id, photo_file_id, photo_width, photo_height, status, amount_uzs, gen_started_at)
  SELECT $1, $2, $3, $4, $5, 'generating', 0, now()
  WHERE EXISTS (SELECT 1 FROM ok) AND NOT EXISTS (SELECT 1 FROM busy)
  RETURNING id
), u AS (
  UPDATE users SET state = 'idle', selected_template = NULL, total_orders = total_orders + 1
  WHERE telegram_id = $1 AND EXISTS (SELECT 1 FROM ins)
  RETURNING telegram_id
)
SELECT (SELECT id FROM ins) AS order_id,
       EXISTS (SELECT 1 FROM busy) AS busy
""", "[ $json.user_id, $json.template_id, $json.file_id, $json.width, $json.height ]", (1100, 420))
    w.code("Build order reply", r"""
const ctx = $('Context').first().json;
const chat_id = $('Normalize').first().json.chat_id;
const T = ctx.texts || {};
""" + JS_T + r"""
const r = $input.first().json;
let text;
let markup;
if (r.order_id) text = t('generating');
else if (r.busy) text = t('err_active_order');
else { text = t('template_unavailable'); markup = { inline_keyboard: [[{ text: t('btn_back'), callback_data: 'menu' }]] }; }
return [{ json: { method: 'sendMessage', payload: { chat_id, text, parse_mode: 'HTML', ...(markup ? { reply_markup: markup } : {}) } } }];
""", (1320, 420))
    w.iff("Order created?", "!!$json.order_id", (1320, 560))
    w.exec_wf("Run process-order", WF_PROCESS, (1540, 640))

    # --- regen ---
    w.pg("Start regen", """
WITH busy AS (
  SELECT 1 FROM orders WHERE user_id = $2 AND status IN ('awaiting_payment', 'paid', 'generating')
)
UPDATE orders
SET regen_used = true, status = 'generating', attempt = 0,
    fal_request_id = NULL, status_url = NULL, response_url = NULL,
    prev_video_url = video_url, video_url = NULL,
    gen_started_at = now(), submitted_at = NULL, error_text = NULL
WHERE id = $1 AND user_id = $2 AND status = 'done' AND regen_used = false
  AND NOT EXISTS (SELECT 1 FROM busy)
RETURNING id AS order_id
""", "[ $json.order_id, $json.user_id ]", (1100, 780), always=True)
    w.code("Build regen reply", r"""
const ctx = $('Context').first().json;
const n = $('Normalize').first().json;
const chat_id = n.chat_id;
const T = ctx.texts || {};
""" + JS_T + r"""
const r = $input.first().json;
const out = [];
if (r.order_id) {
  if (n.cb_message_id) {
    out.push({ json: { method: 'editMessageReplyMarkup', payload: {
      chat_id, message_id: n.cb_message_id,
      reply_markup: { inline_keyboard: [[{ text: t('btn_new'), callback_data: 'new' }]] },
    } } });
  }
  out.push({ json: { method: 'sendMessage', payload: { chat_id, text: t('generating'), parse_mode: 'HTML' } } });
} else {
  out.push({ json: { method: 'sendMessage', payload: { chat_id, text: t('regen_unavailable'), parse_mode: 'HTML' } } });
}
return out;
""", (1320, 780))
    w.iff("Regen started?", "!!$json.order_id", (1320, 920))

    # --- connections ---
    w.chain("Telegram Trigger", "Normalize", "Context", "Router", "Route")
    w.link("Route", "Send TG", 0)
    w.link("Route", "Templates", 1)
    w.link("Route", "Set template", 2)
    w.link("Route", "Create order", 3)
    w.link("Route", "Start regen", 4)
    w.chain("Templates", "Build template list", "Send TG")
    w.chain("Set template", "Build ask photo", "Send TG")
    w.chain("Create order", "Build order reply", "Send TG")
    w.link("Create order", "Order created?")
    w.link("Order created?", "Run process-order", 0)
    w.chain("Start regen", "Build regen reply", "Send TG")
    w.link("Start regen", "Regen started?")
    w.link("Regen started?", "Run process-order", 0)
    return w


# ===========================================================================
# VB2 process-order  — fal.ai'ga yuborish / qayta urinish / failed
#   kirish: { order_id, error? }
# ===========================================================================
def build_process_order() -> WF:
    w = WF(WF_PROCESS)
    w.sub_trigger("Start", (0, 300))
    w.pg("Load order", f"""
SELECT o.id, o.user_id, o.status, o.attempt, o.photo_file_id, o.template_id,
       t.prompt, t.duration,
       coalesce(nullif(t.negative_prompt, ''), (SELECT value FROM settings WHERE key = 'default_negative_prompt')) AS negative_prompt,
       $2::text AS error,
       (SELECT jsonb_object_agg(key, value) FROM settings) AS settings,
       {SQL_TEXTS} AS texts
FROM orders o
JOIN templates t ON t.id = o.template_id
JOIN users u ON u.telegram_id = o.user_id
WHERE o.id = $1
""", "[ $json.order_id, $json.error || '' ]", (220, 300))
    w.code("Decide", r"""
// submit: fal.ai'ga (qayta) yuborish | fail: urinishlar tugadi
return $input.all().filter((i) => i.json.id).map((i) => {
  const o = i.json;
  const max = Number(o.settings?.max_attempts || 2);
  let action = 'skip';
  if (o.status === 'generating') action = o.error && o.attempt >= max ? 'fail' : 'submit';
  return { json: { ...o, action, max_attempts: max } };
});
""", (440, 300))
    w.switch("Action", "$json.action", ["submit", "fail"], (660, 300))

    # --- submit ---
    w.pg("Start attempt", """
UPDATE orders
SET attempt = attempt + 1, submitted_at = now(), model = $3,
    fal_request_id = NULL, status_url = NULL, response_url = NULL
WHERE id = $1 AND status = 'generating' AND attempt = $2
RETURNING id, attempt
""", "[ $json.id, $json.attempt, $env.FAL_MODEL ]", (880, 200))
    w.http("TG getFile", "GET",
           "={{ 'https://api.telegram.org/bot' + $env.TELEGRAM_BOT_TOKEN + '/getFile?file_id=' + encodeURIComponent($('Decide').first().json.photo_file_id) }}",
           (1100, 200))
    w.http("TG download", "GET",
           "={{ 'https://api.telegram.org/file/bot' + $env.TELEGRAM_BOT_TOKEN + '/' + $json.result.file_path }}",
           (1320, 200), file=True)
    w.code("Build fal request", r"""
// Rasm -> data URI (fal.ai qabul qiladi). Telegram fayl URL'ini bermaymiz: unda bot tokeni bor.
const o = $('Decide').first().json;
const buf = await this.helpers.getBinaryDataBuffer(0, 'data');
let mime = 'image/jpeg';
if (buf[0] === 0x89 && buf[1] === 0x50) mime = 'image/png';
else if (buf.subarray(0, 4).toString() === 'RIFF' && buf.subarray(8, 12).toString() === 'WEBP') mime = 'image/webp';
const image_url = `data:${mime};base64,${buf.toString('base64')}`;

const model = String($env.FAL_MODEL);
const dur = Number(o.duration || 5);
const body = { prompt: o.prompt, image_url };
if (/kling/i.test(model)) {
  body.duration = dur >= 10 ? '10' : '5';
  if (o.negative_prompt) body.negative_prompt = o.negative_prompt;
  body.cfg_scale = 0.5;
} else if (/hailuo/i.test(model)) {
  body.duration = dur >= 10 ? '10' : '6';   // Hailuo: 6 yoki 10
  body.prompt_optimizer = false;            // shablon prompti o'zgarmasin
} else {
  body.duration = String(dur);
  if (o.negative_prompt) body.negative_prompt = o.negative_prompt;
}
const hook = String($env.WEBHOOK_URL).replace(/\/+$/, '') + '/webhook/fal-result?secret=' +
  encodeURIComponent($env.FAL_WEBHOOK_SECRET || '');
return [{ json: {
  order_id: o.id,
  url: 'https://queue.fal.run/' + model + '?fal_webhook=' + encodeURIComponent(hook),
  body,
} }];
""", (1540, 200))
    w.http("fal submit", "POST", "={{ $json.url }}", (1760, 200),
           body="={{ JSON.stringify($json.body) }}",
           headers=[("Authorization", "={{ 'Key ' + $env.FAL_KEY }}")],
           timeout=60000, on_error="continueErrorOutput")
    w.pg("Save request", """
UPDATE orders SET fal_request_id = $2, status_url = $3, response_url = $4
WHERE id = $1 AND status = 'generating'
""", "[ $('Decide').first().json.id, $json.request_id, $json.status_url, $json.response_url ]", (1980, 120))
    w.pg("Save submit error", """
UPDATE orders SET error_text = $2 WHERE id = $1
""", "[ $('Decide').first().json.id, ('submit: ' + JSON.stringify($json.error || $json)).slice(0, 1000) ]", (1980, 300))

    # --- fail ---
    w.pg("Mark failed", """
WITH f AS (
  UPDATE orders SET status = 'failed', error_text = $3, failed_at = now()
  WHERE id = $1 AND status = 'generating' AND attempt = $2
  RETURNING id, user_id, template_id, attempt
)
SELECT f.*, u.username FROM f JOIN users u ON u.telegram_id = f.user_id
""", "[ $json.id, $json.attempt, $json.error ]", (880, 480))
    w.code("Build fail messages", r"""
const o = $('Decide').first().json;
const T = o.texts || {};
""" + JS_T + r"""
const r = $input.first().json;
if (!r.id) return [];
const user = (r.username ? '@' + r.username + ' ' : '') + r.user_id;
return [
  { json: { method: 'sendMessage', payload: {
    chat_id: r.user_id, text: t('err_generation'), parse_mode: 'HTML',
    reply_markup: { inline_keyboard: [[{ text: t('btn_new'), callback_data: 'new' }]] },
  } } },
  { json: { method: 'sendMessage', payload: {
    chat_id: $env.ADMIN_CHAT_ID, parse_mode: 'HTML',
    text: t('admin_failed', { order_id: r.id, user: esc(user), template: esc(r.template_id), attempt: r.attempt, error: esc(String(o.error).slice(0, 500)) }),
  } } },
];
""", (1100, 480))
    w.tg_send("Send TG", (1320, 480))

    w.chain("Start", "Load order", "Decide", "Action")
    w.link("Action", "Start attempt", 0)
    w.link("Action", "Mark failed", 1)
    w.chain("Start attempt", "TG getFile", "TG download", "Build fal request", "fal submit")
    w.link("fal submit", "Save request", 0)
    w.link("fal submit", "Save submit error", 1)
    w.chain("Mark failed", "Build fail messages", "Send TG")
    return w


# ===========================================================================
# VB3 fal-result — fal.ai webhook (yoki watchdog'dan) natijasi
# ===========================================================================
def build_fal_result() -> WF:
    w = WF(WF_RESULT)
    w.add("fal webhook", "n8n-nodes-base.webhook", 2,
          {"httpMethod": "POST", "path": "fal-result", "responseMode": "onReceived", "options": {}},
          (0, 200), webhookId=uid("fal-result"))
    w.sub_trigger("From watchdog", (0, 420))
    w.code("Normalize", r"""
const out = [];
for (const it of $input.all()) {
  const j = it.json;
  let r = j;
  if (j.headers && j.body !== undefined) {           // fal.ai webhook
    if (String(j.query?.secret || '') !== String($env.FAL_WEBHOOK_SECRET || '')) continue;
    r = j.body || {};
  }
  if (!r.request_id) continue;
  const video_url = r.payload?.video?.url || null;
  const ok = r.status === 'OK' && !!video_url;
  let error = null;
  if (!ok) {
    const e = r.error ?? r.payload?.detail ?? r.payload ?? 'unknown';
    error = (typeof e === 'string' ? e : JSON.stringify(e)).slice(0, 1000);
  }
  out.push({ json: { request_id: r.request_id, ok, video_url, error } });
}
return out;
""", (220, 300))
    w.iff("OK?", "$json.ok === true", (440, 300))

    # --- OK ---
    w.pg("Claim done", f"""
WITH d AS (
  UPDATE orders
  SET status = 'done', video_url = $2, api_cost_usd = api_cost_usd + $3, done_at = now()
  WHERE fal_request_id = $1 AND status = 'generating'
  RETURNING id, user_id, regen_used, video_url
)
SELECT d.*, {SQL_TEXTS} AS texts
FROM d JOIN users u ON u.telegram_id = d.user_id
""", "[ $json.request_id, $json.video_url, Number($env.FAL_COST_PER_VIDEO_USD || 0) ]", (660, 200))
    w.code("Build video message", r"""
const r = $input.first().json;
if (!r.id) return [];
const T = r.texts || {};
""" + JS_T + r"""
const rows = [];
if (!r.regen_used) rows.push([{ text: t('btn_regen'), callback_data: 'regen:' + r.id }]);
rows.push([{ text: t('btn_new'), callback_data: 'new' }]);
return [{ json: {
  order_id: r.id,
  video_url: r.video_url,
  method: 'sendVideo',
  payload: { chat_id: r.user_id, video: r.video_url, caption: t('done'), parse_mode: 'HTML', supports_streaming: true, reply_markup: { inline_keyboard: rows } },
} }];
""", (880, 200))
    w.tg_send("Send video", (1100, 200))
    w.pg("Save file_id", """
UPDATE orders SET video_file_id = $2 WHERE id = $1
""", "[ $('Build video message').first().json.order_id, $json.result?.video?.file_id ?? $json.result?.document?.file_id ?? null ]", (1320, 120))
    w.iff("Delivery failed?", "$json.ok !== true", (1320, 300))
    w.code("Build delivery alert", r"""
const m = $('Build video message').first().json;
const r = $input.first().json;
const T = $('Claim done').first().json.texts || {};
""" + JS_T + r"""
return [{ json: { method: 'sendMessage', payload: {
  chat_id: $env.ADMIN_CHAT_ID, parse_mode: 'HTML', disable_web_page_preview: true,
  text: t('admin_delivery_failed', { order_id: m.order_id, video_url: esc(m.video_url), error: esc(r.description || JSON.stringify(r).slice(0, 300)) }),
} } }];
""", (1540, 300))
    w.tg_send("Send alert", (1760, 300))

    # --- ERROR ---
    w.pg("Find order", """
SELECT id AS order_id, $2::text AS error
FROM orders WHERE fal_request_id = $1 AND status = 'generating'
""", "[ $json.request_id, $json.error ]", (660, 440))
    w.exec_wf("Run process-order", WF_PROCESS, (880, 440))

    w.link("fal webhook", "Normalize")
    w.link("From watchdog", "Normalize")
    w.chain("Normalize", "OK?")
    w.link("OK?", "Claim done", 0)
    w.link("OK?", "Find order", 1)
    w.chain("Claim done", "Build video message", "Send video", "Save file_id")
    w.link("Send video", "Delivery failed?")
    w.link("Delivery failed?", "Build delivery alert", 0)
    w.chain("Build delivery alert", "Send alert")
    w.chain("Find order", "Run process-order")
    return w


# ===========================================================================
# VB4 watchdog — har daqiqada: kech qolgan webhook, timeout, yuborilmay qolganlar
# ===========================================================================
def build_watchdog() -> WF:
    w = WF("VB4 watchdog")
    w.add("Every minute", "n8n-nodes-base.scheduleTrigger", 1.2,
          {"rule": {"interval": [{"field": "minutes", "minutesInterval": 1}]}}, (0, 300))
    w.pg("Due orders", """
WITH s AS (
  SELECT coalesce((SELECT value FROM settings WHERE key = 'gen_timeout_min'), '5')::int AS tmo
), x AS (
  SELECT o.id AS order_id, o.fal_request_id, o.status_url, o.response_url, o.error_text,
    CASE
      WHEN o.fal_request_id IS NULL AND o.submitted_at IS NOT NULL
           AND o.submitted_at < now() - interval '60 seconds' THEN 'resubmit'
      WHEN o.fal_request_id IS NULL AND o.submitted_at IS NULL
           AND o.gen_started_at < now() - interval '2 minutes' THEN 'stuck'
      WHEN o.fal_request_id IS NOT NULL
           AND o.submitted_at < now() - interval '60 seconds' THEN 'poll'
    END AS kind,
    coalesce(o.submitted_at < now() - make_interval(mins => s.tmo), false) AS timed_out
  FROM orders o CROSS JOIN s
  WHERE o.status = 'generating'
)
SELECT * FROM x WHERE kind IS NOT NULL
""", None, (220, 300))
    w.switch("Kind", "$json.kind", ["resubmit", "stuck", "poll"], (440, 300))
    w.code("Retry input", r"""
return $input.all().map((i) => ({ json: {
  order_id: i.json.order_id,
  error: i.json.kind === 'stuck' ? 'stuck before submit' : (i.json.error_text || 'submit failed'),
} }));
""", (660, 160))
    w.http("fal status", "GET", "={{ $json.status_url }}", (660, 420),
           headers=[("Authorization", "={{ 'Key ' + $env.FAL_KEY }}")], never=True, timeout=20000)
    w.code("Poll decide", r"""
const out = [];
$input.all().forEach((it, i) => {
  const row = $('Due orders').itemMatching(i).json;
  const st = it.json.status;
  if (st === 'COMPLETED') {
    out.push({ json: { next: 'completed', order_id: row.order_id, request_id: row.fal_request_id, response_url: row.response_url } });
  } else if (row.timed_out) {
    out.push({ json: { next: 'timeout', order_id: row.order_id, error: 'timeout (' + (st || 'unknown') + ')' } });
  }
});
return out;
""", (880, 420))
    w.switch("Next", "$json.next", ["completed", "timeout"], (1100, 420))
    w.http("fal result", "GET", "={{ $json.response_url }}", (1320, 360),
           headers=[("Authorization", "={{ 'Key ' + $env.FAL_KEY }}")], full=True, never=True, timeout=20000)
    w.code("Build result", r"""
return $input.all().map((it, i) => {
  const p = $('Poll decide').itemMatching(i).json;
  const r = it.json;
  const ok = r.statusCode === 200 && !!r.body?.video?.url;
  return { json: {
    request_id: p.request_id,
    status: ok ? 'OK' : 'ERROR',
    payload: r.body,
    error: ok ? null : 'result HTTP ' + r.statusCode + ': ' + JSON.stringify(r.body).slice(0, 500),
  } };
});
""", (1540, 360))
    w.exec_wf("Run fal-result", WF_RESULT, (1760, 360))
    w.exec_wf("Run process-order", WF_PROCESS, (1320, 560))

    w.chain("Every minute", "Due orders", "Kind")
    w.link("Kind", "Retry input", 0)
    w.link("Kind", "Retry input", 1)
    w.link("Kind", "fal status", 2)
    w.chain("Retry input", "Run process-order")
    w.chain("fal status", "Poll decide", "Next")
    w.link("Next", "fal result", 0)
    w.link("Next", "Run process-order", 1)
    w.chain("fal result", "Build result", "Run fal-result")
    return w


# ===========================================================================
# VB5 error-handler
# ===========================================================================
def build_error_handler() -> WF:
    w = WF("VB5 error-handler")
    w.add("Error Trigger", "n8n-nodes-base.errorTrigger", 1, {}, (0, 300))
    w.code("Build alert", r"""
const j = $input.first().json;
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const err = j.execution?.error?.message || j.trigger?.error?.message || 'unknown';
const text = [
  '⚠️ <b>n8n xato</b>',
  'Workflow: ' + esc(j.workflow?.name),
  'Node: ' + esc(j.execution?.lastNodeExecuted || '-'),
  '<code>' + esc(String(err).slice(0, 800)) + '</code>',
  j.execution?.url || '',
].join('\n');
return [{ json: { method: 'sendMessage', payload: { chat_id: $env.ADMIN_CHAT_ID, text, parse_mode: 'HTML', disable_web_page_preview: true } } }];
""", (220, 300))
    w.tg_send("Send TG", (440, 300))
    w.chain("Error Trigger", "Build alert", "Send TG")
    return w


# ---------------------------------------------------------------------------
# Seed SQL
# ---------------------------------------------------------------------------
def q(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def build_seed() -> str:
    tpl = json.loads((ROOT / "config/templates.json").read_text(encoding="utf-8"))["templates"]
    settings = json.loads((ROOT / "config/settings.json").read_text(encoding="utf-8"))
    texts = json.loads((ROOT / "config/texts.json").read_text(encoding="utf-8"))
    lines = [
        "-- AVTOMATIK yaratilgan: python3 scripts/build.py  (qo'lda tahrirlamang)",
        "-- Manba: config/templates.json, config/settings.json, config/texts.json",
        "-- Mavjud qatorlar O'ZGARTIRILMAYDI (ON CONFLICT DO NOTHING) — Supabase'dagi tahrirlaringiz saqlanadi.",
        "-- Majburan yangilash uchun: pastdagi DO NOTHING ni DO UPDATE ... ga almashtiring yoki qatorni o'chirib qayta ishga tushiring.",
        "",
        "INSERT INTO templates (id, category, name_uz, name_ru, prompt, negative_prompt, duration, active, sample_file_id, sort_order) VALUES",
    ]
    rows = []
    for t in tpl:
        rows.append("  (" + ", ".join(q(t.get(k)) for k in (
            "id", "category", "name_uz", "name_ru", "prompt", "negative_prompt",
            "duration", "active", "sample_file_id", "sort_order")) + ")")
    lines.append(",\n".join(rows) + "\nON CONFLICT (id) DO NOTHING;\n")
    lines.append("INSERT INTO settings (key, value, note) VALUES")
    lines.append(",\n".join(f"  ({q(k)}, {q(v['value'])}, {q(v.get('note'))})" for k, v in settings.items())
                 + "\nON CONFLICT (key) DO NOTHING;\n")
    lines.append("INSERT INTO bot_texts (key, uz, ru) VALUES")
    lines.append(",\n".join(f"  ({q(k)}, {q(v['uz'])}, {q(v.get('ru') or None)})"
                            for k, v in texts.items() if not k.startswith("_"))
                 + "\nON CONFLICT (key) DO NOTHING;\n")
    return "\n".join(lines)


def main():
    (ROOT / "sql/002_seed.sql").write_text(build_seed(), encoding="utf-8")
    out = ROOT / "workflows"
    out.mkdir(exist_ok=True)
    files = {
        "VB1_bot-main.json": build_bot_main(),
        "VB2_process-order.json": build_process_order(),
        "VB3_fal-result.json": build_fal_result(),
        "VB4_watchdog.json": build_watchdog(),
        "VB5_error-handler.json": build_error_handler(),
    }
    for fname, wf in files.items():
        wf.dump(out / fname)
        print("yozildi:", out / fname)
    print("yozildi:", ROOT / "sql/002_seed.sql")


if __name__ == "__main__":
    main()
