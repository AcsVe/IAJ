"""
الرجوع من الهاتف إلى السيرفر: نقل بيانات الهاتف (من Google Drive) إلى قاعدة السيرفر.

    python manage.py standby_return

• يقرأ  BACKUP_DIR/db/ACTIVE_SITE.txt  (يكتبه الهاتف عند takeover)
• يسترجع أحدث نسخة رفعها الهاتف بعد وقت التحويل فقط — حماية من استرجاع نسخة تجربة قديمة بالخطأ
• رمز الخروج: 0 = تم أو لا حاجة، 2 = نسخة الهاتف لم تصل بعد
"""
import glob
import os
import sys

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from .restore_site import _STAMP


def marker_path():
    root = os.environ.get('BACKUP_DIR') or os.path.join(settings.BASE_DIR, 'backups')
    return root, os.path.join(root, 'db', 'ACTIVE_SITE.txt')


class Command(BaseCommand):
    help = 'نقل بيانات الهاتف إلى السيرفر بعد انتهاء الطوارئ'

    def handle(self, *args, **opts):
        root, marker = marker_path()
        state = open(marker, encoding='utf-8').read().split() if os.path.isfile(marker) else []
        if not state or state[0] != 'phone':
            self.stdout.write(self.style.SUCCESS('الموقع لم يكن يعمل من الهاتف (حسب السجل) — لا توجد بيانات لنقلها.'))
            return
        since = state[1] if len(state) > 1 else ''
        self.stdout.write(f'الهاتف بدأ تشغيل الموقع: {since}')
        phone = []
        for f in glob.glob(os.path.join(root, 'db', 'iaj-*-phone.json.gz')):
            m = _STAMP.search(os.path.basename(f))
            if m and m.group(1) >= since:
                phone.append((m.group(1), f))
        if not phone:
            self.stderr.write('✖ لم تصل نسخة الهاتف بعد إلى Drive.\n'
                              '  على الهاتف: Ctrl+C ثم  bash ~/iaj/standby/phone.sh handback\n'
                              '  ثم انتظر دقيقة حتى يزامن Google Drive وأعد المحاولة.')
            sys.exit(2)
        stamp, path = max(phone)
        self.stdout.write(f'نسخة الهاتف: {os.path.basename(path)}')
        call_command('restore_site', path, media=True, yes=True)
        with open(marker, 'w', encoding='utf-8') as fh:
            fh.write(f'server {timezone.localtime(timezone.now()):%Y-%m-%d_%H%M%S}\n')
        self.stdout.write(self.style.SUCCESS('✓ بيانات الهاتف صارت على السيرفر'))
