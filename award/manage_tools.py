"""
صفحات إضافية في /manage/: الاعتراضات، ما بعد النتائج (الشهادات، الدعوات، الأثر)، الأدوات (المحاكاة والتنظيف
والقوالب والإعدادات)، وسجل العمليات.
"""
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .audit import audit
from .manage_views import _ctx, _cycle, manager_required
from .models import (STATUS_CHOICES, Appeal, AuditLog, AwardCycle, Certificate, DecisionTemplate, ImpactReport,
                     Invitation, PortalSetting, SimulationRun, Submission)
from . import cleanup, workflow


@manager_required
def appeals(request):
    if request.method == 'POST':
        ap = get_object_or_404(Appeal.objects.select_related('submission'), pk=request.POST.get('aid'))
        st, resp = request.POST.get('status'), (request.POST.get('response') or '').strip()
        if st in ('accepted', 'rejected') and resp:
            workflow.respond_appeal(ap, st, resp, request.user)
            audit(request, 'رد على اعتراض', ap.submission.ref, ap.get_status_display())
            messages.success(request, f'أُرسل الرد إلى {ap.submission.school_name}.')
        else:
            messages.error(request, 'اختر القرار واكتب الرد.')
        return redirect('/manage/appeals/' + (f'?show={request.GET["show"]}' if request.GET.get('show') else ''))
    qs = Appeal.objects.select_related('submission__cycle', 'by', 'responded_by')
    show = request.GET.get('show', 'open')
    counts = dict(qs.values('status').annotate(n=Count('pk')).values_list('status', 'n'))
    if show in ('open', 'accepted', 'rejected'):
        qs = qs.filter(status=show)
    return render(request, 'award/manage/appeals.html', _ctx(request, 'appeals', items=qs, show=show, counts=counts,
                                                             total=sum(counts.values())))


@manager_required
def post_results(request):
    """ما بعد النتائج: الشهادات + دعوات الحفل + تقارير الأثر"""
    cycle = _cycle(request)
    if request.method == 'POST' and cycle:
        act = request.POST.get('act')
        if act == 'certs':
            n = workflow.issue_certificates(cycle, judges=bool(request.POST.get('judges')))
            audit(request, 'إصدار شهادات', str(cycle), f'{n}')
            messages.success(request, f'أُصدرت {n} شهادة جديدة.')
        elif act == 'invite':
            statuses = request.POST.getlist('statuses') or ['winner']
            n = workflow.send_invitations(cycle, statuses)
            audit(request, 'إرسال دعوات الحفل', str(cycle), f'{n}')
            messages.success(request, f'أُرسلت {n} دعوة جديدة.')
        elif act == 'ceremony':
            from django.utils.dateparse import parse_datetime
            raw = request.POST.get('ceremony_date') or ''
            dt = parse_datetime(raw) if raw else None
            cycle.ceremony_date = timezone.make_aware(dt) if dt and timezone.is_naive(dt) else dt
            cycle.ceremony_place = (request.POST.get('ceremony_place') or '').strip()[:255]
            cycle.save(update_fields=['ceremony_date', 'ceremony_place'])
            messages.success(request, 'حُفظ موعد الحفل ومكانه.')
        elif act == 'revoke':
            Certificate.objects.filter(pk=request.POST.get('cid'), cycle=cycle).update(revoked=True)
            audit(request, 'إلغاء شهادة', request.POST.get('cid'))
            messages.info(request, 'أُلغيت الشهادة (صفحة التحقق ستظهرها ملغاة).')
        elif act == 'del_invites':
            ids = [i for i in request.POST.getlist('ids') if i.isdigit()]
            n = Invitation.objects.filter(pk__in=ids, cycle=cycle).delete()[0]
            messages.info(request, f'حُذفت {n} دعوة.')
        return redirect('/manage/post/')
    certs = Certificate.objects.filter(cycle=cycle).select_related('submission', 'user') if cycle else Certificate.objects.none()
    invs = Invitation.objects.filter(cycle=cycle).select_related('submission') if cycle else Invitation.objects.none()
    rsvp = dict(invs.values('rsvp').annotate(n=Count('pk')).values_list('rsvp', 'n'))
    impact = ImpactReport.objects.filter(submission__cycle=cycle).select_related('submission') if cycle else ImpactReport.objects.none()
    winners = cycle.submissions.filter(status='winner') if cycle else Submission.objects.none()
    return render(request, 'award/manage/post.html', _ctx(
        request, 'post', cycle=cycle, certs=certs, invs=invs, rsvp=rsvp,
        guests=invs.filter(rsvp='yes').aggregate(g=Sum('guests'))['g'] or 0,
        cert_counts=dict(certs.values('kind').annotate(n=Count('pk')).values_list('kind', 'n')),
        impact=impact, winners_n=winners.count(),
        winners_no_report=winners.filter(impact_reports__isnull=True).count(),
        statuses=[(k, l) for k, l in STATUS_CHOICES if k in ('winner', 'accepted', 'rejected')]))


