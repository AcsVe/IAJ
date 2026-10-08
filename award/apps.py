from django.apps import AppConfig


class AwardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'award'

    def ready(self):
        from . import signals
        signals.connect(self)
        from django.db.models.signals import post_migrate
        from .roles import sync_role_groups
        post_migrate.connect(lambda sender, **kw: sync_role_groups() if sender.name == 'award' else None,
                             weak=False, dispatch_uid='iaj_sync_role_groups')
