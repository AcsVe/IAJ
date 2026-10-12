"""
صفحة إدارة الجائزة (/manage/) — للإداري المسؤول عن الجائزة (نوع الحساب: إداري الجائزة) أو مديري الموقع.
استقبال الطلبات ومتابعتها، المراسلة وطلب الاستكمال، القبول والتعليق والرفض، لجان التحكيم والمحكّمون،
اعتماد الفائزين بناءً على التحكيم، والإعلانات (بطاقات نصية ووسائط).
"""
import csv
from functools import wraps

from django import forms
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Count, Q, Avg
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (Announcement, AnnouncementMedia, Appeal, Assignment, AwardCycle, ConflictDeclaration,
                     DecisionTemplate, Directorate, Field, Governorate, JudgingCommittee, Notification, PortalSetting,
                     Profile, STAGE_CHOICES, STATUS_CHOICES, Submission, SubmissionFile, SubmissionMessage, Track,
                     Winner, WinnerCategory)
from .audit import audit
from .notify import notify
from .portal_views import is_manager
from . import workflow

STATUS = dict(STATUS_CHOICES)
ACTIONS = [  # (الحالة، نص الزر، أيقونة، لون)
    ('screening', 'قيد التدقيق', 'fa-magnifying-glass', 'info'),
    ('revision', 'طلب استكمال / تعديل', 'fa-pen-to-square', 'warning'),
    ('on_hold', 'تعليق', 'fa-pause', 'secondary'),
    ('judging', 'تحويل للتحكيم', 'fa-scale-balanced', 'purple'),
    ('accepted', 'قبول', 'fa-check', 'success'),
    ('rejected', 'رفض', 'fa-xmark', 'danger'),
]
NEEDS_REASON = ('revision', 'on_hold', 'rejected')   # يُطلب سبب يصل للمدرسة


def _templates():
    out = {}
    for t in DecisionTemplate.objects.all():
        out.setdefault(t.status, []).append({'t': t.title, 'b': t.body})
    return out


def manager_required(view):
    @wraps(view)
    def wrapper(request, *a, **kw):
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.path}')
        if not is_manager(request.user):
            raise Http404
        return view(request, *a, **kw)
    return wrapper


def _cycle(request):
    cid = request.GET.get('cycle') or request.session.get('mg_cycle')
    if cid == 'all':
        request.session['mg_cycle'] = 'all'
        return None
    c = AwardCycle.objects.filter(pk=cid).first() if str(cid).isdigit() else None
    c = c or AwardCycle.current() or AwardCycle.objects.first()
    if c:
        request.session['mg_cycle'] = c.pk
    return c


def _ctx(request, nav, **kw):
    unread = SubmissionMessage.objects.filter(from_staff=False, is_read=False).count()
    return {'nav': nav, 'mg_unread': unread, 'cycles': AwardCycle.objects.all(), 'cur_cycle': kw.pop('cycle', None),
            'mg_appeals': Appeal.objects.filter(status='open').count(), 'mg_test_mode': PortalSetting.get().test_mode, **kw}


# =====================================================
#   لوحة المتابعة
# =====================================================
@manager_required
def dashboard(request):
    cycle = _cycle(request)
    subs = Submission.objects.exclude(status='draft')
    if cycle:
        subs = subs.filter(cycle=cycle)
    by_status = dict(subs.values('status').annotate(n=Count('pk')).values_list('status', 'n'))
    a = Assignment.objects.filter(submission__in=subs)
    return render(request, 'award/manage/dashboard.html', _ctx(
        request, 'dash', cycle=cycle,
        total=sum(by_status.values()),
        stats=[(k, STATUS[k], by_status.get(k, 0)) for k, _ in STATUS_CHOICES if k != 'draft'],
        drafts=Submission.objects.filter(status='draft', **({'cycle': cycle} if cycle else {})).count(),
        schools=Profile.objects.filter(role='school').count(),
        judges=Profile.objects.filter(role='judge', user__is_active=True).count(),
        a_total=a.count(), a_done=a.filter(completed_at__isnull=False).count(),
        recent=subs.select_related('track').order_by('-sent_at')[:8],
        inbox=SubmissionMessage.objects.filter(from_staff=False).select_related('submission').order_by('-created_at')[:8],
    ))


