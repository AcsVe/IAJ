"""تحديث كود الموقع على الهاتف من GitHub مباشرة (بدون الحاجة لجهاز السيرفر).

    python gh_update.py          # يقرأ الرمز من ~/.iaj_github_token

• الرمز: Fine-grained token للقراءة فقط (Contents: Read-only) لمستودع IAJ وحده.
• لا يلمس: .env، قاعدة البيانات db.sqlite3، مجلد media، staticfiles.
"""
import io
import os
import shutil
import sys
import urllib.request
import zipfile

REPO = os.environ.get('IAJ_GITHUB_REPO', 'AcsVe/IAJ')
BRANCH = os.environ.get('IAJ_GITHUB_BRANCH', 'main')
SITE = os.path.expanduser('~/iaj')
KEEP = {'.env', 'IAJ.env', 'db.sqlite3', 'media', 'staticfiles', 'logs', 'backups'}
EN = os.environ.get('IAJ_LANG') == 'en'


def main():
    tok_file = os.path.expanduser('~/.iaj_github_token')
    headers = {'User-Agent': 'iaj-phone'}
    if os.path.isfile(tok_file):          # the repository is public; a token only raises the rate limit
        headers['Authorization'] = f'Bearer {open(tok_file).read().strip()}'
    req = urllib.request.Request(f'https://api.github.com/repos/{REPO}/zipball/{BRANCH}', headers=headers)
    try:
        data = urllib.request.urlopen(req, timeout=120).read()
    except Exception as e:
        print(('GitHub failed: ' if EN else 'تعذّر الاتصال بـ GitHub: ') + str(e))
        sys.exit(2)
    z = zipfile.ZipFile(io.BytesIO(data))
    root = z.namelist()[0].split('/')[0] + '/'
    n = 0
    for info in z.infolist():
        rel = info.filename[len(root):]
        if not rel or rel.split('/')[0] in KEEP:
            continue
        dest = os.path.join(SITE, rel)
        if info.is_dir():
            os.makedirs(dest, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        content = z.read(info)
        if rel.endswith('.sh'):
            content = content.replace(b'\r\n', b'\n')
        with open(dest, 'wb') as fh:
            fh.write(content)
        n += 1
    print((f'GitHub: {n} files updated' if EN else f'GitHub: تم تحديث {n} ملف'))


if __name__ == '__main__':
    main()
