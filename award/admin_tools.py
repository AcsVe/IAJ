"""أدوات لوحة Django: «حالة الموقع»، «دليل الأدوار والمصطلحات»، و«المعاينة قبل الحفظ»."""
import threading

from django.apps import apps
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import render
from django.urls import resolve, reverse, NoReverseMatch
from django.utils import timezone, translation

from . import preview_state
from .roles import ROLE_LABELS, section_models, GROUP_EDITOR, GROUP_AWARD

# الجداول التي يمكن معاينتها قبل الحفظ: محتوى الموقع + التصميم (لا شيء يرسل بريداً أو إشعارات)
# + الإعلانات والدورات (تظهر للزوار). الجداول الداخلية (الطلبات، التقييمات…) ليس لها صفحة في الموقع لمعاينتها
PREVIEW_MODELS = set(section_models('editor')) | {'ThemeSetting', 'PortalSetting', 'AwardCycle', 'Announcement', 'HeroCard', 'SectionBackground'}


def can_preview(opts):
    return getattr(opts, 'app_label', '') == 'award' and getattr(opts, 'object_name', '') in PREVIEW_MODELS


def _admin_url(name, *args, query=''):
    try:
        return reverse(f'admin:award_{name}', args=args) + query
    except NoReverseMatch:
        return ''