# =====================================================
#   الطلبات
# =====================================================
def _filtered_subs(request, cycle):
    qs = Submission.objects.select_related('track', 'field', 'owner__profile__governorate', 'owner__profile__directorate', 'cycle')
    if cycle:
        qs = qs.filter(cycle=cycle)
    if not request.GET.get('drafts'):
        qs = qs.exclude(status='draft')
    base = qs
    f = request.GET
    if f.get('status'):
        qs = qs.filter(status=f['status'])
    if f.get('stage') in dict(STAGE_CHOICES):
        qs = qs.filter(judging_stage=f['stage'])
    if f.get('test') == '1':
        qs = qs.filter(is_simulation=True)
    elif f.get('test') == '0':
        qs = qs.filter(is_simulation=False)
    for key, field in (('track', 'track_id'), ('field', 'field_id'), ('gov', 'owner__profile__governorate_id'),
                       ('dir', 'owner__profile__directorate_id')):
        if f.get(key, '').isdigit():
            qs = qs.filter(**{field: int(f[key])})
    q = (f.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(ref__icontains=q) | Q(school_name__icontains=q) | Q(project_title__icontains=q) |
                       Q(contact_person__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
    return base, qs


def _counts(qs, field):
    return dict(qs.values(field).annotate(n=Count('pk')).values_list(field, 'n'))


@manager_required
def submissions(request):
    cycle = _cycle(request)
    if request.method == 'POST':
        return _bulk(request, cycle)
    base, qs = _filtered_subs(request, cycle)
    st_counts = _counts(base.order_by(), 'status')
    qs = qs.prefetch_related('assignments__scores__criterion').order_by('-sent_at', '-submitted_at')
    subs = list(qs[:1000])
    if request.GET.get('flag') == 'disc':
        subs = [x for x in subs if x.has_discrepancy]
    return render(request, 'award/manage/submissions.html', _ctx(
        request, 'subs', cycle=cycle, subs=subs, total=len(subs), base_total=base.count(),
        stages=STAGE_CHOICES, tpl=_templates(), needs_reason=NEEDS_REASON,
        n_test=base.filter(is_simulation=True).count(),
        status_tabs=[(k, STATUS[k], st_counts.get(k, 0)) for k, _ in STATUS_CHOICES if st_counts.get(k) or k == request.GET.get('status')],
        tracks=_with_counts(Track.objects.filter(is_active=True), _counts(base.order_by(), 'track_id')),
        fields_=_with_counts(Field.objects.all(), _counts(base.order_by(), 'field_id')),
        govs=_with_counts(Governorate.objects.all(), _counts(base.order_by(), 'owner__profile__governorate_id')),
        dirs=_with_counts(Directorate.objects.all(), _counts(base.order_by(), 'owner__profile__directorate_id')),
        committees=JudgingCommittee.objects.all(), actions=ACTIONS, f=request.GET,
    ))


def _with_counts(qs, counts):
    return [(o, counts.get(o.pk, 0)) for o in qs if counts.get(o.pk)]


def _bulk(request, cycle):
    from . import cleanup
    ids = [int(i) for i in request.POST.getlist('ids') if i.isdigit()]
    subs = Submission.objects.filter(pk__in=ids).select_related('cycle', 'owner')
    act = request.POST.get('bulk')
    note = request.POST.get('note', '').strip()
    back = request.POST.get('back') or '/manage/submissions/'
    if not ids:
        messages.warning(request, 'لم تحدّد أي طلب.')
        return redirect(back)
    if act in STATUS:
        if act in NEEDS_REASON and not note:
            messages.error(request, f'«{STATUS[act]}» يحتاج سبباً يصل للمدرسة — اختر من القوالب أو اكتب الملاحظة.')
            return redirect(back)
        n = sum(1 for s in subs if workflow.change_status(s, act, by=request.user, note=note))
        if act in ('accepted', 'rejected'):
            audit(request, f'قرار جماعي: {STATUS[act]}', f'{n} طلب', ', '.join(s.ref for s in subs))
        messages.success(request, f'تم تغيير حالة {n} طلب إلى «{STATUS[act]}».' +
                         (' تصل النتيجة للمدارس عند نشر النتائج.' if act in ('accepted', 'rejected', 'winner') else ''))
    elif act and act.startswith('stage_') and act[6:] in dict(STAGE_CHOICES):
        n = workflow.set_stage(subs, act[6:], by=request.user)
        messages.success(request, f'نُقل {n} طلب إلى «{dict(STAGE_CHOICES)[act[6:]]}». استخدم «توزيع تلقائي» لإسناد محكّمي هذه المرحلة.')
    elif act == 'auto_assign':
        messages.success(request, f'تم إنشاء {workflow.auto_assign(subs)} إسناد للمحكّمين (مع استبعاد تعارض المصالح).')
    elif act == 'extra_judge':
        messages.success(request, f'أُسند {workflow.auto_assign(subs, extra=1)} محكّم إضافي.')
    elif act == 'committee':
        com = JudgingCommittee.objects.filter(pk=request.POST.get('committee')).first()
        n = _assign_committee(com, subs) if com else 0
        messages.success(request, f'تم إسناد {n} تقييم لأعضاء اللجنة.')
    elif act == 'message' and note:
        for s in subs:
            _staff_message(request, s, note, None)
        messages.success(request, f'أُرسلت الرسالة إلى {subs.count()} مدرسة.')
    elif act == 'export':
        audit(request, 'تصدير Excel', f'{subs.count()} طلب')
        from .export_xlsx import response
        return response(cycle, subs, f'submissions-{timezone.localdate()}.xlsx')
    elif act == 'export_csv':
        return _export(subs)
    elif act in ('mark_test', 'unmark_test'):
        n = subs.update(is_simulation=act == 'mark_test')
        messages.success(request, f'{"عُلّم" if act == "mark_test" else "أُزيلت علامة التجربة عن"} {n} طلب' +
                         (' — تُحذف مع «مسح بيانات التجربة».' if act == 'mark_test' else '.'))
    elif act == 'delete':
        n, path = cleanup.delete_submissions(subs, 'manual-delete')
        audit(request, 'حذف طلبات', f'{n} طلب', path)
        messages.success(request, f'تم حذف {n} طلب. نسخة احتياطية مما حُذف: {path.split("backups")[-1] if path else "—"}')
    else:
        messages.warning(request, 'اختر إجراءً (والرسالة تحتاج نصاً).')
    return redirect(back)


def _assign_committee(com, subs):
    n = 0
    for s in subs:
        for j in com.members.filter(is_active=True):
            if workflow.assign_judge(s, j)[1]:
                n += 1
    return n


def _export(subs):
    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="submissions-{timezone.localdate()}.csv"'
    resp.write('﻿')
    w = csv.writer(resp)
    w.writerow(['رقم الطلب', 'المدرسة', 'المحافظة', 'المديرية', 'ضابط الارتباط', 'الهاتف', 'البريد', 'المجال', 'المسار',
                'المشروع', 'المشرف', 'الطلبة', 'الحالة', 'تاريخ الإرسال', 'التحكيم', 'المتوسط', 'عدد الملفات'])
    for s in subs.select_related('owner__profile__governorate', 'owner__profile__directorate').prefetch_related('assignments__scores__criterion', 'files'):
        pr = getattr(s.owner, 'profile', None) if s.owner_id else None
        w.writerow([s.ref, s.school_name, getattr(pr, 'governorate', '') or '', getattr(pr, 'directorate', '') or '',
                    s.contact_person, s.phone, s.email, s.field or '', s.track or '', s.project_title, s.supervisor,
                    ' | '.join(s.team_members.splitlines()), STATUS.get(s.status, s.status),
                    timezone.localtime(s.sent_at).strftime('%Y-%m-%d %H:%M') if s.sent_at else '',
                    s.judging_progress, s.avg_score if s.avg_score is not None else '', s.files.count()])
    return resp


def _staff_message(request, sub, body, attachment):
    SubmissionMessage.objects.create(submission=sub, sender=request.user, from_staff=True, body=body,
                                     attachment=attachment or '')
    if sub.owner:
        notify(sub.owner, f'رسالة من إدارة الجائزة — {sub.ref}', body, sub.get_absolute_url() + '#messages',
               button='عرض الرسالة')


class StaffMsgForm(forms.Form):
    body = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'توجيهات، طلب نواقص، استفسار…'}))
    attachment = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-control'}))


