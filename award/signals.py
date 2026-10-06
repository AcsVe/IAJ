"""
تنظيف الصور المخزّنة في قاعدة البيانات:
عند استبدال صورة أو حذف السجل، تُحذف النسخة القديمة حتى لا تكبر القاعدة بدون داعي.
"""
from django.db import models
from django.db.models.signals import post_delete, pre_save

from .storage import DB_PREFIX


def _file_fields(instance):
    return [f for f in instance._meta.get_fields() if isinstance(f, models.FileField)]


def _remove(name):
    if name and name.startswith(DB_PREFIX):
        from .models import StoredFile
        StoredFile.objects.filter(name=name).delete()


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
    for model in app_config.get_models():
        if model.__name__ == 'StoredFile':
            continue
        if any(isinstance(f, models.FileField) for f in model._meta.get_fields()):
            pre_save.connect(cleanup_replaced_files, sender=model, dispatch_uid=f'iaj_clean_{model.__name__}')
            post_delete.connect(cleanup_deleted_files, sender=model, dispatch_uid=f'iaj_del_{model.__name__}')
