"""بوابة أنظمة العمل (/systems/): بطاقة لكل نظام من أنظمة المدرسة، ونافذة تعرّف به وتوصل إليه.

- اللغة تُختار بـ ?lang=ar|en وتُحفظ في ملف تعريف ارتباط، فيأتي الاتجاه (RTL/LTR) من الخادم مباشرة.
- الشريط الإخباري هو شريط نظام القاعات نفسه (محتواه وإعداداته من لوحة تحكم القاعات): يقرؤه الخادم من
  ‎/api/ticker‎ في نظام القاعات على الجهاز نفسه (أو من عنوانه العام احتياطاً)، وينقّي نصوصه، ويحتفظ به دقيقة.
"""
import re
import time
from html import escape
from html.parser import HTMLParser

import requests
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

LANG_COOKIE = 'portal_lang'

# ترتيب البطاقات كما طلبه المستخدم. النصوص بلا أي تفاصيل تقنية.
SYSTEMS = [
    {
        'key': 'support', 'url': 'https://1.iajaward.org', 'icon': 'fa-headset', 'color': '#38bdf8',
        'ar': {
            'name': 'تذاكر الدعم الفني',
            'tagline': 'طلبات الدعم الفني ومتابعتها حتى إنجازها',
            'about': 'يتيح للمعلمين والموظفين تقديم طلبات الدعم الفني والصيانة للأجهزة والبرامج والشبكة، '
                     'ومتابعة كل طلب خطوة بخطوة حتى إنجازه.',
            'steps': [
                'يقدّم الموظف طلبه ويصف المشكلة ويختار تصنيفها ودرجة أهميتها.',
                'يتسلّم فريق الدعم الطلب ويُسنده إلى المختص.',
                'تتغيّر حالة الطلب (مفتوح، قيد المعالجة، مغلق) ويصل إشعار بالبريد عند كل تحديث.',
                'يمكن الاستعلام عن أي طلب برقمه في أي وقت.',
            ],
        },
        'en': {
            'name': 'IT Support Tickets',
            'tagline': 'Technical support requests, tracked until resolved',
            'about': 'Teachers and staff submit requests for technical support and maintenance of devices, '
                     'software and the network, and follow every request step by step until it is resolved.',
            'steps': [
                'The staff member submits a request, describes the issue and selects its category and priority.',
                'The support team receives the request and assigns it to the right specialist.',
                'The request status changes (open, in progress, closed) and an e-mail is sent with every update.',
                'Any request can be looked up by its number at any time.',
            ],
        },
    },
    {
        'key': 'trolley', 'url': 'https://2.iajaward.org', 'icon': 'fa-laptop', 'color': '#a78bfa',
        'ar': {
            'name': 'Trolley Reservation',
            'tagline': 'حجز Trolley الأجهزة المحمولة للحصص الدراسية',
            'about': 'ينظّم حجز Trolley الأجهزة المحمولة لكل مرحلة دراسية وفق روزنامة واضحة تمنع التعارض، '
                     'ويتابع تسليم الأجهزة للطلبة في كل حصة.',
            'steps': [
                'يختار المعلم المرحلة والصف والشعبة والحصة من الروزنامة.',
                'يُراجَع الطلب ويُعتمد، ويصل إلى المعلم تأكيد بالبريد.',
                'يعبّئ المعلم نموذج تسليم الأجهزة للطلبة بعد الحصة.',
                'تعرض الروزنامة العامة الحجوزات والفترات غير المتاحة للجميع.',
            ],
        },
        'en': {
            'name': 'Trolley Reservation',
            'tagline': 'Reserving device trolleys for class periods',
            'about': 'Organizes the reservation of each stage\'s device trolley on a clear calendar that prevents '
                     'clashes, and keeps track of the devices handed to students in every period.',
            'steps': [
                'The teacher chooses the stage, grade, section and period on the calendar.',
                'The request is reviewed and approved, and the teacher receives an e-mail confirmation.',
                'After the period, the teacher completes the device handover form for the students.',
                'The public calendar shows every reservation and unavailable period to everyone.',
            ],
        },
    },
    {
        'key': 'attendance', 'url': 'https://3.iajaward.org', 'icon': 'fa-fingerprint', 'color': '#34d399',
        'ar': {
            'name': 'الحضور والانصراف',
            'tagline': 'رصد دوام الموظفين وتقاريره اليومية والشهرية',
            'about': 'يرصد حضور الموظفين وانصرافهم من أجهزة البصمة، ويحوّل الحركات إلى تقارير يومية وشهرية دقيقة '
                     'تراعي أوقات دوام كل قسم.',
            'steps': [
                'تُجمع حركات البصمة من الأجهزة تلقائياً.',
                'تُحتسب حالات الحضور في الوقت والتأخير والغياب وفق أوقات كل قسم.',
                'تُسجَّل الإجازات والمغادرات وأسباب الغياب.',
                'تُصدر التقارير وتُرسل بالبريد في مواعيد محددة.',
            ],
        },
        'en': {
            'name': 'Attendance',
            'tagline': 'Staff attendance with daily and monthly reports',
            'about': 'Records staff arrivals and departures from the fingerprint devices and turns them into accurate '
                     'daily and monthly reports that respect each department\'s working hours.',
            'steps': [
                'Fingerprint records are collected from the devices automatically.',
                'On-time arrival, lateness and absence are worked out from each department\'s hours.',
                'Leaves, early departures and absence reasons are recorded.',
                'Reports are produced and e-mailed on a set schedule.',
            ],
        },
    },
    {
        'key': 'timetable', 'url': 'https://4.iajaward.org', 'icon': 'fa-calendar-week', 'color': '#fbbf24',
        'ar': {
            'name': 'جدولة الحصص',
            'tagline': 'بناء الجدول المدرسي الأسبوعي دون تعارض',
            'about': 'يبني الجدول المدرسي الأسبوعي للصفوف والمعلمين والقاعات، مع مراعاة أنصبة المعلمين '
                     'والقيود والتفضيلات المعتمدة.',
            'steps': [
                'تُدخل المواد والأنصبة والمعلمون والقاعات.',
                'تُحدَّد القيود والتفضيلات لكل معلم وصف.',
                'يُبنى الجدول دون تعارض، ويمكن تعديله يدوياً بعد ذلك.',
                'يُنشر الجدول ويُطبع لكل صف ولكل معلم.',
            ],
        },
        'en': {
            'name': 'Class Scheduling',
            'tagline': 'Building the weekly school timetable without clashes',
            'about': 'Builds the weekly school timetable for classes, teachers and rooms, respecting teaching loads '
                     'and the agreed constraints and preferences.',
            'steps': [
                'Subjects, teaching loads, teachers and rooms are entered.',
                'Constraints and preferences are set for each teacher and class.',
                'The timetable is built without clashes and can then be adjusted by hand.',
                'The timetable is published and printed for every class and every teacher.',
            ],
        },
    },
    {
        'key': 'bell', 'url': 'https://5.iajaward.org', 'icon': 'fa-bell', 'color': '#fb7185',
        'ar': {
            'name': 'جرس الحصص',
            'tagline': 'إدارة مواعيد الجرس المدرسي من مكان واحد',
            'about': 'يدير مواعيد قرع الجرس المدرسي مركزياً وفق جدول الدوام، مع أنغام مختلفة للحصص والاستراحات '
                     'والمناسبات.',
            'steps': [
                'تُضبط أوقات الحصص والاستراحات لكل يوم من أيام الأسبوع.',
                'تُحدَّد العطل والأيام المستثناة مسبقاً.',
                'تقرع أجهزة الجرس في مواعيدها تلقائياً.',
                'يمكن قرع الجرس يدوياً عند الحاجة.',
            ],
        },
        'en': {
            'name': 'School Bell',
            'tagline': 'Managing the school bell schedule from one place',
            'about': 'Manages the school bell centrally according to the daily schedule, with different tones for '
                     'periods, breaks and special occasions.',
            'steps': [
                'Period and break times are set for each day of the week.',
                'Holidays and excluded days are set in advance.',
                'The bell devices ring automatically on time.',
                'The bell can also be rung manually when needed.',
            ],
        },
    },
    {
        'key': 'clearance', 'url': 'https://6.iajaward.org', 'icon': 'fa-file-signature', 'color': '#22d3ee',
        'ar': {
            'name': 'المخالصة',
            'tagline': 'إجراءات براءة الذمة ومتابعة العهد',
            'about': 'ينظّم إجراءات براءة الذمة للموظفين عند انتهاء الخدمة أو الانتقال، ويتابع العهد المسلَّمة '
                     'لكل موظف.',
            'steps': [
                'تُنشئ شؤون الموظفين طلب المخالصة للموظف.',
                'يصل إلى كل قسم معني رابط للتوقيع والتأكد من عدم وجود التزامات.',
                'تُتابَع الموافقات حتى اكتمالها، وتراجعها المحاسبة.',
                'تُطبع شهادة براءة الذمة معتمدة.',
            ],
        },
        'en': {
            'name': 'Clearance',
            'tagline': 'Staff clearance procedures and custody tracking',
            'about': 'Organizes staff clearance when employment ends or a staff member moves, and keeps track of '
                     'the items in each staff member\'s custody.',
            'steps': [
                'Human Resources opens a clearance request for the staff member.',
                'Each department involved receives a link to sign and confirm there are no obligations.',
                'Approvals are followed until complete, then reviewed by Accounts.',
                'An approved clearance certificate is printed.',
            ],
        },
    },
    {
        'key': 'absence', 'url': 'https://8.iajaward.org', 'icon': 'fa-user-clock', 'color': '#fb923c',
        'ar': {
            'name': 'غياب الطلاب',
            'tagline': 'تسجيل غياب الطلبة واستئذانهم وإبلاغ أولياء الأمور',
            'about': 'يسجّل غياب الطلبة اليومي واستئذانهم والخروج من الحصص، ويُبلغ أولياء الأمور، ويقدّم '
                     'تقارير ومقارنات للإدارة.',
            'steps': [
                'يسجّل المعلم أو المشرف غياب الشعبة يومياً.',
                'تُرفق الأعذار وتُعتمد.',
                'يُرسل إشعار إلى ولي الأمر بالبريد.',
                'تُتابع حالات الخروج من الحصة، وتُستخرج التقارير والمقارنات بين الفترات.',
            ],
        },
        'en': {
            'name': 'Student Absence',
            'tagline': 'Student absence, permissions and parent notices',
            'about': 'Records daily student absence, permissions and leaving class, notifies parents, and gives '
                     'the administration reports and comparisons.',
            'steps': [
                'The teacher or supervisor records each section\'s absence every day.',
                'Excuses are attached and approved.',
                'A notice is e-mailed to the parent.',
                'Students out of class are followed, and reports and period comparisons are produced.',
            ],
        },
    },
    {
        'key': 'forms', 'url': 'https://9.iajaward.org', 'icon': 'fa-clipboard-list', 'color': '#60a5fa',
        'ar': {
            'name': 'النماذج والاستبيانات',
            'tagline': 'تصميم النماذج والاستبيانات وتحليل الإجابات',
            'about': 'يصمّم النماذج والاستبيانات والاختبارات القصيرة، ويجمع الإجابات ويعرض نتائجها بوضوح.',
            'steps': [
                'يُنشأ النموذج بأنواع متعددة من الأسئلة وشروط للإظهار.',
                'يُنشر برابط أو رمز QR، أو تُرسل دعوات شخصية إلى المستهدفين.',
                'تُجمع الإجابات وتُعرض نتائجها برسوم بيانية.',
                'تُصدَّر النتائج إلى ملف Excel.',
            ],
        },
        'en': {
            'name': 'Forms & Surveys',
            'tagline': 'Designing forms and surveys and analysing answers',
            'about': 'Designs forms, surveys and short quizzes, collects the answers and presents the results clearly.',
            'steps': [
                'A form is built with many question types and display conditions.',
                'It is shared by link or QR code, or sent as personal invitations.',
                'Answers are collected and the results shown as charts.',
                'Results are exported to an Excel file.',
            ],
        },
    },
]

