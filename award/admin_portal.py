"""
لوحة التحكم — التسجيل والتحكيم:
دورات الجائزة، الطلبات (تغيير الحالة بالجملة + توزيع على المحكّمين + تصدير)،
الحسابات (إضافة محكّم بدعوة بالبريد + رسالة جماعية)، التقييمات، الإشعارات، سجل البريد.
"""
import csv

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.html import format_html, format_html_join
from django.utils.http import urlsafe_base64_encode

from .models import (AwardCycle, Area, PortalSetting, SocialLink, SubmissionFile, SubmissionMessage, JudgingCommittee, Announcement, AnnouncementMedia, Assignment, Criterion, Directorate, EmailLog, Governorate, Notification, Profile, Score,
                     StatusLog, Submission, SuccessPageContent, STATUS_CHOICES, ROLE_CHOICES)
from .notify import notify, send_email
from . import workflow

FACETS = admin.ShowFacets.ALWAYS

STATUS_COLORS = {
    'draft': '#9aa0a6', 'submitted': '#1a73e8', 'screening': '#7b61ff', 'revision': '#e8710a',
    'judging': '#9c27b0', 'accepted': '#188038', 'rejected': '#d93025', 'winner': '#c5a059', 'withdrawn': '#5f6368',
}


def status_badge(status):
    return format_html('<span style="background:{};color:#fff;padding:3px 10px;border-radius:12px;'
                       'font-size:12px;font-weight:700;white-space:nowrap">{}</span>',
                       STATUS_COLORS.get(status, '#666'), dict(STATUS_CHOICES).get(status, status))


try:
    admin.site.unregister(SuccessPageContent)   # لم تعد مستخدمة — صفحة الطلب في حساب المدرسة تحل محلها
except admin.sites.NotRegistered:
    pass


# =====================================================
#   الدورات
# =====================================================
class CriterionInline(admin.TabularInline):
    model = Criterion
    extra = 0
    fields = ('order', 'name', 'max_score', 'weight', 'track', 'description')


