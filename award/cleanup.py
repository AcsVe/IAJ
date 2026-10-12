"""
حذف وتنظيف آمن: قبل أي حذف جماعي تُحفظ نسخة JSON من كل ما سيُحذف في backups/deleted/
(يمكن استرجاعها بـ:  python manage.py loaddata backups/deleted/<الملف>.json ).

• مسح بيانات التجربة/المحاكاة (كل ما عليه علامة «تجريبي» + دورات المحاكاة)
• حذف طلبات / حسابات مدارس / محكّمين محددين
• تنظيف دورة (المسودات، المسحوبة، أو كل الطلبات) وإعادة ضبط حالة النتائج
• حذف الحسابات غير المفعّلة القديمة والحسابات بلا طلبات
"""
import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core import serializers
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (Appeal, Assignment, AwardCycle, Certificate, ConflictDeclaration, Criterion, ImpactReport,
                     Invitation, Notification, Profile, Score, SimulationRun, StatusLog, Submission, SubmissionFile,
                     SubmissionMessage, Winner)


def backup_dir():
    d = os.path.join(settings.BASE_DIR, 'backups', 'deleted')
    os.makedirs(d, exist_ok=True)
    return d


def snapshot(label, querysets):
    """نسخة JSON مما سيُحذف — ترجع مسار الملف (أو '' إن لم يكن هناك شيء)"""
    objs = []
    for qs in querysets:
        objs.extend(list(qs))
    if not objs:
        return ''
    path = os.path.join(backup_dir(), f'{timezone.localtime():%Y-%m-%d_%H%M%S}-{label}.json')
    with open(path, 'w', encoding='utf-8') as fh:
        serializers.serialize('json', objs, stream=fh, ensure_ascii=False, indent=1)
    # الاحتفاظ بآخر 50 نسخة
    files = sorted(f for f in os.listdir(backup_dir()) if f.endswith('.json'))
    for old in files[:-50]:
        try:
            os.remove(os.path.join(backup_dir(), old))
        except OSError:
            pass
    return path


def _sub_related(subs):
    ids = list(subs.values_list('pk', flat=True))
    return [
        Submission.objects.filter(pk__in=ids),
        StatusLog.objects.filter(submission_id__in=ids),
        Assignment.objects.filter(submission_id__in=ids),
        Score.objects.filter(assignment__submission_id__in=ids),
        SubmissionFile.objects.filter(submission_id__in=ids),
        SubmissionMessage.objects.filter(submission_id__in=ids),
        Appeal.objects.filter(submission_id__in=ids),
        Certificate.objects.filter(submission_id__in=ids),
        Invitation.objects.filter(submission_id__in=ids),
        ImpactReport.objects.filter(submission_id__in=ids),
        ConflictDeclaration.objects.filter(submission_id__in=ids),
        Winner.objects.filter(submission_id__in=ids),
    ]


def _delete_files(subs):
    """ملفات الطلبات المحذوفة (المجلد الخاص) — حتى لا تبقى على القرص"""
    names = []
    for s in subs:
        for f in (s.document, s.attachment):
            if f:
                names.append(f)
        names += [x.file for x in s.files.all() if x.file]
        names += [m.attachment for m in s.messages.all() if m.attachment]
    for f in names:
        try:
            f.storage.delete(f.name)
        except Exception:   # noqa: BLE001
            pass


def delete_submissions(subs, label='submissions', files=True):
    """يحذف الطلبات وكل ما يتبعها (ومنها سجل الفائز المرتبط). يرجع (العدد، ملف النسخة)"""
    subs = Submission.objects.filter(pk__in=list(subs.values_list('pk', flat=True)))
    n = subs.count()
    if not n:
        return 0, ''
    path = snapshot(label, _sub_related(subs))
    items = list(subs.prefetch_related('files', 'messages'))
    with transaction.atomic():
        Winner.objects.filter(submission__in=subs).delete()
        subs.delete()
    if files:
        _delete_files(items)
    _clear_caches()
    return n, path