@manager_required
def submission_detail(request, pk):
    sub = get_object_or_404(Submission.objects.select_related('track', 'field', 'cycle', 'owner__profile__governorate',
                                                              'owner__profile__area', 'owner__profile__directorate'), pk=pk)
    if request.method == 'POST':
        act = request.POST.get('act')
        note = request.POST.get('note', '').strip()
        if act == 'status':
            new = request.POST.get('status')
            if new in NEEDS_REASON and not note and request.POST.get('notify', '1'):
                messages.error(request, f'«{STATUS[new]}» يحتاج سبباً يصل للمدرسة — اختر من القوالب أو اكتب الملاحظة.')
                return redirect(f'/manage/submissions/{sub.pk}/')
            if new in STATUS:
                if request.POST.get('deadline'):
                    from django.utils.dateparse import parse_datetime
                    dl = parse_datetime(request.POST['deadline'])
                    if dl:
                        sub.revision_deadline = timezone.make_aware(dl) if timezone.is_naive(dl) else dl
                workflow.change_status(sub, new, by=request.user, note=note,
                                       notify_school=bool(request.POST.get('notify', '1')))
                messages.success(request, f'الحالة الآن: {STATUS[new]}' + (' (النتيجة تُرسل للمدرسة عند نشر النتائج)' if sub.results_hidden else ''))
        elif act == 'message':
            form = StaffMsgForm(request.POST, request.FILES)
            if form.is_valid():
                _staff_message(request, sub, form.cleaned_data['body'], form.cleaned_data.get('attachment'))
                messages.success(request, 'أُرسلت الرسالة للمدرسة.')
        elif act == 'internal':
            sub.internal_note = request.POST.get('internal_note', '')
            sub.save(update_fields=['internal_note', 'updated_at'])
            messages.success(request, 'حُفظت الملاحظات الداخلية.')
        elif act == 'assign':
            for jid in request.POST.getlist('judges'):
                j = User.objects.filter(pk=jid, profile__role='judge').first()
                if j:
                    workflow.assign_judge(sub, j)
            com = JudgingCommittee.objects.filter(pk=request.POST.get('committee') or 0).first()
            if com:
                _assign_committee(com, [sub])
            messages.success(request, 'تم الإسناد وأُبلغ المحكّمون.')
        elif act == 'unassign':
            Assignment.objects.filter(pk=request.POST.get('aid'), submission=sub).delete()
            messages.info(request, 'أُلغي الإسناد.')
        elif act == 'reopen':
            Assignment.objects.filter(pk=request.POST.get('aid'), submission=sub).update(completed_at=None)
            messages.info(request, 'أُعيد فتح التقييم للمحكّم.')
        elif act == 'winner':
            _make_winner(request, sub)
        elif act == 'stage' and request.POST.get('stage') in dict(STAGE_CHOICES):
            workflow.set_stage([sub], request.POST['stage'], by=request.user)
            messages.success(request, f'مرحلة التحكيم: {sub.get_judging_stage_display()}')
        elif act == 'extra_judge':
            n = workflow.auto_assign([sub], extra=1)
            messages.success(request, 'أُسند محكّم إضافي.' if n else 'لا يوجد محكّم متاح (بدون تعارض ومن نفس المجال).')
        elif act == 'conflict':
            j = User.objects.filter(pk=request.POST.get('judge'), profile__role='judge').first()
            if j:
                whole = request.POST.get('scope') == 'school'
                _c, removed = workflow.declare_conflict(j, None if whole else sub, sub.school_name if whole else '',
                                                        note or 'سجّلته الإدارة', by=request.user)
                messages.success(request, f'سُجّل تعارض المصالح لـ {j.get_full_name() or j.email}' +
                                 (f' وأُلغي {len(removed)} إسناد.' if removed else '.'))
        elif act == 'del_conflict':
            ConflictDeclaration.objects.filter(pk=request.POST.get('cid')).delete()
            messages.info(request, 'حُذف إقرار التعارض.')
        elif act == 'test':
            sub.is_simulation = not sub.is_simulation
            sub.save(update_fields=['is_simulation'])
            messages.info(request, 'عُلّم الطلب «تجريبي».' if sub.is_simulation else 'أُزيلت علامة التجربة.')
        elif act == 'appeal':
            ap = get_object_or_404(Appeal, pk=request.POST.get('aid'), submission=sub)
            if request.POST.get('status') in ('accepted', 'rejected') and note:
                workflow.respond_appeal(ap, request.POST['status'], note, request.user)
                audit(request, 'رد على اعتراض', sub.ref, ap.get_status_display())
                messages.success(request, 'أُرسل رد اللجنة للمدرسة.')
        elif act == 'delete_sub':
            from . import cleanup
            ref = sub.ref
            n, path = cleanup.delete_submissions(Submission.objects.filter(pk=sub.pk), f'delete-{ref}')
            audit(request, 'حذف طلب', ref, path)
            messages.success(request, f'حُذف الطلب {ref} (نسخة احتياطية محفوظة).')
            return redirect('/manage/submissions/')
        elif act == 'delete_file':
            SubmissionFile.objects.filter(pk=request.POST.get('fid'), submission=sub).delete()
            messages.info(request, 'حُذف الملف.')
        return redirect(f'/manage/submissions/{sub.pk}/' + {'message': '#messages', 'assign': '#judging', 'extra_judge': '#judging',
                                                            'conflict': '#judging', 'appeal': '#appeals'}.get(act, ''))
    sub.messages.filter(from_staff=False, is_read=False).update(is_read=True)
    assigned = set(sub.assignments.filter(stage=sub.judging_stage).values_list('judge_id', flat=True))
    cmap = workflow.conflict_map()
    judges = list(User.objects.filter(profile__role='judge', is_active=True).exclude(pk__in=assigned)
                  .select_related('profile').order_by('first_name'))
    for j in judges:
        j.conflict = workflow.has_conflict(j, sub, cmap)
    return render(request, 'award/manage/submission_detail.html', _ctx(
        request, 'subs', cycle=sub.cycle, sub=sub, prof=getattr(sub.owner, 'profile', None) if sub.owner_id else None,
        files=sub.files.all(), msgs=sub.messages.select_related('sender'), msg_form=StaffMsgForm(),
        logs=sub.logs.select_related('by'), actions=ACTIONS,
        assignments=sub.assignments.select_related('judge').prefetch_related('scores__criterion'),
        judges=judges, tpl=_templates(), needs_reason=NEEDS_REASON, stages=STAGE_CHOICES,
        conflicts=ConflictDeclaration.objects.filter(Q(submission=sub) | Q(school_name__iexact=sub.school_name)).select_related('judge'),
        appeals=sub.appeals.select_related('by', 'responded_by'),
        committees=JudgingCommittee.objects.all(), categories=WinnerCategory.objects.filter(is_active=True),
        winner=getattr(sub, 'winner_entry', None),
        prev_next=_prev_next(sub),
    ))


