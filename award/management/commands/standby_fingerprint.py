"""بصمة البيانات: تتغيّر إذا أُضيف أو عُدّل أي سجل — يستخدمها الهاتف ليعرف هل سُجّل عليه شيء أثناء الطوارئ."""
import hashlib

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db.models import Max

SKIP = {'Session', 'LogEntry', 'StoredFile'}


class Command(BaseCommand):
    help = 'بصمة مختصرة لكل البيانات'

    def handle(self, *args, **opts):
        parts = []
        for model in apps.get_models():
            if model._meta.app_label not in ('award', 'auth') or model.__name__ in SKIP:
                continue
            qs = model.objects.all()
            fields = {f.name for f in model._meta.fields}
            agg = {'m': Max('pk')}
            for f in ('updated_at', 'modified_at', 'is_read', 'status'):
                if f in fields and f in ('updated_at', 'modified_at'):
                    agg['u'] = Max(f)
            vals = qs.aggregate(**agg)
            parts.append(f"{model.__name__}:{qs.count()}:{vals.get('m')}:{vals.get('u')}")
        self.stdout.write(hashlib.sha1('|'.join(parts).encode()).hexdigest()[:16])
