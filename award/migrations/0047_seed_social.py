from django.db import migrations


def forwards(apps, schema_editor):
    SocialLink = apps.get_model('award', 'SocialLink')
    if not SocialLink.objects.exists():
        for i, p in enumerate(['facebook', 'x', 'instagram', 'youtube', 'linkedin', 'snapchat']):
            SocialLink.objects.create(platform=p, order=i, is_active=True, url='')


class Migration(migrations.Migration):
    dependencies = [('award', '0046_cycle_card_social_portal')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
