"""
تجهيز البيانات لنظام التسجيل الجديد:
  • تحويل حالات الطلبات القديمة (قيد المراجعة → مُرسل، تمت المراجعة → قيد التدقيق)
  • أرقام طلبات للطلبات القديمة
  • إنشاء «الدورة الأولى» تلقائياً (موعد الإغلاق = موعد العداد الحالي) حتى يبقى التسجيل مفتوحاً
  • معايير تحكيم مبدئية قابلة للتعديل
"""
import datetime

from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    Submission = apps.get_model('award', 'Submission')
    AwardCycle = apps.get_model('award', 'AwardCycle')
    SiteSetting = apps.get_model('award', 'SiteSetting')
    Criterion = apps.get_model('award', 'Criterion')

    cycle = AwardCycle.objects.filter(is_current=True).first()
    if cycle is None and not AwardCycle.objects.exists():
        st = SiteSetting.objects.first()
        now = timezone.now()
        closes = st.registration_deadline if st and st.registration_deadline else None
        if not closes or closes < now:
            closes = datetime.datetime(now.year if now.month < 12 else now.year + 1, 12, 31, 23, 59, tzinfo=datetime.timezone.utc)
        first = Submission.objects.order_by('submitted_at').values_list('submitted_at', flat=True).first()
        opens = min(first, now) if first else now
        cycle = AwardCycle.objects.create(name='الدورة الأولى', year=closes.year, opens_at=opens,
                                          closes_at=closes, is_current=True)

    mapping = {'pending': 'submitted', 'reviewed': 'screening'}
    for sub in Submission.objects.all():
        changed = []
        if sub.status in mapping:
            sub.status = mapping[sub.status]
            changed.append('status')
        if not sub.sent_at and sub.status != 'draft':
            sub.sent_at = sub.submitted_at
            changed.append('sent_at')
        if not sub.cycle_id and cycle:
            sub.cycle_id = cycle.pk
            changed.append('cycle')
        if not sub.ref:
            year = cycle.year if cycle else sub.submitted_at.year
            sub.ref = f'IAJ-{year}-{sub.pk:04d}'
            changed.append('ref')
        if changed:
            sub.save(update_fields=changed)

    if not Criterion.objects.exists():
        for i, (name, desc) in enumerate([
            ('الأصالة والابتكار', 'جِدّة الفكرة وتميّزها عن الحلول الموجودة.'),
            ('المنهجية العلمية', 'وضوح المشكلة والأهداف، وسلامة الأدوات والخطوات.'),
            ('الأثر وقابلية التطبيق', 'الفائدة المتوقعة على المدرسة والمجتمع وإمكانية التنفيذ والاستدامة.'),
            ('جودة التوثيق والعرض', 'تنظيم البحث، اللغة، المراجع، ووضوح النتائج.'),
            ('دور الطلبة', 'مدى مشاركة الطلبة الفعلية في التخطيط والتنفيذ.'),
        ]):
            Criterion.objects.create(name=name, description=desc, max_score=20, weight=1, order=i)


class Migration(migrations.Migration):
    dependencies = [('award', '0042_registration_portal')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
