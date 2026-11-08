"""خادم تجربة لفحص المظهر واللغة (tests/ui_audit.py): قاعدة SQLite مؤقتة تُبنى من الترحيلات، ثم يُملأ المحتوى التجريبي
(seed_demo) وتُحاكى دورة كاملة (simulate_cycle: مدارس ومحكّمون وطلبات ونتائج)، ويُنشأ مدير.

    python tests/audit_server.py <مجلد مؤقت> <المنفذ>
يطبع سطر JSON (حسابات التجربة) ثم يشغّل الخادم حتى يُوقَف. لا يمسّ القاعدة الحقيقية ولا ملف .env.
"""
import json
import os
import sys

DATA, PORT = sys.argv[1], sys.argv[2]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(DATA, exist_ok=True)
db = os.path.join(DATA, 'iaj.db')
if os.path.exists(db):
    os.remove(db)
# كل قيمة مضبوطة هنا صراحةً حتى لا يُقرأ ما يقابلها من .env على جهاز المطوّر
os.environ.update(DATABASE_URL='sqlite:///' + db.replace('\\', '/'), MEDIA_ROOT=os.path.join(DATA, 'media'),
                  SECRET_KEY='audit-secret', DEBUG='False', SITE_URL=f'http://127.0.0.1:{PORT}', ALLOWED_HOSTS='*',
                  PYTHONUTF8='1', DJANGO_SETTINGS_MODULE='core.settings')
for k in ('CLOUD_DATABASE_URL', 'EMAIL_HOST', 'MS_TENANT_ID', 'MS_CLIENT_ID', 'MS_CLIENT_SECRET', 'MS_SENDER_EMAIL'):
    os.environ.pop(k, None)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import django  # noqa: E402
django.setup()
from django.conf import settings  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.core.management import call_command  # noqa: E402

settings.EMAIL_ENABLED = False
call_command('migrate', verbosity=0)
call_command('seed_demo', verbosity=0)
call_command('simulate_cycle', verbosity=0)
PASSWORD = 'Audit-Pass-2026'
admin = User.objects.create_superuser('admin@audit.test', 'admin@audit.test', PASSWORD, first_name='مدير التجربة')
from award.models import Submission  # noqa: E402
sub = Submission.objects.select_related('owner').order_by('pk').first()
school = sub.owner if sub else None
judge = next((u for u in User.objects.exclude(pk=admin.pk)
              if getattr(getattr(u, 'profile', None), 'role', '') == 'judge'), None)
for u in (school, judge):
    if u:
        u.set_password(PASSWORD)
        u.save()
from award import models as M  # noqa: E402


def first(name):
    model = getattr(M, name, None)
    obj = model.objects.order_by('pk').first() if model else None
    return obj.pk if obj else 0


print(json.dumps({'admin': admin.email, 'school': school.email if school else None, 'judge': judge.email if judge else None,
                  'password': PASSWORD, 'sub': sub.pk if sub else 0, 'news': first('News'), 'track': first('Track'),
                  'cycle': first('AwardCycle'), 'committee': first('JudgingCommittee') or first('Committee'), 'announcement': first('Announcement')}), flush=True)
call_command('runserver', f'127.0.0.1:{PORT}', '--noreload', '--insecure', verbosity=0)
