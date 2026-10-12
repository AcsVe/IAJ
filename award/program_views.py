"""
ما بعد الإرسال وما بعد النتائج: الإيصال، الاعتراض، تقرير التغذية الراجعة، الشهادات (مع رمز QR للتحقق)،
دعوات الحفل (RSVP)، تقارير متابعة الأثر، والتحقق بخطوتين لحسابات الإدارة والمحكّمين.
"""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .audit import audit
from .models import (FINAL_STATUSES, Appeal, Certificate, ImpactReport, Invitation, PortalSetting, Submission)
from .notify import absolute, notify_staff, send_email
from . import workflow

User = get_user_model()


def _qr_svg(url, scale=3):
    try:
        import segno
        return segno.make(url, error='m').svg_inline(scale=scale, dark='#0a1632')
    except Exception:   # المكتبة غير مثبتة بعد — الشهادة تعمل بدون QR
        return ''


def _published(sub):
    return bool(sub.cycle and sub.cycle.results_published and sub.status in FINAL_STATUSES)


def school_extras(sub):
    """ما تراه المدرسة في صفحة الطلب بعد النتائج"""
    c = sub.cycle
    pub = _published(sub)
    impact_due = None
    if pub and sub.status == 'winner' and c.results_published_at and c.impact_after_days:
        impact_due = c.results_published_at + timedelta(days=c.impact_after_days)
    return {
        'published': pub,
        'feedback': workflow.feedback(sub) if pub and c.share_feedback else None,
        'can_appeal': workflow.can_appeal(sub),
        'appeal_until': c.appeal_until if c else None,
        'appeals': list(sub.appeals.all()),
        'certificates': list(sub.certificates.filter(revoked=False)) if pub else [],
        'invitation': sub.invitations.first() if pub else None,
        'impact_due': impact_due,
        'impact_reports': list(sub.impact_reports.all()) if sub.status == 'winner' else [],
        'show_impact': pub and sub.status == 'winner',
    }


def _sub_for(request, pk):
    from .portal_views import is_manager
    sub = get_object_or_404(Submission.objects.select_related('cycle', 'track', 'field'), pk=pk)
    if sub.owner_id != request.user.pk and not is_manager(request.user):
        raise Http404
    return sub


@login_required
def receipt(request, pk):
    sub = _sub_for(request, pk)
    if not sub.sent_at:
        messages.warning(request, 'الإيصال متاح بعد إرسال الطلب.')
        return redirect(sub.get_absolute_url())
    return render(request, 'award/portal/receipt.html', {
        'sub': sub, 'files': sub.files.all(), 'now': timezone.now(),
        'qr': _qr_svg(absolute(f'/portal/submissions/{sub.pk}/'), 2)})


@login_required
@require_POST
def appeal(request, pk):
    sub = get_object_or_404(Submission, pk=pk, owner=request.user)
    body = (request.POST.get('body') or '').strip()
    if not workflow.can_appeal(sub):
        messages.warning(request, 'لا يمكن تقديم اعتراض على هذا الطلب الآن.')
    elif len(body) < 20:
        messages.error(request, 'اكتبوا أسباب الاعتراض بوضوح (20 حرفاً على الأقل).')
    else:
        Appeal.objects.create(submission=sub, by=request.user, body=body)
        if not sub.is_simulation:
            notify_staff(f'اعتراض على نتيجة {sub.ref}', f"{sub.school_name}:\n{body[:400]}", '/manage/appeals/')
        messages.success(request, 'استلمنا اعتراضكم وسيُدرس من لجنة الجائزة، ويصلكم الرد هنا وبالبريد.')
    return redirect(sub.get_absolute_url() + '#results')


@login_required
@require_POST
def impact(request, pk):
    sub = get_object_or_404(Submission, pk=pk, owner=request.user, status='winner')
    body = (request.POST.get('body') or '').strip()
    if len(body) < 20:
        messages.error(request, 'اكتبوا وصفاً لما حدث للمشروع (20 حرفاً على الأقل).')
    else:
        b = request.POST.get('beneficiaries') or ''
        ImpactReport.objects.create(submission=sub, by=request.user, body=body,
                                    beneficiaries=int(b) if b.isdigit() else None,
                                    attachment=request.FILES.get('attachment') or '')
        if not sub.is_simulation:
            notify_staff(f'تقرير أثر — {sub.ref}', f"{sub.school_name}:\n{body[:400]}", '/manage/impact/', email=False)
        messages.success(request, 'شكراً لكم — وصلنا تقرير المتابعة.')
    return redirect(sub.get_absolute_url() + '#impact')


