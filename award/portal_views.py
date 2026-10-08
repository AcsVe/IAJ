"""
بوابة التسجيل: حسابات المدارس، الطلبات، المحكّمون، الإشعارات.
"""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode, url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import (AwardCycle, Assignment, Criterion, Notification, Profile, Score, Submission,
                     EDITABLE_STATUSES, RECOMMEND_CHOICES)
from .notify import send_email, notify_staff
from .portal_forms import SchoolSignupForm, ProfileForm, PortalSubmissionForm
from . import workflow

User = get_user_model()


def _verify_required():
    return settings.EMAIL_ENABLED and getattr(settings, 'REQUIRE_EMAIL_VERIFICATION', True)


def _role(user):
    if not user.is_authenticated:
        return ''
    prof = getattr(user, 'profile', None)
    if prof:
        return prof.role
    return 'staff' if user.is_staff else ''


def _safe_next(request, default='/portal/'):
    nxt = request.POST.get('next') or request.GET.get('next') or ''
    if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}, require_https=request.is_secure()):
        return nxt
    return default


def _home_for(user):
    role = _role(user)
    if role == 'judge':
        return '/judge/'
    if role == 'staff':
        return '/admin/'
    return '/portal/'


# =====================================================
#   الحسابات
# =====================================================
def _send_activation(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    url = f'/accounts/activate/{uid}/{token}/'
    send_email(user.email, 'تفعيل حسابك في جائزة انتصار عباس جردانة',
               f"مرحباً {user.first_name or ''}،\nشكراً لتسجيلكم. اضغطوا الزر لتفعيل الحساب ثم تقديم مشاريعكم.\n"
               f"الرابط صالح لمدة 3 أيام.", url, 'تفعيل الحساب')


def signup(request):
    if request.user.is_authenticated:
        return redirect(_home_for(request.user))
    nxt = _safe_next(request, '/portal/')
    form = SchoolSignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        if _verify_required():
            _send_activation(request, user)
            from email.utils import parseaddr
            return render(request, 'award/portal/check_email.html',
                          {'email': user.email, 'sender': parseaddr(settings.DEFAULT_FROM_EMAIL)[1]})
        user.is_active = True
        user.save(update_fields=['is_active'])
        login(request, user, backend='award.auth.EmailOrUsernameBackend')
        messages.success(request, 'تم إنشاء حسابكم بنجاح. يمكنكم الآن تقديم مشروعكم.')
        return redirect(nxt)
    return render(request, 'award/portal/signup.html', {'form': form, 'next': nxt})


def activate(request, uidb64, token):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except Exception:
        user = None
    if user and default_token_generator.check_token(user, token):
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])
        login(request, user, backend='award.auth.EmailOrUsernameBackend')
        messages.success(request, 'تم تفعيل حسابكم. أهلاً بكم!')
        return redirect(_home_for(user))
    return render(request, 'award/portal/activate_failed.html', status=400)


def resend_activation(request):
    sent = False
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=False).first()
        if user and _verify_required():
            _send_activation(request, user)
        sent = True   # نفس الرسالة دائماً حتى لا نكشف أي البريدات مسجّلة
    return render(request, 'award/portal/resend.html', {'sent': sent})


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request, _home_for(request.user)))
    error, inactive = '', False
    email = ''
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip()
        password = request.POST.get('password') or ''
        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            if not request.POST.get('remember'):
                request.session.set_expiry(0)
            return redirect(_safe_next(request, _home_for(user)))
        cand = User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).first()
        if cand and not cand.is_active and cand.check_password(password):
            inactive = True
            error = 'الحساب غير مفعّل بعد — افتحوا رسالة التفعيل في بريدكم.'
        else:
            error = 'البريد الإلكتروني أو كلمة المرور غير صحيحة.'
    return render(request, 'award/portal/login.html',
                  {'error': error, 'inactive': inactive, 'email': email, 'next': _safe_next(request, '')})


@require_POST
def logout_view(request):
    logout(request)
    return redirect('/')


# =====================================================
#   لوحة المدرسة
# =====================================================
def _school_profile(request):
    prof = getattr(request.user, 'profile', None)
    if not prof:
        if request.user.is_staff:
            prof = Profile.objects.create(user=request.user, role='school',
                                          contact_person=request.user.get_full_name() or request.user.username)
        else:
            prof = Profile.objects.create(user=request.user, role='school')
    return prof


