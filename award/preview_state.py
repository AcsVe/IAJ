"""حالة «المعاينة قبل الحفظ» — خاصة بالطلب الحالي فقط (thread-local).

أثناء المعاينة: لا يُقرأ ولا يُكتب الكاش المشترك، ولا تُحذف ملفات قديمة،
حتى لا يرى الزوار أي شيء من التعديل غير المحفوظ."""
import threading

from django.core.cache.backends.locmem import LocMemCache

_state = threading.local()


def active():
    return getattr(_state, 'on', False)


def set_active(on):
    _state.on = on
    if on:
        _state.new_files = []


def note_new_file(name):
    if active():
        _state.new_files.append(name)


def new_files():
    return list(getattr(_state, 'new_files', []))


class PreviewAwareLocMemCache(LocMemCache):
    """نفس كاش الذاكرة العادي، لكنه يتجاهل القراءة والكتابة أثناء المعاينة"""

    def get(self, key, default=None, version=None):
        return default if active() else super().get(key, default, version)

    def set(self, key, value, timeout=None, version=None):
        if not active():
            super().set(key, value, timeout, version)

    def add(self, key, value, timeout=None, version=None):
        return False if active() else super().add(key, value, timeout, version)

    def get_many(self, keys, version=None):
        return {} if active() else super().get_many(keys, version)

    def set_many(self, data, timeout=None, version=None):
        return [] if active() else super().set_many(data, timeout, version)