def _prev_next(sub):
    qs = Submission.objects.exclude(status='draft').filter(cycle=sub.cycle).order_by('pk')
    return (qs.filter(pk__lt=sub.pk).last(), qs.filter(pk__gt=sub.pk).first())


def _make_winner(request, sub):
    try:
        rank = int(request.POST.get('rank') or 1)
    except ValueError:
        rank = 1
    cat = WinnerCategory.objects.filter(pk=request.POST.get('category') or 0).first()
    was_approved = bool(sub.cycle and sub.cycle.is_approved)
    workflow.make_winner(sub, rank=rank, category=cat, by=request.user, note=request.POST.get('note', '').strip())
    audit(request, 'اعتماد فائز', sub.ref, f'المركز {rank}')
    messages.success(request, f'اعتُمد {sub.ref} فائزاً بالمركز {rank}' +
                     (' — يُبلَّغ عند نشر نتائج الدورة.' if sub.results_hidden else '.') +
                     (' تنبيه: أُلغي اعتماد اللجنة بسبب التعديل — أعيدوا الاعتماد قبل النشر.' if was_approved and not sub.cycle.results_published else ''))


# =====================================================
#   النتائج واعتماد الفائزين
# =====================================================
@manager_required
def results(request):
    cycle = _cycle(request)
    if request.method == 'POST' and cycle:
        act = request.POST.get('act')
        if act == 'approve':
            workflow.approve_results(cycle, request.user, request.POST.get('note', '').strip())
            audit(request, 'اعتماد النتائج', str(cycle), request.POST.get('note', ''))
            messages.success(request, 'سُجّل اعتماد اللجنة للنتائج. يمكنكم النشر الآن.')
        elif act == 'unapprove':
            workflow.reset_approval(cycle)
            audit(request, 'إلغاء اعتماد النتائج', str(cycle))
            messages.info(request, 'أُلغي الاعتماد.')
        elif act == 'publish':
            try:
                n = workflow.publish_results(cycle, request.user)
                audit(request, 'نشر النتائج', str(cycle), f'{n} إشعار')
                messages.success(request, f'نُشرت النتائج وأُرسل {n} إشعار.')
            except workflow.NotApproved:
                messages.error(request, 'لا يمكن النشر قبل تسجيل اعتماد لجنة الجائزة.')
        elif act == 'winners':
            ids = request.POST.getlist('ids')
            for s in Submission.objects.filter(pk__in=ids, cycle=cycle).select_related('cycle'):
                request.POST = request.POST.copy()
                request.POST['rank'] = request.POST.get(f'rank_{s.pk}') or 1
                request.POST['category'] = request.POST.get(f'cat_{s.pk}') or ''
                _make_winner(request, s)
        elif act == 'export':
            audit(request, 'تصدير Excel للدورة', str(cycle))
            from .export_xlsx import response
            return response(cycle)
        return redirect('/manage/results/')
    subs = Submission.objects.filter(status__in=('judging', 'accepted', 'winner')).select_related('track', 'field', 'cycle')
    if cycle:
        subs = subs.filter(cycle=cycle)
    subs = list(subs.prefetch_related('assignments__scores__criterion', 'assignments__judge'))
    groups = {}
    for s in subs:
        groups.setdefault(str(s.track or 'بدون مسار'), []).append(s)
    out = {}
    disc = 0
    for track in sorted(groups):
        rows = workflow.rank_rows(groups[track], cycle.tie_break if cycle else 'criterion')
        for r in rows:
            s = r['s']
            recs = [a.recommendation for a in s.stage_done() if a.recommendation]
            r.update(prog=s.judging_progress, strong=recs.count('strong'), yes=recs.count('yes'), no=recs.count('no'),
                     winner=getattr(s, 'winner_entry', None), disc=s.has_discrepancy, spread=s.score_spread)
            disc += r['disc']
        out[track] = rows
    pending = Assignment.objects.filter(submission__in=subs, completed_at__isnull=True).count()
    return render(request, 'award/manage/results.html', _ctx(
        request, 'results', cycle=cycle, groups=out, total=len(subs), disc=disc, pending=pending,
        n_winners=Winner.objects.filter(cycle=cycle).count() if cycle else 0,
        categories=WinnerCategory.objects.filter(is_active=True)))


