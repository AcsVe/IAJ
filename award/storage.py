"""
التخزين المحلي — كل الملفات (صور، فيديو، PDF) تُحفظ على الجهاز داخل مجلد media.

  • الصور تُصغَّر وتُضغط تلقائياً قبل الحفظ.
  • الملفات القديمة المخزّنة داخل قاعدة البيانات (db/...) تبقى تعمل،
    ويمكن نقلها للمجلد بالأمر:  python manage.py localize_media
  • أي رابط كامل (https://...) يُعرض كما هو.
"""
import io
import os
import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.avif', '.ico', '.jfif'}
DB_PREFIX = 'db/'
MAX_IMAGE_SIDE = 2400        # أقصى عرض/ارتفاع بعد التصغير التلقائي
JPEG_QUALITY = 85


def norm(name):
    """مسارات Windows تستخدم \\ — نوحّدها إلى /"""
    return (name or '').replace('\\', '/')


_MAGIC = [
    (b'\x89PNG\r\n\x1a\n', '.png'), (b'\xff\xd8\xff', '.jpg'), (b'GIF8', '.gif'),
    (b'%PDF', '.pdf'), (b'\x1aE\xdf\xa3', '.webm'), (b'BM', '.bmp'), (b'\x00\x00\x01\x00', '.ico'),
]


def sniff_ext(head):
    """معرفة نوع الملف من أول بايتات فيه (لملفات Cloudinary التي بلا امتداد)"""
    head = head or b''
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return '.webp'
    if head[4:8] == b'ftyp':
        brand = head[8:12]
        if brand in (b'avif', b'avis'):
            return '.avif'
        if brand in (b'heic', b'heix', b'mif1'):
            return '.heic'
        return '.mov' if brand == b'qt  ' else '.mp4'
    for sig, ext in _MAGIC:
        if head.startswith(sig):
            return ext
    stripped = head.lstrip()[:200].lower()
    if stripped.startswith(b'<svg') or (stripped.startswith(b'<?xml') and b'<svg' in head.lower()):
        return '.svg'
    return ''


def is_image_name(name):
    return os.path.splitext(name or '')[1].lower() in IMAGE_EXTS


def is_url(name):
    return bool(name) and (name.startswith('http://') or name.startswith('https://'))


def optimize_image(data, ext):
    """تصغير الصور الكبيرة جداً وضغطها لتوفير المساحة وتسريع الموقع"""
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


@deconstructible
class LocalMediaStorage(FileSystemStorage):

    # ---------- حفظ ----------
    def generate_filename(self, filename):
        filename = norm(filename)
        if is_image_name(filename):
            # الصور تأخذ اسماً فريداً قصيراً
            folder = os.path.dirname(filename)
            ext = os.path.splitext(filename)[1].lower()
            filename = (folder + '/' if folder else '') + uuid.uuid4().hex + ext
        return norm(super().generate_filename(filename))

    def _save(self, name, content):
        name = norm(name)
        if is_image_name(name):
            try:
                content.seek(0)
            except Exception:
                pass
            data = content.read()
            if isinstance(data, str):
                data = data.encode()
            content = ContentFile(optimize_image(data, os.path.splitext(name)[1].lower()))
        saved = norm(super()._save(name, content))
        from .preview_state import note_new_file
        note_new_file(saved)        # ملف رُفع أثناء «المعاينة» — يُحذف لاحقاً تلقائياً
        return saved

    # ---------- قراءة ----------
    def url(self, name):
        if not name:
            return ''
        if is_url(name):
            return name
        return super().url(norm(name))

    def path(self, name):
        return super().path(norm(name))

    def exists(self, name):
        if is_url(name):
            return True
        if name and norm(name).startswith(DB_PREFIX):
            from .models import StoredFile
            return StoredFile.objects.filter(name=norm(name)).exists()
        return super().exists(norm(name))

    def _open(self, name, mode='rb'):
        if norm(name).startswith(DB_PREFIX):
            from .models import StoredFile
            obj = StoredFile.objects.get(name=norm(name))
            return ContentFile(bytes(obj.content), name=name)
        return super()._open(norm(name), mode)

    def size(self, name):
        if norm(name).startswith(DB_PREFIX):
            from .models import StoredFile
            return StoredFile.objects.filter(name=norm(name)).values_list('size', flat=True).first() or 0
        return super().size(norm(name))

    def delete(self, name):
        if not name or is_url(name):
            return
        if norm(name).startswith(DB_PREFIX):
            from .models import StoredFile
            StoredFile.objects.filter(name=norm(name)).delete()
            return
        try:
            super().delete(norm(name))
        except Exception:
            pass


# أسماء قديمة قد تكون مذكورة في إعدادات أو migrations — كلها تشير للتخزين المحلي الآن
HybridMediaStorage = LocalMediaStorage
AutoCloudinaryStorage = LocalMediaStorage
VideoCloudinaryStorage = LocalMediaStorage
RawCloudinaryStorage = LocalMediaStorage
