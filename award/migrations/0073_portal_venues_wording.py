from django.db import migrations

# صياغة تسويقية لميزة قواعد الحجز في بطاقة حجز القاعات (لا تُكتب فوق نص عُدّل من لوحة التحكم)
URL = 'https://2.iajaward.org'
OLD = {'why_points_ar': 'قواعد تمنع التعارض وتكرار الحجز للشعبة في اليوم نفسه.',
       'why_points_en': 'Rules that prevent clashes and repeated bookings for a section on the same day.'}
NEW = {'why_points_ar': 'قواعد حجز ذكية تمنع التعارض وتوزّع الأجهزة بعدالة على الصفوف.',
       'why_points_en': 'Smart booking rules prevent clashes and share the devices fairly across classes.'}


def reword(apps, schema_editor, src=OLD, dst=NEW):
    System = apps.get_model('award', 'WorkPortalSystem')
    for s in System.objects.all():
        if (s.url or '').rstrip('/') != URL:
            continue
        changed = False
        for k in src:
            text = getattr(s, k) or ''
            if src[k] in text:
                setattr(s, k, text.replace(src[k], dst[k]))
                changed = True
        if changed:
            s.save()


def back(apps, schema_editor):
    reword(apps, schema_editor, NEW, OLD)


class Migration(migrations.Migration):

    dependencies = [
        ("award", "0072_portal_why"),
    ]

    operations = [
        migrations.RunPython(reword, back),
    ]