def delete_users(users, label='accounts', with_submissions=True):
    """حذف حسابات (مدارس/محكّمين) — مع طلباتها إن طُلب. لا يحذف المديرين أبداً."""
    users = User.objects.filter(pk__in=list(users.values_list('pk', flat=True))).exclude(is_superuser=True).exclude(is_staff=True)
    users = users.exclude(profile__role='manager', profile__is_simulation=False)
    ids = list(users.values_list('pk', flat=True))
    if not ids:
        return 0, 0, ''
    subs = Submission.objects.filter(owner_id__in=ids)
    qsets = [User.objects.filter(pk__in=ids), Profile.objects.filter(user_id__in=ids),
             ConflictDeclaration.objects.filter(judge_id__in=ids), Assignment.objects.filter(judge_id__in=ids),
             Score.objects.filter(assignment__judge_id__in=ids), Certificate.objects.filter(user_id__in=ids)]
    if with_submissions:
        qsets += _sub_related(subs)
    path = snapshot(label, qsets)
    n_subs = 0
    if with_submissions and subs.exists():
        n_subs, _ = delete_submissions(subs, label + '-subs')
    with transaction.atomic():
        n = User.objects.filter(pk__in=ids).delete()[1].get('auth.User', 0)
    _clear_caches()
    return n, n_subs, path


def simulation_counts():
    sim_cycles = AwardCycle.objects.filter(is_simulation=True)
    subs = Submission.objects.filter(Q(is_simulation=True) | Q(cycle__in=sim_cycles))
    users = User.objects.filter(profile__is_simulation=True)
    return {'cycles': sim_cycles.count(), 'submissions': subs.count(), 'users': users.count(),
            'schools': users.filter(profile__role='school').count(), 'judges': users.filter(profile__role='judge').count(),
            'runs': SimulationRun.objects.count()}


def clear_simulation(keep_reports=False):
    """مسح كل بيانات التجربة: الطلبات والحسابات المعلّمة «تجريبي» + دورات المحاكاة الآلية وما يتبعها"""
    sim_cycles = AwardCycle.objects.filter(is_simulation=True)
    subs = Submission.objects.filter(Q(is_simulation=True) | Q(cycle__in=sim_cycles))
    users = User.objects.filter(profile__is_simulation=True)
    path = snapshot('simulation', _sub_related(subs) + [users, Profile.objects.filter(user__in=users), sim_cycles,
                                                         Criterion.objects.filter(cycle__in=sim_cycles)])
    n_subs, _ = delete_submissions(subs, 'simulation-subs')
    n_users = delete_users(users, 'simulation-users', with_submissions=True)[0]
    Winner.objects.filter(cycle__in=sim_cycles).delete()
    n_cycles = sim_cycles.count()
    sim_cycles.delete()
    if not keep_reports:
        SimulationRun.objects.all().delete()
    _clear_caches()
    return {'submissions': n_subs, 'users': n_users, 'cycles': n_cycles, 'backup': path}


def cycle_cleanup(cycle, what='drafts', reset_results=False):
    """what: drafts | withdrawn | all"""
    subs = Submission.objects.filter(cycle=cycle)
    if what == 'drafts':
        subs = subs.filter(status='draft')
    elif what == 'withdrawn':
        subs = subs.filter(status='withdrawn')
    elif what != 'all':
        subs = subs.none()
    n, path = delete_submissions(subs, f'cycle{cycle.pk}-{what}')
    if reset_results:
        cycle.results_published = False
        cycle.results_published_at = None
        cycle.results_approved_at = None
        cycle.results_approved_by = None
        cycle.save(update_fields=['results_published', 'results_published_at', 'results_approved_at', 'results_approved_by'])
        Certificate.objects.filter(cycle=cycle).delete()
        Invitation.objects.filter(cycle=cycle).delete()
    return n, path


def stale_accounts(days=30, kind='inactive'):
    """kind: inactive = غير مفعّلة أقدم من N يوم | empty = مدارس بلا أي طلب أقدم من N يوم"""
    cutoff = timezone.now() - timedelta(days=days)
    qs = User.objects.filter(profile__role='school', date_joined__lt=cutoff, is_staff=False, is_superuser=False)
    if kind == 'inactive':
        qs = qs.filter(is_active=False)
    else:
        qs = qs.filter(submissions__isnull=True)
    return qs.distinct()


def _clear_caches():
    try:
        from .site_cache import clear_home_bundle
        clear_home_bundle()
    except Exception:   # noqa: BLE001
        pass
