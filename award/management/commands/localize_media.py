"""
تنزيل كل الملفات القديمة إلى مجلد media على الجهاز:

  • روابط Cloudinary (صور، فيديو، PDF)
  • الصور التي كانت مخزّنة داخل قاعدة البيانات (db/...)
  • روابط Cloudinary المكتوبة داخل النصوص (محرر الأخبار مثلاً)

    python manage.py localize_media --dry-run   # عرض فقط
    python manage.py localize_media             # تنفيذ
    python manage.py localize_media --cleanup   # + حذف نسخ الصور القديمة من القاعدة بعد نقلها

آمن للتكرار: ما تم نقله سابقاً يتم تجاهله. يحتاج إنترنت لتنزيل ملفات Cloudinary.
"""
import os
import re
import tempfile
import uuid
from urllib.parse import unquote, urlparse

import requests
from django.apps import apps
from django.conf import settings
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import models

from award.storage import DB_PREFIX, is_url, norm, sniff_ext

CLOUD_URL_RE = re.compile(r'https?://res\.cloudinary\.com/[^\s"\'<>()\\]+')


def _folder(field):
    up = field.upload_to
    return norm(up).strip('/') if isinstance(up, str) and up else 'uploads'


def _name_from_url(url):
    base = os.path.basename(unquote(urlparse(url).path)) or uuid.uuid4().hex
    return re.sub(r'[^\w.\-]+', '_', base)