# =====================================================================
#   حالة الموقع: ما الظاهر وما المخفي ولماذا
# =====================================================================
def _status_items():
    from .models import (HeroCard, HeroTextSlide, HeroSlide, AwardCycle, PortalSetting, TickerSetting, TickerItem,
                         SocialLink, TimelineEvent, Sponsor, Judge, News, Winner, Announcement, Track)
    now = timezone.now()
    groups = []

    # ---- أعلى الصفحة الرئيسية ----
    rows = []
    card = HeroCard.objects.first()
    n_texts = HeroTextSlide.objects.filter(is_active=True).count()
    if card is None or card.is_enabled:
        rows.append(('ok', 'بطاقة النصوص تحت الفيديو', f'ظاهرة — {n_texts} نص متبدّل مفعّل' + ('' if (n_texts or (card and (card.heading or card.body_text))) else ' (لا يوجد نص بعد، فلن تظهر)'),
                     _admin_url('herocard_changelist')))
    else:
        rows.append(('off', 'بطاقة النصوص تحت الفيديو', f'مخفية — لذلك لا يظهر أي من النصوص ({n_texts})', _admin_url('herocard_changelist')))
    n_sl = HeroSlide.objects.filter(is_active=True).count()
    rows.append(('ok' if n_sl else 'info', 'بطاقة الفيديو والصور', f'{n_sl} شريحة ظاهرة' if n_sl else 'لا توجد شرائح — تُستخدم صورة/فيديو الإعدادات العامة إن وُجدت', _admin_url('heroslide_changelist')))
    ts = TickerSetting.objects.first()
    n_ti = TickerItem.objects.filter(is_active=True).count()
    if ts and not ts.is_enabled:
        rows.append(('off', 'شريط الأخبار', 'متوقف من «إعدادات الشريط»', _admin_url('tickersetting_changelist')))
    else:
        rows.append(('ok' if n_ti else 'info', 'شريط الأخبار', f'{n_ti} رسالة ظاهرة' if n_ti else 'يعمل لكن لا توجد رسائل مفعّلة', _admin_url('tickeritem_changelist')))
    groups.append(('الصفحة الرئيسية', rows))

    # ---- الدورة والتسجيل ----
    rows = []
    cyc = AwardCycle.current()
    if not cyc:
        rows.append(('off', 'الدورة الحالية', 'لا توجد دورة حالية — يختفي العداد وزر «سجل الآن» والتسجيل مغلق', _admin_url('awardcycle_changelist')))
    else:
        if cyc.opens_at <= now <= cyc.closes_at:
            rows.append(('ok', 'التسجيل', f'مفتوح في «{cyc.name}» حتى {timezone.localtime(cyc.closes_at):%Y-%m-%d}', _admin_url('awardcycle_change', cyc.pk)))
        elif now < cyc.opens_at:
            rows.append(('info', 'التسجيل', f'لم يبدأ بعد — يفتح {timezone.localtime(cyc.opens_at):%Y-%m-%d}', _admin_url('awardcycle_change', cyc.pk)))
        else:
            rows.append(('off', 'التسجيل', f'مغلق — انتهى {timezone.localtime(cyc.closes_at):%Y-%m-%d}', _admin_url('awardcycle_change', cyc.pk)))
        rows.append(('ok' if cyc.show_card else 'off', 'بطاقة الدورة (عند المرور على اسم الجائزة)', 'ظاهرة' if cyc.show_card else 'مخفية من إعدادات الدورة', _admin_url('awardcycle_change', cyc.pk)))
        rows.append(('ok' if cyc.results_published else 'info', 'نتائج التحكيم', 'منشورة للمدارس' if cyc.results_published else 'غير منشورة بعد (مقصود: تظهر للمدارس «قيد التحكيم» حتى تنشرها)', '/manage/results/'))
    p = PortalSetting.get()
    rows.append(('ok' if p.show_register_btn else 'off', 'زر «سجل الآن» في الهيدر', 'ظاهر (عند فتح التسجيل)' if p.show_register_btn else 'مخفي من إعدادات البوابة', _admin_url('portalsetting_changelist')))
    rows.append(('ok' if p.show_login_btn else 'off', 'زر «دخول» في الهيدر', 'ظاهر' if p.show_login_btn else 'مخفي من إعدادات البوابة', _admin_url('portalsetting_changelist')))
    groups.append(('الدورة والتسجيل', rows))

    # ---- الأقسام ----
    rows = []
    cur_id = cyc.pk if cyc else None
    tl_all = TimelineEvent.objects.count()
    tl_home = TimelineEvent.objects.filter(cycle_id=cur_id).count() + TimelineEvent.objects.filter(cycle__isnull=True).count() if cur_id else tl_all
    rows.append(('ok' if tl_home else 'info', 'الجدول الزمني', f'{tl_home} مرحلة في الصفحة الرئيسية' + (f' — و{tl_all - tl_home} من دورات أخرى تظهر في أرشيف الدورات فقط' if tl_all - tl_home else ''), _admin_url('timelineevent_changelist')))
    for model, label, url in ((Sponsor, 'الرعاة', 'sponsor_changelist'), (Judge, 'لجنة التحكيم', 'judge_changelist'),
                              (News, 'الأخبار', 'news_changelist'), (Winner, 'الفائزون', 'winner_changelist')):
        n = model.objects.count()
        rows.append(('ok' if n else 'info', label, f'{n} عنصر' if n else 'فارغ — تظهر رسالة «قريباً» بدل القسم', _admin_url(url)))
    n_ann = Announcement.objects.filter(is_published=True, show_on_home=True).count()
    rows.append(('ok' if n_ann else 'info', 'الإعلانات في الصفحة الرئيسية', f'{n_ann} إعلان' if n_ann else 'لا توجد إعلانات للرئيسية', _admin_url('announcement_changelist')))
    n_notice = Track.objects.filter(notice_enabled=True).count()
    if n_notice:
        rows.append(('info', 'شريط ملاحظة داخل المسارات', f'مفعّل في {n_notice} مسار', _admin_url('track_changelist', query='?notice_enabled__exact=1')))
    groups.append(('أقسام الموقع', rows))

    # ---- التواصل والوسائط ----
    rows = []
    n_soc = SocialLink.objects.filter(is_active=True).exclude(url='').count()
    rows.append(('ok' if n_soc else 'off', 'روابط التواصل الاجتماعي', f'{n_soc} رابط' if n_soc else 'لا توجد روابط مفعّلة', _admin_url('sociallink_changelist')))
    rows.append(('ok' if p.social_in_footer else 'off', 'التواصل في الفوتر', 'ظاهر' if p.social_in_footer else 'مخفي', _admin_url('portalsetting_changelist')))
    rows.append(('ok' if p.social_in_menu else 'off', 'التواصل في قائمة الموبايل', 'ظاهر' if p.social_in_menu else 'مخفي', _admin_url('portalsetting_changelist')))
    rows.append(('ok' if p.wm_enabled else 'off', 'شعار الجائزة على الصور والفيديو', 'ظاهر' if p.wm_enabled else 'مخفي', _admin_url('portalsetting_changelist')))
    rows.append(('ok' if p.captions_enabled else 'off', 'نص الشرح بجانب الشعار', 'ظاهر' if p.captions_enabled else 'مخفي', _admin_url('portalsetting_changelist')))
    groups.append(('التواصل والوسائط', rows))

    # ---- عناصر أطفأها أحد يدوياً ----
    rows = []
    for name in section_models('editor'):
        try:
            model = apps.get_model('award', name)
        except LookupError:
            continue
        fields = {f.name for f in model._meta.fields}
        flag = 'is_active' if 'is_active' in fields else ('is_published' if 'is_published' in fields else None)
        if not flag:
            continue
        hidden = model.objects.filter(**{flag: False}).count()
        if hidden:
            rows.append(('off', str(model._meta.verbose_name_plural), f'{hidden} عنصر مخفي (خانة «ظاهر/مفعّل/منشور» مطفأة)',
                         _admin_url(f'{model._meta.model_name}_changelist', query=f'?{flag}__exact=0')))
    if not rows:
        rows.append(('ok', 'لا يوجد', 'لا توجد عناصر مخفية يدوياً', ''))
    groups.append(('عناصر مخفية يدوياً', rows))

    # ---- تقني ----
    rows = []
    backend = getattr(settings, 'EMAIL_BACKEND', '')
    if not getattr(settings, 'EMAIL_ENABLED', True):
        rows.append(('off', 'البريد الإلكتروني', 'متوقف (EMAIL_ENABLED=0) — لا تُرسل رسائل', ''))
    elif 'filebased' in backend or 'console' in backend:
        rows.append(('off', 'البريد الإلكتروني', 'لا يُرسل فعلياً — يُحفظ في logs/emails (إعدادات SMTP ناقصة في .env)', ''))
    else:
        rows.append(('ok', 'البريد الإلكتروني', 'يعمل — راجع «سجل رسائل البريد» لمعرفة ما أُرسل', _admin_url('emaillog_changelist')))
    rows.append(('info', 'تفعيل حساب المدرسة بالبريد', 'مطلوب' if getattr(settings, 'REQUIRE_EMAIL_VERIFICATION', False) else 'غير مطلوب (المدرسة تدخل مباشرة بعد التسجيل)', ''))
    groups.append(('إعدادات تقنية', rows))
    return groups


