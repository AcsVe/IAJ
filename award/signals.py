"""
تنظيف الملفات المرفوعة:
عند استبدال صورة أو حذف السجل، تُحذف النسخة القديمة حتى لا تكبر القاعدة بدون داعي.
"""
from django.db import models
from django.db.models.signals import post_delete, pre_save



def _file_fields(instance):
    return [f for f in instance._meta.get_fields() if isinstance(f, models.FileField)]


def _remove(name):
    """حذف الملف القديم (من المجلد أو من القاعدة) — الروابط الخارجية لا تُلمس"""
    if not name or name.startswith('http://') or name.startswith('https://'):
        return
    from .preview_state import active
    if active():          # المعاينة قبل الحفظ: لا نحذف شيئاً
        return
    from django.core.files.storage import default_storage
    default_storage.delete(name)


def cleanup_replaced_files(sender, instance, raw=False, **kwargs):
    if raw or not instance.pk:
        return
    fields = _file_fields(instance)
    if not fields:
        return
    old = sender.objects.filter(pk=instance.pk).values(*[f.attname for f in fields]).first()
    if not old:
        return
    for f in fields:
        old_name = old.get(f.attname) or ''
        new_name = getattr(instance, f.attname)
        new_name = getattr(new_name, 'name', new_name) or ''
        if old_name != new_name:
            _remove(old_name)


def cleanup_deleted_files(sender, instance, **kwargs):
    for f in _file_fields(instance):
        val = getattr(instance, f.attname)
        _remove(getattr(val, 'name', val) or '')


def connect(app_config):
    from django.db.models.signals import post_save
    from .site_cache import CACHED_MODELS, clear_site_bundle, HOME_MODELS, clear_home_bundle
    for model in app_config.get_models():
        if model.__name__ in CACHED_MODELS:
            post_save.connect(clear_site_bundle, sender=model, dispatch_uid=f'iaj_cache_save_{model.__name__}')
            post_delete.connect(clear_site_bundle, sender=model, dispatch_uid=f'iaj_cache_del_{model.__name__}')
        if model.__name__ in HOME_MODELS:
            post_save.connect(clear_home_bundle, sender=model, dispatch_uid=f'iaj_home_save_{model.__name__}')
            post_delete.connect(clear_home_bundle, sender=model, dispatch_uid=f'iaj_home_del_{model.__name__}')
        if model.__name__ == 'StoredFile':
            continue
        if any(isinstance(f, models.FileField) for f in model._meta.get_fields()):
            pre_save.connect(cleanup_replaced_files, sender=model, dispatch_uid=f'iaj_clean_{model.__name__}')
            post_delete.connect(cleanup_deleted_files, sender=model, dispatch_uid=f'iaj_del_{model.__name__}')
