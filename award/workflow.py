"""
مراحل الطلب — كل تغيير حالة يمرّ من هنا: يُسجَّل في السجل ويُرسل الإشعار المناسب.

  مسودة → مُرسل → قيد التدقيق → (مطلوب تعديل ↺) → قيد التحكيم → مقبول / غير مقبول / فائز
"""
from datetime import timedelta

from django.utils import timezone

from .models import FINAL_STATUSES, StatusLog, Assignment
from .notify import notify, notify_staff

ADMIN_URL = '/admin/award/submission/{}/change/'

SCHOOL_MESSAGES = {
    'submitted': ('تم استلام طلبك {ref}', 'شكراً لكم. استلمنا طلب «{title}» وسيبدأ فريق الجائزة بتدقيقه قريباً.', 'success'),
    'screening': ('طلبك {ref} قيد التدقيق', 'بدأ فريق الجائزة تدقيق طلب «{title}» والتأكد من اكتمال متطلباته.', 'info'),
    'revision': ('مطلوب تعديل على طلبك {ref}', 'يرجى الدخول إلى حسابكم وتعديل طلب «{title}» ثم إعادة إرساله.', 'warning'),
    'judging': ('طلبك {ref} في مرحلة التحكيم', 'اجتاز طلب «{title}» مرحلة التدقيق وانتقل إلى لجنة التحكيم.', 'info'),
    'accepted': ('نتيجة طلبك {ref}: مقبول', 'يسعدنا إبلاغكم بقبول مشروع «{title}». سنتواصل معكم بالخطوات التالية.', 'success'),
    'rejected': ('نتيجة طلبك {ref}', 'نشكركم على مشاركتكم بمشروع «{title}». نأسف لعدم تأهله في هذه الدورة، ونتطلع لمشاركتكم القادمة.', 'info'),
    'winner': ('مبارك! مشروعكم {ref} من الفائزين', 'يسعدنا إبلاغكم بفوز مشروع «{title}» بجائزة انتصار عباس جردانة. سنتواصل معكم بتفاصيل الحفل.', 'success'),
}


def _school_message(sub, status, note=''):
    tpl = SCHOOL_MESSAGES.get(status)
    if not tpl or not sub.owner:
        return
    title, body, level = tpl
    body = body.format(title=sub.project_title, ref=sub.ref)
    if status == 'revision' and sub.revision_deadline:
        body += f"\nآخر موعد للتعديل: {timezone.localtime(sub.revision_deadline):%Y-%m-%d %H:%M}"
    note = note or (sub.school_note if status in ('revision', 'accepted', 'rejected', 'winner') else '')
    if note:
        body += f"\n\nملاحظة فريق الجائزة:\n{note}"
    notify(sub.owner, title.format(ref=sub.ref), body, sub.get_absolute_url(), level, button='عرض الطلب')


def change_status(sub, new, by=None, note='', notify_school=True, save=True):
    """تغيير حالة طلب مع السجل والإشعارات. يرجع True لو تغيّرت."""
    old = sub.status
    if old == new:
        return False
    sub.status = new
    now = timezone.now()
    if new == 'submitted' and not sub.sent_at:
        sub.sent_at = now
    if new == 'revision':
        days = (sub.cycle.revision_days if sub.cycle else 7) or 7
        if not sub.revision_deadline or sub.revision_deadline < now:
            sub.revision_deadline = now + timedelta(days=days)
        if note:
            sub.school_note = note
    if save:
        sub.save()
    StatusLog.objects.create(submission=sub, old_status=old, new_status=new, note=note, by=by)

    # إشعار المدرسة — النتائج النهائية تنتظر «نشر النتائج»
    if notify_school and not (new in FINAL_STATUSES and sub.results_hidden):
        _school_message(sub, new, note)

    # تنبيه الإدارة
    if new == 'submitted':
        again = old == 'revision'
        notify_staff(
            ('تعديل على الطلب ' if again else 'طلب جديد ') + sub.ref,
            f"{sub.school_name}\n«{sub.project_title}»\nالمسار: {sub.track or '—'}",
            ADMIN_URL.format(sub.pk))
    elif new == 'withdrawn':
        notify_staff(f'سحب الطلب {sub.ref}', f"{sub.school_name} سحبت طلب «{sub.project_title}».",
                     ADMIN_URL.format(sub.pk), email=False)
    return True


def publish_results(cycle, by=None):
    """نشر نتائج الدورة: إرسال إشعار النتيجة لكل مدرسة"""
    if cycle.results_published:
        already = True
    else:
        already = False
        cycle.results_published = True
        cycle.save(update_fields=['results_published'])
    count = 0
    if not already:
        for sub in cycle.submissions.filter(status__in=FINAL_STATUSES).select_related('owner', 'cycle'):
            _school_message(sub, sub.status)
            count += 1
    return count


def assign_judge(sub, judge, notify_judge=True):
    a, created = Assignment.objects.get_or_create(submission=sub, judge=judge)
    if created and notify_judge:
        notify(judge, f'طلب جديد للتحكيم: {sub.ref}',
               f"أُسند إليك تقييم مشروع «{sub.project_title}» — المسار: {sub.track or '—'}.",
               f'/judge/{a.pk}/', button='بدء التقييم')
    return a, created


def auto_assign(subs, per_submission=None):
    """توزيع متوازن: كل طلب يأخذ N محكّمين من مجاله، الأقل حملاً أولاً"""
    from django.contrib.auth.models import User
    from django.db.models import Count, Q
    judges = list(User.objects.filter(profile__role='judge', is_active=True)
                  .annotate(load=Count('assignments', filter=Q(assignments__completed_at__isnull=True)))
                  .prefetch_related('profile__judge_fields'))
    if not judges:
        return 0
    load = {j.pk: j.load for j in judges}
    made = 0
    for sub in subs:
        n = per_submission or (sub.cycle.judges_per_submission if sub.cycle else 2) or 2
        have = set(sub.assignments.values_list('judge_id', flat=True))
        pool = []
        for j in judges:
            if j.pk in have:
                continue
            fields = [f.pk for f in j.profile.judge_fields.all()]
            if fields and sub.field_id not in fields:
                continue
            pool.append(j)
        pool.sort(key=lambda j: load[j.pk])
        for j in pool[:max(0, n - len(have))]:
            assign_judge(sub, j)
            load[j.pk] += 1
            made += 1
    return made
