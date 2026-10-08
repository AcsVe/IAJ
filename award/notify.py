"""
الإشعارات: داخل الموقع (الجرس) + البريد الإلكتروني.
البريد يُرسل في الخلفية حتى لا تتأخر الصفحة، وكل رسالة تُسجَّل في «سجل رسائل البريد».
"""
import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

log = logging.getLogger('iaj')


def absolute(url):
    if not url or url.startswith('http'):
        return url or ''
    base = getattr(settings, 'SITE_URL', '') or 'http://localhost:8000'
    return base.rstrip('/') + url


_logo_cache = {'key': None, 'data': None}


def _logo_png():
    """شعار الجائزة كصورة PNG صغيرة تُضمَّن داخل الرسالة (تظهر حتى لو كانت الصور الخارجية محجوبة)"""
    try:
        from .models import SiteSetting
        st = SiteSetting.objects.only('site_logo').first()
        name = st.site_logo.name if st and st.site_logo else ''
        if not name:
            return None
        if _logo_cache['key'] == name:
            return _logo_cache['data']
        data = None
        if not name.lower().endswith('.svg'):
            import io
            from PIL import Image
            with st.site_logo.open('rb') as fh:
                img = Image.open(io.BytesIO(fh.read()))
                img.load()
            img = img.convert('RGBA')
            img.thumbnail((180, 180), Image.LANCZOS)
            out = io.BytesIO()
            img.save(out, 'PNG', optimize=True)
            data = out.getvalue()
        _logo_cache.update(key=name, data=data)
        return data
    except Exception as e:
        log.warning('Email logo skipped: %s', e)
        return None


def _send(to, subject, html, text, logo=None):
    from .models import EmailLog
    status, err = 'sent', ''
    try:
        from email.utils import make_msgid
        from urllib.parse import urlparse
        domain = urlparse(getattr(settings, 'SITE_URL', '') or '').hostname or 'iajaward.org'
        msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, to,
                                     reply_to=getattr(settings, 'EMAIL_REPLY_TO', None) or None,
                                     headers={'Message-ID': make_msgid(domain=domain)})
        msg.attach_alternative(html, 'text/html')
        if logo:
            from email.mime.image import MIMEImage
            img = MIMEImage(logo, 'png')
            img.add_header('Content-ID', '<iajlogo>')
            img.add_header('Content-Disposition', 'inline', filename='logo.png')
            msg.mixed_subtype = 'related'
            msg.attach(img)
        msg.send()
        if not settings.EMAIL_ENABLED:
            status = 'saved'
    except Exception as e:   # لا نوقف الموقع بسبب البريد
        status, err = 'failed', f'{type(e).__name__}: {e}'
        log.warning('Email to %s failed: %s', to, err)
    try:
        EmailLog.objects.create(to=', '.join(to)[:500], subject=subject[:255], status=status, error=err)
    except Exception:
        pass
    finally:
        from django.db import connection
        connection.close()


def send_email(to, subject, body, url='', button='', wait=False):
    """رسالة بقالب الجائزة. body نص عادي (الأسطر تُحفظ)."""
    from .preview_state import active as _preview
    if _preview():   # «معاينة قبل الحفظ»: لا رسائل ولا إشعارات
        return None
    to = [t for t in ([to] if isinstance(to, str) else to) if t]
    if not to:
        return
    logo = _logo_png()
    ctx = {'subject': subject, 'body': body, 'url': absolute(url), 'button': button or 'فتح في الموقع',
           'site_url': absolute('/'), 'has_logo': bool(logo)}
    try:
        from .brand import brand_colors
        ctx['brand'] = brand_colors()
    except Exception:
        ctx['brand'] = {'menu': '#0a1632', 'menu_light': '#3a4560', 'menu_dark': '#06101f', 'menu_deep': '#040914',
                        'menu_rgb': '10,22,50', 'gold': '#c5a059', 'gold_rgb': '197,160,89'}
    html = render_to_string('award/email/message.html', ctx)
    text = body + (f"\n\n{ctx['url']}" if url else '') + '\n\n— جائزة انتصار عباس جردانة'
    if wait:
        _send(to, subject, html, text, logo)
    else:
        threading.Thread(target=_send, args=(to, subject, html, text, logo), daemon=True).start()


def notify(user, title, body='', url='', level='info', email=True, button=''):
    """إشعار لمستخدم: جرس داخل الموقع + بريد (إن كان مفعّلاً لديه)"""
    from .preview_state import active as _preview
    if _preview():   # «معاينة قبل الحفظ»: لا رسائل ولا إشعارات
        return None
    from .models import Notification
    if not user:
        return
    Notification.objects.create(user=user, title=title[:255], body=body, url=url, level=level)
    prof = getattr(user, 'profile', None)
    wants = prof.email_notifications if prof else True
    if email and wants and user.email:
        send_email(user.email, title, body, url, button)


def notify_staff(title, body='', url='', email=True):
    """تنبيه الإدارة (كل المديرين) + بريد ADMIN_NOTIFY_EMAILS"""
    from .preview_state import active as _preview
    if _preview():   # «معاينة قبل الحفظ»: لا رسائل ولا إشعارات
        return None
    from django.contrib.auth.models import User
    from .models import Notification
    from django.db.models import Q
    from .roles import award_manager_users
    staff = list(award_manager_users())   # المدير التقني + مديرو الجائزة (وليس محرري المحتوى)
    Notification.objects.bulk_create([Notification(user=u, title=title[:255], body=body, url=url) for u in staff])
    if email:
        to = settings.ADMIN_NOTIFY_EMAILS or [u.email for u in staff if u.email]
        if to:
            send_email(to, title, body, url, 'فتح في لوحة التحكم')
