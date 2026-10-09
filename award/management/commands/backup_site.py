r"""
نسخة احتياطية: قاعدة البيانات (pg_dump) + مجلد الملفات media.

    python manage.py backup_site              # نسخة الآن
    python manage.py backup_site --keep 30    # الاحتفاظ بآخر 30 نسخة للقاعدة

• القاعدة: backups/db/iaj-YYYY-MM-DD_HHMM.dump  (تُحذف الأقدم تلقائياً)
• الملفات: backups/media  (نسخة مطابقة تُحدَّث بالملفات الجديدة فقط)
• نسخة «محمولة»: backups/db/iaj-YYYY-MM-DD_HHMMSS.json.gz — تُسترجع على أي جهاز (حتى الهاتف بدون PostgreSQL)
• الكود: backups/code/iaj-code.zip — لتشغيل الموقع على جهاز احتياطي بدون GitHub
• يُفضّل وضع BACKUP_DIR في .env على مجلد Google Drive (مثال: G:\My Drive\IAJ-backups)
"""
import glob
import os
import shutil
import subprocess
from datetime import datetime

from django.conf import settings
from django.utils import timezone
from django.core.management.base import BaseCommand, CommandError
from django.db import connections


def find_pg_tool(tool):
    exe = tool + ('.exe' if os.name == 'nt' else '')
    if os.environ.get('PG_BIN'):
        p = os.path.join(os.environ['PG_BIN'], exe)
        if os.path.isfile(p):
            return p
    found = shutil.which(tool)
    if found:
        return found
    cands = glob.glob(rf'C:\Program Files\PostgreSQL\*\bin\{exe}') + glob.glob(f'/usr/lib/postgresql/*/bin/{tool}')

    def ver(p):
        try:
            return int(os.path.basename(os.path.dirname(os.path.dirname(p))).split('.')[0])
        except ValueError:
            return 0
    return max(cands, key=ver) if cands else None


def pg_env(db):
    env = os.environ.copy()
    env['PGPASSWORD'] = str(db.get('PASSWORD') or '')
    return env


def pg_args(db):
    return ['-h', str(db.get('HOST') or 'localhost'), '-p', str(db.get('PORT') or 5432),
            '-U', str(db.get('USER') or 'postgres')]



def _t(ar, en):
    """رسائل بالإنجليزية على الهاتف إن اختار المستخدم ذلك (Termux لا يعرض العربية جيداً)"""
    return en if os.environ.get('IAJ_LANG') == 'en' else ar


