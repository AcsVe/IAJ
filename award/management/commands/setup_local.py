"""
إعداد الموقع على الجهاز (مرة واحدة) — يكتب ملف .env وينشئ قاعدة البيانات في PostgreSQL.

    python manage.py setup_local
"""
import getpass
import os
import secrets
import shutil
from urllib.parse import quote, urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1', ''}


def read_env(path):
    data = {}
    if os.path.isfile(path):
        for raw in open(path, encoding='utf-8-sig', errors='ignore').read().splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            if line.lower().startswith('export '):
                line = line[7:].strip()
            k, v = line.split('=', 1)
            data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def ask(prompt, default=''):
    val = input(f'{prompt}' + (f' [{default}]' if default else '') + ': ').strip()
    return val or default


class Command(BaseCommand):
    help = 'كتابة ملف .env وإنشاء قاعدة PostgreSQL على الجهاز'

    def handle(self, *args, **opts):
        import psycopg2
        from psycopg2 import sql

        base = str(settings.BASE_DIR)
        env_path = os.path.join(base, '.env')
        old = {}
        for name in ('.env', 'IAJ.env'):
            old.update({k: v for k, v in read_env(os.path.join(base, name)).items() if k not in old})

        # رابط Neon القديم يُحفظ باسم CLOUD_DATABASE_URL للاستيراد
        cloud = old.get('CLOUD_DATABASE_URL', '')
        cur = old.get('DATABASE_URL', '')
        if cur and urlparse(cur).hostname not in LOCAL_HOSTS:
            cloud = cloud or cur

        self.stdout.write('\n=== قاعدة البيانات على الجهاز (PostgreSQL) ===')
        prev = urlparse(cur) if cur and urlparse(cur).hostname in LOCAL_HOSTS else None
        host = ask('Host', prev.hostname if prev else 'localhost')
        port = ask('Port', str(prev.port or 5432) if prev else '5432')
        user = ask('User', prev.username if prev else 'postgres')
        password = getpass.getpass(f'Password of PostgreSQL user "{user}" (the one chosen when installing PostgreSQL): ')
        dbname = ask('Database name', (prev.path.lstrip('/') if prev else '') or 'iaj')

        try:
            conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname='postgres',
                                    connect_timeout=10)
        except Exception as e:
            raise CommandError(f'تعذّر الاتصال بـ PostgreSQL — تأكد من كلمة المرور وأن الخدمة تعمل.\n{e}')
        conn.autocommit = True
        with conn.cursor() as c:
            c.execute('SHOW server_version')
            self.stdout.write(f'✓ متصل — PostgreSQL {c.fetchone()[0]}')
            c.execute('SELECT 1 FROM pg_database WHERE datname=%s', [dbname])
            if c.fetchone():
                self.stdout.write(f'✓ القاعدة "{dbname}" موجودة')
            else:
                c.execute(sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' TEMPLATE template0").format(sql.Identifier(dbname)))
                self.stdout.write(self.style.SUCCESS(f'✓ تم إنشاء القاعدة "{dbname}"'))
        conn.close()

        self.stdout.write('\n=== عنوان الموقع على الإنترنت ===')
        self.stdout.write('مثال: https://award.example.com  (اتركه فارغاً إذا لم يجهز الدومين بعد)')
        site_url = ask('SITE_URL', old.get('SITE_URL', '')).rstrip('/')
        if site_url and not site_url.startswith('http'):
            site_url = 'https://' + site_url

        if not cloud:
            self.stdout.write('\nرابط Neon (لنقل البيانات القديمة) — اتركه فارغاً إذا لا تريد النقل:')
            cloud = ask('CLOUD_DATABASE_URL', '')

        if os.path.isfile(env_path) and not os.path.isfile(env_path + '.cloud-backup'):
            shutil.copy(env_path, env_path + '.cloud-backup')

        db_url = f'postgresql://{quote(user, safe="")}:{quote(password, safe="")}@{host}:{port}/{quote(dbname, safe="")}'
        lines = [
            '# إعدادات موقع الجائزة على هذا الجهاز — لا تشارك هذا الملف',
            f'DATABASE_URL={db_url}',
            f'SECRET_KEY={old.get("SECRET_KEY") or old.get("DJANGO_SECRET_KEY") or secrets.token_urlsafe(50)}',
            "DEBUG=False",
            f'SITE_URL={site_url}',
            f'PORT={old.get("PORT", "8000")}',
            f'MEDIA_ROOT={old.get("MEDIA_ROOT", "")}',
            f'BACKUP_DIR={old.get("BACKUP_DIR", "")}',
            '',
            '# القاعدة السحابية القديمة — للاستيراد فقط (احذف السطر بعد التأكد من النقل)',
            f'CLOUD_DATABASE_URL={cloud}',
        ]
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
        self.stdout.write(self.style.SUCCESS(f'\n✓ تم حفظ الإعدادات في {env_path}'))
