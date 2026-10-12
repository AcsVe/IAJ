"""
مراحل الطلب — كل تغيير حالة يمرّ من هنا: يُسجَّل في السجل ويُرسل الإشعار المناسب.

  مسودة → مُرسل → قيد التدقيق → (مطلوب تعديل ↺) → قيد التحكيم → مقبول / غير مقبول / فائز
"""
from datetime import timedelta

from django.utils import timezone

from .models import FINAL_STATUSES, StatusLog, Assignment, ConflictDeclaration
from .notify import notify, notify_staff

ADMIN_URL = '/admin/award/submission/{}/change/'

SCHOOL_MESSAGES = {
    'submitted': ('تم استلام طلبك {ref}', 'شكراً لكم. استلمنا طلب «{title}» وسيبدأ فريق الجائزة بتدقيقه قريباً.', 'success'),
    'screening': ('طلبك {ref} قيد التدقيق', 'بدأ فريق الجائزة تدقيق طلب «{title}» والتأكد من اكتمال متطلباته.', 'info'),
    'revision': ('مطلوب استكمال/تعديل على طلبك {ref}', 'يرجى الدخول إلى حسابكم واستكمال أو تعديل طلب «{title}» ثم إعادة إرساله.', 'warning'),
    'on_hold': ('طلبك {ref} معلّق مؤقتاً', 'تم تعليق طلب «{title}» مؤقتاً لدى فريق الجائزة.', 'warning'),
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
    note = note or (sub.school_note if status in ('revision', 'on_hold', 'accepted', 'rejected', 'winner') else '')
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
    if new in ('on_hold',) and note:
        sub.school_note = note
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

    # تنبيه الإدارة (ليس لطلبات التجربة)
    if sub.is_simulation:
        return True
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


class NotApproved(Exception):
    pass


def approve_results(cycle, by=None, note=''):
    cycle.results_approved_at = timezone.now()
    cycle.results_approved_by = by
    cycle.results_approval_note = note
    cycle.save(update_fields=['results_approved_at', 'results_approved_by', 'results_approval_note'])


def reset_approval(cycle):
    """أي تعديل على الفائزين بعد الاعتماد (وقبل النشر) يلغي الاعتماد"""
    from .models import AwardCycle
    if not cycle:
        return False
    n = AwardCycle.objects.filter(pk=cycle.pk, results_approved_at__isnull=False, results_published=False).update(
        results_approved_at=None, results_approved_by=None)
    if n:
        cycle.results_approved_at = None
        cycle.results_approved_by = None
    return bool(n)


def publish_results(cycle, by=None, force=False):
    """نشر نتائج الدورة: إرسال إشعار النتيجة لكل مدرسة (بعد اعتماد اللجنة إن كان مطلوباً)"""
    if cycle.require_approval and not cycle.results_approved_at and not cycle.results_published and not force:
        raise NotApproved('اعتماد اللجنة مطلوب قبل النشر')
    if cycle.results_published:
        already = True
    else:
        already = False
        cycle.results_published = True
        cycle.results_published_at = timezone.now()
        cycle.save(update_fields=['results_published', 'results_published_at'])
    count = 0
    if not already:
        for sub in cycle.submissions.filter(status__in=FINAL_STATUSES).select_related('owner', 'cycle'):
            _school_message(sub, sub.status)
            count += 1
    return count


# =====================================================
#   تعارض المصالح
# =====================================================
def conflict_map(judge_ids=None):
    """{judge_id: (set(submission_ids), set(school names lower))}"""
    qs = ConflictDeclaration.objects.all()
    if judge_ids is not None:
        qs = qs.filter(judge_id__in=judge_ids)
    out = {}
    for c in qs.values('judge_id', 'submission_id', 'school_name'):
        subs, schools = out.setdefault(c['judge_id'], (set(), set()))
        if c['submission_id']:
            subs.add(c['submission_id'])
        if c['school_name'].strip():
            schools.add(c['school_name'].strip().lower())
    return out


def has_conflict(judge, sub, cmap=None):
    cmap = conflict_map([judge.pk]) if cmap is None else cmap
    subs, schools = cmap.get(judge.pk, (set(), set()))
    return sub.pk in subs or (sub.school_name or '').strip().lower() in schools


def declare_conflict(judge, sub=None, school_name='', reason='', by=None):
    """تسجيل تعارض + إلغاء أي إسناد غير منتهٍ يتعارض معه"""
    c = ConflictDeclaration.objects.create(judge=judge, submission=sub, school_name=school_name.strip(),
                                           reason=reason, created_by=by or judge)
    qs = Assignment.objects.filter(judge=judge, completed_at__isnull=True)
    qs = qs.filter(submission=sub) if sub else qs.filter(submission__school_name__iexact=school_name.strip())
    removed = list(qs.select_related('submission'))
    qs.delete()
    if removed and not all(a.submission.is_simulation for a in removed):
        notify_staff(f'تعارض مصالح — {judge.get_full_name() or judge.email}',
                     'أعلن المحكّم تعارض مصالح، وأُلغي إسناده على: ' + '، '.join(a.submission.ref for a in removed) +
                     (f"\nالسبب: {reason}" if reason else '') + '\nأسندوا محكّماً بديلاً من صفحة الطلب أو «توزيع تلقائي».',
                     '/manage/submissions/', email=False)
    return c, removed


# =====================================================
#   الإسناد
# =====================================================
def assign_judge(sub, judge, notify_judge=True, stage=None, check_conflict=True):
    stage = stage or sub.judging_stage or 'initial'
    if check_conflict and has_conflict(judge, sub):
        return None, False
    a, created = Assignment.objects.get_or_create(submission=sub, judge=judge, stage=stage)
    if created and notify_judge:
        notify(judge, f'طلب جديد للتحكيم: {sub.ref}',
               f"أُسند إليك تقييم مشروع «{sub.project_title}» — المسار: {sub.track or '—'}." +
               (f"\nآخر موعد للتحكيم: {timezone.localtime(sub.cycle.judging_closes_at):%Y-%m-%d %H:%M}"
                if sub.cycle and sub.cycle.judging_closes_at else ''),
               f'/judge/{a.pk}/', button='بدء التقييم')
    return a, created


def _judge_pool():
    from django.contrib.auth.models import User
    from django.db.models import Count, Q
    return list(User.objects.filter(profile__role='judge', is_active=True)
                .annotate(load=Count('assignments', filter=Q(assignments__completed_at__isnull=True)))
                .select_related('profile').prefetch_related('profile__judge_fields'))


def auto_assign(subs, per_submission=None, extra=0):
    """توزيع متوازن: كل طلب يأخذ N محكّمين من مجاله في مرحلته الحالية، الأقل حملاً أولاً.
    • يستبعد من لديه تعارض مصالح، ومن قيّم الطلب في مرحلة سابقة إن وُجد غيره.
    • طلبات التجربة تأخذ محكّمي التجربة فقط، والطلبات الحقيقية المحكّمين الحقيقيين فقط.
    • extra=1: محكّم إضافي فوق الموجود (عند تباين الدرجات)."""
    judges = _judge_pool()
    if not judges:
        return 0
    load = {j.pk: j.load for j in judges}
    cmap = conflict_map([j.pk for j in judges])
    made = 0
    for sub in subs:
        stage = sub.judging_stage or 'initial'
        n = per_submission or (sub.cycle.judges_per_submission if sub.cycle else 2) or 2
        rows = list(sub.assignments.values_list('judge_id', 'stage'))
        have = {j for j, st in rows if st == stage}
        before = {j for j, st in rows if st != stage}
        need = extra if extra else max(0, n - len(have))
        if need <= 0:
            continue
        pool = []
        for j in judges:
            if j.pk in have or j.profile.is_simulation != sub.is_simulation or has_conflict(j, sub, cmap):
                continue
            fields = [f.pk for f in j.profile.judge_fields.all()]
            if fields and sub.field_id not in fields:
                continue
            pool.append(j)
        pool.sort(key=lambda j: (j.pk in before, load[j.pk]))
        for j in pool[:need]:
            if assign_judge(sub, j, stage=stage, check_conflict=False)[1]:
                load[j.pk] += 1
                made += 1
    return made


def check_discrepancy(sub):
    """بعد اكتمال تقييمات المرحلة: إن تباينت الدرجات كثيراً يُسند محكّم إضافي مرة واحدة"""
    stage = sub.judging_stage
    items = [a for a in sub.assignments.all() if a.stage == stage]
    if not items or any(not a.is_done for a in items) or not sub.has_discrepancy:
        return 0
    n = (sub.cycle.judges_per_submission if sub.cycle else 2) or 2
    if len(items) > n:   # أُضيف محكّم إضافي من قبل
        return 0
    made = auto_assign([sub], extra=1)
    if made and not sub.is_simulation:
        notify_staff(f'تباين في درجات {sub.ref}',
                     f"الفرق بين المحكّمين {sub.score_spread} درجة — أُسند الطلب تلقائياً لمحكّم إضافي.",
                     f'/manage/submissions/{sub.pk}/#judging', email=False)
    return made


def set_stage(subs, stage, by=None):
    """نقل طلبات إلى مرحلة تحكيم (القائمة القصيرة / النهائي) — التقييمات السابقة تبقى في السجل"""
    n = 0
    for s in subs:
        if s.judging_stage != stage:
            old = s.get_judging_stage_display()
            s.judging_stage = stage
            s.save(update_fields=['judging_stage', 'updated_at'])
            StatusLog.objects.create(submission=s, old_status=s.status, new_status=s.status, by=by,
                                     note=f'مرحلة التحكيم: {old} ← {s.get_judging_stage_display()}')
            n += 1
    return n


# =====================================================
#   الترتيب وكسر التعادل
# =====================================================
def _tie_values(sub):
    done = sub.stage_done()
    if not done:
        return 0, 0, 0
    # المعيار الأكبر وزناً: متوسط نسبته
    top = None
    for a in done:
        for sc in a.scores.all():
            if top is None or float(sc.criterion.weight or 1) > float(top.weight or 1):
                top = sc.criterion
    crit = 0
    if top:
        vals = [float(sc.value) / (top.max_score or 1) for a in done for sc in a.scores.all() if sc.criterion_id == top.pk]
        crit = sum(vals) / len(vals) if vals else 0
    strong = sum(1 for a in done if a.recommendation == 'strong')
    low = min(a.total for a in done)
    return crit, strong, low


def rank_rows(subs, tie_break='criterion'):
    """صفوف مرتبة حسب المتوسط ثم قاعدة كسر التعادل. كل صف: s, avg, tie (هل تعادل مع غيره), tb"""
    order = {'criterion': (0, 1, 2), 'strong': (1, 0, 2), 'min': (2, 0, 1)}.get(tie_break, (0, 1, 2))
    rows = []
    for s in subs:
        tv = _tie_values(s)
        rows.append({'s': s, 'avg': s.avg_score, 'tb': tuple(tv[i] for i in order)})
    rows.sort(key=lambda r: (-(r['avg'] if r['avg'] is not None else -1), tuple(-x for x in r['tb']),
                             r['s'].sent_at or r['s'].submitted_at))
    for i, r in enumerate(rows):
        same = [o for o in rows if o is not r and o['avg'] is not None and o['avg'] == r['avg']]
        r['tie'] = bool(same)
        r['suggest'] = i + 1
    return rows


# =====================================================
#   ما بعد النتائج
# =====================================================
def can_appeal(sub):
    c = sub.cycle
    if not c or not c.appeal_until or sub.status not in ('accepted', 'rejected'):
        return False
    return timezone.now() <= c.appeal_until and not sub.appeals.exists()


def feedback(sub):
    """تقرير التغذية الراجعة: متوسط كل معيار (نسبة مئوية) بدون أسماء المحكّمين"""
    done = sub.stage_done()
    per = {}
    for a in done:
        for sc in a.scores.all():
            c = sc.criterion
            per.setdefault(c.pk, {'c': c, 'vals': []})['vals'].append(float(sc.value))
    rows = []
    for d in sorted(per.values(), key=lambda d: (d['c'].order, d['c'].pk)):
        avg = sum(d['vals']) / len(d['vals'])
        rows.append({'name': d['c'].name, 'avg': round(avg, 1), 'max': d['c'].max_score,
                     'pct': round(avg / (d['c'].max_score or 1) * 100)})
    comments = [a.comment for a in done if a.comment.strip()] if sub.cycle and sub.cycle.share_judge_comments else []
    return {'rows': rows, 'avg': sub.avg_score, 'n': len(done), 'comments': comments,
            'best': max(rows, key=lambda r: r['pct']) if rows else None,
            'weak': min(rows, key=lambda r: r['pct']) if rows else None}


def issue_certificates(cycle, judges=True):
    """شهادات الفوز والمشاركة (والشكر للمحكّمين) — لا تتكرر"""
    from .models import Certificate
    made = 0
    subs = cycle.submissions.exclude(status__in=('draft', 'withdrawn')).filter(status__in=FINAL_STATUSES)
    for s in subs.select_related('cycle'):
        kind = 'winner' if s.status == 'winner' else 'participation'
        w = getattr(s, 'winner_entry', None)
        _c, created = Certificate.objects.get_or_create(
            cycle=cycle, submission=s, kind=kind,
            defaults={'recipient': s.school_name, 'title': s.project_title, 'rank': w.rank if w and kind == 'winner' else None})
        made += created
    if judges:
        from django.contrib.auth.models import User
        for u in User.objects.filter(assignments__submission__cycle=cycle, assignments__completed_at__isnull=False).distinct():
            _c, created = Certificate.objects.get_or_create(
                cycle=cycle, user=u, kind='judge',
                defaults={'recipient': u.get_full_name() or u.email, 'title': 'المشاركة في لجان تحكيم الجائزة'})
            made += created
    return made


def send_invitations(cycle, statuses=('winner',)):
    from .models import Invitation
    made = 0
    for s in cycle.submissions.filter(status__in=statuses).select_related('owner'):
        inv, created = Invitation.objects.get_or_create(
            cycle=cycle, submission=s, defaults={'user': s.owner, 'name': s.school_name, 'email': s.email})
        if created:
            made += 1
            when = (f"\nالموعد: {timezone.localtime(cycle.ceremony_date):%Y-%m-%d %H:%M}" if cycle.ceremony_date else '') + \
                   (f"\nالمكان: {cycle.ceremony_place}" if cycle.ceremony_place else '')
            if s.owner:
                notify(s.owner, f'دعوة لحضور حفل تكريم {cycle.short_name or cycle.name}',
                       f"يسرّنا دعوتكم لحضور حفل تكريم الفائزين بجائزة انتصار عباس جردانة.{when}\nيرجى تأكيد الحضور من الرابط.",
                       f'/rsvp/{inv.code}/', 'success', button='تأكيد الحضور')
    return made


def make_winner(sub, rank=1, category=None, by=None, note=''):
    """اعتماد طلب فائزاً (يظهر في صفحة الفائزين بعد النشر) — يلغي اعتماد اللجنة إن كان مسجلاً"""
    from .models import Winner
    w, _ = Winner.objects.update_or_create(submission=sub, defaults=dict(
        school_name=sub.school_name, project_title=sub.project_title, rank=rank, category=category,
        year=sub.cycle.year if sub.cycle else timezone.now().year, cycle=sub.cycle, is_active=True,
        description=sub.abstract[:1000]))
    change_status(sub, 'winner', by=by, note=note)
    reset_approval(sub.cycle)
    return w


def respond_appeal(ap, status, response, by=None):
    ap.status = status
    ap.response = response
    ap.responded_by = by
    ap.responded_at = timezone.now()
    ap.save()
    sub = ap.submission
    if sub.owner:
        notify(sub.owner, f'الرد على اعتراضكم — {sub.ref}',
               f"{ap.get_status_display()}\n\n{response}", sub.get_absolute_url() + '#results',
               'success' if status == 'accepted' else 'info', button='عرض الطلب')
