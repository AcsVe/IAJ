"""
نسخة احتياطية: قاعدة البيانات (pg_dump) + مجلد الملفات media.

    python manage.py backup_site              # نسخة الآن
    python manage.py backup_site --keep 30    # الاحتفاظ بآخر 30 نسخة للقاعدة

• القاعدة: backups/db/iaj-YYYY-MM-DD_HHMM.dump  (تُحذف الأقدم تلقائياً)
• الملفات: backups/media  (نسخة مطابقة تُحدَّث بالملفات الجديدة فقط)
• يُفضّل وضع BACKUP_DIR في .env على قرص آخر أو فلاشة/مجلد OneDrive
"""
import glob
import os
import shutil
import subprocess
from datetime import datetime

from django.conf import settings
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


class Command(BaseCommand):
    help = 'نسخة احتياطية للقاعدة والملفات'

    def add_arguments(self, parser):
        parser.add_argument('--keep', type=int, default=14)

    def handle(self, *args, **opts):
        db = connections['default'].settings_dict
        if 'postgresql' not in db['ENGINE']:
            raise CommandError('النسخ الاحتياطي يعمل مع PostgreSQL فقط')
        pg_dump = find_pg_tool('pg_dump')
        if not pg_dump:
            raise CommandError('لم أجد pg_dump — ضع مسار مجلد bin الخاص بـ PostgreSQL في .env باسم PG_BIN')

        root = os.environ.get('BACKUP_DIR') or os.path.join(settings.BASE_DIR, 'backups')
        db_dir = os.path.join(root, 'db')
        os.makedirs(db_dir, exist_ok=True)

        out = os.path.join(db_dir, f'iaj-{datetime.now():%Y-%m-%d_%H%M%S}.dump')
        r = subprocess.run([pg_dump, *pg_args(db), '-Fc', '-f', out, db['NAME']],
                           env=pg_env(db), capture_output=True, text=True)
        if r.returncode != 0:
            raise CommandError('فشل pg_dump:\n' + r.stderr)
        self.stdout.write(self.style.SUCCESS(f'✓ القاعدة: {out} ({os.path.getsize(out) / 1024 / 1024:.1f} MB)'))

        dumps = sorted(glob.glob(os.path.join(db_dir, 'iaj-*.dump')))
        for old in dumps[:-opts['keep']] if opts['keep'] > 0 else []:
            os.remove(old)

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
        self.stdout.write(self.style.SUCCESS(f'✓ الملفات: {copied} ملف جديد → {dst}'))
