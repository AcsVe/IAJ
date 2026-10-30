"""Email settings of every system, from the school computer to the standby phone, in one step.

Each system has its own email settings (its own keys and sender) in its settings file on the computer. Copying
them to the phone by hand means typing dozens of values; instead:

  on the computer:  phone_mail.bat           (award site)  -> export: reads the email lines of every system's
                    settings file, encrypts them with a password you choose, and puts the file in the Google
                    Drive backup folder:  IAJ-backups/phone/mail-settings.enc
  on the phone:     «★ لوحة الأنظمة» > m      -> import: downloads that file, asks for the password, and writes
                    each system's lines into its settings file on the phone (only the email lines change).

The file is encrypted (PBKDF2-SHA256, 300 000 rounds; HMAC-SHA256 stream with an authentication tag), so the
Drive copy is unreadable without the password. Standard library only (works on Windows and in Termux).
Values are never printed — only the names of the systems and how many lines each one got.
"""
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import sys

MAGIC = b'IAJMAIL1'
ROUNDS = 300_000
# GitHub repository | usual folder on the computer | settings file | file on the phone (inside ~/<system>)
SYSTEMS = {
    'iaj':        ('IAJ', r'C:\IAJ', '.env', '.env'),
    'rastkt':     ('RASTKT|Ticketing', r'C:\TKT', '.env', '.env'),
    'venues':     ('venues', r'C:\Venue', '.env', '.env'),
    'attendance': ('Attendance', r'C:\Att', '.env', '.env'),
    'timetable':  ('Timetable', r'C:\TT\Timetable', '.env', '.env'),
    'bell':       ('Bell', r'C:\Bell', '.env', '.env'),
    'clearance':  ('Clearance', r'C:\Clearance', 'config.env', 'config.env'),
    'sas':        ('sas', r'C:\SAS', 'config.env', 'config.env'),
}


def _repo_of(folder):
    """The AcsVe repository a folder was cloned from (its .git/config), lower-case; '' when none."""
    try:
        cfg = open(os.path.join(folder, '.git', 'config'), encoding='utf-8', errors='ignore').read()
    except OSError:
        return ''
    m = re.search(r'github\.com[/:]AcsVe/([A-Za-z0-9_.-]+?)(?:\.git)?\s*$', cfg, re.I | re.M)
    return m.group(1).lower() if m else ''


def find_folder(name):
    """Where this system is installed on the computer: the usual folder, else any folder on C: (two levels deep)
    cloned from its repository — the one that has its settings file, the shallowest first."""
    repo, usual, fn, _ = SYSTEMS[name]
    names = repo.lower().split('|')          # the current name and earlier names of the repository
    if _repo_of(usual) in names or (os.path.isfile(os.path.join(usual, fn)) and not _repo_of(usual)):
        return usual
    found = []
    for top in sorted(os.listdir('C:\\')) if os.path.isdir('C:\\') else []:
        a = os.path.join('C:\\', top)
        if not os.path.isdir(a) or top.lower() in ('windows', 'program files', 'program files (x86)', 'programdata', 'users'):
            continue
        cands = [a]
        try:
            cands += [os.path.join(a, x) for x in os.listdir(a) if os.path.isdir(os.path.join(a, x))]
        except OSError:
            pass
        for c in cands:
            if _repo_of(c) in names:
                found.append((not os.path.isfile(os.path.join(c, fn)), c.count(os.sep), c))
    return sorted(found)[0][2] if found else None