@staff_member_required
def site_status(request):
    groups = _status_items()
    counts = {'off': 0, 'ok': 0, 'info': 0}
    for _t, rows in groups:
        for r in rows:
            counts[r[0]] = counts.get(r[0], 0) + 1
    ctx = {**admin.site.each_context(request), 'title': 'حالة الموقع: الظاهر والمخفي', 'groups': groups, 'counts': counts}
    return render(request, 'admin/iaj_status.html', ctx)


@staff_member_required
def roles_guide(request):
    from django.contrib.auth.models import User
    ctx = {**admin.site.each_context(request), 'title': 'دليل الأدوار والمصطلحات',
           'tech_users': User.objects.filter(is_superuser=True, is_active=True),
           'editor_users': User.objects.filter(groups__name=GROUP_EDITOR, is_active=True).distinct(),
           'award_users': User.objects.filter(groups__name=GROUP_AWARD, is_active=True).distinct(),
           'award_role_users': User.objects.filter(profile__role='manager', is_active=True).distinct(),
           'GROUP_EDITOR': GROUP_EDITOR, 'GROUP_AWARD': GROUP_AWARD, 'ROLE_LABELS': ROLE_LABELS}
    return render(request, 'admin/iaj_guide.html', ctx)


# =====================================================================
#   المعاينة قبل الحفظ
#   يُحفظ التعديل داخل «معاملة» مؤقتة، تُعرض صفحة الموقع به، ثم يُلغى كل شيء.
# =====================================================================
class _Rollback(Exception):
    def __init__(self, response):
        self.response = response


