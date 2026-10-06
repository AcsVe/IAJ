"""
التخزين:
  • الصور  ← قاعدة البيانات (موديل StoredFile) وتُعرض من /media/db/...
  • الفيديو وملفات PDF ← Cloudinary كما كان سابقاً
  • الروابط القديمة (https://res.cloudinary.com/...) تبقى شغالة بدون أي تغيير
"""
import io
import mimetypes
import os
import uuid

import cloudinary
import cloudinary.uploader
from django.conf import settings
from django.core.files.base import ContentFile
from cloudinary_storage.storage import MediaCloudinaryStorage

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.avif', '.ico', '.jfif'}
DB_PREFIX = 'db/'
MAX_IMAGE_SIDE = 2400        # أقصى عرض/ارتفاع بعد التصغير التلقائي
JPEG_QUALITY = 85


def is_image_name(name):
    return os.path.splitext(name or '')[1].lower() in IMAGE_EXTS


def is_url(name):
    return bool(name) and (name.startswith('http://') or name.startswith('https://'))


def optimize_image(data, ext):
    """تصغير الصور الكبيرة جداً وضغطها لتوفير مساحة قاعدة البيانات"""
    if ext in ('.gif', '.svg', '.ico'):
        return data
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(data))
        fmt = (img.format or '').upper()
        img = ImageOps.exif_transpose(img)
        resized = max(img.size) > MAX_IMAGE_SIDE
        if resized:
            img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.LANCZOS)

        out = io.BytesIO()
        if fmt in ('JPEG', 'MPO') or ext in ('.jpg', '.jpeg', '.jfif'):
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            img.save(out, 'JPEG', quality=JPEG_QUALITY, optimize=True, progressive=True)
        elif fmt == 'PNG':
            img.save(out, 'PNG', optimize=True)
        elif fmt == 'WEBP':
            img.save(out, 'WEBP', quality=JPEG_QUALITY)
        else:
            return data
        new = out.getvalue()
        return new if (resized or len(new) < len(data)) else data
    except Exception:
        return data


class HybridMediaStorage(MediaCloudinaryStorage):

    # ---------- حفظ ----------
    def get_available_name(self, name, max_length=None):
        # الصور تأخذ اسم فريد (uuid) داخل _save — لا داعي لسؤال Cloudinary
        if is_image_name(name):
            return name
        return super().get_available_name(name, max_length)

    def _save(self, name, content):
        if is_image_name(name):
            return self.save_to_db(name, content)
        return self._save_cloudinary(name, content)

    def save_to_db(self, name, content):
        from .models import StoredFile
        ext = os.path.splitext(name)[1].lower()
        if hasattr(content, 'seek'):
            try:
                content.seek(0)
            except Exception:
                pass
        data = content.read()
        if isinstance(data, str):
            data = data.encode()
        data = optimize_image(data, ext)

        folder = os.path.dirname(name).strip('/')
        new_name = DB_PREFIX + (folder + '/' if folder else '') + uuid.uuid4().hex + ext
        ctype = mimetypes.guess_type(new_name)[0] or 'application/octet-stream'
        StoredFile.objects.create(name=new_name, content=data, content_type=ctype, size=len(data))
        return new_name

    def _save_cloudinary(self, name, content):
        response = cloudinary.uploader.upload(
            content,
            resource_type='auto',
            use_filename=True,
            unique_filename=True,
            folder=os.path.dirname(name) or '',
        )
        return response.get('secure_url', response.get('public_id', name))

    # ---------- قراءة ----------
    def url(self, name):
        if not name:
            return ''
        if is_url(name):
            return name
        if name.startswith(DB_PREFIX):
            return settings.MEDIA_URL + name
        return super().url(name)

    def exists(self, name):
        if name and name.startswith(DB_PREFIX):
            from .models import StoredFile
            return StoredFile.objects.filter(name=name).exists()
        if is_url(name):
            return True
        return super().exists(name)

    def _open(self, name, mode='rb'):
        if name.startswith(DB_PREFIX):
            from .models import StoredFile
            obj = StoredFile.objects.get(name=name)
            f = ContentFile(bytes(obj.content), name=name)
            return f
        return super()._open(name, mode)

    def size(self, name):
        if name.startswith(DB_PREFIX):
            from .models import StoredFile
            return StoredFile.objects.filter(name=name).values_list('size', flat=True).first() or 0
        return super().size(name)

    def delete(self, name):
        if not name:
            return
        if name.startswith(DB_PREFIX):
            from .models import StoredFile
            StoredFile.objects.filter(name=name).delete()
            return
        if is_url(name):
            return  # ملفات Cloudinary القديمة لا نحذفها تلقائياً
        try:
            super().delete(name)
        except Exception:
            pass


# أسماء قديمة كانت مستخدمة في settings / migrations — نخليها تشير لنفس الكلاس
AutoCloudinaryStorage = HybridMediaStorage


class VideoCloudinaryStorage(MediaCloudinaryStorage):
    def _save(self, name, content):
        response = cloudinary.uploader.upload(
            content, resource_type='video', use_filename=True, unique_filename=True,
            folder=os.path.dirname(name) or '',
        )
        return response.get('secure_url', response.get('public_id', name))

    def url(self, name):
        return name if is_url(name) else super().url(name)


class RawCloudinaryStorage(MediaCloudinaryStorage):
    def _save(self, name, content):
        response = cloudinary.uploader.upload(
            content, resource_type='raw', use_filename=True, unique_filename=True,
            folder=os.path.dirname(name) or '',
        )
        return response.get('secure_url', response.get('public_id', name))

    def url(self, name):
        return name if is_url(name) else super().url(name)
