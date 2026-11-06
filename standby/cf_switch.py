"""
تحويل iajaward.org بين الخادم والهاتف تلقائياً عبر Cloudflare API — بدون الدخول للوحة Cloudflare.

    python standby/cf_switch.py status    # أين يشير الموقع الآن + حالة النفقين
    python standby/cf_switch.py phone     # iajaward.org ← الهاتف (نفق iaj-standby)
    python standby/cf_switch.py server    # iajaward.org ← الخادم (نفق iajaward)

يحتاج في ملف .env (على الخادم وعلى الهاتف):
    CF_API_TOKEN=...            # رمز API من Cloudflare بصلاحيات: Zone:Read + DNS:Edit + Cloudflare Tunnel:Edit
اختياري:
    CF_ZONE=iajaward.org
    CF_MAIN_TUNNEL=iajaward
    CF_STANDBY_TUNNEL=iaj-standby

الفكرة: كلا النفقين يعرفان اسم iajaward.org، والتحويل = تغيير سجل DNS ليشير إلى النفق المطلوب
(السجلات «Proxied» عبر Cloudflare، لذلك التحويل شبه فوري).
"""
import os
import sys
import time

import requests

API = 'https://api.cloudflare.com/client/v4'
HERE = os.path.dirname(os.path.abspath(__file__))


