"""
Django settings for core project.
"""

from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file():
    """
    قراءة إعدادات الجهاز من ملف .env (أو IAJ.env) بجانب manage.py.
    يقبل: KEY=value  أو  KEY = "value"  أو  export KEY='value'
    المتغيرات الموجودة مسبقاً في النظام لها الأولوية.
    """
    for fname in ('.env', 'IAJ.env'):
        path = BASE_DIR / fname
        if not path.is_file():
            continue
        for raw in path.read_text(encoding='utf-8-sig', errors='ignore').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            if line.lower().startswith('export '):
                line = line[7:].strip()
            key, val = line.split('=', 1)
            key, val = key.strip(), val.strip().strip('"').strip("'").strip()
            if key and val and not os.environ.get(key):
                os.environ[key] = val
        break


_load_env_file()

SECRET_KEY = (
    os.environ.get('DJANGO_SECRET_KEY')
    or os.environ.get('SECRET_KEY')
    or 'django-insecure-_vr60vi(0iqx)t8i@j9xmoo_#ca24=n1joalaumf4u#10gt%c='
)

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# عنوان الموقع العام (مثال: https://award.example.com) — يُكتب في .env
SITE_URL = os.environ.get('SITE_URL', '').strip().rstrip('/')

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '*').split(',') if h.strip()]

# Cloudflare Tunnel يمرّر HTTPS عبر بروكسي — بدونها تسجيل الدخول للإدمن ممكن يرفض (CSRF Origin)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in (os.environ.get('CSRF_TRUSTED_ORIGINS', '') + ',' + SITE_URL).split(',') if o.strip()
]
if SITE_URL.startswith('https://') and not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'award',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'award.middleware.AdminArabicMiddleware',   # لوحة Django بالعربية RTL
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'award.middleware.SvgIconsMiddleware',      # أيقونات SVG مدمجة بدل خط Font Awesome
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'award/templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'award.context_processors.ticker_context',
                'award.context_processors.site_context',
                'award.context_processors.portal_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# DATABASE_URL في .env  ← قاعدة PostgreSQL على الجهاز (مثال: postgresql://postgres:PASS@localhost:5432/iaj)
# LOCAL_SQLITE=1        ← قاعدة تجريبية (ملف db.sqlite3) تتجاهل DATABASE_URL
# CLOUD_DATABASE_URL    ← القاعدة السحابية القديمة (Neon) — تُستخدم فقط للاستيراد مرة واحدة
import re as _re


def _clean_db_url(value):
    value = (value or '').strip()
    # استخراج الرابط حتى لو كان داخل نص إضافي، مثل: psql 'postgresql://...'
    m = _re.search(r'(postgres(?:ql)?|sqlite|mysql)://[^\s\'"]+', value)
    return m.group(0) if m else value.strip('"').strip("'").strip()


_db_url = _clean_db_url(os.environ.get('DATABASE_URL'))
if _db_url and os.environ.get('LOCAL_SQLITE') != '1':
    DATABASES['default'] = dj_database_url.parse(_db_url, conn_max_age=600, conn_health_checks=True)

_cloud_url = _clean_db_url(os.environ.get('CLOUD_DATABASE_URL'))
if _cloud_url:
    DATABASES['cloud'] = dj_database_url.parse(_cloud_url, conn_max_age=0)

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.environ.get('TIME_ZONE', 'Asia/Amman')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'award/static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# كل الملفات المرفوعة (صور، فيديو، PDF) تُحفظ على الجهاز
MEDIA_URL = '/media/'
MEDIA_ROOT = os.environ.get('MEDIA_ROOT') or os.path.join(BASE_DIR, 'media')

STORAGES = {
    "default": {"BACKEND": "award.storage.LocalMediaStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
    "videos": {"BACKEND": "award.storage.LocalMediaStorage"},
    "raw": {"BACKEND": "award.storage.LocalMediaStorage"},
}

# بيانات Cloudinary القديمة — تُستخدم فقط لتنزيل الملفات القديمة (localize_media)
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', 'dd1ylbi9k')

FILE_UPLOAD_PERMISSIONS = 0o644
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ذاكرة مؤقتة داخل السيرفر (للإعدادات العامة والصور المخزّنة)
CACHES = {
    'default': {
        'BACKEND': 'award.preview_state.PreviewAwareLocMemCache',   # كاش الذاكرة + تجاهله أثناء «المعاينة»
        'LOCATION': 'iaj',
        'OPTIONS': {'MAX_ENTRIES': 600},
    }
}


# =====================================================
#   البريد الإلكتروني (إشعارات التسجيل)
#   بدون EMAIL_HOST في .env تُحفظ الرسائل في logs/emails بدل إرسالها
# =====================================================
EMAIL_HOST = os.environ.get('EMAIL_HOST', '').strip()
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587') or 587)
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
if 'gmail' in EMAIL_HOST.lower() or 'google' in EMAIL_HOST.lower():
    EMAIL_HOST_PASSWORD = ''.join(EMAIL_HOST_PASSWORD.split())   # كلمة مرور التطبيق من Google تُنسخ بمسافات
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'True' if EMAIL_PORT == 465 else 'False') == 'True'
EMAIL_USE_TLS = (not EMAIL_USE_SSL) and os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_TIMEOUT = 20
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'جائزة انتصار عباس جردانة <noreply@iajaward.org>')
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# بريد (أو أكثر، بفاصلة) يستلم تنبيه «طلب جديد» — فارغ = بريد كل مدير في لوحة التحكم
ADMIN_NOTIFY_EMAILS = [e.strip() for e in os.environ.get('ADMIN_NOTIFY_EMAILS', '').split(',') if e.strip()]
# Microsoft 365 (Graph) — له الأولوية إن وُجد
MS_TENANT_ID = os.environ.get('MS_TENANT_ID', '').strip()
MS_CLIENT_ID = os.environ.get('MS_CLIENT_ID', '').strip()
MS_CLIENT_SECRET = os.environ.get('MS_CLIENT_SECRET', '').strip()
MS_SENDER = os.environ.get('MS_SENDER', '').strip()
EMAIL_VIA_GRAPH = all((MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET, MS_SENDER))
EMAIL_ENABLED = EMAIL_VIA_GRAPH or bool(EMAIL_HOST)
_reply_to = os.environ.get('REPLY_TO', '').strip()
EMAIL_REPLY_TO = [_reply_to] if _reply_to else []
if EMAIL_VIA_GRAPH:
    EMAIL_BACKEND = 'award.mail_graph.GraphEmailBackend'
    if not os.environ.get('DEFAULT_FROM_EMAIL'):
        DEFAULT_FROM_EMAIL = f'جائزة انتصار عباس جردانة <{MS_SENDER}>'
elif EMAIL_HOST:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
    EMAIL_FILE_PATH = os.path.join(BASE_DIR, 'logs', 'emails')

# تفعيل الحساب برابط في البريد قبل الدخول؟ (False = يدخل فوراً، فلا يتعطل لو ذهبت الرسالة إلى Spam)
REQUIRE_EMAIL_VERIFICATION = os.environ.get('REQUIRE_EMAIL_VERIFICATION', 'False') == 'True'
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/portal/'
LOGOUT_REDIRECT_URL = '/'
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24 * 3   # روابط التفعيل/الاستعادة صالحة 3 أيام
AUTHENTICATION_BACKENDS = ['award.auth.EmailOrUsernameBackend']

# رفع ملفات الطلبات
SUBMISSION_MAX_MB = int(os.environ.get('SUBMISSION_MAX_MB', '95') or 95)   # Cloudflare (المجاني) يقبل حتى 100MB للطلب الواحد