def _home():
    """The award site's folder on this computer (this file is in its standby folder)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


MAIL_KEY = re.compile(r'^(MS_[A-Z0-9_]+|EMAIL_[A-Z0-9_]+|MAIL_[A-Z0-9_]+|SMTP_[A-Z0-9_]+|GRAPH_[A-Z0-9_]+)\s*=')
SKIP = re.compile(r'(_PATH|_DIR|_OUTBOX|_FILE)$')      # folders of the computer mean nothing on the phone


# ---------------------------------------------------------------- crypto (standard library)
def _keys(password, salt):
    k = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ROUNDS, dklen=64)
    return k[:32], k[32:]


def _stream(key, nonce, n):
    out = bytearray()
    i = 0
    while len(out) < n:
        out += hmac.new(key, nonce + i.to_bytes(8, 'big'), hashlib.sha256).digest()
        i += 1
    return bytes(out[:n])


def seal(data, password):
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(16)
    ek, mk = _keys(password, salt)
    ct = bytes(a ^ b for a, b in zip(data, _stream(ek, nonce, len(data))))
    body = MAGIC + salt + nonce + ct
    return body + hmac.new(mk, body, hashlib.sha256).digest()


def unseal(blob, password):
    if not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + 64:
        raise ValueError('not a settings file')
    body, tag = blob[:-32], blob[-32:]
    salt, nonce, ct = body[8:24], body[24:40], body[40:]
    ek, mk = _keys(password, salt)
    if not hmac.compare_digest(tag, hmac.new(mk, body, hashlib.sha256).digest()):
        raise PermissionError('wrong password')
    return bytes(a ^ b for a, b in zip(ct, _stream(ek, nonce, len(ct))))


# ---------------------------------------------------------------- settings files
def mail_lines(path):
    try:
        text = open(path, encoding='utf-8-sig').read()
    except OSError:
        return None
    out = []
    for line in text.splitlines():
        s = line.strip()
        m = MAIL_KEY.match(s)
        if m and not SKIP.search(m.group(1)) and s.split('=', 1)[1].strip():
            out.append(s)
    return out


def merge(path, lines):
    """Write ``lines`` into the settings file at ``path``: the same keys are replaced, every other line is kept."""
    keys = {ln.split('=', 1)[0].strip() for ln in lines}
    old = open(path, encoding='utf-8-sig').read().splitlines() if os.path.isfile(path) else []
    kept = [ln for ln in old if ln.split('=', 1)[0].strip() not in keys]
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(kept + lines) + '\n')
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _cf_token(env_path):
    """The Cloudflare token of the award site: the computer and the phone both have it already, so it locks the
    file without asking anyone for a password."""
    try:
        for ln in open(env_path, encoding='utf-8-sig').read().splitlines():
            if ln.strip().startswith('CF_API_TOKEN='):
                v = ln.split('=', 1)[1].strip().strip('"')
                if v:
                    return 'cf:' + v
    except OSError:
        pass
    return None


def _ask_new_password():
    for _ in range(3):
        a = getpass.getpass('  Choose a password for the file (it is asked again on the phone): ')
        if len(a) < 6:
            print('  At least 6 characters.')
            continue
        if a == getpass.getpass('  Type it again: '):
            return a
        print('  The two entries differ.')
    sys.exit('  No password - nothing was written.')


def _drive_folder():
    """IAJ-backups in Google Drive on this computer: BACKUP_DIR of the award site, else the usual Drive folders."""
    try:
        env = open(os.path.join(_home(), '.env'), encoding='utf-8-sig').read().splitlines()
    except OSError:
        env = []
    for ln in env:
        if ln.strip().startswith('BACKUP_DIR='):
            d = ln.split('=', 1)[1].strip().strip('"')
            if d and os.path.isdir(d):
                return d
    for letter in 'GHIJKLMNOPDEF':
        for sub in ('My Drive', 'Mon Drive', 'محرّك الأقراص', 'محرك الأقراص الخاص بي'):
            d = f'{letter}:\\{sub}\\IAJ-backups'
            if os.path.isdir(d):
                return d
    return None


def export():
    bundle, report = {}, []
    for name in SYSTEMS:
        fn = SYSTEMS[name][2]
        folder = _home() if name == 'iaj' else find_folder(name)
        lines = mail_lines(os.path.join(folder, fn)) if folder else None
        if folder and lines is None:
            report.append(f'  -  {name:<11} not set up on this computer (no {fn} in {folder})')
        elif lines is None:
            report.append(f'  -  {name:<11} not on this computer')
        elif not lines:
            report.append(f'  -  {name:<11} no email settings')
        else:
            bundle[name] = lines
            report.append(f'  OK {name:<11} {len(lines)} lines   ({folder})')
    print('\n'.join(report))
    if not bundle:
        sys.exit('\n  No email settings were found - nothing was written.')
    drive = _drive_folder()
    if not drive:
        sys.exit('\n  The Google Drive folder IAJ-backups was not found on this computer (BACKUP_DIR in the award site .env).')
    print()
    pw = _cf_token(os.path.join(_home(), '.env'))
    if pw:
        print('  Locked with the Cloudflare token already on the computer and the phone - no password needed.')
    else:
        pw = _ask_new_password()
    out = os.path.join(drive, 'phone')
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'mail-settings.enc'), 'wb') as f:
        f.write(seal(json.dumps(bundle).encode('utf-8'), pw))
    print(f'\n  Saved (encrypted): {os.path.join(out, "mail-settings.enc")}')
    print('  On the phone: the Systems panel button (lawhat al-anzima) > m')


def import_(path):
    blob = open(path, 'rb').read()
    bundle = None
    key = _cf_token(os.path.join(os.path.expanduser('~'), 'iaj', '.env'))
    if key:
        try:
            bundle = json.loads(unseal(blob, key))
        except (PermissionError, ValueError):
            bundle = None
    for _ in range(0 if bundle is not None else 3):
        pw = getpass.getpass('  Password of the email settings file: ')
        try:
            bundle = json.loads(unseal(blob, pw))
            break
        except PermissionError:
            print('  Wrong password.')
    if bundle is None:
        sys.exit(1)
    home = os.path.expanduser('~')
    for name, lines in bundle.items():
        if name not in SYSTEMS or not os.path.isdir(os.path.join(home, name, 'standby')):
            continue
        merge(os.path.join(home, name, SYSTEMS[name][3]), lines)
        try:
            os.remove(os.path.join(home, name, '.mail_skip'))
        except OSError:
            pass
        print(f'  OK {name:<11} {len(lines)} lines')
    print('  Used from the next start of each system.')


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'export':
        export()
    elif len(sys.argv) >= 3 and sys.argv[1] == 'import':
        import_(sys.argv[2])
    else:
        sys.exit('usage: mail_bundle.py export | import FILE')
