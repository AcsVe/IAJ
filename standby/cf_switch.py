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


EN = os.environ.get('IAJ_LANG', os.environ.get('LANG_UI', '')) == 'en'


def t(ar, en):
    return en if EN else ar


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
    if cmd not in ('status', 'phone', 'server'):
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
    by_target = {f"{t_main['id']}.cfargotunnel.com": t(f'السيرفر ({main_name})', f'SERVER ({main_name})'),
                 f"{t_standby['id']}.cfargotunnel.com": t(f'الهاتف ({standby_name})', f'PHONE ({standby_name})')}

    def ingress(tun):
        res = cf.call('GET', f"/accounts/{acc}/cfd_tunnel/{tun['id']}/configurations") or {}
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

    def status_line(tun):
        st = (tun.get('status') or '').lower()
        return ({'healthy': '🟢 متصل', 'degraded': '🟡 متصل جزئياً', 'inactive': '⚪ متوقف', 'down': '🔴 منقطع'} if not EN else {'healthy': '[OK] connected', 'degraded': '[~] degraded', 'inactive': '[-] stopped', 'down': '[X] down'}).get(st, st)

    if cmd == 'status':
        print(t(f'\nنفق السيرفر  «{main_name}»: {status_line(t_main)}', f'\nServer tunnel  {main_name}: {status_line(t_main)}'))
        print(t(f'نفق الهاتف   «{standby_name}»: {status_line(t_standby)}\n', f'Phone tunnel   {standby_name}: {status_line(t_standby)}\n'))
        for h, rec in records().items():
            print(f'  {h}  {t("←", "->")}  {by_target.get(rec["content"], rec["content"])}')
        return

    target = t_standby if cmd == 'phone' else t_main
    who = (t('الهاتف', 'the PHONE') if cmd == 'phone' else t('السيرفر', 'the SERVER'))

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