def load_env():
    for path in (os.path.join(HERE, '..', '.env'), os.path.join(HERE, '..', 'IAJ.env'),
                 os.path.expanduser('~/.iaj_standby')):
        if not os.path.isfile(path):
            continue
        with open(path, encoding='utf-8-sig', errors='ignore') as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                if line.lower().startswith('export '):
                    line = line[7:]
                k, v = line.split('=', 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and v and not os.environ.get(k):
                    os.environ[k] = v


# نوافذ الأوامر في ويندوز لا تعرض العربية (مربعات)، لذلك الكمبيوتر بالإنجليزية والهاتف (Termux) بالعربية.
# يمكن فرض أي منهما بـ IAJ_LANG=ar أو IAJ_LANG=en.
_LANG = os.environ.get('IAJ_LANG') or os.environ.get('LANG_UI') or ('en' if os.name == 'nt' else 'ar')
EN = _LANG == 'en'
_ASCII = {'✓': '[OK]', '✅': '[OK]', '✖': '[X]', '❌': '[X]', '⚠': '[!]', '←': '<-', '→': '->', '★': '*', '•': '-',
          '🟢': '[OK]', '🔴': '[X]', '✋': '[!]', '…': '...', '—': '-', '–': '-', '«': '"', '»': '"'}


def _plain(text):
    for k, v in _ASCII.items():
        text = text.replace(k, v)
    return text


def t(ar, en):
    if not EN:
        return ar
    return _plain(en) if os.name == 'nt' else en


class _PlainOut:
    """على ويندوز: كل ما يُطبع يمر بـ _plain، فلا تظهر الرموز (✓ ✖ ←) مربعات في نافذة الأوامر."""

    def __init__(self, stream):
        self._stream = stream

    def write(self, text):
        return self._stream.write(_plain(text) if isinstance(text, str) else text)

    def __getattr__(self, name):
        return getattr(self._stream, name)


if EN and os.name == 'nt':
    for _name in ('stdout', 'stderr'):
        if getattr(sys, _name, None) is not None and not isinstance(getattr(sys, _name), _PlainOut):
            setattr(sys, _name, _PlainOut(getattr(sys, _name)))


def die(msg):
    print(f'\n✖ {msg}')
    sys.exit(1)


class CF:
    def __init__(self, token):
        self.s = requests.Session()
        self.s.headers.update({'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})

    def call(self, method, path, **kw):
        r = self.s.request(method, API + path, timeout=30, **kw)
        try:
            data = r.json()
        except ValueError:
            die(t(f'رد غير متوقع من Cloudflare ({r.status_code})', f'Unexpected reply from Cloudflare ({r.status_code})'))
        if not data.get('success'):
            errs = '; '.join(e.get('message', '') for e in data.get('errors', []))
            die(t(f'Cloudflare رفض الطلب: {errs or r.status_code}\n  (تأكد من صلاحيات رمز API)', f'Cloudflare refused: {errs or r.status_code}\n  (check the API token permissions)'))
        return data.get('result')


def main():
    load_env()
    cmd = (sys.argv[1] if len(sys.argv) > 1 else 'status').lower()
    if cmd not in ('status', 'phone', 'server', 'auto', 'server-up'):
        print(__doc__)
        return
    token = os.environ.get('CF_API_TOKEN', '').strip()
    if not token:
        die(t('لا يوجد CF_API_TOKEN في ملف .env — أنشئ رمز API من Cloudflare وضعه فيه', 'No CF_API_TOKEN in .env - create a Cloudflare API token and add it'))
    zone_name = os.environ.get('CF_ZONE', 'iajaward.org')
    main_name = os.environ.get('CF_MAIN_TUNNEL', 'iajaward')
    standby_name = os.environ.get('CF_STANDBY_TUNNEL', 'iaj-standby')
    cf = CF(token)

    zones = cf.call('GET', '/zones', params={'name': zone_name})
    if not zones:
        die(t(f'لم أجد النطاق {zone_name} — هل الرمز يملك صلاحية Zone:Read عليه؟', f'Zone {zone_name} not found - does the token have Zone:Read?'))
    zone, acc = zones[0]['id'], zones[0]['account']['id']

    def tunnel(name):
        res = cf.call('GET', f'/accounts/{acc}/cfd_tunnel', params={'name': name, 'is_deleted': 'false'})
        if not res:
            die(t(f'لم أجد النفق «{name}» في Cloudflare', f'Tunnel "{name}" not found in Cloudflare'))
        return res[0]

    t_main, t_standby = tunnel(main_name), tunnel(standby_name)
    by_target = {f"{t_main['id']}.cfargotunnel.com": t(f'الخادم ({main_name})', f'SERVER ({main_name})'),
                 f"{t_standby['id']}.cfargotunnel.com": t(f'الهاتف ({standby_name})', f'PHONE ({standby_name})')}

    def ingress(tun):
        res = cf.call('GET', f"/accounts/{acc}/cfd_tunnel/{tun['id']}/configurations") or {}
        return (res.get('config') or {}).get('ingress') or []

    # الأسماء العامة للموقع = أسماء نفق الخادم (مثل iajaward.org و www.iajaward.org)
    # فقط أسماء هذا الموقع (المنفذ 8000) — أسماء أنظمة أخرى على نفس النفق (مثل 1.iajaward.org للتذاكر) لا تُلمس
    port = os.environ.get('PORT', '8000')
    rules = [r for r in ingress(t_main) if r.get('hostname') and not r['hostname'].startswith('standby.')]
    mine = [r['hostname'] for r in rules if str(r.get('service', '')).rstrip('/').endswith(':' + port)]
    others = {h.strip() for h in os.environ.get('CF_OTHER_HOSTS', '1.' + zone_name + ',2.' + zone_name + ',3.' + zone_name).split(',') if h.strip()}
    hosts = mine or [r['hostname'] for r in rules if r['hostname'] not in others] or [zone_name]

    def records():
        out = {}
        for h in hosts:
            rec = cf.call('GET', f'/zones/{zone}/dns_records', params={'name': h, 'type': 'CNAME'})
            if rec:
                out[h] = rec[0]
        return out

    def status_line(tun):
        st = (tun.get('status') or '').lower()
        return ({'healthy': '🟢 متصل', 'degraded': '🟡 متصل جزئياً', 'inactive': '⚪ متوقف', 'down': '🔴 منقطع'} if not EN else {'healthy': '[OK] connected', 'degraded': '[~] degraded', 'inactive': '[-] stopped', 'down': '[X] down'}).get(st, st)

    def is_up(tun):
        return (tun.get('status') or '').lower() in ('healthy', 'degraded')

    if cmd == 'server-up':
        # للهاتف: هل الخادم يعمل؟ (رمز خروج 0 = نعم) — يمنع تشغيل الطوارئ والخادم سليم
        sys.exit(0 if is_up(t_main) else 1)

    logs = os.path.join(HERE, '..', 'logs')

    if cmd == 'auto':
        # حارس على الخادم (كل 5 دقائق): إذا كان الموقع موجّهاً للهاتف والهاتف منقطع والخادم متصل
        # ← نتحقق مرة ثانية بعد 30 ثانية، ثم نعيد الموقع للخادم (يحمي من توقف الهاتف أو إغلاق Termux)
        os.makedirs(logs, exist_ok=True)
        stamp = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(os.path.join(logs, 'watchdog_last.txt'), 'w', encoding='utf-8') as fh:
            fh.write(stamp)   # دليل أن الحارس يعمل (يظهر في site_where.bat)
        recs = records()
        on_phone = any(r['content'].startswith(t_standby['id']) for r in recs.values())
        if not on_phone or is_up(t_standby) or not is_up(t_main):
            print(f'{stamp} OK (on_phone={on_phone}, phone_up={is_up(t_standby)}, server_up={is_up(t_main)})')
            return
        time.sleep(30)
        t_sb2 = tunnel(standby_name)
        if is_up(t_sb2):
            print(f'{stamp} phone tunnel came back - nothing changed')
            return
        content = f"{t_main['id']}.cfargotunnel.com"
        for h, rec in recs.items():
            if rec['content'] != content:
                cf.call('PATCH', f"/zones/{zone}/dns_records/{rec['id']}", json={'content': content, 'proxied': True})
        with open(os.path.join(logs, 'failover.log'), 'a', encoding='utf-8') as fh:
            fh.write(f'{stamp} الهاتف منقطع والموقع موجّه له — أُعيد iajaward.org إلى الخادم تلقائياً\n')
        print(f'{stamp} ✅ الهاتف منقطع — أُعيد iajaward.org إلى الخادم تلقائياً')
        return

    if cmd == 'status':
        print(t(f'\nنفق الخادم  «{main_name}»: {status_line(t_main)}', f'\nServer tunnel  {main_name}: {status_line(t_main)}'))
        print(t(f'نفق الهاتف   «{standby_name}»: {status_line(t_standby)}\n', f'Phone tunnel   {standby_name}: {status_line(t_standby)}\n'))
        recs = records()
        for h, rec in recs.items():
            print(f'  {h}  {t("←", "->")}  {by_target.get(rec["content"], rec["content"])}')
        on_phone = any(r['content'].startswith(t_standby['id']) for r in recs.values())
        on_target = t_standby if on_phone else t_main
        print()
        code = None
        try:
            code = requests.get(f'https://{hosts[0]}/', timeout=15, allow_redirects=False,
                                headers={'User-Agent': 'iaj-status'}).status_code
        except Exception:
            pass
        if is_up(on_target) and code and code < 500:
            print(t('✅ الموقع يعمل.', '✅ The site is up.'))
        elif is_up(on_target):
            print(t(f'❌ النفق متصل لكن موقع الجائزة نفسه لا يستجيب ({code or "لا رد"}) — متوقف؟ على الكمبيوتر: iaj_on.bat',
                    f'❌ The tunnel is connected but the award site itself does not respond ({code or "no reply"}) - stopped? On the PC: iaj_on.bat'))
        elif on_phone and is_up(t_main):
            print(t('❌ الموقع متوقف: موجّه للهاتف والهاتف منقطع.\n   الحل الآن: switch_to_server.bat (على الخادم)',
                    '❌ The site is DOWN: it points to the phone and the phone is offline.\n   Fix now: switch_to_server.bat (on the server)'))
        elif on_phone:
            print(t('❌ الموقع متوقف: الهاتف والخادم كلاهما منقطعان.', '❌ The site is DOWN: both the phone and the server are offline.'))
        else:
            print(t('❌ الموقع متوقف: الخادم منقطع — تأكد أن الكمبيوتر يعمل ومتصل بالإنترنت، أو شغّل الطوارئ من الهاتف.',
                    '❌ The site is DOWN: the server is offline - check the PC and its internet, or start the emergency mode on the phone.'))
        last = os.path.join(logs, 'watchdog_last.txt')
        if os.path.isfile(os.path.join(HERE, '..', 'manage.py')) and os.name == 'nt':
            if os.path.isfile(last):
                age = (time.time() - os.path.getmtime(last)) / 60
                ok = age < 15
                print(t(f'{"✅" if ok else "⚠"} حارس الخادم: آخر فحص قبل {age:.0f} دقيقة' + ('' if ok else ' — لا يعمل! شغّل 3_autostart.bat كمسؤول'),
                        f'{"✅" if ok else "⚠"} Server watchdog: last check {age:.0f} min ago' + ('' if ok else ' - NOT running! Run 3_autostart.bat as administrator')))
            else:
                print(t('⚠ حارس الخادم غير مفعّل — شغّل 3_autostart.bat كمسؤول (زر يمين ← Run as administrator)',
                        '⚠ Server watchdog is not set up - run 3_autostart.bat as administrator'))
            flog = os.path.join(logs, 'failover.log')
            if os.path.isfile(flog):
                lines = open(flog, encoding='utf-8', errors='ignore').read().strip().splitlines()[-3:]
                if lines:
                    print(t('\nآخر تدخلات الحارس:', '\nLast watchdog actions:'))
                    for ln in lines:
                        print('  ' + ln)
        return

    target = t_standby if cmd == 'phone' else t_main
    who = (t('الهاتف', 'the PHONE') if cmd == 'phone' else t('الخادم', 'the SERVER'))

    # ١) النفق المستهدف يجب أن يعرف أسماء الموقع (يُضاف مرة واحدة لنفق الهاتف)
    rules = ingress(target)
    known = {r.get('hostname') for r in rules}
    missing = [h for h in hosts if h not in known]
    if missing:
        catch_all = [r for r in rules if not r.get('hostname')] or [{'service': 'http_status:404'}]
        named = [r for r in rules if r.get('hostname')]
        named += [{'hostname': h, 'service': 'http://localhost:8000'} for h in missing]
        res = cf.call('GET', f"/accounts/{acc}/cfd_tunnel/{target['id']}/configurations") or {}
        cfg = res.get('config') or {}
        cfg['ingress'] = named + catch_all[-1:]
        cf.call('PUT', f"/accounts/{acc}/cfd_tunnel/{target['id']}/configurations", json={'config': cfg})
        print(t(f'✓ أُضيفت الأسماء {", ".join(missing)} إلى نفق {who}', f'✓ Added {", ".join(missing)} to the tunnel of {who}'))

    # ٢) التأكد أن النفق المستهدف متصل (ننتظر حتى 60 ثانية)
    for i in range(12):
        tn = cf.call('GET', f"/accounts/{acc}/cfd_tunnel/{target['id']}")
        if (tn.get('status') or '').lower() in ('healthy', 'degraded'):
            break
        if i == 0:
            print(t(f'… انتظار اتصال نفق {who}', f'... waiting for the tunnel of {who}'))
        time.sleep(5)
    else:
        die(t(f'نفق {who} غير متصل — شغّل الموقع عليه أولاً (على الهاتف: phone.sh takeover)', f'The tunnel of {who} is not connected - start the site there first'))

    # ٣) توجيه DNS للنفق المستهدف
    content = f"{target['id']}.cfargotunnel.com"
    recs = records()
    if not recs:
        die(t('لم أجد سجلات DNS للموقع (CNAME)', 'No DNS (CNAME) records found for the site'))
    for h, rec in recs.items():
        if rec['content'] == content:
            print(t(f'  {h} يشير إلى {who} أصلاً', f'  {h} already points to {who}'))
            continue
        cf.call('PATCH', f"/zones/{zone}/dns_records/{rec['id']}", json={'content': content, 'proxied': True})
        print(t(f'✓ {h}  ←  {who}', f'✓ {h}  ->  {who}'))
    print(t(f'\n✅ الموقع يعمل الآن من {who} (خلال دقيقة على الأكثر).', f'\n✅ The site now runs from {who} (within a minute).'))


if __name__ == '__main__':
    main()
