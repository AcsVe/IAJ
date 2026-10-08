"""تجربة إعدادات البريد:  python manage.py test_email you@example.com"""
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'إرسال رسالة تجريبية للتأكد من إعدادات البريد في .env'

    def add_arguments(self, parser):
        parser.add_argument('to')

    def handle(self, to, **opts):
        from award.notify import send_email
        from award.models import EmailLog
        if not settings.EMAIL_HOST:
            self.stdout.write(self.style.WARNING('EMAIL_HOST غير موجود في .env — الرسالة ستُحفظ في logs/emails بدل إرسالها.'))
        else:
            self.stdout.write(f'SMTP: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}  SSL={settings.EMAIL_USE_SSL} TLS={settings.EMAIL_USE_TLS}  From: {settings.DEFAULT_FROM_EMAIL}')
        send_email(to, 'رسالة تجريبية — جائزة انتصار عباس جردانة',
                   'إذا وصلتك هذه الرسالة فإعدادات البريد في الموقع تعمل بشكل صحيح.', '/', 'فتح الموقع', wait=True)
        log = EmailLog.objects.order_by('-id').first()
        if log and log.status == 'failed':
            self.stdout.write(self.style.ERROR(f'فشل الإرسال: {log.error}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'تم ({log.get_status_display() if log else "?"}) → {to}'))