# =====================================================
#   المحكّمون ولجان التحكيم
# =====================================================
class JudgeForm(forms.Form):
    name = forms.CharField(label='الاسم', max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label='البريد الإلكتروني', widget=forms.EmailInput(attrs={'class': 'form-control', 'dir': 'ltr'}))
    phone = forms.CharField(label='الهاتف', max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}))
    specialty = forms.CharField(label='التخصص / الجهة', max_length=255, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    fields = forms.ModelMultipleChoiceField(Field.objects.all(), label='مجالات التحكيم', required=False,
                                            widget=forms.CheckboxSelectMultiple)

    def clean_email(self):
        e = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(Q(email__iexact=e) | Q(username__iexact=e)).exists():
            raise forms.ValidationError('يوجد حساب بهذا البريد.')
        return e


@manager_required
def judges(request):
    from .admin_portal import _send_invite
    from . import reminders, cleanup
    cycle = _cycle(request)
    form = JudgeForm(request.POST or None)
    if request.method == 'POST':
        act = request.POST.get('act')
        uid = request.POST.get('uid')
        if request.POST.get('row'):   # أزرار داخل الجدول: «invite:12»
            act, _, uid = request.POST['row'].partition(':')
        if act == 'add' and form.is_valid():
            d = form.cleaned_data
            u = User.objects.create_user(username=d['email'], email=d['email'], first_name=d['name'][:150])
            u.set_unusable_password()
            u.save()
            p = Profile.objects.create(user=u, role='judge', contact_person=d['name'], phone=d['phone'], specialty=d['specialty'],
                                       is_simulation=PortalSetting.get().test_mode)
            p.judge_fields.set(d['fields'])
            _send_invite(request, u)
            messages.success(request, f'أُضيف المحكّم وأُرسلت دعوة إلى {u.email}.')
            return redirect('/manage/judges/')
        if act in ('toggle', 'invite'):
            u = get_object_or_404(User, pk=uid, profile__role='judge')
            if act == 'toggle':
                u.is_active = not u.is_active
                u.save(update_fields=['is_active'])
            else:
                _send_invite(request, u)
                messages.success(request, f'أُرسل رابط الدخول إلى {u.email}.')
            return redirect('/manage/judges/')
        if act == 'deadline' and cycle:
            from django.utils.dateparse import parse_datetime
            raw = request.POST.get('judging_closes_at') or ''
            dl = parse_datetime(raw) if raw else None
            cycle.judging_closes_at = (timezone.make_aware(dl) if dl and timezone.is_naive(dl) else dl)
            cycle.save(update_fields=['judging_closes_at'])
            audit(request, 'موعد التحكيم', str(cycle), raw or 'بدون موعد')
            messages.success(request, 'حُفظ موعد التحكيم.' if dl else 'أُلغي قفل التحكيم (بدون موعد).')
            return redirect('/manage/judges/')
        ids = [int(i) for i in request.POST.getlist('ids') if i.isdigit()]
        sel = User.objects.filter(pk__in=ids, profile__role='judge')
        if not ids:
            messages.warning(request, 'حدّد محكّمين أولاً.')
        elif act == 'remind':
            n = reminders.judge_reminders(cycle, force=True, judges=sel, repeat=True)
            messages.success(request, f'أُرسل تذكير إلى {n} محكّم لديه طلبات غير منتهية.' if n else 'لا توجد طلبات متبقية لدى المحددين.')
        elif act == 'message':
            body = request.POST.get('note', '').strip()
            for u in sel:
                notify(u, request.POST.get('title', '').strip() or 'رسالة من إدارة الجائزة', body, '/judge/')
            messages.success(request, f'أُرسلت الرسالة إلى {sel.count()} محكّم.')
        elif act in ('activate', 'deactivate'):
            n = sel.update(is_active=act == 'activate')
            messages.success(request, f'{"فُعّل" if act == "activate" else "عُطّل"} {n} حساب.')
        elif act in ('mark_test', 'unmark_test'):
            n = Profile.objects.filter(user__in=sel).update(is_simulation=act == 'mark_test')
            messages.success(request, f'تم تحديث {n} حساب.')
        elif act == 'delete':
            n, _ns, path = cleanup.delete_users(sel, 'judges', with_submissions=False)
            audit(request, 'حذف محكّمين', f'{n} حساب', path)
            messages.success(request, f'حُذف {n} محكّم مع تقييماتهم (نسخة احتياطية محفوظة).')
        return redirect('/manage/judges/')
    now = timezone.now()
    flt = Q(assignments__submission__cycle=cycle) if cycle else Q()
    js = (User.objects.filter(profile__role='judge').select_related('profile')
          .annotate(n=Count('assignments', filter=flt, distinct=True),
                    done=Count('assignments', filter=flt & Q(assignments__completed_at__isnull=False), distinct=True),
                    conflicts_n=Count('conflicts', distinct=True))
          .prefetch_related('profile__judge_fields', 'committees').order_by('-is_active', 'first_name'))
    js = list(js)
    for j in js:
        j.todo = j.n - j.done
        j.pct = round(j.done / j.n * 100) if j.n else 0
        j.last_reminded = Assignment.objects.filter(judge=j, reminded_at__isnull=False).order_by('-reminded_at').values_list('reminded_at', flat=True).first()
    late = cycle and cycle.judging_closes_at and cycle.judging_closes_at < now
    return render(request, 'award/manage/judges.html', _ctx(
        request, 'judges', cycle=cycle, judges=js, form=form, late=late,
        totals={'n': sum(j.n for j in js), 'done': sum(j.done for j in js), 'todo': sum(j.todo for j in js),
                'active': sum(1 for j in js if j.is_active), 'with_todo': sum(1 for j in js if j.todo)}))


class CommitteeForm(forms.ModelForm):
    class Meta:
        model = JudgingCommittee
        fields = ['name', 'cycle', 'fields', 'tracks', 'members', 'chair', 'notes']
        widgets = {'name': forms.TextInput(attrs={'class': 'form-control'}), 'cycle': forms.Select(attrs={'class': 'form-select'}),
                   'chair': forms.Select(attrs={'class': 'form-select'}),
                   'fields': forms.CheckboxSelectMultiple, 'tracks': forms.CheckboxSelectMultiple,
                   'members': forms.CheckboxSelectMultiple, 'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2})}


@manager_required
def committees(request, pk=None):
    obj = get_object_or_404(JudgingCommittee, pk=pk) if pk else None
    if request.method == 'POST' and request.POST.get('act') == 'delete' and obj:
        obj.delete()
        messages.info(request, 'حُذفت اللجنة.')
        return redirect('/manage/committees/')
    if request.method == 'POST' and request.POST.get('act') == 'assign_all' and obj:
        subs = [s for s in Submission.objects.filter(status='judging', cycle=obj.cycle or AwardCycle.current()) if obj.covers(s)]
        n = _assign_committee(obj, subs)
        messages.success(request, f'أُسند {n} تقييم لأعضاء «{obj.name}» على {len(subs)} طلب في مرحلة التحكيم.')
        return redirect(f'/manage/committees/{obj.pk}/')
    form = CommitteeForm(request.POST or None, instance=obj)
    form.fields['members'].queryset = User.objects.filter(profile__role='judge', is_active=True)
    form.fields['chair'].queryset = User.objects.filter(profile__role='judge', is_active=True)
    form.fields['tracks'].queryset = Track.objects.filter(is_active=True)
    if request.method == 'POST' and form.is_valid():
        c = form.save()
        messages.success(request, f'حُفظت اللجنة «{c.name}».')
        return redirect(f'/manage/committees/{c.pk}/')
    items = JudgingCommittee.objects.annotate(n=Count('members', distinct=True)).prefetch_related('fields', 'tracks', 'members')
    return render(request, 'award/manage/committees.html', _ctx(request, 'committees', items=items, form=form, obj=obj))


# =====================================================
#   الإعلانات
# =====================================================
class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'kind', 'body', 'link_url', 'link_text', 'cycle', 'publish_date', 'show_on_home', 'pinned', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}), 'kind': forms.Select(attrs={'class': 'form-select'}),
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
            'link_url': forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr', 'placeholder': '/news/ أو https://…'}),
            'link_text': forms.TextInput(attrs={'class': 'form-control'}), 'cycle': forms.Select(attrs={'class': 'form-select'}),
            'publish_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }


@manager_required
def announcements(request, pk=None):
    from .portal_forms import MultipleFileField
    obj = get_object_or_404(Announcement, pk=pk) if pk else None
    if request.method == 'POST' and obj and request.POST.get('act') == 'delete':
        obj.delete()
        messages.info(request, 'حُذف الإعلان.')
        return redirect('/manage/announcements/')
    if request.method == 'POST' and obj and request.POST.get('act') == 'del_media':
        AnnouncementMedia.objects.filter(pk=request.POST.get('mid'), announcement=obj).delete()
        return redirect(f'/manage/announcements/{obj.pk}/')
    form = AnnouncementForm(request.POST or None, request.FILES or None, instance=obj)
    form.fields['media_files'] = MultipleFileField(label='صور / فيديو (يمكن اختيار عدة ملفات)', required=False)
    form.fields['youtube'] = forms.CharField(label='روابط يوتيوب (كل رابط في سطر)', required=False,
                                             widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'dir': 'ltr'}))
    if request.method == 'POST' and form.is_valid():
        a = form.save(commit=False)
        if not a.created_by_id:
            a.created_by = request.user
        a.save()
        start = a.media.count()
        for i, f in enumerate(form.cleaned_data.get('media_files') or []):
            AnnouncementMedia.objects.create(announcement=a, file=f, order=start + i)
        for line in (form.cleaned_data.get('youtube') or '').splitlines():
            if line.strip():
                AnnouncementMedia.objects.create(announcement=a, youtube_url=line.strip(), order=999)
        if a.media.exists() and a.kind == 'text':
            a.kind = 'media'
            a.save(update_fields=['kind'])
        from .site_cache import clear_home_bundle
        clear_home_bundle()
        messages.success(request, 'حُفظ الإعلان.')
        return redirect(f'/manage/announcements/{a.pk}/')
    items = Announcement.objects.annotate(n=Count('media')).select_related('cycle')
    return render(request, 'award/manage/announcements.html', _ctx(request, 'ann', items=items, form=form, obj=obj))