@manager_required
def tools(request):
    from django.core.management import call_command
    if request.method == 'POST':
        act = request.POST.get('act')
        ps = PortalSetting.get()
        if act == 'test_mode':
            ps.test_mode = not ps.test_mode
            ps.save()
            audit(request, 'وضع التجربة', 'تشغيل' if ps.test_mode else 'إيقاف')
            messages.success(request, 'وضع التجربة مفعّل: كل حساب أو طلب جديد يُعلَّم «تجريبي».' if ps.test_mode
                             else 'أُوقف وضع التجربة. ما سُجّل أثناءه ما زال معلّماً «تجريبي» حتى تمسحوه.')
        elif act == 'two_factor' and request.POST.get('mode') in ('off', 'staff', 'all'):
            ps.two_factor = request.POST['mode']
            ps.save()
            audit(request, 'التحقق بخطوتين', ps.get_two_factor_display())
            messages.success(request, f'التحقق بخطوتين: {ps.get_two_factor_display()}')
        elif act == 'simulate':
            from .simulation import Sim
            try:
                n = max(8, min(40, int(request.POST.get('schools') or 10)))
            except ValueError:
                n = 10
            run = Sim(by=request.user, n_schools=n).run()
            (messages.success if not run.failed else messages.warning)(
                request, f'انتهت المحاكاة: {run.passed} خطوة ناجحة · {run.failed} فاشلة. التقرير بالأسفل.')
            return redirect(f'/manage/tools/?run={run.pk}#sim')
        elif act == 'clear_sim':
            if request.POST.get('confirm', '').strip() != 'مسح':
                messages.error(request, 'اكتب كلمة «مسح» للتأكيد.')
            else:
                r = cleanup.clear_simulation(keep_reports=bool(request.POST.get('keep')))
                audit(request, 'مسح بيانات التجربة', '', str(r))
                messages.success(request, f"مُسحت بيانات التجربة: {r['submissions']} طلب، {r['users']} حساب، {r['cycles']} دورة محاكاة. "
                                          "نسخة احتياطية مما حُذف محفوظة في backups/deleted.")
        elif act == 'cycle_clean':
            c = AwardCycle.objects.filter(pk=request.POST.get('cycle')).first()
            what = request.POST.get('what')
            if not c or what not in ('drafts', 'withdrawn', 'all'):
                messages.error(request, 'اختر الدورة ونوع التنظيف.')
            elif what == 'all' and request.POST.get('confirm', '').strip() != 'حذف':
                messages.error(request, 'حذف كل طلبات الدورة يحتاج كتابة كلمة «حذف» للتأكيد.')
            else:
                n, path = cleanup.cycle_cleanup(c, what, reset_results=bool(request.POST.get('reset')))
                audit(request, 'تنظيف دورة', str(c), f'{what}: {n} طلب {path}')
                messages.success(request, f'حُذف {n} طلب من «{c}»' + (' وأُعيد ضبط حالة النتائج.' if request.POST.get('reset') else '.'))
        elif act == 'stale':
            try:
                days = max(1, int(request.POST.get('days') or 30))
            except ValueError:
                days = 30
            kind = request.POST.get('kind') if request.POST.get('kind') in ('inactive', 'empty') else 'inactive'
            qs = cleanup.stale_accounts(days, kind)
            if request.POST.get('do') == '1':
                n, _ns, path = cleanup.delete_users(qs, f'stale-{kind}', with_submissions=False)
                audit(request, 'حذف حسابات قديمة', kind, f'{n} {path}')
                messages.success(request, f'حُذف {n} حساب.')
            else:
                messages.info(request, f'عدد الحسابات المطابقة: {qs.count()} — اضغط «حذف» للتنفيذ.')
                return redirect(f'/manage/tools/?stale={kind}&days={days}#clean')
        elif act == 'tpl_add':
            st, title, body = request.POST.get('status'), (request.POST.get('title') or '').strip(), (request.POST.get('body') or '').strip()
            if st in dict(STATUS_CHOICES) and title and body:
                DecisionTemplate.objects.create(status=st, title=title[:120], body=body, order=DecisionTemplate.objects.count())
                messages.success(request, 'أُضيف القالب.')
        elif act == 'tpl_del':
            DecisionTemplate.objects.filter(pk=request.POST.get('tid')).delete()
            messages.info(request, 'حُذف القالب.')
        elif act == 'reminders':
            from . import reminders
            r = reminders.run_all()
            messages.success(request, f"التذكيرات: مسودات {r['drafts']} · استكمال {r['revision']} · محكّمون {r['judges']} · أثر {r['impact']}")
        return redirect('/manage/tools/')
    runs = SimulationRun.objects.select_related('cycle')[:10]
    sel = request.GET.get('run')
    run = SimulationRun.objects.filter(pk=sel).first() if sel and sel.isdigit() else (runs[0] if runs else None)
    stale_n = None
    if request.GET.get('stale') in ('inactive', 'empty'):
        stale_n = cleanup.stale_accounts(int(request.GET.get('days') or 30), request.GET['stale']).count()
    return render(request, 'award/manage/tools.html', _ctx(
        request, 'tools', ps=PortalSetting.get(), runs=runs, run=run, sim=cleanup.simulation_counts(),
        all_cycles=AwardCycle.objects.annotate(n=Count('submissions'),
                                               n_draft=Count('submissions', filter=Q(submissions__status='draft')),
                                               n_wd=Count('submissions', filter=Q(submissions__status='withdrawn'))),
        templates=DecisionTemplate.objects.all(), statuses=[(k, l) for k, l in STATUS_CHOICES if k not in ('draft', 'submitted', 'withdrawn')],
        stale=request.GET.get('stale'), stale_days=request.GET.get('days') or 30, stale_n=stale_n,
        backups=_backup_files()))


def _backup_files():
    import os
    d = cleanup.backup_dir()
    files = sorted((f for f in os.listdir(d) if f.endswith('.json')), reverse=True)[:8]
    return [(f, os.path.getsize(os.path.join(d, f)) // 1024) for f in files]


@manager_required
def audit_log(request):
    qs = AuditLog.objects.select_related('user')
    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(action__icontains=q) | Q(target__icontains=q) | Q(detail__icontains=q) | Q(user__email__icontains=q))
    return render(request, 'award/manage/audit.html', _ctx(request, 'audit', items=qs[:500], total=qs.count(), q=q))