@admin.register(AwardCycle)
class AwardCycleAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'opens_at', 'closes_at', 'phase_label', 'is_current', 'results_published', 'subs_count')
    list_display_links = ('name',)
    list_filter = ('is_current', 'results_published', 'year')
    show_facets = FACETS
    filter_horizontal = ('tracks',)
    inlines = [CriterionInline]
    actions = ['make_current', 'clone_cycle', 'close_now', 'publish_results_action']
    fieldsets = (
        (None, {'fields': (('name', 'short_name'), ('year', 'hijri_year'), 'is_current', ('opens_at', 'closes_at'))}),
        ('صفحة الدورة في أرشيف الموقع', {'fields': ('summary', 'cover')}),
        ('بطاقة العداد', {'fields': ('countdown_title',), 'description': 'العنوان أعلى بطاقة «باقي … يوماً». فارغ = «استقبال طلبات» + الاسم المختصر.'}),
        ('بطاقة الدورة في الهيدر', {'fields': ('show_card', 'card_note'),
                                    'description': 'تظهر عند المرور بالماوس على اسم الجائزة أو زر «سجل الآن»: الاسم + السنة الهجرية/الميلادية + مواعيد التسجيل.'}),
        ('قواعد التسجيل', {'fields': ('tracks', 'max_per_school', 'revision_days')}),
        ('التحكيم والنتائج', {'fields': ('judges_per_submission', 'blind_judging', 'results_date', 'results_published')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _subs=Count('submissions', filter=~Q(submissions__status__in=('draft', 'withdrawn'))))

    @admin.display(description='الطلبات المرسلة', ordering='_subs')
    def subs_count(self, obj):
        return obj._subs

    @admin.display(description='المرحلة')
    def phase_label(self, obj):
        m = {'upcoming': ('لم يبدأ', '#9aa0a6'), 'open': ('التسجيل مفتوح', '#188038'),
             'closed': ('مغلق — تحكيم', '#9c27b0'), 'results': ('النتائج منشورة', '#c5a059')}
        t, c = m.get(obj.phase, ('—', '#666'))
        return format_html('<b style="color:{}">{}</b>', c, t)

    def save_model(self, request, obj, form, change):
        was_published = False
        if change:
            was_published = AwardCycle.objects.filter(pk=obj.pk, results_published=True).exists()
        publish_now = obj.results_published and not was_published
        if publish_now:
            obj.results_published = False
        super().save_model(request, obj, form, change)
        if publish_now:
            n = workflow.publish_results(obj, request.user)
            self.message_user(request, f'تم نشر النتائج وإرسال {n} إشعار للمدارس.', messages.SUCCESS)

    @admin.action(description='اجعلها الدورة الحالية')
    def make_current(self, request, queryset):
        c = queryset.first()
        if c:
            c.is_current = True
            c.save()
            self.message_user(request, f'«{c}» هي الدورة الحالية الآن.')

    @admin.action(description='فتح دورة جديدة بنفس الإعدادات (استنساخ)')
    def clone_cycle(self, request, queryset):
        from datetime import timedelta
        src = queryset.first()
        if not src:
            return
        new = AwardCycle.objects.create(
            name=f'{src.name} (جديدة)', short_name='', year=src.year + 1,
            hijri_year=str(int(src.hijri_year) + 1) if src.hijri_year.isdigit() else '',
            opens_at=src.opens_at + timedelta(days=365), closes_at=src.closes_at + timedelta(days=365),
            is_current=False, max_per_school=src.max_per_school, revision_days=src.revision_days,
            judges_per_submission=src.judges_per_submission, blind_judging=src.blind_judging, show_card=src.show_card)
        new.tracks.set(src.tracks.all())
        for c in src.criteria.all():
            Criterion.objects.create(cycle=new, track=c.track, name=c.name, description=c.description,
                                     max_score=c.max_score, weight=c.weight, order=c.order)
        self.message_user(request, f'أُنشئت «{new.name}» بنفس المسارات والمعايير. عدّل الاسم والمواعيد ثم اختر «اجعلها الدورة الحالية».', messages.SUCCESS)

    @admin.action(description='إغلاق التسجيل الآن')
    def close_now(self, request, queryset):
        n = 0
        for c in queryset:
            if c.closes_at > timezone.now():
                c.closes_at = timezone.now()
                c.save()
                n += 1
        self.message_user(request, f'أُغلق التسجيل في {n} دورة.')

    @admin.action(description='نشر النتائج وإبلاغ المدارس')
    def publish_results_action(self, request, queryset):
        total = 0
        for c in queryset:
            total += workflow.publish_results(c, request.user)
        self.message_user(request, f'تم النشر — أُرسل {total} إشعار.', messages.SUCCESS)


# =====================================================
#   الطلبات
# =====================================================
class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0
    fields = ('judge', 'assigned_at', 'completed_at', 'score_total', 'recommendation', 'comment')
    readonly_fields = ('assigned_at', 'completed_at', 'score_total', 'recommendation', 'comment')
    verbose_name = 'محكّم'
    verbose_name_plural = 'المحكّمون المُسند إليهم الطلب'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'judge':
            kwargs['queryset'] = User.objects.filter(profile__role='judge', is_active=True).order_by('first_name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description='الدرجة /100')
    def score_total(self, obj):
        return obj.total if obj.pk and obj.is_done else '—'


class StatusLogInline(admin.TabularInline):
    model = StatusLog
    extra = 0
    can_delete = False
    fields = ('created_at', 'old_label', 'new_label', 'note', 'by')
    readonly_fields = fields
    verbose_name_plural = 'سجل الحالات'

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description='من')
    def old_label(self, obj):
        return obj.old_label

    @admin.display(description='إلى')
    def new_label(self, obj):
        return obj.new_label


class StatusChangeForm(forms.Form):
    status = forms.ChoiceField(label='الحالة الجديدة', choices=[c for c in STATUS_CHOICES if c[0] != 'draft'])
    note = forms.CharField(label='ملاحظة للمدرسة (اختياري)', required=False,
                           widget=forms.Textarea(attrs={'rows': 4, 'style': 'width:100%'}),
                           help_text='تظهر في الإشعار والبريد. ضرورية عند «مطلوب تعديل».')
    notify_school = forms.BooleanField(label='إرسال إشعار للمدارس', required=False, initial=True)


class MessageForm(forms.Form):
    title = forms.CharField(label='العنوان', max_length=200, widget=forms.TextInput(attrs={'style': 'width:100%'}))
    body = forms.CharField(label='نص الرسالة', widget=forms.Textarea(attrs={'rows': 6, 'style': 'width:100%'}))
    url = forms.CharField(label='رابط (اختياري)', required=False, help_text='مثال: /portal/ أو /news/5/')
    email = forms.BooleanField(label='إرسال بالبريد أيضاً', required=False, initial=True)


def _intermediate(modeladmin, request, queryset, form, title, action, intro=''):
    return render(request, 'admin/award/intermediate_form.html', {
        **modeladmin.admin_site.each_context(request), 'title': title, 'form': form, 'queryset': queryset,
        'count': queryset.count(), 'action': action, 'intro': intro, 'opts': modeladmin.model._meta,
        'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        'select_across': request.POST.get('select_across', '0'),
    })


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('ref', 'school_name', 'project_title', 'track', 'status_col', 'judging_col', 'avg_col', 'sent_at')
    list_display_links = ('ref', 'school_name')
    list_filter = ('cycle', 'status', 'field', 'track', ('owner__profile__governorate', admin.RelatedOnlyFieldListFilter),
                   ('owner__profile__directorate', admin.RelatedOnlyFieldListFilter))
    show_facets = FACETS
    search_fields = ('ref', 'school_name', 'project_title', 'email', 'contact_person', 'phone', 'team_members')
    list_per_page = 50
    date_hierarchy = 'sent_at'
    inlines = [AssignmentInline, StatusLogInline]
    actions = ['change_status_action', 'auto_assign_action', 'message_schools_action', 'export_csv']
    readonly_fields = ('ref', 'owner_link', 'submitted_at', 'sent_at', 'updated_at', 'files_col', 'scores_table')
    fieldsets = (
        ('الطلب', {'fields': (('ref', 'cycle'), 'status', 'school_note', 'revision_deadline', 'internal_note')}),
        ('المشروع', {'fields': (('field', 'track'), 'project_title', 'abstract', 'team_members', 'supervisor',
                                'files_col', 'document', 'attachment')}),
        ('المدرسة', {'fields': ('owner_link', 'school_name', ('contact_person', 'phone'), 'email')}),
        ('التحكيم', {'fields': ('scores_table',)}),
        ('التواريخ', {'classes': ('collapse',), 'fields': (('submitted_at', 'sent_at', 'updated_at'),)}),
    )

    def get_queryset(self, request):
        return (super().get_queryset(request).select_related('track', 'cycle', 'owner')
                .prefetch_related('assignments__scores__criterion'))

    @admin.display(description='الحالة', ordering='status')
    def status_col(self, obj):
        b = status_badge(obj.status)
        if obj.results_hidden:
            b = format_html('{} <span title="النتيجة لم تُنشر للمدرسة بعد">🔒</span>', b)
        return b

    @admin.display(description='التحكيم')
    def judging_col(self, obj):
        return obj.judging_progress

    @admin.display(description='المتوسط /100')
    def avg_col(self, obj):
        v = obj.avg_score
        return '—' if v is None else format_html('<b>{}</b>', v)

    @admin.display(description='حساب المدرسة')
    def owner_link(self, obj):
        if not obj.owner_id:
            return '— (طلب قديم بدون حساب)'
        prof = getattr(obj.owner, 'profile', None)
        url = f'/admin/award/profile/{prof.pk}/change/' if prof else f'/admin/auth/user/{obj.owner_id}/change/'
        return format_html('<a href="{}">{}</a> — {}', url, prof.display_name if prof else obj.owner, obj.owner.email)

    @admin.display(description='فتح الملفات')
    def files_col(self, obj):
        links = []
        if obj.document:
            links.append(format_html('<a href="{}" target="_blank">📄 ملف البحث</a>', obj.document.url))
        if obj.attachment:
            links.append(format_html('<a href="{}" target="_blank">📎 المرفق</a>', obj.attachment.url))
        return format_html_join(' &nbsp; ', '{}', ((l,) for l in links)) if links else '—'

    @admin.display(description='الدرجات')
    def scores_table(self, obj):
        if not obj.pk:
            return '—'
        rows = []
        for a in obj.assignments.all():
            name = a.judge.get_full_name() or a.judge.email
            if not a.is_done:
                rows.append(format_html('<tr><td>{}</td><td colspan="3" style="color:#999">لم ينهِ التقييم</td></tr>', name))
                continue
            detail = ' · '.join(f'{s.criterion.name}: {s.value:g}/{s.criterion.max_score}' for s in a.scores.all())
            rows.append(format_html('<tr><td>{}</td><td><b>{}</b></td><td>{}</td><td>{}</td></tr>',
                                    name, a.total, a.get_recommendation_display() or '—', detail))
        if not rows:
            return 'لم يُسند لأي محكّم بعد — أضف محكّمين من الجدول أدناه أو استخدم «توزيع تلقائي».'
        avg = obj.avg_score
        return format_html('<table style="width:100%"><tr><th>المحكّم</th><th>/100</th><th>التوصية</th><th>التفاصيل</th></tr>{}'
                           '</table><p style="margin-top:8px"><b>المتوسط: {}</b></p>',
                           format_html_join('', '{}', ((r,) for r in rows)), '—' if avg is None else avg)

    # ---------- تغيير الحالة من صفحة الطلب ----------
    def save_model(self, request, obj, form, change):
        new_status = obj.status
        old_status = Submission.objects.filter(pk=obj.pk).values_list('status', flat=True).first() if change else None
        if change and old_status != new_status:
            obj.status = old_status
            super().save_model(request, obj, form, change)
            note = obj.school_note if new_status in ('revision', 'accepted', 'rejected', 'winner') else ''
            workflow.change_status(obj, new_status, by=request.user, note=note)
            msg = f'تم تغيير الحالة إلى «{obj.get_status_display()}»'
            msg += ' (النتيجة ستُرسل للمدرسة عند نشر نتائج الدورة).' if obj.results_hidden else ' وأُبلغت المدرسة.'
            self.message_user(request, msg)
        else:
            super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for o in formset.deleted_objects:
            o.delete()
        for inst in instances:
            is_new = inst.pk is None
            inst.save()
            if is_new and isinstance(inst, Assignment):
                sub = inst.submission
                notify(inst.judge, f'طلب جديد للتحكيم: {sub.ref}',
                       f"أُسند إليك تقييم مشروع «{sub.project_title}» — المسار: {sub.track or '—'}.",
                       f'/judge/{inst.pk}/', button='بدء التقييم')
        formset.save_m2m()

    # ---------- إجراءات بالجملة ----------
    @admin.action(description='تغيير الحالة (مع إشعار وملاحظة)…')
    def change_status_action(self, request, queryset):
        if 'apply' in request.POST:
            form = StatusChangeForm(request.POST)
            if form.is_valid():
                new, note, send = form.cleaned_data['status'], form.cleaned_data['note'], form.cleaned_data['notify_school']
                n = 0
                for sub in queryset.select_related('cycle', 'owner'):
                    if workflow.change_status(sub, new, by=request.user, note=note, notify_school=send):
                        n += 1
                self.message_user(request, f'تم تغيير حالة {n} طلب إلى «{dict(STATUS_CHOICES)[new]}».', messages.SUCCESS)
                return None
        else:
            form = StatusChangeForm()
        return _intermediate(self, request, queryset, form, 'تغيير حالة الطلبات المحددة', 'change_status_action',
                             'النتائج النهائية (مقبول/غير مقبول/فائز) لا تُرسل للمدرسة قبل «نشر النتائج» في الدورة.')

    @admin.action(description='توزيع تلقائي على المحكّمين')
    def auto_assign_action(self, request, queryset):
        subs = queryset.exclude(status__in=('draft', 'withdrawn')).select_related('cycle')
        n = workflow.auto_assign(subs)
        if n:
            self.message_user(request, f'تم إنشاء {n} إسناد وأُبلغ المحكّمون.', messages.SUCCESS)
        else:
            self.message_user(request, 'لم يُسند شيء — تأكد من وجود حسابات محكّمين مفعّلة (حسابات المدارس والمحكّمين ← النوع: محكّم).',
                              messages.WARNING)

    @admin.action(description='إرسال رسالة للمدارس صاحبة الطلبات…')
    def message_schools_action(self, request, queryset):
        users = User.objects.filter(pk__in=queryset.exclude(owner__isnull=True).values('owner_id'))
        return _send_message_action(self, request, queryset, users, 'message_schools_action')

    @admin.action(description='تصدير إلى Excel (CSV)')
    def export_csv(self, request, queryset):
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="submissions-{timezone.localdate()}.csv"'
        resp.write('﻿')
        w = csv.writer(resp)
        w.writerow(['رقم الطلب', 'الدورة', 'المدرسة', 'المحافظة', 'اللواء', 'المديرية', 'ضابط الارتباط', 'البريد', 'الهاتف', 'المجال', 'المسار',
                    'عنوان المشروع', 'المشرف', 'الطلبة', 'الحالة', 'تاريخ الإرسال', 'التحكيم', 'المتوسط'])
        for s in queryset.select_related('cycle', 'field', 'track', 'owner__profile__governorate', 'owner__profile__area',
                                         'owner__profile__directorate').prefetch_related('assignments__scores__criterion'):
            pr = getattr(s.owner, 'profile', None) if s.owner_id else None
            w.writerow([s.ref, s.cycle or '', s.school_name, getattr(pr, 'governorate', '') or '', getattr(pr, 'area', '') or '',
                        getattr(pr, 'directorate', '') or '', s.contact_person, s.email, s.phone, s.field or '',
                        s.track or '', s.project_title, s.supervisor, ' | '.join(s.team_members.splitlines()),
                        s.get_status_display(), timezone.localtime(s.sent_at).strftime('%Y-%m-%d %H:%M') if s.sent_at else '',
                        s.judging_progress, s.avg_score if s.avg_score is not None else ''])
        return resp


def _send_message_action(modeladmin, request, queryset, users, action):
    if 'apply' in request.POST:
        form = MessageForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            n = 0
            for u in users:
                notify(u, d['title'], d['body'], d['url'], email=d['email'])
                n += 1
            modeladmin.message_user(request, f'أُرسلت الرسالة إلى {n} حساب.', messages.SUCCESS)
            return None
    else:
        form = MessageForm()
    return _intermediate(modeladmin, request, queryset, form, f'رسالة إلى {users.count()} حساب', action,
                         'تظهر في جرس الإشعارات داخل الموقع، وتُرسل بالبريد لمن فعّل الإشعارات.')


# =====================================================
#   الحسابات
# =====================================================
class ProfileAddForm(forms.ModelForm):
    email = forms.EmailField(label='البريد الإلكتروني (للدخول)')
    send_invite = forms.BooleanField(label='إرسال دعوة بالبريد ليختار كلمة المرور', required=False, initial=True)

    class Meta:
        model = Profile
        fields = ('role', 'email', 'contact_person', 'school_name', 'phone', 'governorate', 'area', 'directorate',
                  'specialty', 'judge_fields', 'send_invite')

    def clean_email(self):
        e = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(Q(email__iexact=e) | Q(username__iexact=e)).exists():
            raise forms.ValidationError('يوجد حساب بهذا البريد.')
        return e


def _send_invite(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    role = getattr(getattr(user, 'profile', None), 'role', 'school')
    intro = ('تمت دعوتك كمحكّم في جائزة انتصار عباس جردانة.' if role == 'judge'
             else 'تم إنشاء حساب لمدرستكم في جائزة انتصار عباس جردانة.')
    send_email(user.email, 'دعوة إلى حسابك — جائزة انتصار عباس جردانة',
               f"مرحباً {user.first_name or ''}،\n{intro}\nاضغط الزر لاختيار كلمة المرور ثم الدخول. الرابط صالح 3 أيام.",
               f"{request.scheme}://{request.get_host()}/accounts/reset/{uid}/{token}/", 'اختيار كلمة المرور')


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'role', 'email_col', 'phone', 'governorate', 'directorate', 'active_col', 'subs_col', 'created_at')
    list_display_links = ('display_name',)
    list_filter = ('role', 'user__is_active', 'governorate', ('directorate', admin.RelatedOnlyFieldListFilter))
    show_facets = FACETS
    search_fields = ('school_name', 'contact_person', 'user__email', 'phone', 'city', 'specialty')
    filter_horizontal = ('judge_fields',)
    actions = ['activate', 'deactivate', 'send_invites', 'make_judge', 'message_action']
    readonly_fields = ('email_col', 'active_col', 'created_at', 'last_login_col')
    fieldsets = (
        (None, {'fields': ('role', 'email_col', 'active_col', 'last_login_col')}),
        ('البيانات', {'fields': ('school_name', 'contact_person', 'phone', 'email_notifications')}),
        ('الموقع', {'fields': ('governorate', 'area', 'directorate')}),
        ('للمحكّم', {'fields': ('specialty', 'judge_fields')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'governorate', 'directorate').annotate(
            _subs=Count('user__submissions', filter=~Q(user__submissions__status='draft')))

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = ProfileAddForm
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return ((None, {'fields': ('role', 'email', 'send_invite')}),
                    ('البيانات', {'fields': ('contact_person', 'school_name', 'phone', 'governorate', 'area', 'directorate')}),
                    ('للمحكّم', {'fields': ('specialty', 'judge_fields')}))
        return self.fieldsets

    def get_readonly_fields(self, request, obj=None):
        return () if obj is None else self.readonly_fields

    def save_model(self, request, obj, form, change):
        if not change:
            email = form.cleaned_data['email']
            user = User.objects.create_user(username=email, email=email, first_name=(obj.contact_person or '')[:150])
            user.set_unusable_password()
            user.save()
            obj.user = user
            super().save_model(request, obj, form, change)
            if form.cleaned_data.get('send_invite'):
                _send_invite(request, user)
                self.message_user(request, f'أُرسلت دعوة إلى {email}.')
        else:
            super().save_model(request, obj, form, change)

    @admin.display(description='البريد', ordering='user__email')
    def email_col(self, obj):
        return obj.user.email

    @admin.display(description='مفعّل؟', boolean=True, ordering='user__is_active')
    def active_col(self, obj):
        return obj.user.is_active

    @admin.display(description='آخر دخول')
    def last_login_col(self, obj):
        return obj.user.last_login or 'لم يدخل بعد'

    @admin.display(description='الطلبات', ordering='_subs')
    def subs_col(self, obj):
        return obj._subs if obj.role == 'school' else obj.user.assignments.count()

    @admin.action(description='تفعيل الحسابات')
    def activate(self, request, queryset):
        n = User.objects.filter(profile__in=queryset).update(is_active=True)
        self.message_user(request, f'تم تفعيل {n} حساب.')

    @admin.action(description='إيقاف الحسابات')
    def deactivate(self, request, queryset):
        n = User.objects.filter(profile__in=queryset).exclude(is_superuser=True).update(is_active=False)
        self.message_user(request, f'تم إيقاف {n} حساب.')

    @admin.action(description='إرسال رابط اختيار/استعادة كلمة المرور')
    def send_invites(self, request, queryset):
        n = 0
        for p in queryset.select_related('user'):
            if p.user.email:
                if not p.user.is_active:
                    p.user.is_active = True
                    p.user.save(update_fields=['is_active'])
                _send_invite(request, p.user)
                n += 1
        self.message_user(request, f'أُرسل الرابط إلى {n} حساب.')

    @admin.action(description='تحويل إلى محكّم')
    def make_judge(self, request, queryset):
        n = queryset.update(role='judge')
        self.message_user(request, f'تم تحويل {n} حساب إلى محكّم.')

    @admin.action(description='إرسال رسالة/إشعار للمحدّدين…')
    def message_action(self, request, queryset):
        users = User.objects.filter(profile__in=queryset)
        return _send_message_action(self, request, queryset, users, 'message_action')


# =====================================================
#   التحكيم
# =====================================================
class ScoreInline(admin.TabularInline):
    model = Score
    extra = 0
    fields = ('criterion', 'value', 'note')


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('submission', 'judge_name', 'assigned_at', 'done_col', 'total_col', 'recommendation')
    list_filter = ('submission__cycle', ('completed_at', admin.EmptyFieldListFilter), 'judge', 'recommendation')
    show_facets = FACETS
    search_fields = ('submission__ref', 'submission__project_title', 'judge__email', 'judge__first_name')
    autocomplete_fields = ('submission',)
    inlines = [ScoreInline]
    actions = ['reopen', 'remind']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('submission', 'judge').prefetch_related('scores__criterion')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'judge':
            kwargs['queryset'] = User.objects.filter(profile__role='judge')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None
        super().save_model(request, obj, form, change)
        if is_new:
            sub = obj.submission
            notify(obj.judge, f'طلب جديد للتحكيم: {sub.ref}', f"أُسند إليك تقييم مشروع «{sub.project_title}».",
                   f'/judge/{obj.pk}/', button='بدء التقييم')

    @admin.display(description='المحكّم', ordering='judge__first_name')
    def judge_name(self, obj):
        return obj.judge.get_full_name() or obj.judge.email

    @admin.display(description='أنهى التقييم؟', boolean=True, ordering='completed_at')
    def done_col(self, obj):
        return obj.is_done

    @admin.display(description='الدرجة /100')
    def total_col(self, obj):
        return obj.total if obj.is_done else '—'

    @admin.action(description='إعادة فتح التقييم للمحكّم')
    def reopen(self, request, queryset):
        n = queryset.update(completed_at=None)
        self.message_user(request, f'أُعيد فتح {n} تقييم.')

    @admin.action(description='تذكير المحكّمين بالتقييمات غير المنتهية')
    def remind(self, request, queryset):
        n = 0
        for a in queryset.filter(completed_at__isnull=True).select_related('submission', 'judge'):
            notify(a.judge, f'تذكير: تقييم الطلب {a.submission.ref}',
                   f"بانتظار تقييمك لمشروع «{a.submission.project_title}».", f'/judge/{a.pk}/', button='فتح التقييم')
            n += 1
        self.message_user(request, f'أُرسل {n} تذكير.')


@admin.register(Criterion)
class CriterionAdmin(admin.ModelAdmin):
    list_display = ('name', 'max_score', 'weight', 'cycle', 'track', 'order')
    list_editable = ('max_score', 'weight', 'order')
    list_display_links = ('name',)
    list_filter = ('cycle', 'track')
    show_facets = FACETS
    search_fields = ('name', 'description')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'level', 'is_read', 'created_at')
    list_filter = ('is_read', 'level', 'created_at')
    show_facets = FACETS
    search_fields = ('title', 'body', 'user__email')
    readonly_fields = ('user', 'title', 'body', 'url', 'level', 'is_read', 'created_at')

    def has_add_permission(self, request):
        return False


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ('subject', 'to', 'status_col', 'created_at')
    list_filter = ('status', 'created_at')
    show_facets = FACETS
    search_fields = ('to', 'subject', 'error')
    readonly_fields = ('to', 'subject', 'status', 'error', 'created_at')

    def has_add_permission(self, request):
        return False

    @admin.display(description='الحالة', ordering='status')
    def status_col(self, obj):
        c = {'sent': '#188038', 'saved': '#e8710a', 'failed': '#d93025'}.get(obj.status, '#666')
        return format_html('<b style="color:{}">{}</b>', c, obj.get_status_display())


# =====================================================
#   المحافظات والألوية ومديريات التربية (تظهر في نموذج تسجيل المدرسة)
# =====================================================
class AreaInline(admin.TabularInline):
    model = Area
    extra = 0
    fields = ('order', 'name', 'directorate')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'directorate':
            gid = request.resolver_match.kwargs.get('object_id') if request.resolver_match else None
            qs = Directorate.objects.all()
            if gid:
                qs = qs.filter(Q(governorate_id=gid) | Q(governorate__isnull=True))
            kwargs['queryset'] = qs
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class DirectorateInline(admin.TabularInline):
    model = Directorate
    extra = 0
    fields = ('order', 'name', 'is_active')


@admin.register(Governorate)
class GovernorateAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'areas_n', 'dirs_n', 'schools_n')
    list_editable = ('order',)
    list_display_links = ('name',)
    search_fields = ('name',)
    inlines = [DirectorateInline, AreaInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _a=Count('areas', distinct=True), _d=Count('directorates', distinct=True),
            _s=Count('profile', filter=Q(profile__role='school'), distinct=True))

    @admin.display(description='الألوية', ordering='_a')
    def areas_n(self, obj): return obj._a

    @admin.display(description='المديريات', ordering='_d')
    def dirs_n(self, obj): return obj._d

    @admin.display(description='المدارس المسجّلة', ordering='_s')
    def schools_n(self, obj): return obj._s


@admin.register(Directorate)
class DirectorateAdmin(admin.ModelAdmin):
    list_display = ('name', 'governorate', 'is_active', 'order', 'schools_n')
    list_editable = ('is_active', 'order')
    list_display_links = ('name',)
    list_filter = ('governorate', 'is_active')
    show_facets = FACETS
    search_fields = ('name', 'governorate__name')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('governorate').annotate(
            _s=Count('profile', filter=Q(profile__role='school')))

    @admin.display(description='المدارس المسجّلة', ordering='_s')
    def schools_n(self, obj): return obj._s


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ('name', 'governorate', 'directorate', 'order')
    list_editable = ('order',)
    list_display_links = ('name',)
    list_filter = ('governorate',)
    show_facets = FACETS
    search_fields = ('name', 'governorate__name')


# =====================================================
#   التواصل الاجتماعي + إعدادات الحسابات والهيدر
# =====================================================
@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):
    list_display = ('icon_preview', 'platform', 'url', 'is_active', 'order')
    list_display_links = ('icon_preview', 'platform')
    list_editable = ('url', 'is_active', 'order')
    list_filter = ('is_active', 'platform')
    show_facets = FACETS
    search_fields = ('url', 'platform')
    actions = ['show_links', 'hide_links']

    class Media:
        css = {'all': ('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css',)}

    @admin.display(description='الأيقونة')
    def icon_preview(self, obj):
        return format_html('<i class="{}" style="font-size:20px;color:{}"></i>', obj.icon_class, obj.color or '#0a1632')

    @admin.action(description='إظهار الروابط المحددة')
    def show_links(self, request, queryset):
        for o in queryset:
            o.is_active = True
            o.save()
        self.message_user(request, f'تم إظهار {queryset.count()} رابط. (الرابط الفارغ لا يظهر في الموقع)')

    @admin.action(description='إخفاء الروابط المحددة')
    def hide_links(self, request, queryset):
        for o in queryset:
            o.is_active = False
            o.save()
        self.message_user(request, f'تم إخفاء {queryset.count()} رابط.')

    def delete_queryset(self, request, queryset):
        from django.core.cache import cache
        super().delete_queryset(request, queryset)
        cache.delete('iaj_social')


@admin.register(PortalSetting)
class PortalSettingAdmin(admin.ModelAdmin):
    fieldsets = (
        ('أزرار الهيدر', {'fields': (('show_login_btn', 'login_btn_text'), 'account_btn_text', 'show_register_btn')}),
        ('شريط التواصل الاجتماعي', {'fields': ('social_title', 'social_in_footer', 'social_in_menu'),
                                     'description': 'الروابط نفسها من «روابط التواصل الاجتماعي».'}),
        ('نصوص صفحات الحساب', {'fields': ('login_intro', 'signup_title', 'signup_intro', 'submit_intro', 'show_spam_hint')}),
        ('العداد', {'fields': ('countdown_badge',)}),
        ('شعار الجائزة على الصور والفيديو', {'fields': ('wm_enabled', ('wm_position', 'wm_size', 'wm_opacity'), 'captions_enabled'),
                                            'description': 'يظهر الشعار أعلى كل صورة وفيديو في الموقع (المعرض، الفيديو، الأخبار، شرائح الصفحة الرئيسية). '
                                                           'نص الشرح يُكتب لكل صورة/فيديو في حقل «نص الشرح» ويمكن إخفاؤه لكل عنصر.'}),
        ('الدورات في الموقع', {'fields': ('show_cycle_filter',)}),
    )

    def has_add_permission(self, request):
        return not PortalSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        from django.shortcuts import redirect
        obj = PortalSetting.get()
        return redirect(f'/admin/award/portalsetting/{obj.pk}/change/')


# =====================================================
#   ربط المواد بالدورات: فلتر + عمود + نقل جماعي إلى دورة
# =====================================================
class MoveCycleForm(forms.Form):
    cycle = forms.ModelChoiceField(AwardCycle.objects.all(), required=False, label='الدورة',
                                   empty_label='— عام (بدون دورة) —')


def _move_to_cycle(modeladmin, request, queryset):
    if 'apply' in request.POST:
        form = MoveCycleForm(request.POST)
        if form.is_valid():
            n = queryset.update(cycle=form.cleaned_data['cycle'])
            from .site_cache import clear_home_bundle
            clear_home_bundle()
            modeladmin.message_user(request, f'تم نقل {n} عنصر إلى «{form.cleaned_data["cycle"] or "عام"}».', messages.SUCCESS)
            return None
    else:
        form = MoveCycleForm()
    return _intermediate(modeladmin, request, queryset, form, 'نقل إلى دورة', 'move_to_cycle')


_move_to_cycle.short_description = 'نقل المحدد إلى دورة…'


def _attach_cycle_admin():
    from .models import Photo, Video, News, SuccessStory, Winner, MediaGallery, TimelineEvent
    for model in (Photo, Video, News, SuccessStory, Winner, MediaGallery, TimelineEvent):
        ma = admin.site._registry.get(model)
        if not ma:
            continue
        ld = list(ma.list_display)
        if 'cycle' not in ld:
            ld.insert(min(2, len(ld)), 'cycle')
            ma.list_display = tuple(ld)
        if 'cycle' not in (ma.list_filter or ()):
            ma.list_filter = ('cycle',) + tuple(ma.list_filter or ())
        ma.show_facets = FACETS
        acts = list(ma.actions or [])
        if 'move_to_cycle' not in [a if isinstance(a, str) else getattr(a, '__name__', '') for a in acts]:
            acts.append(_move_to_cycle)
        ma.actions = acts


_move_to_cycle.__name__ = 'move_to_cycle'
_attach_cycle_admin()


# =====================================================
#   الملفات، المراسلات، اللجان، الإعلانات (العمل اليومي من /manage/)
# =====================================================
class SubmissionFileInline(admin.TabularInline):
    model = SubmissionFile
    extra = 0
    fields = ('file', 'title', 'kind', 'size', 'after_submit', 'created_at')
    readonly_fields = ('kind', 'size', 'after_submit', 'created_at')


class SubmissionMessageInline(admin.TabularInline):
    model = SubmissionMessage
    extra = 0
    fields = ('created_at', 'from_staff', 'sender', 'body', 'attachment', 'is_read')
    readonly_fields = ('created_at', 'sender')


SubmissionAdmin.inlines = [AssignmentInline, SubmissionFileInline, SubmissionMessageInline, StatusLogInline]


@admin.register(SubmissionMessage)
class SubmissionMessageAdmin(admin.ModelAdmin):
    list_display = ('submission', 'from_staff', 'short', 'is_read', 'created_at')
    list_filter = ('from_staff', 'is_read', 'submission__cycle')
    show_facets = FACETS
    search_fields = ('body', 'submission__ref', 'submission__school_name')

    @admin.display(description='الرسالة')
    def short(self, obj):
        return obj.body[:80]


@admin.register(JudgingCommittee)
class JudgingCommitteeAdmin(admin.ModelAdmin):
    list_display = ('name', 'cycle', 'chair', 'members_n')
    list_filter = ('cycle',)
    show_facets = FACETS
    filter_horizontal = ('fields', 'tracks', 'members')
    search_fields = ('name',)

    @admin.display(description='الأعضاء')
    def members_n(self, obj):
        return obj.members.count()


class AnnouncementMediaInline(admin.TabularInline):
    model = AnnouncementMedia
    extra = 1
    fields = ('order', 'file', 'youtube_url', 'caption')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'cycle', 'is_published', 'show_on_home', 'pinned', 'publish_date')
    list_editable = ('is_published', 'show_on_home', 'pinned')
    list_display_links = ('title',)
    list_filter = ('cycle', 'kind', 'is_published', 'show_on_home')
    show_facets = FACETS
    search_fields = ('title', 'body')
    inlines = [AnnouncementMediaInline]
