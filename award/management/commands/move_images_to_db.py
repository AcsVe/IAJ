"""
نقل الصور القديمة من Cloudinary إلى قاعدة البيانات.

    python manage.py move_images_to_db --dry-run   # عرض فقط بدون تغيير
    python manage.py move_images_to_db             # تنفيذ النقل

ينقل الصور فقط (jpg/png/webp/...) — الفيديو وملفات PDF تبقى على Cloudinary.
آمن للتكرار: الصور المنقولة سابقاً (db/...) يتم تجاهلها.
"""
import os

import requests
from django.apps import apps
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import models

from award.storage import DB_PREFIX, HybridMediaStorage, is_image_name, is_url


class Command(BaseCommand):
    help = "نقل الصور المخزّنة على Cloudinary إلى قاعدة البيانات"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='عرض ما سيتم نقله بدون تنفيذ')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        storage = HybridMediaStorage()
        moved = skipped = failed = 0

        for model in apps.get_app_config('award').get_models():
            file_fields = [f for f in model._meta.get_fields() if isinstance(f, models.FileField)]
            for field in file_fields:
                for obj in model.objects.exclude(**{field.name: ''}).exclude(**{f'{field.name}__isnull': True}):
                    name = getattr(obj, field.name).name
                    if not name or name.startswith(DB_PREFIX):
                        continue
                    path_part = name.split('?')[0]
                    if not is_image_name(path_part):
                        skipped += 1
                        continue
                    url = name if is_url(name) else storage.url(name)
                    label = f'{model.__name__}#{obj.pk}.{field.name}'
                    if dry:
                        self.stdout.write(f'[dry-run] {label}: {url}')
                        moved += 1
                        continue
                    try:
                        r = requests.get(url, timeout=60)
                        r.raise_for_status()
                        folder = field.upload_to if isinstance(field.upload_to, str) else ''
                        ext = os.path.splitext(path_part)[1].lower() or '.jpg'
                        new_name = storage.save_to_db(os.path.join(folder, 'img' + ext), ContentFile(r.content))
                        model.objects.filter(pk=obj.pk).update(**{field.name: new_name})
                        moved += 1
                        self.stdout.write(self.style.SUCCESS(f'✓ {label} → {new_name}'))
                    except Exception as e:
                        failed += 1
                        self.stdout.write(self.style.ERROR(f'✗ {label}: {e}'))

        self.stdout.write(f'\nتم: {moved} | تم تجاهل (ليست صور): {skipped} | فشل: {failed}')
