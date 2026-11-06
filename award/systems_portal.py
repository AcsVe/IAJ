"""بوابة أنظمة العمل — الصفحة الرئيسية للموقع (/): بطاقة لكل نظام، ونافذة تعرّف به وتوصل إليه.

- البطاقات ونصوص الصفحة من لوحة الإدارة: «أنظمة البوابة» (WorkPortalSystem) و«إعدادات الصفحة الرئيسية»
  (WorkPortalSetting). الأنظمة الثمانية الأولى أُضيفت بالترحيل 0071.

- اللغة تُختار بـ ?lang=ar|en وتُحفظ في ملف تعريف ارتباط، فيأتي الاتجاه (RTL/LTR) من الخادم مباشرة.
- الشريط الإخباري هو شريط نظام القاعات نفسه (محتواه وإعداداته من لوحة تحكم القاعات): يقرؤه الخادم من
  ‎/api/ticker‎ في نظام القاعات على الجهاز نفسه (أو من عنوانه العام احتياطاً)، وينقّي نصوصه، ويحتفظ به دقيقة.
"""
import re
import time
from urllib.parse import urlparse
from html import escape
from html.parser import HTMLParser

import requests
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

LANG_COOKIE = 'portal_lang'

TEXT = {
    'ar': {
        'switch': 'English', 'switch_lang': 'en',
        'details': 'التفاصيل',
        'about': 'عن النظام',
        'how': 'آلية العمل',
        'open': 'الدخول إلى النظام',
        'close': 'إغلاق',
        'award': 'موقع الجائزة',
    },
    'en': {
        'switch': 'العربية', 'switch_lang': 'ar',
        'details': 'Details',
        'about': 'About',
        'how': 'How it works',
        'open': 'Open the system',
        'close': 'Close',
        'award': 'Award website',
    },
}


def _lang(request):
    lang = request.GET.get('lang') or request.COOKIES.get(LANG_COOKIE) or 'ar'
    return lang if lang in TEXT else 'ar'


def portal_setting():
    from .models import WorkPortalSetting
    return WorkPortalSetting.objects.first() or WorkPortalSetting()


def systems_portal(request):
    from .models import WorkPortalSystem
    lang = _lang(request)
    st = portal_setting()
    en = lang == 'en'
    systems = [{
        'key': f's{x.pk}', 'url': x.url, 'host': urlparse(x.url).netloc or x.url, 'icon': x.icon, 'color': x.color if _COLOR.match(x.color or '') else '#60a5fa',
        'name': x.name_en if en else x.name_ar, 'tagline': x.tagline_en if en else x.tagline_ar,
        'about': x.about_en if en else x.about_ar, 'steps': x.steps(lang),
    } for x in WorkPortalSystem.objects.filter(is_active=True)]
    t = dict(TEXT[lang], title=st.title_en if en else st.title_ar, subtitle=st.subtitle_en if en else st.subtitle_ar,
             hint=st.hint_en if en else st.hint_ar)
    resp = render(request, 'award/systems_portal.html', {
        'lang': lang, 'dir': 'ltr' if en else 'rtl', 't': t, 'systems': systems, 'portal': st,
    })
    if request.GET.get('lang') in TEXT:
        resp.set_cookie(LANG_COOKIE, lang, max_age=365 * 24 * 3600, samesite='Lax',
                        secure=not settings.DEBUG and request.is_secure())
    return resp


# ───────────────────────── الشريط الإخباري (من نظام القاعات) ─────────────────────────

_ALLOWED_TAGS = {'p', 'div', 'span', 'b', 'strong', 'i', 'em', 'u', 's', 'a', 'br', 'h1', 'h2', 'h3', 'h4',
                 'h5', 'h6', 'li', 'ul', 'ol', 'font', 'sub', 'sup', 'mark', 'small'}
_ALLOWED_CSS = re.compile(r'^\s*(color|background-color|font-weight|font-size|font-style|text-decoration)\s*:'
                          r'\s*[#\w\s.,%()-]+\s*$', re.I)
_COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')


