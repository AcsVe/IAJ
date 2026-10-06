from django.apps import AppConfig


class AwardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'award'

    def ready(self):
        from . import signals
        signals.connect(self)
