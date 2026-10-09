"""
تحويل iajaward.org بين السيرفر والهاتف تلقائياً عبر Cloudflare API — بدون الدخول للوحة Cloudflare.

    python standby/cf_switch.py status    # أين يشير الموقع الآن + حالة النفقين
    python standby/cf_switch.py phone     # iajaward.org ← الهاتف (نفق iaj-standby)
    python standby/cf_switch.py server    # iajaward.org ← السيرفر (نفق iajaward)

يحتاج في ملف .env (على السيرفر وعلى الهاتف):
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
            die(f'رد غير متوقع من Cloudflare ({r.status_code})')
        if not data.get('success'):
            errs = '; '.join(e.get('message', '') for e in data.get('errors', []))
            die(f'Cloudflare رفض الطلب: {errs or r.status_code}\n  (تأكد من صلاحيات رمز API)')
        return data.get('result')


def main():
    load_env()
    cmd = (sys.argv[1] if len(sys.argv) > 1 else 'status').lower()
    if cmd not in ('status', 'phone', 'server'):
        print(__doc__)
        return
    token = os.environ.get('CF_API_TOKEN', '').strip()
    if not token:
        die('لا يوجد CF_API_TOKEN في ملف .env — أنشئ رمز API من Cloudflare وضعه فيه')
    zone_name = os.environ.get('CF_ZONE', 'iajaward.org')
    main_name = os.environ.get('CF_MAIN_TUNNEL', 'iajaward')
    standby_name = os.environ.get('CF_STANDBY_TUNNEL', 'iaj-standby')
    cf = CF(token)

    zones = cf.call('GET', '/zones', params={'name': zone_name})
    if not zones:
        die(f'لم أجد النطاق {zone_name} — هل الرمز يملك صلاحية Zone:Read عليه؟')
    zone, acc = zones[0]['id'], zones[0]['account']['id']

    def tunnel(name):
        res = cf.call('GET', f'/accounts/{acc}/cfd_tunnel', params={'name': name, 'is_deleted': 'false'})
        if not res:
            die(f'لم أجد النفق «{name}» في Cloudflare')
        return res[0]

    t_main, t_standby = tunnel(main_name), tunnel(standby_name)
    by_target = {f"{t_main['id']}.cfargotunnel.com": f'السيرفر ({main_name})',
                 f"{t_standby['id']}.cfargotunnel.com": f'الهاتف ({standby_name})'}

    def ingress(t):
        res = cf.call('GET', f"/accounts/{acc}/cfd_tunnel/{t['id']}/configurations") or {}
        return (res.get('config') or {}).get('ingress') or []

    # الأسماء العامة للموقع = أسماء نفق السيرفر (مثل iajaward.org و www.iajaward.org)
    hosts = [r['hostname'] for r in ingress(t_main) if r.get('hostname')]
    hosts = [h for h in hosts if not h.startswith('standby.')] or [zone_name]

    def records():
        out = {}
        for h in hosts:
            rec = cf.call('GET', f'/zones/{zone}/dns_records', params={'name': h, 'type': 'CNAME'})
            if rec:
                out[h] = rec[0]
        return out

    def status_line(t):
        st = (t.get('status') or '').lower()
        return {'healthy': '🟢 متصل', 'degraded': '🟡 متصل جزئياً', 'inactive': '⚪ متوقف', 'down': '🔴 منقطع'}.get(st, st)

    if cmd == 'status':
        print(f'\nنفق السيرفر  «{main_name}»: {status_line(t_main)}')
        print(f'نفق الهاتف   «{standby_name}»: {status_line(t_standby)}\n')
        for h, rec in records().items():
            print(f'  {h}  ←  {by_target.get(rec["content"], rec["content"])}')
        return

    target = t_standby if cmd == 'phone' else t_main
    who = 'الهاتف' if cmd == 'phone' else 'السيرفر'

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
        print(f'✓ أُضيفت الأسماء {", ".join(missing)} إلى نفق {who}')

    # ٢) التأكد أن النفق المستهدف متصل (ننتظر حتى 60 ثانية)
    for i in range(12):
        t = cf.call('GET', f"/accounts/{acc}/cfd_tunnel/{target['id']}")
        if (t.get('status') or '').lower() in ('healthy', 'degraded'):
            break
        if i == 0:
            print(f'… انتظار اتصال نفق {who}')
        time.sleep(5)
    else:
        die(f'نفق {who} غير متصل — شغّل الموقع عليه أولاً (على الهاتف: phone.sh takeover)')

    # ٣) توجيه DNS للنفق المستهدف
    content = f"{target['id']}.cfargotunnel.com"
    recs = records()
    if not recs:
        die('لم أجد سجلات DNS للموقع (CNAME)')
    for h, rec in recs.items():
        if rec['content'] == content:
            print(f'  {h} يشير إلى {who} أصلاً')
            continue
        cf.call('PATCH', f"/zones/{zone}/dns_records/{rec['id']}", json={'content': content, 'proxied': True})
        print(f'✓ {h}  ←  {who}')
    print(f'\n✅ الموقع يعمل الآن من {who} (خلال دقيقة على الأكثر).')


if __name__ == '__main__':
    main()
