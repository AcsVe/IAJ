"""
فتح «الدورة الأولى» للجائزة (1448هـ / 2026م):
يعدّل الدورة التي أُنشئت تلقائياً (أو ينشئها) ويجعلها الدورة الحالية والتسجيل مفتوحاً من اليوم.
موعد الإغلاق: يبقى الموعد الحالي إن كان في المستقبل، وإلا 31/12/2026 — عدّله من لوحة التحكم.
"""
import datetime

from django.db import migrations
from django.utils import timezone

AMMAN = datetime.timezone(datetime.timedelta(hours=3))


def forwards(apps, schema_editor):
    C = apps.get_model('award', 'AwardCycle')
    now = timezone.now()
    c = C.objects.filter(is_current=True).first() or C.objects.order_by('id').first()
    default_close = datetime.datetime(2026, 12, 31, 23, 59, tzinfo=AMMAN)
    if c is None:
        c = C(opens_at=now, closes_at=default_close)
    c.name = 'الدورة الأولى'
    c.short_name = 'الدورة الأولى'
    c.year = 2026
    c.hijri_year = '1448'
    c.is_current = True
    c.results_published = False
    if not c.opens_at or c.opens_at > now:
        c.opens_at = now
    if not c.closes_at or c.closes_at <= now:
        c.closes_at = default_close
    c.save()
    C.objects.exclude(pk=c.pk).update(is_current=False)


class Migration(migrations.Migration):
    dependencies = [('award', '0050_cycles_media_data')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