class Command(BaseCommand):
    help = 'تنزيل الملفات من Cloudinary ومن قاعدة البيانات إلى مجلد media'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--cleanup', action='store_true',
                            help='حذف نسخ الصور من قاعدة البيانات بعد نقلها للمجلد')

    # ---------- تنزيل ----------
    def _download(self, url, dest):
        """تنزيل على دفعات (الفيديوهات الكبيرة لا تُحمّل كلها في الذاكرة)"""
        with requests.get(url, stream=True, timeout=(15, 300)) as r:
            r.raise_for_status()
            tmp = tempfile.NamedTemporaryFile(delete=False)
            try:
                for chunk in r.iter_content(1024 * 1024):
                    tmp.write(chunk)
                tmp.close()
                with open(tmp.name, 'rb') as f:
                    if not os.path.splitext(dest)[1]:
                        ext = sniff_ext(f.read(64)) or self._ext_from_type(r.headers.get('Content-Type', ''))
                        dest += ext
                        f.seek(0)
                    return default_storage.save(dest, File(f))
            finally:
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass

    @staticmethod
    def _ext_from_type(ctype):
        import mimetypes
        ext = mimetypes.guess_extension((ctype or '').split(';')[0].strip()) or ''
        return {'.jpe': '.jpg', '.jpeg': '.jpg'}.get(ext, ext)

    def _fix_extension(self, name):
        """ملف موجود على الجهاز بلا امتداد → إضافة الامتداد الصحيح. يرجع الاسم الجديد أو None"""
        name = norm(name)
        if os.path.splitext(name)[1]:
            return None
        full = os.path.join(settings.MEDIA_ROOT, name)
        if not os.path.isfile(full):
            return None
        with open(full, 'rb') as f:
            ext = sniff_ext(f.read(64))
        if not ext:
            return None
        new = name + ext
        n = 1
        while os.path.exists(os.path.join(settings.MEDIA_ROOT, new)):
            new = f'{name}_{n}{ext}'
            n += 1
        if not self.dry:
            os.replace(full, os.path.join(settings.MEDIA_ROOT, new))
        return new

    def _cloudinary_candidates(self, name):
        cloud = settings.CLOUDINARY_CLOUD_NAME
        name = norm(name).lstrip('/')
        return [f'https://res.cloudinary.com/{cloud}/{rt}/upload/{name}' for rt in ('image', 'video', 'raw')]

    def _localize(self, name, folder):
        """يرجع الاسم الجديد داخل media أو None إذا لا يحتاج نقل"""
        name = norm(name)
        if is_url(name):
            if self.dry:
                return '(dry-run)'
            return self._download(name, f'{folder}/{_name_from_url(name)}')
        if name.startswith(DB_PREFIX):
            from award.models import StoredFile
            obj = StoredFile.objects.filter(name__in=[name, name.replace('/', '\\')]).first()
            if not obj:
                raise FileNotFoundError(f'غير موجود في القاعدة: {name}')
            if self.dry:
                return '(dry-run)'
            return default_storage.save(name[len(DB_PREFIX):], ContentFile(bytes(obj.content)))
        if os.path.isfile(os.path.join(settings.MEDIA_ROOT, name)):
            return self._fix_extension(name)   # موجود على الجهاز (يُضاف الامتداد إن كان ناقصاً)
        # اسم Cloudinary قديم بدون رابط كامل
        last = None
        for url in self._cloudinary_candidates(name):
            try:
                if self.dry:
                    requests.head(url, timeout=15).raise_for_status()
                    return '(dry-run)'
                return self._download(url, f'{folder}/{_name_from_url(url)}')
            except Exception as e:
                last = e
        raise last or FileNotFoundError(name)

    # ---------- التنفيذ ----------
    def handle(self, *args, **opts):
        self.dry = opts['dry_run']
        ok = same = failed = 0
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        url_map = {}

        for model in apps.get_models():
            if model.__name__ == 'StoredFile':
                continue
            file_fields = [f for f in model._meta.concrete_fields if isinstance(f, models.FileField)]
            text_fields = [f for f in model._meta.concrete_fields
                           if isinstance(f, (models.TextField, models.CharField)) and not isinstance(f, models.FileField)]

            for field in file_fields:
                qs = model.objects.exclude(**{field.attname: ''}).exclude(**{f'{field.attname}__isnull': True})
                for pk, name in qs.values_list('pk', field.attname):
                    label = f'{model.__name__}#{pk}.{field.name}'
                    try:
                        new = self._localize(name, _folder(field))
                    except Exception as e:
                        failed += 1
                        self.stdout.write(self.style.ERROR(f'✗ {label}: {name} → {e}'))
                        continue
                    if new is None:
                        same += 1
                        continue
                    ok += 1
                    if not self.dry:
                        model.objects.filter(pk=pk).update(**{field.attname: norm(new)})
                    self.stdout.write(self.style.SUCCESS(f'✓ {label} → {new}'))

            # روابط Cloudinary داخل النصوص
            for field in text_fields:
                qs = model.objects.filter(**{f'{field.attname}__contains': 'res.cloudinary.com'})
                for pk, text in qs.values_list('pk', field.attname):
                    new_text = text
                    for url in set(CLOUD_URL_RE.findall(text or '')):
                        try:
                            if url not in url_map:
                                url_map[url] = '(dry-run)' if self.dry else \
                                    settings.MEDIA_URL + self._download(url, f'imported/{_name_from_url(url)}')
                            new_text = new_text.replace(url, url_map[url])
                            ok += 1
                            self.stdout.write(self.style.SUCCESS(f'✓ {model.__name__}#{pk}.{field.name} (نص) → {url_map[url]}'))
                        except Exception as e:
                            failed += 1
                            self.stdout.write(self.style.ERROR(f'✗ {model.__name__}#{pk}.{field.name}: {url} → {e}'))
                    if not self.dry and new_text != text:
                        model.objects.filter(pk=pk).update(**{field.attname: new_text})

        if opts['cleanup'] and not self.dry:
            # حذف نسخ الصور من القاعدة التي لم يعد أي سجل يشير إليها
            from award.models import StoredFile
            used = set()
            for model in apps.get_models():
                for f in model._meta.concrete_fields:
                    if isinstance(f, models.FileField):
                        used.update(model.objects.filter(**{f'{f.attname}__startswith': DB_PREFIX})
                                    .values_list(f.attname, flat=True))
            removed = StoredFile.objects.exclude(name__in=used).delete()[0]
            self.stdout.write(f'حذف {removed} نسخة صورة قديمة من قاعدة البيانات (أصبحت في المجلد)')

        from award.site_cache import clear_site_bundle, clear_home_bundle
        clear_site_bundle()
        clear_home_bundle()
        self.stdout.write(f'\nتم نقل: {ok} | موجود مسبقاً: {same} | فشل: {failed}')
        self.stdout.write(f'المجلد: {settings.MEDIA_ROOT}')