class _Sanitizer(HTMLParser):
    """يبقي التنسيق (غامق، ألوان، أحجام، روابط) ويحذف كل ما سواه: لا نصوص برمجية ولا معالجات أحداث."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'iframe', 'object', 'embed', 'template'):
            self.skip += 1
            return
        if self.skip or tag not in _ALLOWED_TAGS:
            return
        kept = []
        for k, v in attrs:
            v = v or ''
            if k == 'href' and tag == 'a' and re.match(r'^https?://', v.strip(), re.I):
                kept.append(f' href="{escape(v.strip())}" target="_blank" rel="noopener"')
            elif k == 'style':
                css = ';'.join(d for d in v.split(';') if _ALLOWED_CSS.match(d) and 'url' not in d.lower())
                if css:
                    kept.append(f' style="{escape(css)}"')
            elif k == 'color' and tag == 'font' and _COLOR.match(v):
                kept.append(f' color="{v}"')
            elif k == 'dir' and v in ('rtl', 'ltr', 'auto'):
                kept.append(f' dir="{v}"')
        self.out.append(f'<{tag}{"".join(kept)}>' if tag != 'br' else '<br>')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'iframe', 'object', 'embed', 'template'):
            self.skip = max(0, self.skip - 1)
            return
        if not self.skip and tag in _ALLOWED_TAGS and tag != 'br':
            self.out.append(f'</{tag}>')

    def handle_data(self, data):
        if not self.skip:
            self.out.append(escape(data))


def clean_ticker_html(html):
    p = _Sanitizer()
    try:
        p.feed((html or '')[:20000])
        p.close()
    except Exception:
        return ''
    return ''.join(p.out)


def _num(v, default, lo, hi):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return default


def _clean_payload(d):
    """ما تحتاجه الصفحة فقط، بعد التنقية والتحقق من كل قيمة."""
    if not isinstance(d, dict) or not d.get('enabled'):
        return {'enabled': False}
    rss = []
    for it in (d.get('rssItems') or [])[:30]:
        if isinstance(it, dict) and it.get('title'):
            link = str(it.get('link') or '')
            rss.append({'title': str(it['title'])[:300], 'link': link if re.match(r'^https?://', link) else ''})
    return {
        'enabled': True,
        'html': clean_ticker_html(d.get('html')),
        'htmlEn': clean_ticker_html(d.get('htmlEn')),
        'rssItems': rss,
        'rssColor': d.get('rssColor') if _COLOR.match(str(d.get('rssColor') or '')) else '',
        'rssBold': bool(d.get('rssBold')),
        'rssFontSize': _num(d.get('rssFontSize'), 0, 0, 40),
        'speedSeconds': _num(d.get('speedSeconds'), 25, 3, 300),
        'pulse': bool(d.get('pulse')),
        'pulseSeconds': _num(d.get('pulseSeconds'), 1.6, 0.3, 10),
        'textShadow': d.get('textShadow') if d.get('textShadow') in ('none', 'light', 'strong') else 'light',
        'bgColor': d.get('bgColor') if _COLOR.match(str(d.get('bgColor') or '')) else '',
        'bgOpacity': _num(d.get('bgOpacity'), 0, 0, 100),
        'textColor': d.get('textColor') if _COLOR.match(str(d.get('textColor') or '')) else '',
    }


_cache = {'at': 0.0, 'data': None}
_CACHE_SECONDS = 60
_FAIL_SECONDS = 20


def _ticker_sources():
    custom = getattr(settings, 'VENUES_TICKER_URL', '') or ''
    if custom:
        return [custom]
    return ['http://127.0.0.1:8002/api/ticker', 'https://2.iajaward.org/api/ticker']


def fetch_venues_ticker():
    now = time.time()
    if _cache['data'] is not None and now - _cache['at'] < (
            _CACHE_SECONDS if _cache['data'].get('enabled') else _FAIL_SECONDS):
        return _cache['data']
    data = {'enabled': False}
    for url in _ticker_sources():
        try:
            r = requests.get(url, timeout=3, headers={'User-Agent': 'IAJ-Portal/1.0'})
            if r.status_code == 200:
                data = _clean_payload(r.json())
                break
        except Exception:
            continue
    _cache.update(at=now, data=data)
    return data


@never_cache
def systems_ticker(request):
    if not portal_setting().show_ticker:
        return JsonResponse({'enabled': False})
    return JsonResponse(fetch_venues_ticker())
