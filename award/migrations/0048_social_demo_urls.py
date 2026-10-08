"""روابط تجريبية (وهمية) حتى يظهر شريط التواصل — استبدلها بالحسابات الحقيقية من لوحة التحكم"""
from django.db import migrations

DEMO = {
    'facebook': 'https://www.facebook.com/iajaward', 'x': 'https://x.com/iajaward',
    'instagram': 'https://www.instagram.com/iajaward', 'youtube': 'https://www.youtube.com/@iajaward',
    'linkedin': 'https://www.linkedin.com/company/iajaward', 'snapchat': 'https://www.snapchat.com/add/iajaward',
}


def forwards(apps, schema_editor):
    SocialLink = apps.get_model('award', 'SocialLink')
    for s in SocialLink.objects.filter(url=''):
        if s.platform in DEMO:
            s.url = DEMO[s.platform]
            s.save(update_fields=['url'])


class Migration(migrations.Migration):
    dependencies = [('award', '0047_seed_social')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
