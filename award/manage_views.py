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

from .models import (Announcement, AnnouncementMedia, Assignment, AwardCycle, Directorate, Field, Governorate,
                     JudgingCommittee, Notification, Profile, STATUS_CHOICES, Submission, SubmissionFile,
                     SubmissionMessage, Track, Winner, WinnerCategory)
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
    return {'nav': nav, 'mg_unread': unread, 'cycles': AwardCycle.objects.all(), 'cur_cycle': kw.pop('cycle', None), **kw}


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
    return render(request, 'award/manage/submissions.html', _ctx(
        request, 'subs', cycle=cycle, subs=qs[:1000], total=qs.count(), base_total=base.count(),
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
    ids = [int(i) for i in request.POST.getlist('ids') if i.isdigit()]
    subs = Submission.objects.filter(pk__in=ids).select_related('cycle', 'owner')
    act = request.POST.get('bulk')
    note = request.POST.get('note', '').strip()
    back = request.POST.get('back') or '/manage/submissions/'
    if not ids:
        messages.warning(request, 'لم تحدّد أي طلب.')
        return redirect(back)
    if act in STATUS:
        n = sum(1 for s in subs if workflow.change_status(s, act, by=request.user, note=note))
        messages.success(request, f'تم تغيير حالة {n} طلب إلى «{STATUS[act]}».')
    elif act == 'auto_assign':
        messages.success(request, f'تم إنشاء {workflow.auto_assign(subs)} إسناد للمحكّمين.')
    elif act == 'committee':
        com = JudgingCommittee.objects.filter(pk=request.POST.get('committee')).first()
        n = _assign_committee(com, subs) if com else 0
        messages.success(request, f'تم إسناد {n} تقييم لأعضاء اللجنة.')
    elif act == 'message' and note:
        for s in subs:
            _staff_message(request, s, note, None)
        messages.success(request, f'أُرسلت الرسالة إلى {subs.count()} مدرسة.')
    elif act == 'export':
        return _export(subs)
    elif act == 'delete':
        n = subs.count()
        subs.delete()
        messages.success(request, f'تم حذف {n} طلب.')
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
        elif act == 'delete_file':
            SubmissionFile.objects.filter(pk=request.POST.get('fid'), submission=sub).delete()
            messages.info(request, 'حُذف الملف.')
        return redirect(f'/manage/submissions/{sub.pk}/' + {'message': '#messages', 'assign': '#judging'}.get(act, ''))
    sub.messages.filter(from_staff=False, is_read=False).update(is_read=True)
    assigned = set(sub.assignments.values_list('judge_id', flat=True))
    return render(request, 'award/manage/submission_detail.html', _ctx(
        request, 'subs', cycle=sub.cycle, sub=sub, prof=getattr(sub.owner, 'profile', None) if sub.owner_id else None,
        files=sub.files.all(), msgs=sub.messages.select_related('sender'), msg_form=StaffMsgForm(),
        logs=sub.logs.select_related('by'), actions=ACTIONS,
        assignments=sub.assignments.select_related('judge').prefetch_related('scores__criterion'),
        judges=User.objects.filter(profile__role='judge', is_active=True).exclude(pk__in=assigned).order_by('first_name'),
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
    w, _ = Winner.objects.update_or_create(submission=sub, defaults=dict(
        school_name=sub.school_name, project_title=sub.project_title, rank=rank, category=cat,
        year=sub.cycle.year if sub.cycle else timezone.now().year, cycle=sub.cycle, is_active=True,
        description=sub.abstract[:1000]))
    workflow.change_status(sub, 'winner', by=request.user, note=request.POST.get('note', '').strip())
    messages.success(request, f'اعتُمد الطلب فائزاً بالمركز {rank}. يظهر في صفحة الفائزين' +
                     (' ويُبلَّغ عند نشر نتائج الدورة.' if sub.results_hidden else '.'))


# =====================================================
#   النتائج واعتماد الفائزين
# =====================================================
@manager_required
def results(request):
    cycle = _cycle(request)
    if request.method == 'POST' and cycle:
        if request.POST.get('act') == 'publish':
            n = workflow.publish_results(cycle, request.user)
            messages.success(request, f'نُشرت النتائج وأُرسل {n} إشعار.')
        elif request.POST.get('act') == 'winners':
            ids = request.POST.getlist('ids')
            for s in Submission.objects.filter(pk__in=ids, cycle=cycle):
                request.POST = request.POST.copy()
                request.POST['rank'] = request.POST.get(f'rank_{s.pk}') or 1
                request.POST['category'] = request.POST.get(f'cat_{s.pk}') or ''
                _make_winner(request, s)
        return redirect('/manage/results/')
    subs = Submission.objects.filter(status__in=('judging', 'accepted', 'winner')).select_related('track', 'field')
    if cycle:
        subs = subs.filter(cycle=cycle)
    subs = list(subs.prefetch_related('assignments__scores__criterion', 'assignments__judge'))
    rows = []
    for s in subs:
        recs = [a.recommendation for a in s.assignments.all() if a.is_done and a.recommendation]
        rows.append({'s': s, 'avg': s.avg_score, 'prog': s.judging_progress,
                     'strong': recs.count('strong'), 'yes': recs.count('yes'), 'no': recs.count('no'),
                     'winner': getattr(s, 'winner_entry', None)})
    rows.sort(key=lambda r: (str(r['s'].track or ''), -(r['avg'] or -1)))
    groups = {}
    for r in rows:
        groups.setdefault(str(r['s'].track or 'بدون مسار'), []).append(r)
    for g in groups.values():
        for i, r in enumerate(g, 1):
            r['suggest'] = i
    return render(request, 'award/manage/results.html', _ctx(
        request, 'results', cycle=cycle, groups=groups, total=len(rows),
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
    form = JudgeForm(request.POST or None)
    if request.method == 'POST':
        act = request.POST.get('act')
        if act == 'add' and form.is_valid():
            d = form.cleaned_data
            u = User.objects.create_user(username=d['email'], email=d['email'], first_name=d['name'][:150])
            u.set_unusable_password()
            u.save()
            p = Profile.objects.create(user=u, role='judge', contact_person=d['name'], phone=d['phone'], specialty=d['specialty'])
            p.judge_fields.set(d['fields'])
            _send_invite(request, u)
            messages.success(request, f'أُضيف المحكّم وأُرسلت دعوة إلى {u.email}.')
            return redirect('/manage/judges/')
        if act in ('toggle', 'invite'):
            u = get_object_or_404(User, pk=request.POST.get('uid'), profile__role='judge')
            if act == 'toggle':
                u.is_active = not u.is_active
                u.save(update_fields=['is_active'])
            else:
                _send_invite(request, u)
                messages.success(request, f'أُرسل رابط الدخول إلى {u.email}.')
            return redirect('/manage/judges/')
    js = (User.objects.filter(profile__role='judge').select_related('profile')
          .annotate(n=Count('assignments', distinct=True),
                    done=Count('assignments', filter=Q(assignments__completed_at__isnull=False), distinct=True))
          .prefetch_related('profile__judge_fields', 'committees').order_by('-is_active', 'first_name'))
    return render(request, 'award/manage/judges.html', _ctx(request, 'judges', judges=js, form=form))


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
    if request.method == 'POST':
        ids = request.POST.getlist('ids')
        body = request.POST.get('note', '').strip()
        title = request.POST.get('title', '').strip() or 'رسالة من إدارة الجائزة'
        if ids and body:
            for u in User.objects.filter(profile__pk__in=ids):
                notify(u, title, body, '/portal/')
            messages.success(request, f'أُرسلت الرسالة إلى {len(ids)} مدرسة.')
        else:
            messages.warning(request, 'حدّد مدارس واكتب الرسالة.')
        return redirect(request.get_full_path())
    qs = Profile.objects.filter(role='school').select_related('user', 'governorate', 'directorate').annotate(
        n=Count('user__submissions', filter=~Q(user__submissions__status='draft')))
    base = qs
    f = request.GET
    if f.get('gov', '').isdigit():
        qs = qs.filter(governorate_id=f['gov'])
    if f.get('dir', '').isdigit():
        qs = qs.filter(directorate_id=f['dir'])
    gc = dict(base.order_by().values('governorate').annotate(c=Count('pk')).values_list('governorate', 'c'))
    return render(request, 'award/manage/schools.html', _ctx(
        request, 'schools', items=qs.order_by('-created_at'), total=base.count(), f=f,
        govs=[(g, gc.get(g.pk, 0)) for g in Governorate.objects.all() if gc.get(g.pk)],
        dirs=_with_counts(Directorate.objects.all(), dict(base.order_by().values('directorate').annotate(c=Count('pk')).values_list('directorate', 'c')))))
