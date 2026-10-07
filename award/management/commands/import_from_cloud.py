"""
نقل كل البيانات من القاعدة السحابية (Neon) إلى قاعدة PostgreSQL على الجهاز.

    python manage.py import_from_cloud --yes

يحتاج في ملف .env:
    DATABASE_URL=postgresql://postgres:PASS@localhost:5432/iaj        ← الهدف (الجهاز)
    CLOUD_DATABASE_URL=postgresql://...neon.tech/neondb?sslmode=require ← المصدر (Neon)

• يقرأ فقط من Neon (إلا إذا كانت جداولها قديمة: يضيف الأعمدة الناقصة فقط، بدون حذف أي بيانات).
• يمسح القاعدة المحلية أولاً ثم ينسخ كل شيء: الإعدادات، الأخبار، الطلبات، المستخدمين، الصور المخزّنة.
• بعده شغّل:  python manage.py localize_media   لتنزيل الصور والفيديو إلى مجلد media
"""
import os
import tempfile

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.migrations.executor import MigrationExecutor

EXCLUDE = ['contenttypes', 'auth.permission', 'admin.logentry', 'sessions']


def _same_db(a, b):
    keys = ('HOST', 'PORT', 'NAME')
    return all(str(a.get(k) or '') == str(b.get(k) or '') for k in keys)


class Command(BaseCommand):
    help = 'نسخ كل البيانات من Neon إلى قاعدة الجهاز'

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='تأكيد مسح القاعدة المحلية قبل النسخ')

    def handle(self, *args, **opts):
        if 'cloud' not in connections.databases:
            raise CommandError('ضع رابط Neon في ملف .env باسم CLOUD_DATABASE_URL')
        local, cloud = connections['default'], connections['cloud']
        if _same_db(local.settings_dict, cloud.settings_dict):
            raise CommandError('DATABASE_URL و CLOUD_DATABASE_URL يشيران لنفس القاعدة — توقّف للحماية')
        if not opts['yes']:
            raise CommandError('سيتم مسح القاعدة المحلية قبل النسخ — أعد التشغيل مع --yes للتأكيد')

        self.stdout.write('1/5 فحص الاتصال بـ Neon...')
        with cloud.cursor() as c:
            c.execute('SELECT 1')

        executor = MigrationExecutor(cloud)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            self.stdout.write(f'    جداول Neon قديمة ({len(plan)} تحديث) — إضافة الأعمدة الناقصة فقط...')
            call_command('migrate', database='cloud', interactive=False, verbosity=0)

        self.stdout.write('2/5 تجهيز القاعدة المحلية...')
        call_command('migrate', database='default', interactive=False, verbosity=0)
        call_command('flush', database='default', interactive=False, verbosity=0)
        self._match_column_sizes(local, cloud)

        fd, tmp = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        try:
            self.stdout.write('3/5 تنزيل البيانات من Neon (قد يأخذ دقيقة)...')
            call_command('dumpdata', database='cloud', exclude=EXCLUDE, natural_foreign=True,
                         natural_primary=True, output=tmp, verbosity=0)
            self.stdout.write(f'    الحجم: {os.path.getsize(tmp) / 1024 / 1024:.1f} MB')

            self.stdout.write('4/5 حفظ البيانات على الجهاز...')
            call_command('loaddata', tmp, database='default', verbosity=0)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass

        self.stdout.write('5/5 فحص النتيجة...')
        self._report_long_values()
        from django.apps import apps
        total = 0
        for model in apps.get_app_config('award').get_models():
            a = model.objects.using('cloud').count()
            b = model.objects.using('default').count()
            total += b
            if a != b:
                self.stdout.write(self.style.WARNING(f'    {model.__name__}: Neon={a} الجهاز={b}'))
        self.stdout.write(self.style.SUCCESS(f'✓ تم نقل البيانات ({total} سجل). الخطوة التالية: localize_media'))

    # ---------- أعمدة نصية أطول في Neon (عُدّلت هناك سابقاً) ----------
    def _match_column_sizes(self, local, cloud):
        if local.vendor != 'postgresql' or cloud.vendor != 'postgresql':
            return
        sql = """SELECT table_name, column_name, data_type, character_maximum_length
                 FROM information_schema.columns
                 WHERE table_schema = current_schema() AND data_type IN ('character varying', 'text')"""
        with cloud.cursor() as c:
            c.execute(sql)
            cloud_cols = {(t, col): (dt, n) for t, col, dt, n in c.fetchall()}
        with local.cursor() as c:
            c.execute(sql)
            local_cols = c.fetchall()
            for t, col, dt, n in local_cols:
                if dt != 'character varying' or (t, col) not in cloud_cols:
                    continue
                cdt, cn = cloud_cols[(t, col)]
                if cdt == 'text' or (cn or 0) > (n or 0):
                    new = 'text' if cdt == 'text' else f'varchar({cn})'
                    c.execute(f'ALTER TABLE "{t}" ALTER COLUMN "{col}" TYPE {new}')
                    self.stdout.write(f'    توسيع {t}.{col}: varchar({n}) ← {new}')

    def _report_long_values(self):
        """تنبيه إذا وُجد نص أطول من المسموح في لوحة التحكم (حتى لا يتفاجأ المستخدم عند الحفظ)"""
        from django.apps import apps
        from django.db import models as m
        for model in apps.get_app_config('award').get_models():
            for f in model._meta.concrete_fields:
                if isinstance(f, m.CharField) and f.max_length:
                    for pk, val in model.objects.values_list('pk', f.attname):
                        if val and len(val) > f.max_length:
                            self.stdout.write(self.style.WARNING(
                                f'    تنبيه: {model.__name__}#{pk}.{f.name} طوله {len(val)} (المسموح {f.max_length})'))