def submit_entry(request):
    """زر «سجّل الآن» في الموقع: حساب جديد ← طلب جديد (مع المسار المختار)"""
    qs = request.META.get('QUERY_STRING', '')
    target = '/portal/submissions/new/' + (f'?{qs}' if qs else '')
    if request.user.is_authenticated:
        return redirect(target)
    from urllib.parse import quote
    return redirect(f'/accounts/signup/?next={quote(target)}')


@login_required
def portal_home(request):
    role = _role(request.user)
    if role == 'judge':
        return redirect('judge_home')
    if role == 'staff' and not request.GET.get('school'):
        return redirect('/admin/')
    prof = _school_profile(request)
    cycle = AwardCycle.current()
    subs = (Submission.objects.filter(owner=request.user)
            .select_related('cycle', 'track', 'field').order_by('-submitted_at'))
    return render(request, 'award/portal/dashboard.html', {
        'tab': 'home', 'prof': prof, 'cycle': cycle, 'subs': subs,
        'mail_sender': __import__('email.utils').utils.parseaddr(settings.DEFAULT_FROM_EMAIL)[1] if settings.EMAIL_ENABLED else '', 'can_new': _can_create(request.user, cycle)[0],
        'new_block_reason': _can_create(request.user, cycle)[1],
        'notes': request.user.notifications.all()[:5],
        'counts': {
            'all': len(subs),
            'active': sum(1 for s in subs if s.status not in ('draft', 'withdrawn')),
            'draft': sum(1 for s in subs if s.status == 'draft'),
            'revision': sum(1 for s in subs if s.status == 'revision'),
        },
    })


def _can_create(user, cycle):
    if not cycle:
        return False, 'لا توجد دورة تسجيل حالياً.'
    if not cycle.is_open:
        if timezone.now() < cycle.opens_at:
            return False, f'يبدأ التسجيل في {timezone.localtime(cycle.opens_at):%Y-%m-%d}.'
        return False, 'انتهت فترة التسجيل لهذه الدورة.'
    if cycle.max_per_school:
        n = Submission.objects.filter(owner=user, cycle=cycle).exclude(status='withdrawn').count()
        if n >= cycle.max_per_school:
            return False, f'وصلتم للحد الأقصى ({cycle.max_per_school}) من الطلبات في هذه الدورة.'
    return True, ''


def _track_map(form):
    import json
    return json.dumps({str(t.pk): str(t.field_id) for t in form.fields['track'].queryset})


def _save_submission(request, form, sub, creating):
    action = request.POST.get('action', 'draft')
    sub = form.save(commit=False)
    if creating:
        prof = request.user.profile
        sub.owner = request.user
        sub.cycle = AwardCycle.current()
        sub.school_name = prof.school_name or prof.contact_person
        sub.email = request.user.email
        sub.status = 'draft'
    if action == 'submit' and not sub.document:
        form.add_error('document', 'ملف البحث (PDF) مطلوب قبل الإرسال.')
        return None
    sub.save()
    form.save_m2m()
    if action == 'submit':
        workflow.change_status(sub, 'submitted', by=request.user)
        messages.success(request, f'تم إرسال الطلب {sub.ref} بنجاح. ستصلكم الإشعارات عند كل تحديث.')
    else:
        if creating:
            workflow.StatusLog.objects.create(submission=sub, new_status='draft', by=request.user)
        messages.info(request, f'تم حفظ الطلب {sub.ref} كمسودة. لم يُرسل بعد.')
    return sub


@login_required
def submission_new(request):
    if _role(request.user) == 'judge':
        raise Http404
    _school_profile(request)
    cycle = AwardCycle.current()
    ok, reason = _can_create(request.user, cycle)
    if not ok:
        messages.warning(request, reason)
        return redirect('portal_home')
    prof = request.user.profile
    initial = {'contact_person': prof.contact_person, 'phone': prof.phone}
    for key in ('field', 'track'):
        v = request.GET.get(key, '')
        if v.isdigit():
            initial[key] = int(v)
    form = PortalSubmissionForm(request.POST or None, request.FILES or None, cycle=cycle, initial=initial)
    if request.method == 'POST' and form.is_valid():
        sub = _save_submission(request, form, None, True)
        if sub:
            return redirect(sub.get_absolute_url())
    return render(request, 'award/portal/submission_form.html',
                  {'tab': 'home', 'form': form, 'cycle': cycle, 'track_map': _track_map(form), 'creating': True})