# =====================================================
#   الشهادات والتحقق (عام — بالرمز فقط)
# =====================================================
def certificate(request, code):
    cert = get_object_or_404(Certificate.objects.select_related('cycle', 'submission'), code=code.upper())
    if cert.revoked:
        raise Http404
    if cert.submission_id and not (cert.cycle.results_published or request.user.is_authenticated):
        raise Http404
    verify = absolute(f'/verify/{cert.code}/')
    from .models import SiteSetting
    return render(request, 'award/certificate.html', {
        'cert': cert, 'qr': _qr_svg(verify, 3), 'verify_url': verify, 'site': SiteSetting.objects.first()})


def verify(request, code=''):
    code = (code or request.GET.get('code') or '').strip().upper()
    cert = Certificate.objects.select_related('cycle').filter(code=code).first() if code else None
    return render(request, 'award/verify.html', {'code': code, 'cert': cert})


# =====================================================
#   دعوات الحفل
# =====================================================
def rsvp(request, code):
    inv = get_object_or_404(Invitation.objects.select_related('cycle'), code=code.upper())
    if request.method == 'POST':
        ans = request.POST.get('rsvp')
        if ans in ('yes', 'no'):
            inv.rsvp = ans
            g = request.POST.get('guests') or '1'
            inv.guests = max(1, min(20, int(g))) if g.isdigit() else 1
            inv.note = (request.POST.get('note') or '').strip()[:500]
            inv.responded_at = timezone.now()
            inv.save()
            messages.success(request, 'شكراً — سُجّل ردكم.' if ans == 'yes' else 'شكراً لإبلاغنا — نتمنى لقاءكم قريباً.')
        return redirect(f'/rsvp/{inv.code}/')
    return render(request, 'award/rsvp.html', {'inv': inv})


# =====================================================
#   التحقق بخطوتين (رمز بالبريد)
# =====================================================
def needs_2fa(user):
    mode = PortalSetting.get().two_factor
    if mode == 'off' or not settings.EMAIL_ENABLED or not user.email:
        return False
    from .portal_views import is_manager
    if user.is_staff or user.is_superuser or is_manager(user):
        return True
    prof = getattr(user, 'profile', None)
    return mode == 'all' and bool(prof and prof.role == 'judge')


def _hash(code):
    return hashlib.sha256((settings.SECRET_KEY + code).encode()).hexdigest()


def start_2fa(request, user, next_url, remember):
    code = f'{secrets.randbelow(10 ** 6):06d}'
    request.session['2fa'] = {'uid': user.pk, 'h': _hash(code), 'exp': (timezone.now() + timedelta(minutes=10)).timestamp(),
                              'next': next_url, 'remember': bool(remember), 'tries': 0,
                              'backend': getattr(user, 'backend', settings.AUTHENTICATION_BACKENDS[0])}
    send_email(user.email, f'رمز الدخول: {code}',
               f'رمز التحقق لدخول حسابك في موقع الجائزة:\n\n{code}\n\nصالح لمدة 10 دقائق. إن لم تطلبه فتجاهل الرسالة وغيّر كلمة المرور.')
    return redirect('/accounts/2fa/')


def login_2fa(request):
    st = request.session.get('2fa')
    if not st:
        return redirect('/accounts/login/')
    error = ''
    if request.method == 'POST':
        code = (request.POST.get('code') or '').strip()
        st['tries'] += 1
        request.session['2fa'] = st
        if timezone.now().timestamp() > st['exp'] or st['tries'] > 5:
            request.session.pop('2fa', None)
            messages.error(request, 'انتهت صلاحية الرمز أو تجاوزت عدد المحاولات — سجّل الدخول من جديد.')
            return redirect('/accounts/login/')
        if secrets.compare_digest(_hash(code), st['h']):
            user = User.objects.filter(pk=st['uid'], is_active=True).first()
            request.session.pop('2fa', None)
            if not user:
                return redirect('/accounts/login/')
            login(request, user, backend=st['backend'])
            if not st['remember']:
                request.session.set_expiry(0)
            audit(request, 'دخول (بخطوتين)', user.email)
            return HttpResponseRedirect(st['next'] or '/')
        error = 'الرمز غير صحيح.'
    return render(request, 'award/portal/login_2fa.html', {'error': error})


def admin_login(request):
    """لوحة Django: عند تفعيل التحقق بخطوتين يمر الدخول عبر صفحة دخول الموقع"""
    if PortalSetting.get().two_factor != 'off' and settings.EMAIL_ENABLED:
        from urllib.parse import quote
        return redirect('/accounts/login/?next=' + quote(request.GET.get('next') or '/admin/'))
    return admin.site.login(request)