TEXT = {
    'ar': {
        'title': 'بوابة أنظمة العمل',
        'subtitle': 'جميع أنظمة العمل في مكان واحد',
        'hint': 'اختر نظاماً للتعرّف عليه ثم ادخل إليه مباشرة',
        'switch': 'English', 'switch_lang': 'en',
        'details': 'التفاصيل',
        'about': 'عن النظام',
        'how': 'آلية العمل',
        'open': 'الدخول إلى النظام',
        'close': 'إغلاق',
    },
    'en': {
        'title': 'Work Systems Portal',
        'subtitle': 'All work systems in one place',
        'hint': 'Choose a system to learn about it, then sign in directly',
        'switch': 'العربية', 'switch_lang': 'ar',
        'details': 'Details',
        'about': 'About',
        'how': 'How it works',
        'open': 'Open the system',
        'close': 'Close',
    },
}


def _lang(request):
    lang = request.GET.get('lang') or request.COOKIES.get(LANG_COOKIE) or 'ar'
    return lang if lang in TEXT else 'ar'


def systems_portal(request):
    lang = _lang(request)
    systems = [dict(key=s['key'], url=s['url'], icon=s['icon'], color=s['color'], **s[lang]) for s in SYSTEMS]
    resp = render(request, 'award/systems_portal.html', {
        'lang': lang, 'dir': 'rtl' if lang == 'ar' else 'ltr', 't': TEXT[lang], 'systems': systems,
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
    return JsonResponse(fetch_venues_ticker())
