"""
استرجاع نسخة احتياطية للقاعدة (تستبدل البيانات الحالية بالكامل).

    python manage.py restore_site backups/db/iaj-2026-10-07_0200.dump --yes

الملفات: انسخ محتوى backups/media إلى مجلد media يدوياً إذا احتجت.
"""
import os
import subprocess

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from .backup_site import find_pg_tool, pg_args, pg_env


class Command(BaseCommand):
    help = 'استرجاع نسخة احتياطية للقاعدة'

    def add_arguments(self, parser):
        parser.add_argument('file')
        parser.add_argument('--yes', action='store_true')

    def handle(self, *args, **opts):
        if not os.path.isfile(opts['file']):
            raise CommandError('الملف غير موجود')
        if not opts['yes']:
            raise CommandError('سيتم استبدال كل البيانات الحالية — أعد التشغيل مع --yes للتأكيد')
        tool = find_pg_tool('pg_restore')
        if not tool:
            raise CommandError('لم أجد pg_restore — ضع PG_BIN في .env')
        db = connections['default'].settings_dict
        connections['default'].close()
        r = subprocess.run([tool, *pg_args(db), '--clean', '--if-exists', '--no-owner', '-d', db['NAME'],
                            opts['file']], env=pg_env(db), capture_output=True, text=True)
        if r.returncode != 0 and 'error' in r.stderr.lower():
            raise CommandError(r.stderr)
        self.stdout.write(self.style.SUCCESS('✓ تم الاسترجاع — أعد تشغيل الموقع'))
