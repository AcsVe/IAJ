"""محاكاة دورة كاملة ببيانات وهمية + تقرير نجح/فشل، أو مسح كل بيانات التجربة.

    python manage.py simulate_cycle                 # تشغيل (10 مدارس، 6 محكّمين)
    python manage.py simulate_cycle --schools 20
    python manage.py simulate_cycle --clear         # مسح كل بيانات التجربة/المحاكاة (مع نسخة احتياطية JSON)
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'محاكاة دورة جائزة كاملة أو مسح بيانات التجربة'

    def add_arguments(self, p):
        p.add_argument('--clear', action='store_true', help='مسح كل بيانات التجربة والمحاكاة')
        p.add_argument('--schools', type=int, default=10)
        p.add_argument('--judges', type=int, default=6)
        p.add_argument('--seed', type=int, default=None)
        p.add_argument('--yes', action='store_true', help='بدون سؤال تأكيد عند المسح')

    def handle(self, *a, **o):
        from award import cleanup
        from award.audit import audit
        if o['clear']:
            c = cleanup.simulation_counts()
            self.stdout.write(f"بيانات التجربة: {c['submissions']} طلب · {c['schools']} مدرسة · {c['judges']} محكّم · "
                              f"{c['cycles']} دورة محاكاة · {c['runs']} تقرير")
            if not o['yes'] and input('اكتب YES لمسحها كلها: ').strip() != 'YES':
                self.stdout.write('تم الإلغاء')
                return
            r = cleanup.clear_simulation()
            audit(None, 'مسح بيانات التجربة', 'سطر الأوامر', str(r))
            self.stdout.write(self.style.SUCCESS(
                f"✓ مُسح: {r['submissions']} طلب، {r['users']} حساب، {r['cycles']} دورة. نسخة مما حُذف: {r['backup'] or '—'}"))
            return
        from award.simulation import Sim
        run = Sim(n_schools=o['schools'], n_judges=o['judges'], seed=o['seed']).run()
        self.stdout.write(run.report)
        style = self.style.SUCCESS if not run.failed else self.style.ERROR
        self.stdout.write(style(f'\n{run.passed} نجح · {run.failed} فشل'))