def _target_path(obj):
    name, pk = obj.__class__.__name__, obj.pk
    if name == 'News':
        return f'/news/{pk}/'
    if name == 'Track':
        return f'/tracks/{pk}/'
    if name == 'TrackDetail':
        return f'/tracks/{obj.track_id}/'
    if name == 'Announcement':
        return f'/announcements/{pk}/'
    return {'Photo': '/photos/', 'MediaGallery': '/photos/', 'Video': '/videos/', 'SuccessStory': '/success-stories/',
            'Winner': '/winners/', 'WinnerCategory': '/winners/'}.get(name, '/')


def _render_site_page(request, path):
    from django.test import RequestFactory
    req = RequestFactory().get(path, HTTP_HOST=request.get_host(), secure=request.is_secure())
    req.user, req.session, req.COOKIES = request.user, request.session, request.COOKIES
    req._messages = getattr(request, '_messages', None)
    match = resolve(path)
    with translation.override(settings.LANGUAGE_CODE):
        resp = match.func(req, *match.args, **match.kwargs)
        if hasattr(resp, 'render') and not getattr(resp, 'is_rendered', True):
            resp.render()
    return resp


BANNER = ('<div id="iajPreviewBar" style="position:fixed;z-index:99999;left:0;right:0;bottom:0;padding:12px 16px;'
          'background:#b3261e;color:#fff;font:700 15px/1.6 Cairo,Tahoma,sans-serif;text-align:center;direction:rtl;'
          'box-shadow:0 -6px 20px rgba(0,0,0,.35)">👁 وضع المعاينة — هذا التعديل <u>لم يُحفظ ولم يُنشر</u>. '
          'إن كان صحيحاً ارجع للوحة التحكم واضغط «حفظ ونشر في الموقع». (الروابط هنا تفتح الموقع الحالي بدون التعديل)'
          '<button onclick="window.close()" style="margin-right:14px;border:0;border-radius:20px;padding:4px 14px;'
          'font:inherit;cursor:pointer">إغلاق المعاينة</button></div>')


def _cleanup_later(names):
    if not names:
        return

    def _go():
        from django.core.files.storage import default_storage
        for n in names:
            try:
                default_storage.delete(n)
            except Exception:
                pass
    t = threading.Timer(15 * 60, _go)   # تبقى الصور المرفوعة للمعاينة ربع ساعة ثم تُحذف
    t.daemon = True
    t.start()


@staff_member_required
def preview(request, app_label, model_name):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        raise Http404
    ma = admin.site._registry.get(model)
    if ma is None or not can_preview(model._meta):
        raise Http404
    object_id = request.GET.get('id') or None
    preview_state.set_active(True)
    try:
        try:
            with transaction.atomic():
                resp = ma.changeform_view(request, object_id)
                if resp.status_code != 302:
                    # أخطاء في النموذج: نعرضها كما هي (لم يُحفظ شيء)
                    if hasattr(resp, 'render') and not getattr(resp, 'is_rendered', True):
                        resp.render()
                    raise _Rollback(resp)
                obj = (model.objects.filter(pk=object_id).first() if object_id
                       else model.objects.order_by('-pk').first())
                path = _target_path(obj) if obj is not None else '/'
                page = _render_site_page(request, path)
                if page.status_code == 404 and path != '/':
                    page = _render_site_page(request, '/')
                raise _Rollback(page)
        except _Rollback as rb:
            resp = rb.response
    finally:
        files = preview_state.new_files()
        preview_state.set_active(False)
        _cleanup_later(files)
        storage = messages.get_messages(request)   # لا نُظهر «تم الحفظ» لاحقاً — لم يُحفظ شيء
        for _m in storage:
            pass
    if resp.status_code == 200 and 'text/html' in resp.get('Content-Type', '') and b'id="content-main"' not in resp.content:
        html = resp.content.decode('utf-8')
        html = html.replace('<head>', '<head><meta name="robots" content="noindex">', 1)
        i = html.rfind('</body>')
        html = (html[:i] + BANNER + html[i:]) if i != -1 else html + BANNER
        out = HttpResponse(html, content_type='text/html; charset=utf-8')
    else:
        out = HttpResponse(resp.content, status=resp.status_code, content_type=resp.get('Content-Type', 'text/html'))
    out['Cache-Control'] = 'no-store'
    return out
