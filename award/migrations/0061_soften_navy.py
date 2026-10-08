from django.db import migrations


def _rgb(h):
    h = (h or '').lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _is_navy(h):
    c = _rgb(h)
    return bool(c) and c[2] > c[0] + 25 and c[0] < 70 and c[1] < 80


def _shade(h, amount):
    c = _rgb(h)
    if not c:
        return h
    return '#%02x%02x%02x' % tuple(int(x * (1 + amount)) for x in c)


def soften(apps, schema_editor):
    """طلب المستخدم: استبدال الكحلي بدرجات من لون الهيدر (يتماشى مع ألوان التصميم)"""
    Theme = apps.get_model('award', 'ThemeSetting')
    Ticker = apps.get_model('award', 'TickerSetting')
    theme = Theme.objects.first()
    primary = (theme.primary_color if theme else '') or '#6c6e60'
    if _is_navy(primary):
        return   # الموقع ما زال بالكحلي الأصلي — لا نغيّر شيئاً
    if theme and _is_navy(theme.secondary_color):
        theme.secondary_color = _shade(primary, -0.30)
        theme.save(update_fields=['secondary_color'])
    for t in Ticker.objects.all():
        if _is_navy(t.bg_color):
            t.bg_color = _shade(primary, -0.50)
            t.save(update_fields=['bg_color'])


class Migration(migrations.Migration):
    dependencies = [('award', '0060_numeric_speeds')]
    operations = [migrations.RunPython(soften, migrations.RunPython.noop)]