class Command(BaseCommand):
    help = 'نسخة احتياطية للقاعدة والملفات'

    def add_arguments(self, parser):
        parser.add_argument('--keep', type=int, default=48, help='عدد النسخ المحفوظة من كل نوع')
        parser.add_argument('--dir', default='', help='مجلد النسخ (بدلاً من BACKUP_DIR)')
        parser.add_argument('--tag', default='', help='لاحقة لاسم الملف، مثل phone')
        parser.add_argument('--no-code', action='store_true')
        parser.add_argument('--no-media', action='store_true')

    def handle(self, *args, **opts):
        db = connections['default'].settings_dict
        root = opts['dir'] or os.environ.get('BACKUP_DIR') or os.path.join(settings.BASE_DIR, 'backups')
        db_dir = os.path.join(root, 'db')
        os.makedirs(db_dir, exist_ok=True)
        # بتوقيت الجائزة (عمّان) على كل الأجهزة — حتى تُقارن نسخ السيرفر والهاتف بشكل صحيح
        stamp = f"{timezone.localtime(timezone.now()):%Y-%m-%d_%H%M%S}" + (f"-{opts['tag']}" if opts['tag'] else '')

        # ١) نسخة PostgreSQL الكاملة (على جهاز السيرفر)
        if 'postgresql' in db['ENGINE']:
            pg_dump = find_pg_tool('pg_dump')
            if not pg_dump:
                raise CommandError('لم أجد pg_dump — ضع مسار مجلد bin الخاص بـ PostgreSQL في .env باسم PG_BIN')
            out = os.path.join(db_dir, f'iaj-{stamp}.dump')
            r = subprocess.run([pg_dump, *pg_args(db), '-Fc', '-f', out, db['NAME']],
                               env=pg_env(db), capture_output=True, text=True)
            if r.returncode != 0:
                raise CommandError('فشل pg_dump:\n' + r.stderr)
            self.stdout.write(self.style.SUCCESS(_t('✓ القاعدة (PostgreSQL)', '✓ Database (PostgreSQL)') + f': {out} ({os.path.getsize(out) / 1024 / 1024:.1f} MB)'))

        # ٢) نسخة محمولة (JSON) تعمل على أي جهاز وأي قاعدة — للجهاز الاحتياطي والهاتف
        out = os.path.join(db_dir, f'iaj-{stamp}.json.gz')
        self._dump_json(out)
        self.stdout.write(self.style.SUCCESS(_t('✓ القاعدة (محمولة)', '✓ Database (portable)') + f': {out} ({os.path.getsize(out) / 1024 / 1024:.1f} MB)'))

        for pattern in ('iaj-*.dump', 'iaj-*.json.gz'):
            files = sorted(glob.glob(os.path.join(db_dir, pattern)))
            for old in files[:-opts['keep']] if opts['keep'] > 0 else []:
                os.remove(old)

        # ٣) الكود (بدون الأسرار والبيانات) — ليُشغَّل على جهاز احتياطي أو هاتف بلا حاجة لـ GitHub
        if not opts['no_code']:
            self._code_zip(os.path.join(root, 'code'))
        if opts['no_media']:
            return

        # الملفات: نسخ الجديد والمعدّل فقط
        src, dst = settings.MEDIA_ROOT, os.path.join(root, 'media')
        copied = 0
        if os.path.isdir(src):
            for d, _, files in os.walk(src):
                target_dir = os.path.join(dst, os.path.relpath(d, src))
                os.makedirs(target_dir, exist_ok=True)
                for fn in files:
                    s, t = os.path.join(d, fn), os.path.join(target_dir, fn)
                    if not os.path.exists(t) or os.path.getmtime(s) > os.path.getmtime(t) or \
                            os.path.getsize(s) != os.path.getsize(t):
                        shutil.copy2(s, t)
                        copied += 1
        self.stdout.write(self.style.SUCCESS(_t(f'✓ الملفات: {copied} ملف جديد → {dst}', f'✓ Files: {copied} new -> {dst}')))

    # ------------------------------------------------------------------
    def _dump_json(self, out):
        import gzip
        from django.core.management import call_command
        tmp = out + '.part'
        with gzip.open(tmp, 'wt', encoding='utf-8') as fh:
            call_command('dumpdata', natural_foreign=True, natural_primary=True, indent=None, stdout=fh,
                         exclude=['contenttypes', 'auth.permission', 'sessions', 'admin.logentry'])
        os.replace(tmp, out)

    def _code_zip(self, code_dir):
        import zipfile
        os.makedirs(code_dir, exist_ok=True)
        out = os.path.join(code_dir, 'iaj-code.zip')
        base = str(settings.BASE_DIR)
        skip_dirs = {'.git', 'venv', '.venv', 'env', 'media', 'backups', 'staticfiles', 'logs', '__pycache__', 'node_modules', 'Music'}
        skip_files = {'.env', 'IAJ.env', 'db.sqlite3'}
        tmp = out + '.part'
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
            for d, dirs, files in os.walk(base):
                dirs[:] = [x for x in dirs if x not in skip_dirs and not x.startswith('.')]
                rel = os.path.relpath(d, base)
                if rel.split(os.sep)[0] in skip_dirs:
                    continue
                for fn in files:
                    if fn in skip_files or fn.endswith(('.pyc', '.log', '.dump', '.part')):
                        continue
                    full = os.path.join(d, fn)
                    arc = os.path.join('iaj', os.path.relpath(full, base)).replace(os.sep, '/')
                    if fn.endswith('.sh'):
                        # سكربتات الهاتف يجب أن تكون بنهايات أسطر Linux (Windows/git قد يحوّلها إلى CRLF)
                        with open(full, 'rb') as fh:
                            z.writestr(arc, fh.read().replace(b'\r\n', b'\n'))
                    else:
                        z.write(full, arc)
        os.replace(tmp, out)
        self.stdout.write(self.style.SUCCESS(_t('✓ الكود', '✓ Code') + f': {out}'))
