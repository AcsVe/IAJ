from django.db import migrations, models


def enable_card(apps, schema_editor):
    """كانت بطاقة النصوص مخفية افتراضياً، فلا تظهر النصوص المضافة. نُظهرها إن وُجدت نصوص."""
    HeroCard = apps.get_model('award', 'HeroCard')
    HeroTextSlide = apps.get_model('award', 'HeroTextSlide')
    has_texts = HeroTextSlide.objects.filter(is_active=True).exists()
    card = HeroCard.objects.first()
    if card is None:
        if has_texts:
            HeroCard.objects.create(is_enabled=True)
    elif has_texts or card.heading or card.body_text:
        card.is_enabled = True
        card.save(update_fields=['is_enabled'])


class Migration(migrations.Migration):
    dependencies = [('award', '0054_results_date')]
    operations = [
        migrations.AddField('herotextslide', 'effect', models.CharField(blank=True, default='', max_length=10, verbose_name='حركة ظهور هذا النص',
            choices=[('', 'نفس حركة البطاقة (الافتراضي)'), ('fade', 'تلاشي ناعم'), ('slide', 'انزلاق جانبي'), ('up', 'صعود من الأسفل'), ('down', 'نزول من الأعلى'), ('zoom', 'تكبير'), ('blur', 'ضبابية ثم وضوح'), ('flip', 'قلب'), ('none', 'بدون حركة')])),
        migrations.AddField('herotextslide', 'effect_speed', models.FloatField(choices=[(0.35, 'سريعة'), (0.6, 'متوسطة'), (1.0, 'بطيئة'), (1.6, 'بطيئة جداً')], default=0.6, verbose_name='سرعة الحركة')),
        migrations.AddField('herotextslide', 'seconds', models.PositiveSmallIntegerField(default=0, help_text='0 = تلقائي حسب طول النص (من إعدادات البطاقة).', verbose_name='مدة بقاء النص (ثوانٍ)')),
        migrations.AlterField('herocard', 'is_enabled', models.BooleanField(default=True, verbose_name='إظهار بطاقة النصوص تحت الفيديو؟')),
        migrations.AlterField('herocard', 'text_effect', models.CharField(choices=[('fade', 'تلاشي ناعم'), ('slide', 'انزلاق جانبي'), ('up', 'صعود من الأسفل'), ('down', 'نزول من الأعلى'), ('zoom', 'تكبير'), ('blur', 'ضبابية ثم وضوح'), ('flip', 'قلب'), ('none', 'بدون حركة')], default='fade', help_text='لكل نص حركته الخاصة من «النصوص المتبدّلة»؛ هذه تُستخدم للنص الأول وللنصوص التي لم تُحدَّد لها حركة.', max_length=10, verbose_name='الحركة الافتراضية بين النصوص')),
        migrations.RunPython(enable_card, migrations.RunPython.noop),
    ]
