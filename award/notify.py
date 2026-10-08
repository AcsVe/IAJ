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


def _send(to, subject, html, text):
    from .models import EmailLog
    status, err = 'sent', ''
    try:
        msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, to)
        msg.attach_alternative(html, 'text/html')
        msg.send()
        if not settings.EMAIL_HOST:
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
    to = [t for t in ([to] if isinstance(to, str) else to) if t]
    if not to:
        return
    ctx = {'subject': subject, 'body': body, 'url': absolute(url), 'button': button or 'فتح في الموقع',
           'site_url': absolute('/')}
    html = render_to_string('award/email/message.html', ctx)
    text = body + (f"\n\n{ctx['url']}" if url else '') + '\n\n— جائزة انتصار عباس جردانة'
    if wait:
        _send(to, subject, html, text)
    else:
        threading.Thread(target=_send, args=(to, subject, html, text), daemon=True).start()


def notify(user, title, body='', url='', level='info', email=True, button=''):
    """إشعار لمستخدم: جرس داخل الموقع + بريد (إن كان مفعّلاً لديه)"""
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
    from django.contrib.auth.models import User
    from .models import Notification
    staff = list(User.objects.filter(is_staff=True, is_active=True))
    Notification.objects.bulk_create([Notification(user=u, title=title[:255], body=body, url=url) for u in staff])
    if email:
        to = settings.ADMIN_NOTIFY_EMAILS or [u.email for u in staff if u.email]
        if to:
            send_email(to, title, body, url, 'فتح في لوحة التحكم')
