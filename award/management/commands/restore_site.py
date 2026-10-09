"""
استرجاع نسخة احتياطية (تستبدل البيانات الحالية بالكامل).

    python manage.py restore_site backups/db/iaj-2026-10-07_020000.dump --yes        # PostgreSQL كاملة
    python manage.py restore_site backups/db/iaj-2026-10-07_020000.json.gz --yes     # محمولة (أي جهاز/قاعدة)
    python manage.py restore_site --latest "G:\\My Drive\\IAJ-backups" --media --yes  # أحدث نسخة + الملفات

• على قاعدة SQLite (الهاتف/جهاز احتياطي بدون PostgreSQL) تُستخدم النسخة المحمولة تلقائياً.
• --media ينسخ مجلد media من مجلد النسخ إلى مجلد الموقع (الجديد والمعدّل فقط).
"""
import glob
import os
import re
import shutil
import subprocess

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from .backup_site import find_pg_tool, pg_args, pg_env

_STAMP = re.compile(r'iaj-(\d{4}-\d{2}-\d{2}_\d{4,6})')


def newest_backup(root, allow_dump=True, tag=''):
    """أحدث نسخة في المجلد (حسب التاريخ في اسم الملف) — من أي جهاز (السيرفر أو الهاتف)"""
    db_dir = os.path.join(root, 'db') if os.path.isdir(os.path.join(root, 'db')) else root
    files = glob.glob(os.path.join(db_dir, 'iaj-*.json.gz'))
    if allow_dump:
        files += glob.glob(os.path.join(db_dir, 'iaj-*.dump'))
    if tag:
        files = [f for f in files if f'-{tag}.' in os.path.basename(f)]

    def key(p):
        m = _STAMP.search(os.path.basename(p))
        stamp = (m.group(1) if m else '').ljust(17, '0')
        return (stamp, p.endswith('.dump'))   # بنفس التوقيت: نفضّل نسخة PostgreSQL الكاملة
    return max(files, key=key) if files else None


class Command(BaseCommand):
    help = 'استرجاع نسخة احتياطية للقاعدة (وملفات media اختيارياً)'

    def add_arguments(self, parser):
        parser.add_argument('file', nargs='?', default='')
        parser.add_argument('--latest', default='', help='مجلد النسخ: يُسترجع أحدث ملف فيه')
        parser.add_argument('--media', action='store_true', help='نسخ ملفات media من مجلد النسخ أيضاً')
        parser.add_argument('--tag', default='', help='أحدث نسخة بهذه اللاحقة فقط (مثل phone)')
        parser.add_argument('--yes', action='store_true')

    def handle(self, *args, **opts):
        db = connections['default'].settings_dict
        is_pg = 'postgresql' in db['ENGINE']
        path = opts['file']
        root = opts['latest']
        if root == 'auto':   # مجلد النسخ من .env (BACKUP_DIR) أو مجلد backups
            root = os.environ.get('BACKUP_DIR') or os.path.join(settings.BASE_DIR, 'backups')
        if root:
            path = newest_backup(root, allow_dump=is_pg, tag=opts['tag'])
            if not path:
                raise CommandError(f'لا توجد نسخ في: {root}')
        if not path or not os.path.isfile(path):
            raise CommandError('الملف غير موجود')
        self.stdout.write(f'النسخة: {path}')
        if not opts['yes']:
            raise CommandError('سيتم استبدال كل البيانات الحالية — أعد التشغيل مع --yes للتأكيد')

        if path.endswith('.dump'):
            if not is_pg:
                raise CommandError('ملف .dump يحتاج PostgreSQL — استخدم ملف .json.gz على هذا الجهاز')
            self._restore_pg(db, path)
        else:
            self._restore_json(path)

        if opts['media']:
            src = os.path.join(root or os.path.dirname(os.path.dirname(os.path.abspath(path))), 'media')
            self._copy_media(src)
        self.stdout.write(self.style.SUCCESS('✓ تم الاسترجاع — أعد تشغيل الموقع'))

    def _restore_pg(self, db, path):
        tool = find_pg_tool('pg_restore')
        if not tool:
            raise CommandError('لم أجد pg_restore — ضع PG_BIN في .env')
        connections['default'].close()
        r = subprocess.run([tool, *pg_args(db), '--clean', '--if-exists', '--no-owner', '-d', db['NAME'], path],
                           env=pg_env(db), capture_output=True, text=True)
        if r.returncode != 0 and 'error' in r.stderr.lower():
            raise CommandError(r.stderr)

    def _restore_json(self, path):
        from django.core.cache import cache
        call_command('migrate', interactive=False, verbosity=0)
        call_command('flush', interactive=False, verbosity=0)     # تفريغ البيانات (تبقى الجداول)
        call_command('loaddata', path, verbosity=0)
        cache.clear()

    def _copy_media(self, src):
        if not os.path.isdir(src):
            self.stdout.write(self.style.WARNING(f'لا يوجد مجلد ملفات في: {src}'))
            return
        dst, n = settings.MEDIA_ROOT, 0
        for d, _, files in os.walk(src):
            target = os.path.join(dst, os.path.relpath(d, src))
            os.makedirs(target, exist_ok=True)
            for fn in files:
                s, t = os.path.join(d, fn), os.path.join(target, fn)
                if not os.path.exists(t) or os.path.getsize(s) != os.path.getsize(t):
                    shutil.copy2(s, t)
                    n += 1
        self.stdout.write(self.style.SUCCESS(f'✓ الملفات: {n} ملف → {dst}'))
