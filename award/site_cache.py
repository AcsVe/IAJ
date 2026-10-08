"""
تسريع: الإعدادات العامة (الشعار، الألوان، النصوص، الشريط...) تُقرأ من قاعدة البيانات
مرة كل دقيقة بدل كل صفحة. أي حفظ من لوحة التحكم يمسح النسخة المحفوظة فوراً.
"""
from django.core.cache import cache

KEY = 'iaj:site-bundle:v1'
TTL = 60  # ثانية


def _first(model):
    try:
        return model.objects.first()
    except Exception:
        return None


def get_site_bundle():
    data = cache.get(KEY)
    if data is not None:
        return data
    from .models import (
        SiteSetting, ThemeSetting, HomeContent, FooterContent, SectionBackground,
        TickerItem, TickerSetting, HeroCard, HeroTextSlide,
    )
    try:
        section_bgs = {sb.section_id: sb for sb in SectionBackground.objects.all()}
    except Exception:
        section_bgs = {}
    try:
        ticker_items = list(TickerItem.objects.filter(is_active=True))
    except Exception:
        ticker_items = []
    hero_card = _first(HeroCard) or HeroCard()   # بدون سجل ← إعدادات افتراضية (البطاقة ظاهرة)
    default_fx = hero_card.text_effect or 'fade'
    hero_text_items = []
    if hero_card.heading or hero_card.body_text:
        hero_text_items.append({'heading': hero_card.heading, 'body': hero_card.body_text,
                                'fx': default_fx, 'speed': 0.6, 'seconds': 0})
    try:
        hero_text_items += [{'heading': t.heading, 'body': t.body_text, 'fx': t.effect or default_fx,
                             'speed': t.effect_speed or 0.6, 'seconds': t.seconds or 0}
                            for t in HeroTextSlide.objects.filter(is_active=True) if t.heading or t.body_text]
    except Exception:
        pass
    data = {
        'hero_text_items': hero_text_items,
        'settings': _first(SiteSetting),
        'theme': _first(ThemeSetting),
        'content': _first(HomeContent),
        'footer': _first(FooterContent),
        'hero_card': hero_card,
        'section_bgs': section_bgs,
        'global_ticker_items': ticker_items,
        'global_ticker_settings': _first(TickerSetting),
    }
    cache.set(KEY, data, TTL)
    return data


def clear_site_bundle(*args, **kwargs):
    cache.delete(KEY)


CACHED_MODELS = ('SiteSetting', 'ThemeSetting', 'HomeContent', 'FooterContent',
                 'SectionBackground', 'TickerItem', 'TickerSetting', 'HeroCard', 'HeroTextSlide')


HOME_KEY = 'iaj:home-bundle:v1'
HOME_MODELS = ('Field', 'Track', 'TimelineEvent', 'Judge', 'Sponsor', 'News', 'Submission', 'Principle',
               'HeroSlide', 'SiteSetting', 'TrackDetail', 'AwardCycle', 'Announcement', 'AnnouncementMedia')


def hero_slides():
    """شرائح بطاقة الفيديو/الصور. بدون شرائح ← الصورة/الفيديو المفرد من إعدادات الموقع (كما كان)"""
    from .models import HeroSlide, SiteSetting, youtube_id
    out = []
    for sl in HeroSlide.objects.filter(is_active=True):
        kind = sl.kind
        if not kind:
            continue
        item = {'kind': kind, 'title': sl.title, 'caption': sl.caption, 'show_caption': sl.show_caption,
                'poster': sl.poster.url if sl.poster else '',
                'click': sl.click_action if kind == 'image' else '', 'link': (sl.link_url or '').strip()}
        if item['click'] == 'link' and not item['link']:
            item['click'] = 'zoom'
        if kind == 'youtube':
            item['yt'] = sl.youtube_id
        else:
            item['src'] = sl.media_file.url
        out.append(item)
    if out:
        return out
    st = SiteSetting.objects.first()
    if not st:
        return out
    poster = st.hero_side_image.url if st.hero_side_image else ''
    if st.hero_side_video:
        out.append({'kind': 'video', 'src': st.hero_side_video.url, 'poster': poster, 'title': ''})
    elif youtube_id(st.hero_side_video_url):
        out.append({'kind': 'youtube', 'yt': youtube_id(st.hero_side_video_url), 'poster': poster, 'title': ''})
    elif poster:
        out.append({'kind': 'image', 'src': poster, 'poster': '', 'title': '', 'click': 'zoom', 'link': ''})
    return out


def ensure_principles():
    """إذا كانت بطاقات المبادئ فارغة تماماً (مثلاً بعد نقل البيانات) تُنشأ الأربعة الأساسية"""
    from .models import Principle, HomeContent
    if Principle.objects.exists():
        return
    icons = ['fa-hand-holding-heart', 'fa-lightbulb', 'fa-recycle', 'fa-chart-line']
    defaults = ['العطاء', 'الريادة والابتكار', 'الاستدامة', 'الأثر والتأثر']
    hc = HomeContent.objects.first()
    for i in range(4):
        title = (getattr(hc, f'principle_{i + 1}', '') if hc else '') or defaults[i]
        Principle.objects.create(title=title, icon=icons[i], order=i + 1)


def _current_timeline(TimelineEvent):
    """الجدول الزمني للدورة الحالية (+ الخطوات العامة بدون دورة)"""
    from django.db.models import Q
    from .models import AwardCycle
    cur = AwardCycle.objects.filter(is_current=True).values_list('pk', flat=True).first()
    qs = TimelineEvent.objects.all()
    if cur:
        qs = qs.filter(Q(cycle_id=cur) | Q(cycle__isnull=True))
    return list(qs)


def _home_announcements():
    from .models import Announcement
    return list(Announcement.objects.filter(is_published=True, show_on_home=True).prefetch_related('media')[:6])


def get_home_bundle():
    data = cache.get(HOME_KEY)
    if data is not None:
        return data
    from .models import Field, TimelineEvent, Judge, Sponsor, News, Submission, Principle
    try:
        ensure_principles()
    except Exception:
        pass
    from django.db.models import Prefetch
    from .models import Track
    fields = list(Field.objects.prefetch_related(
        Prefetch('track_set', queryset=Track.objects.filter(is_active=True).prefetch_related('details'))))
    for f in fields:
        f.tracks_cached = list(f.track_set.all())
    data = {
        'fields': fields,
        'timeline': _current_timeline(TimelineEvent),
        'principles': list(Principle.objects.filter(is_active=True)),
        'hero_slides': hero_slides(),
        'judges': list(Judge.objects.all()),
        'sponsors': list(Sponsor.objects.all()),
        'latest_news': list(News.objects.filter(is_published=True)[:3]),
        'announcements': _home_announcements(),
        'total_submissions': Submission.objects.count(),
        'accepted_submissions': Submission.objects.filter(status='accepted').count(),
    }
    cache.set(HOME_KEY, data, TTL)
    return data


def clear_home_bundle(*args, **kwargs):
    cache.delete(HOME_KEY)
