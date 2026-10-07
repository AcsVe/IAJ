from django.db import migrations

ICONS = ['fa-hand-holding-heart', 'fa-lightbulb', 'fa-recycle', 'fa-chart-line']


def copy_principles(apps, schema_editor):
    """نقل المبادئ الأربعة الحالية من «نصوص الصفحة الرئيسية» إلى بطاقات المبادئ الجديدة"""
    Principle = apps.get_model('award', 'Principle')
    HomeContent = apps.get_model('award', 'HomeContent')
    if Principle.objects.exists():
        return
    hc = HomeContent.objects.first()
    defaults = ['العطاء', 'الريادة والابتكار', 'الاستدامة', 'الأثر والتأثر']
    for i in range(4):
        title = (getattr(hc, f'principle_{i + 1}', '') if hc else '') or defaults[i]
        Principle.objects.create(title=title, icon=ICONS[i], order=i + 1)


class Migration(migrations.Migration):
    dependencies = [('award', '0030_principle')]
    operations = [migrations.RunPython(copy_principles, migrations.RunPython.noop)]
