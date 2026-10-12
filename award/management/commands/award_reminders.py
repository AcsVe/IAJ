"""التذكيرات التلقائية (المسودات، مهلة الاستكمال، المحكّمون المتأخرون، تقارير الأثر) — تعمل تلقائياً مع الموقع كل 6 ساعات."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'إرسال التذكيرات المستحقة'

    def handle(self, *a, **o):
        from award import reminders
        r = reminders.run_all()
        self.stdout.write(f"مسودات {r['drafts']} · استكمال {r['revision']} · محكّمون {r['judges']} · أثر {r['impact']}")