def _own_submission(request, pk):
    return get_object_or_404(Submission.objects.select_related('cycle', 'track', 'field'), pk=pk, owner=request.user)


@login_required
def submission_edit(request, pk):
    sub = _own_submission(request, pk)
    if not sub.can_edit:
        messages.warning(request, 'لا يمكن تعديل هذا الطلب في حالته الحالية.')
        return redirect(sub.get_absolute_url())
    form = PortalSubmissionForm(request.POST or None, request.FILES or None, instance=sub, cycle=sub.cycle or AwardCycle.current())
    if request.method == 'POST' and form.is_valid():
        saved = _save_submission(request, form, sub, False)
        if saved:
            return redirect(saved.get_absolute_url())
    return render(request, 'award/portal/submission_form.html',
                  {'tab': 'home', 'form': form, 'sub': sub, 'cycle': sub.cycle, 'track_map': _track_map(form), 'creating': False})


@login_required
def submission_detail(request, pk):
    sub = _own_submission(request, pk)
    steps = _steps(sub)
    logs = [l for l in sub.logs.all() if not (sub.results_hidden and l.new_status in ('accepted', 'rejected', 'winner'))]
    return render(request, 'award/portal/submission_detail.html', {'tab': 'home', 'sub': sub, 'steps': steps, 'logs': logs})


def _steps(sub):
    """شريط المراحل في صفحة الطلب"""
    order = ['draft', 'submitted', 'screening', 'judging', 'result']
    labels = {'draft': 'مسودة', 'submitted': 'مُرسل', 'screening': 'تدقيق', 'judging': 'تحكيم', 'result': 'النتيجة'}
    st = sub.public_status
    pos = {'draft': 0, 'submitted': 1, 'screening': 2, 'revision': 2, 'judging': 3,
           'accepted': 4, 'rejected': 4, 'winner': 4, 'withdrawn': -1}.get(st, 0)
    out = []
    for i, key in enumerate(order):
        label = labels[key]
        if key == 'result' and pos == 4:
            label = sub.public_status_label
        if key == 'screening' and st == 'revision':
            label = 'مطلوب تعديل'
        out.append({'label': label, 'state': 'done' if i < pos else ('current' if i == pos else 'todo'),
                    'warn': key == 'screening' and st == 'revision'})
    return out


@login_required
@require_POST
def submission_withdraw(request, pk):
    sub = _own_submission(request, pk)
    if sub.can_withdraw:
        if sub.status == 'draft':
            ref = sub.ref
            sub.delete()
            messages.info(request, f'تم حذف المسودة {ref}.')
            return redirect('portal_home')
        workflow.change_status(sub, 'withdrawn', by=request.user, notify_school=False)
        messages.info(request, f'تم سحب الطلب {sub.ref}.')
    return redirect(sub.get_absolute_url())


@login_required
def profile_edit(request):
    prof = _school_profile(request) if _role(request.user) != 'judge' else request.user.profile
    form = ProfileForm(request.POST or None, instance=prof)
    if request.method == 'POST' and form.is_valid():
        form.save()
        if prof.role == 'school':
            request.user.first_name = prof.contact_person[:150]
            request.user.save(update_fields=['first_name'])
        messages.success(request, 'تم حفظ البيانات.')
        return redirect('profile_edit')
    return render(request, 'award/portal/profile.html', {'tab': 'profile', 'form': form, 'prof': prof})


# =====================================================
#   الإشعارات
# =====================================================
@login_required
def notifications(request):
    if request.method == 'POST':
        request.user.notifications.filter(is_read=False).update(is_read=True)
        return redirect('notifications')
    items = request.user.notifications.all()[:200]
    return render(request, 'award/portal/notifications.html', {'tab': 'notes', 'items': items})