# =====================================================
#   المدارس
# =====================================================
@manager_required
def schools(request):
    from . import cleanup
    if request.method == 'POST':
        ids = request.POST.getlist('ids')
        act = request.POST.get('act') or 'message'
        body = request.POST.get('note', '').strip()
        title = request.POST.get('title', '').strip() or 'رسالة من إدارة الجائزة'
        profs = Profile.objects.filter(pk__in=[i for i in ids if i.isdigit()], role='school')
        users = User.objects.filter(profile__in=profs)
        if not ids:
            messages.warning(request, 'حدّد مدارس أولاً.')
        elif act == 'message':
            if body:
                for u in users:
                    notify(u, title, body, '/portal/')
                messages.success(request, f'أُرسلت الرسالة إلى {users.count()} مدرسة.')
            else:
                messages.warning(request, 'اكتب نص الرسالة.')
        elif act in ('mark_test', 'unmark_test'):
            on = act == 'mark_test'
            n = profs.update(is_simulation=on)
            Submission.objects.filter(owner__in=users).update(is_simulation=on)
            messages.success(request, f'{"عُلّمت" if on else "أُزيلت علامة التجربة عن"} {n} مدرسة مع طلباتها.')
        elif act == 'activate':
            n = users.update(is_active=True)
            messages.success(request, f'فُعّل {n} حساب.')
        elif act in ('delete', 'delete_keep'):
            n, ns, path = cleanup.delete_users(users, 'schools', with_submissions=act == 'delete')
            audit(request, 'حذف مدارس', f'{n} حساب / {ns} طلب', path)
            messages.success(request, f'حُذف {n} حساب مدرسة' + (f' و{ns} طلب' if ns else '') + ' (نسخة احتياطية محفوظة).')
        return redirect(request.get_full_path())
    qs = Profile.objects.filter(role='school').select_related('user', 'governorate', 'directorate').annotate(
        n=Count('user__submissions', filter=~Q(user__submissions__status='draft')),
        n_all=Count('user__submissions'))
    base = qs
    f = request.GET
    if f.get('gov', '').isdigit():
        qs = qs.filter(governorate_id=f['gov'])
    if f.get('dir', '').isdigit():
        qs = qs.filter(directorate_id=f['dir'])
    if f.get('show') == 'inactive':
        qs = qs.filter(user__is_active=False)
    elif f.get('show') == 'empty':
        qs = qs.filter(n_all=0)
    elif f.get('show') == 'test':
        qs = qs.filter(is_simulation=True)
    gc = dict(base.order_by().values('governorate').annotate(c=Count('pk')).values_list('governorate', 'c'))
    return render(request, 'award/manage/schools.html', _ctx(
        request, 'schools', items=qs.order_by('-created_at'), total=base.count(), f=f,
        n_inactive=base.filter(user__is_active=False).count(), n_empty=base.filter(n_all=0).count(),
        n_test=base.filter(is_simulation=True).count(),
        govs=[(g, gc.get(g.pk, 0)) for g in Governorate.objects.all() if gc.get(g.pk)],
        dirs=_with_counts(Directorate.objects.all(), dict(base.order_by().values('directorate').annotate(c=Count('pk')).values_list('directorate', 'c')))))
