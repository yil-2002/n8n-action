import json, glob, re, subprocess, sys
# Bo'sh test bazasida ishga tushiring (PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE muhit o'zgaruvchilari):
#   psql -f sql/001_schema.sql && psql -f sql/002_seed.sql && python3 tests/sql_flow.py
# DIQQAT: test ma'lumot yozadi — ishlab turgan bazada ishlatmang.
Q = {}
for f in glob.glob('workflows/*.json'):
    w = json.load(open(f))
    for n in w['nodes']:
        if n['type'] == 'n8n-nodes-base.postgres':
            Q[w['name'][:3] + ':' + n['name']] = n['parameters']['query']
def lit(v):
    if v is None: return 'null'
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, (int, float)): return str(v)
    return "'" + str(v).replace("'", "''") + "'"
def run(key, *params):
    q = re.sub(r'\$(\d+)', lambda m: lit(params[int(m.group(1)) - 1]), Q[key])
    r = subprocess.run(['psql', '-v', 'ON_ERROR_STOP=1', '-At', '-F', '|', '-c', q],
                       capture_output=True, text=True)
    if r.returncode: print('SQL ERROR', key, r.stderr); sys.exit(1)
    out = [l for l in r.stdout.strip().split('\n') if l and not l.startswith('UPDATE') and not l.startswith('INSERT')]
    return out
def sh(sql):
    return subprocess.run(['psql', '-At', '-F', '|', '-c', sql], capture_output=True, text=True).stdout.strip()
def check(name, cond):
    print(('OK   ' if cond else 'FAIL ') + name)
    if not cond: global bad; bad = True
bad = False
U = 5550001

r = run('VB1:Context', U, 'test_user', "O'g'il")
check('Context: user yaratildi, texts+settings bor', len(r) == 1 and '"start"' in r[0] and '"price_uzs"' in r[0])
r = run('VB1:Templates', 'car', 'uz')
check('Templates: 2 ta faol mashina shabloni', len(r) == 2 and r[0].startswith('car_night_city'))
r = run('VB1:Templates', 'portrait', 'uz')
check('Templates: portret hozircha bo\'sh', r == [])
r = run('VB1:Set template', U, 'car_desert', 'uz')
check('Set template: nofaol shablon rad etildi', r == [] and sh(f"select state from users where telegram_id={U}") == 'idle')
r = run('VB1:Set template', U, 'car_night_city', 'uz')
check('Set template: faol shablon -> awaiting_photo', r == ['car|🌃 Night City'] and sh(f"select state||'/'||selected_template from users where telegram_id={U}") == 'awaiting_photo/car_night_city')

r = run('VB1:Create order', U, 'car_night_city', 'FILEID', 1280, 960)
oid = int(r[0].split('|')[0])
check('Create order: yaratildi', r[0].endswith('|f') and oid > 0 and sh(f"select state||'/'||total_orders from users where telegram_id={U}") == 'idle/1')
r = run('VB1:Create order', U, 'car_night_city', 'FILEID2', None, None)
check('Create order: 2-faol buyurtma bloklandi', r == ['|t'])

# process-order: submit
r = run('VB2:Load order', oid, '')
check('Load order: prompt va default negative_prompt', len(r) == 1 and 'warped car body' in r[0] and '|generating|0|' in r[0])
r = run('VB2:Start attempt', oid, 0, 'fal-ai/kling-video/v2.5-turbo/pro/image-to-video')
check('Start attempt: attempt=1', r == [f'{oid}|1'])
r = run('VB2:Start attempt', oid, 0, 'x')
check('Start attempt: parallel chaqiruv (eski attempt) rad etildi', r == [])
run('VB2:Save request', oid, 'REQ1', 'https://q/status', 'https://q/resp')
check('Save request', sh(f"select fal_request_id from orders where id={oid}") == 'REQ1')

# watchdog: hali yangi -> hech narsa
check('Watchdog: yangi buyurtma hali tekshirilmaydi', run('VB4:Due orders') == [])
sh(f"update orders set submitted_at = now() - interval '2 minutes' where id={oid}")
r = run('VB4:Due orders')
check('Watchdog: 60s dan keyin poll, timeout emas', len(r) == 1 and r[0].endswith('|poll|f'))
sh(f"update orders set submitted_at = now() - interval '6 minutes' where id={oid}")
check('Watchdog: 5 daq. dan keyin timed_out', run('VB4:Due orders')[0].endswith('|poll|t'))