@login_required
def notification_go(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    if not n.is_read:
        n.is_read = True
        n.save(update_fields=['is_read'])
    url = n.url or '/portal/notifications/'
    if not url_has_allowed_host_and_scheme(url, {request.get_host()}):
        url = '/portal/notifications/'
    return HttpResponseRedirect(url)


# =====================================================
#   المحكّمون
# =====================================================
def _judge_required(view):
    @login_required
    def wrapper(request, *a, **kw):
        if _role(request.user) != 'judge' and not request.user.is_staff:
            raise Http404
        return view(request, *a, **kw)
    wrapper.__name__ = view.__name__
    return wrapper


@_judge_required
def judge_home(request):
    items = list(Assignment.objects.filter(judge=request.user)
                 .select_related('submission__track', 'submission__field', 'submission__cycle')
                 .prefetch_related('scores__criterion').order_by('completed_at', '-assigned_at'))
    done = sum(1 for a in items if a.is_done)
    return render(request, 'award/portal/judge_home.html', {
        'tab': 'home', 'items': items, 'counts': {'all': len(items), 'done': done, 'todo': len(items) - done},
        'notes': request.user.notifications.all()[:5]})


@_judge_required
def judge_review(request, pk):
    a = get_object_or_404(Assignment.objects.select_related('submission__track', 'submission__field', 'submission__cycle'),
                          pk=pk, judge=request.user)
    sub = a.submission
    criteria = list(Criterion.for_submission(sub))
    existing = {s.criterion_id: s for s in a.scores.all()}
    locked = sub.status != 'judging' and a.is_done
    errors = []
    if request.method == 'POST' and not locked:
        finish = request.POST.get('action') == 'finish'
        values = {}
        for c in criteria:
            raw = (request.POST.get(f'c{c.pk}') or '').strip()
            note = (request.POST.get(f'n{c.pk}') or '').strip()[:500]
            if raw == '':
                if finish:
                    errors.append(f'أدخل درجة «{c.name}».')
                values[c.pk] = (None, note)
                continue
            try:
                v = float(raw)
            except ValueError:
                errors.append(f'درجة «{c.name}» غير صحيحة.')
                continue
            if v < 0 or v > c.max_score:
                errors.append(f'درجة «{c.name}» يجب أن تكون بين 0 و {c.max_score}.')
                continue
            values[c.pk] = (v, note)
        if not errors:
            for c in criteria:
                v, note = values.get(c.pk, (None, ''))
                if v is None:
                    Score.objects.filter(assignment=a, criterion=c).delete()
                else:
                    Score.objects.update_or_create(assignment=a, criterion=c, defaults={'value': v, 'note': note})
            a.comment = (request.POST.get('comment') or '').strip()
            rec = request.POST.get('recommendation', '')
            a.recommendation = rec if rec in dict(RECOMMEND_CHOICES) else ''
            was_done = a.is_done
            if finish:
                a.completed_at = timezone.now()
            a.save()
            if finish and not was_done:
                left = sub.assignments.filter(completed_at__isnull=True).count()
                if left == 0:
                    notify_staff(f'اكتمل تحكيم الطلب {sub.ref}',
                                 f"«{sub.project_title}» — المتوسط: {sub.avg_score}",
                                 f'/admin/award/submission/{sub.pk}/change/', email=False)
                messages.success(request, 'تم إنهاء التقييم وإرساله. شكراً لك.')
                return redirect('judge_home')
            messages.success(request, 'تم حفظ التقييم (لم يُرسل نهائياً بعد).' if not a.is_done else 'تم تحديث التقييم.')
            return redirect('judge_review', pk=a.pk)
    rows = []
    for c in criteria:
        s = existing.get(c.pk)
        rows.append({'c': c, 'value': request.POST.get(f'c{c.pk}', s.value if s else '') if request.method == 'POST' else (s.value if s else ''),
                     'note': s.note if s else ''})
    blind = sub.cycle.blind_judging if sub.cycle else True
    return render(request, 'award/portal/judge_review.html', {
        'tab': 'home', 'a': a, 'sub': sub, 'rows': rows, 'errors': errors, 'locked': locked, 'blind': blind,
        'rec_choices': RECOMMEND_CHOICES[1:]})


# =====================================================
#   صلاحية ملفات الطلبات (تُستدعى من serve_media)
# =====================================================
def can_view_private_file(user, path):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    sub = Submission.objects.filter(Q(document=path) | Q(attachment=path)).first()
    if not sub:
        return False
    if sub.owner_id == user.pk:
        return True
    return sub.assignments.filter(judge=user).exists()
