"""
بيانات تجريبية للتشغيل المحلي (صور + شريط أخبار + محتوى) — لا تستخدمها على السيرفر.
    python manage.py seed_demo
"""
import datetime
import io

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from award.models import (
    Field, FooterContent, HeroCard, HomeContent, Judge, News, Photo,
    SectionBackground, SiteSetting, Sponsor, TickerItem, TickerSetting,
    TimelineEvent, Track,
)


def make_image(w, h, c1, c2, label=''):
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (w, h), c1)
    d = ImageDraw.Draw(img)
    for i in range(h):  # تدرّج لوني
        t = i / h
        d.line([(0, i), (w, i)], fill=tuple(int(c1[k] * (1 - t) + c2[k] * t) for k in range(3)))
    d.ellipse([w * 0.35, h * 0.25, w * 0.65, h * 0.25 + w * 0.3], outline=(197, 160, 89), width=max(4, w // 150))
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=85)
    return ContentFile(buf.getvalue(), name=(label or 'demo') + '.jpg')


class Command(BaseCommand):
    help = 'تعبئة قاعدة البيانات المحلية ببيانات تجريبية'

    def handle(self, *args, **opts):
        s = SiteSetting.objects.first() or SiteSetting()
        if not s.site_logo:
            s.site_logo.save('logo.jpg', make_image(300, 300, (197, 160, 89), (120, 90, 40), 'logo'), save=False)
        if not s.hero_side_image:
            s.hero_side_image.save('side.jpg', make_image(1200, 1600, (30, 70, 120), (10, 22, 50), 'side'), save=False)
        s.registration_deadline = s.registration_deadline or datetime.datetime(2026, 12, 31, tzinfo=datetime.timezone.utc)
        s.save()

        bg, _ = SectionBackground.objects.get_or_create(section_id='home')
        if not bg.bg_image:
            bg.bg_image.save('hero.jpg', make_image(2400, 1400, (110, 60, 35), (30, 15, 10), 'hero'), save=False)
            bg.enable_overlay, bg.overlay_opacity = True, 0.25
            bg.save()

        HomeContent.objects.first() or HomeContent.objects.create()
        FooterContent.objects.first() or FooterContent.objects.create()

        hc = HeroCard.objects.first() or HeroCard()
        hc.is_enabled, hc.border_radius = True, '12px'
        hc.heading = hc.heading or 'جائزة تكرّم العطاء'
        hc.body_text = hc.body_text or 'بطاقة تجريبية — غيّر نصها من لوحة التحكم: البطاقة الشفافة في الهيرو.'
        hc.save()

        ts = TickerSetting.objects.first() or TickerSetting()
        ts.is_enabled, ts.scroll_speed = True, 50
        ts.save()
        if not TickerItem.objects.exists():
            for i, t in enumerate(['باب الترشح مفتوح حتى نهاية العام', 'تابعوا آخر الأخبار والتحديثات', 'حفل توزيع الجوائز قريباً']):
                TickerItem.objects.create(message_html=t, order=i)

        if not Field.objects.exists():
            f = Field.objects.create(name_ar='المجال الثقافي', name_en='Culture')
            Track.objects.create(field=f, name_ar='المسار الأول', name_en='Track 1')
            Field.objects.create(name_ar='المجال التعليمي', name_en='Education')
        if not TimelineEvent.objects.exists():
            for i, t in enumerate(['الإعلان', 'التسجيل', 'التحكيم', 'الحفل']):
                TimelineEvent.objects.create(title=t, date_text=f'{i + 1} سبتمبر', order=i, icon='fa-bullhorn')
        if not Judge.objects.exists():
            for i in range(3):
                j = Judge(name=f'عضو {i + 1}', title='عضو لجنة', order=i)
                j.image.save('judge.jpg', make_image(300, 300, (90, 90, 90), (40, 40, 40), 'judge'), save=False)
                j.save()
        if not News.objects.exists():
            n = News(title='خبر تجريبي', content='<p>محتوى الخبر التجريبي.</p>', date=datetime.date.today())
            n.image.save('news.jpg', make_image(800, 500, (20, 110, 90), (10, 40, 30), 'news'), save=False)
            n.save()
        if not Photo.objects.exists():
            p = Photo(title='صورة تجريبية')
            p.image.save('photo.jpg', make_image(800, 600, (140, 40, 60), (40, 10, 20), 'photo'), save=False)
            p.save()
        if not Sponsor.objects.exists():
            sp = Sponsor(name='شريك تجريبي')
            sp.logo.save('sponsor.jpg', make_image(400, 200, (240, 240, 240), (200, 200, 200), 'sponsor'), save=False)
            sp.save()

        self.stdout.write(self.style.SUCCESS('تمت إضافة البيانات التجريبية.'))