# fal-result: error -> find order -> process-order(error) -> retry
r = run('VB3:Find order', 'REQ1', 'boom')
check('Find order (xato)', r == [f'{oid}|boom'])
r = run('VB2:Load order', oid, 'boom')
check('Load order: error uzatiladi', '|boom|' in r[0] and '|generating|1|' in r[0])
r = run('VB2:Start attempt', oid, 1, 'm')
check('Retry: attempt=2', r == [f'{oid}|2'])
run('VB2:Save request', oid, 'REQ2', 's', 'r')
# eski REQ1 natijasi kech keldi -> e'tiborsiz
check('Kech kelgan eski natija e\'tiborsiz', run('VB3:Claim done', 'REQ1', 'http://v/old.mp4', 0.35) == [])
# REQ2 muvaffaqiyatli
r = run('VB3:Claim done', 'REQ2', 'http://v/1.mp4', 0.35)
check('Claim done: done, texts bor', len(r) == 1 and r[0].startswith(f'{oid}|{U}|f|http://v/1.mp4|'))
check('Claim done: ikkinchi marta (webhook + watchdog) dublikat yo\'q', run('VB3:Claim done', 'REQ2', 'http://v/1.mp4', 0.35) == [])
run('VB3:Save file_id', oid, 'VIDFILE')
check('Save file_id + narx', sh(f"select status||'/'||video_file_id||'/'||api_cost_usd from orders where id={oid}") == 'done/VIDFILE/0.3500')

# regen
r = run('VB1:Start regen', oid, 999)
check('Regen: boshqa foydalanuvchi qila olmaydi', r == [])
r = run('VB1:Start regen', oid, U)
check('Regen: boshlandi', r == [str(oid)] and sh(f"select status||'/'||regen_used||'/'||attempt||'/'||prev_video_url from orders where id={oid}") == 'generating/true/0/http://v/1.mp4')
check('Regen: ikkinchi marta yo\'q', run('VB1:Start regen', oid, U) == [])
# regen: 2 marta xato -> failed
for att, req in ((0, 'R3'), (1, 'R4')):
    run('VB2:Start attempt', oid, att, 'm'); run('VB2:Save request', oid, req, 's', 'r')
r = run('VB2:Load order', oid, 'fal error')
check('Decide uchun: attempt=2 (max) va error', '|generating|2|' in r[0])
r = run('VB2:Mark failed', oid, 2, 'fal error')
check('Mark failed: username bilan qaytadi', r == [f'{oid}|{U}|car_night_city|2|test_user'] and sh(f"select status from orders where id={oid}") == 'failed')
check('Mark failed: takror -> bo\'sh', run('VB2:Mark failed', oid, 2, 'x') == [])

# yangi buyurtma endi mumkin; submit xatosi -> watchdog resubmit
run('VB1:Set template', U, 'car_orbit', 'uz')
r = run('VB1:Create order', U, 'car_orbit', 'F', 1000, 800); o2 = int(r[0].split('|')[0])
run('VB2:Start attempt', o2, 0, 'm'); run('VB2:Save submit error', o2, 'submit: 500')
sh(f"update orders set submitted_at = now() - interval '90 seconds' where id={o2}")
r = run('VB4:Due orders')
check('Watchdog: submit xatosidan keyin resubmit', len(r) == 1 and r[0].startswith(f'{o2}|') and '|submit: 500|resubmit|' in r[0])
sh(f"update orders set status='done' where id={o2}")
# stuck
run('VB1:Set template', U, 'car_orbit', 'uz')
r = run('VB1:Create order', U, 'car_orbit', 'F', 1000, 800); o3 = int(r[0].split('|')[0])
sh(f"update orders set gen_started_at = now() - interval '3 minutes' where id={o3}")
check('Watchdog: yuborilmay qolgan (stuck)', run('VB4:Due orders')[0].startswith(f'{o3}|') and '|stuck|' in run('VB4:Due orders')[0])
# unique index
try:
    sh(f"insert into orders (user_id, template_id, photo_file_id, status) values ({U}, 'car_orbit', 'x', 'generating')")
    check('Unique index: 2-faol buyurtma baza darajasida taqiqlangan', sh(f"select count(*) from orders where user_id={U} and status='generating'") == '1')
except Exception as e: print(e)
print('NATIJA:', 'XATO BOR' if bad else 'hammasi o\'tdi')
sys.exit(1 if bad else 0)
