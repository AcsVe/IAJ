"""
التذكيرات التلقائية (تعمل كل 6 ساعات مع الموقع، أو يدوياً: python manage.py award_reminders):

• المدارس: مسودات لم تُرسل قبل إغلاق التسجيل بـ 3 أيام ثم بيوم — ومهلة «الاستكمال» قبل انتهائها بيومين
• المحكّمون: تقييمات غير منتهية قبل موعد التحكيم بـ 3 أيام ثم بيوم (أو إن مضى على الإسناد 7 أيام بلا موعد)
• الفائزون: طلب تقرير متابعة الأثر بعد المدة المحددة في الدورة
كل تذكير يُرسل مرة واحدة فقط (جدول ReminderSent).
"""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Assignment, AwardCycle, ReminderSent, Submission
from .notify import notify


def _once(key, force_repeat=False):
    if force_repeat:
        return True
    try:
        with transaction.atomic():
            ReminderSent.objects.create(key=key[:120])
        return True
    except IntegrityError:
        return False


def _bucket(delta):
    return 1 if delta <= timedelta(days=1) else 3


def draft_reminders(cycle=None, force=False):
    cycle = cycle or AwardCycle.current()
    if not cycle:
        return 0
    now = timezone.now()
    left = cycle.closes_at - now
    if not force and not (cycle.is_open and left <= timedelta(days=3)):
        return 0
    b = _bucket(left)
    n = 0
    for s in Submission.objects.filter(cycle=cycle, status='draft', owner__isnull=False).select_related('owner'):
        if _once(f'draft:{s.pk}:{b}'):
            days = max(0, left.days)
            notify(s.owner, f'تذكير: طلبك {s.ref} لم يُرسل بعد',
                   f"طلب «{s.project_title}» ما زال مسودة. يُغلق التسجيل في {timezone.localtime(cycle.closes_at):%Y-%m-%d %H:%M}"
                   f"{' (خلال ' + str(days) + ' يوم)' if days else ' (اليوم)'}. أكملوا الطلب واضغطوا «إرسال الطلب».",
                   s.get_absolute_url(), 'warning', button='إكمال الطلب')
            n += 1
    return n


def revision_reminders(force=False):
    now = timezone.now()
    qs = Submission.objects.filter(status='revision', revision_deadline__isnull=False, owner__isnull=False)
    if not force:
        qs = qs.filter(revision_deadline__gt=now, revision_deadline__lte=now + timedelta(days=2))
    n = 0
    for s in qs.select_related('owner'):
        if _once(f'rev:{s.pk}:{s.revision_deadline:%Y%m%d%H}'):
            notify(s.owner, f'تذكير: مهلة استكمال الطلب {s.ref} تنتهي قريباً',
                   f"آخر موعد لتعديل طلب «{s.project_title}» وإعادة إرساله: {timezone.localtime(s.revision_deadline):%Y-%m-%d %H:%M}.",
                   s.get_absolute_url(), 'warning', button='تعديل الطلب')
            n += 1
    return n


def judge_reminders(cycle=None, force=False, judges=None, repeat=False):
    """تذكير المحكّمين المتأخرين — رسالة واحدة لكل محكّم بعدد طلباته المتبقية"""
    now = timezone.now()
    qs = Assignment.objects.filter(completed_at__isnull=True, submission__status='judging').select_related('submission__cycle', 'judge')
    if cycle:
        qs = qs.filter(submission__cycle=cycle)
    if judges is not None:
        qs = qs.filter(judge__in=judges)
    per = {}
    for a in qs:
        c = a.submission.cycle
        due = c.judging_closes_at if c else None
        if not force:
            if due:
                if due < now or due - now > timedelta(days=3):
                    continue
            elif now - a.assigned_at < timedelta(days=7):
                continue
        per.setdefault(a.judge_id, {'judge': a.judge, 'items': [], 'due': due})['items'].append(a)
    n = 0
    for d in per.values():
        due = d['due']
        key = f"judge:{d['judge'].pk}:{(due and _bucket(due - now)) or now.strftime('%Y%U')}:{cycle.pk if cycle else ''}"
        if not _once(key, force_repeat=repeat):
            continue
        k = len(d['items'])
        notify(d['judge'], f'تذكير: {k} طلب بانتظار تقييمك',
               f"لديك {k} طلب لم يكتمل تقييمه" + (f" — آخر موعد للتحكيم {timezone.localtime(due):%Y-%m-%d %H:%M}" if due else '') +
               ".\n" + '\n'.join(f"• {a.submission.ref}" for a in d['items'][:15]),
               '/judge/', 'warning', button='فتح لوحة المحكّم')
        Assignment.objects.filter(pk__in=[a.pk for a in d['items']]).update(reminded_at=now)
        n += 1
    return n


def impact_reminders(cycle=None, force=False):
    now = timezone.now()
    cycles = [cycle] if cycle else list(AwardCycle.objects.filter(results_published=True, impact_after_days__gt=0))
    n = 0
    for c in cycles:
        if not c.results_published_at or not c.impact_after_days:
            continue
        if not force and now < c.results_published_at + timedelta(days=c.impact_after_days):
            continue
        for s in c.submissions.filter(status='winner', owner__isnull=False, impact_reports__isnull=True).select_related('owner'):
            if _once(f'impact:{s.pk}'):
                notify(s.owner, f'حدّثونا عن أثر مشروعكم الفائز {s.ref}',
                       f"مضى وقت على فوز مشروع «{s.project_title}». يسعدنا معرفة ما تحقق بعده: تطبيقه، توسّعه، والمستفيدين منه.",
                       s.get_absolute_url() + '#impact', 'info', button='كتابة تقرير المتابعة')
                n += 1
    return n


def run_all():
    return {'drafts': draft_reminders(), 'revision': revision_reminders(), 'judges': judge_reminders(),
            'impact': impact_reminders()}
