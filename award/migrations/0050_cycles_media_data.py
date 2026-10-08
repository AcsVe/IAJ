"""الفائزون القدامى لا نعرف دورتهم — نتركهم «عام» حتى تُحدَّد من لوحة التحكم (فلتر السنة ما زال يعمل)"""
from django.db import migrations


def forwards(apps, schema_editor):
    Winner = apps.get_model('award', 'Winner')
    Winner.objects.update(cycle=None)
    C = apps.get_model('award', 'AwardCycle')
    for c in C.objects.filter(short_name=''):
        import re
        c.short_name = c.name
        c.save(update_fields=['short_name'])


class Migration(migrations.Migration):
    dependencies = [('award', '0049_cycles_media')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
