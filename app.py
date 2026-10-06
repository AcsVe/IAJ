"""
Render entry point.

Render's default start command is `gunicorn app:app`. This file makes that
command work for this Django project (equivalent to `gunicorn core.wsgi:application`).

It also applies database migrations once at startup, because the free Render
plan has no Shell for running `python manage.py migrate` manually.
Set RUN_MIGRATIONS_ON_START=0 in Render's environment to turn that off.
"""
import logging
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django  # noqa: E402

django.setup()

if os.environ.get('RUN_MIGRATIONS_ON_START', '1') == '1':
    try:
        from django.core.management import call_command
        call_command('migrate', interactive=False, verbosity=1)
    except Exception:  # never block the site from starting
        logging.getLogger(__name__).exception('Automatic migrate failed')

from django.core.wsgi import get_wsgi_application  # noqa: E402

app = application = get_wsgi_application()
