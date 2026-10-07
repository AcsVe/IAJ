"""
تشغيل الموقع على هذا الجهاز بخادم الإنتاج Waitress (يعمل على Windows).

    python serve.py

• يطبّق تحديثات الجداول ويجمع ملفات static تلقائياً عند كل تشغيل.
• العنوان: http://localhost:8000  (أو PORT من .env)
• السجل: logs/server.log
"""
import logging
import logging.handlers
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
sys.path.insert(0, BASE)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

os.makedirs(os.path.join(BASE, 'logs'), exist_ok=True)
handler = logging.handlers.RotatingFileHandler(os.path.join(BASE, 'logs', 'server.log'),
                                               maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])
log = logging.getLogger('iaj')


def main():
    import django
    django.setup()
    from django.core.management import call_command

    log.info('Applying database updates...')
    call_command('migrate', interactive=False, verbosity=0)
    log.info('Collecting static files...')
    call_command('collectstatic', interactive=False, verbosity=0)

    from django.conf import settings
    from django.core.wsgi import get_wsgi_application
    from waitress import serve

    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    port = int(os.environ.get('PORT') or 8000)
    log.info('IAJ website running on http://localhost:%s  (site: %s)', port, settings.SITE_URL or '-')
    serve(
        get_wsgi_application(),
        host=os.environ.get('HOST', '0.0.0.0'),
        port=port,
        threads=int(os.environ.get('THREADS') or 8),
        # Cloudflare Tunnel يتصل من نفس الجهاز ويمرّر https
        trusted_proxy='127.0.0.1',
        trusted_proxy_count=1,
        trusted_proxy_headers={'x-forwarded-proto', 'x-forwarded-host', 'x-forwarded-for'},
        clear_untrusted_proxy_headers=True,
        max_request_body_size=2 * 1024 ** 3,   # رفع فيديو حتى 2GB
        channel_timeout=300,
        ident='IAJ',
    )


if __name__ == '__main__':
    try:
        main()
    except Exception:
        log.exception('Server failed to start')
        raise
