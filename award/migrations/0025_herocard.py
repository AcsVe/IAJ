from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('award', '0024_add_slideshowcard_image_url'),
    ]

    operations = [
        migrations.CreateModel(
            name='HeroCard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_enabled', models.BooleanField(default=False, verbose_name='إظهار البطاقة الشفافة في الهيرو؟')),
                ('heading', models.CharField(blank=True, default='', max_length=300, verbose_name='عنوان البطاقة')),
                ('body_text', models.TextField(blank=True, default='', verbose_name='نص البطاقة')),
                ('card_bg_color', models.CharField(default='#0a1632', max_length=7, verbose_name='لون خلفية البطاقة')),
                ('card_opacity', models.DecimalField(default=0.55, decimal_places=2, max_digits=3, verbose_name='شفافية البطاقة (0=شفاف 1=معتم)')),
                ('font_color', models.CharField(default='#ffffff', max_length=7, verbose_name='لون النص')),
                ('font_size', models.CharField(default='1.1rem', max_length=6, verbose_name='حجم الخط')),
                ('font_weight', models.CharField(default='600', max_length=3, verbose_name='وزن الخط (300/400/600/700/900)')),
                ('border_radius', models.CharField(default='0px', max_length=6, verbose_name='استدارة الزوايا')),
            ],
            options={
                'verbose_name': 'البطاقة الشفافة في الهيرو',
                'verbose_name_plural': 'البطاقة الشفافة في الهيرو',
            },
        ),
    ]