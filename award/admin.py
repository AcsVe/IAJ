from django.utils.safestring import mark_safe
from django.contrib import admin
from django import forms
from .models import (
    Field, Track, Submission, SiteSetting, HeroSlide, TimelineEvent,
    Judge, ThemeSetting, HomeContent, FooterContent, SuccessPageContent,
    SectionBackground, Sponsor, FAQ, Winner, WinnerCategory, MediaGallery,
    ContactMessage, TickerItem, SlideshowCard, TickerSetting, News,
    Photo, Video, SuccessStory, HeroCard, StoredFile, Principle, HeroTextSlide, TrackDetail
)
from django.utils.html import format_html


@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = ('cover_thumb', 'name_ar', 'name_en')
    list_display_links = ('cover_thumb', 'name_ar')
    fields = ('name_ar', 'name_en', 'cover_image', 'cover_overlay')

    @admin.display(description='الغلاف')
    def cover_thumb(self, obj):
        if obj.cover_image:
            return format_html('<img src="{}" style="height:44px;width:70px;object-fit:cover;border-radius:6px">', obj.cover_image.url)
        return '—'


class QuillEditorWidget(forms.Textarea):
    """محرر Quill يُحمّل من CDN — لا يحتاج أي باكدج"""
    template_name = 'award/quill_editor_widget.html'

    class Media:
        css = {
            'all': (
                'https://cdn.quilljs.com/1.3.7/quill.snow.css',
            )
        }
        js = (
            'https://cdn.quilljs.com/1.3.7/quill.min.js',
        )


SUGGESTED_TRACK_ROWS = [
    ('ما هو المسار؟', 'fa-circle-info'),
    ('الفئة المستهدفة', 'fa-users'),
    ('أمثلة على المشاريع', 'fa-lightbulb'),
    ('المتطلبات', 'fa-list-check'),
    ('معايير التقييم', 'fa-scale-balanced'),
    ('المخرجات المتوقعة', 'fa-flag-checkered'),
]


class TrackDetailInline(admin.TabularInline):
    model = TrackDetail
    fields = ('order', 'title', 'content', 'icon')
    extra = 1
    verbose_name = 'بند'
    verbose_name_plural = 'جدول تفاصيل المسار — كل صف بند (مثل: الفئة المستهدفة، أمثلة، معايير التقييم). كل سطر في «التفاصيل» يظهر كنقطة.'

    def get_extra(self, request, obj=None, **kwargs):
        # مسار جديد أو بدون تفاصيل ← صفوف مقترحة جاهزة للتعبئة (الفارغ منها يُتجاهل عند الحفظ)
        if obj is None or not obj.details.exists():
            return len(SUGGESTED_TRACK_ROWS)
        return 1

    def get_formset(self, request, obj=None, **kwargs):
        fs = super().get_formset(request, obj, **kwargs)
        if obj is None or not obj.details.exists():
            init = [{'title': t, 'icon': i, 'order': n + 1} for n, (t, i) in enumerate(SUGGESTED_TRACK_ROWS)]

            class _FS(fs):
                def __init__(self, *a, **kw):
                    kw.setdefault('initial', init)
                    super().__init__(*a, **kw)
            return _FS
        return fs


class TrackAdminForm(forms.ModelForm):
    class Meta:
        model = Track
        fields = '__all__'
        widgets = {
            'details_html': QuillEditorWidget(attrs={'rows': 10, 'style': 'width:100%'}),
            'description_ar': forms.Textarea(attrs={'rows': 3, 'style': 'width:100%'}),
        }


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    form = TrackAdminForm
    list_display = ('name_ar', 'field', 'is_active', 'notice_enabled', 'details_count', 'order', 'view_link')
    list_editable = ('is_active', 'notice_enabled', 'order')
    list_filter = ('is_active', 'field', 'notice_enabled')
    actions = ['enable_tracks', 'disable_tracks', 'show_notice', 'hide_notice']
    list_display_links = ('name_ar',)
    search_fields = ('name_ar', 'name_en', 'description_ar', 'details_html', 'details__content', 'details__title')
    inlines = [TrackDetailInline]
    fieldsets = (
        ('المسار', {'fields': ('field', 'name_ar', 'name_en', 'order', 'is_active')}),
        ('شريط ملاحظة متحرك (اختياري)', {
            'fields': ('notice_enabled', 'notice_text', 'notice_speed'),
            'description': 'يظهر أعلى شرح المسار في النافذة المنبثقة وصفحة المسار، بنفس ألوان الصندوق.',
        }),
        ('النبذة والشرح', {
            'fields': ('description_ar', 'details_html', 'description_en'),
            'description': 'ترتيب العرض في صفحة المسار: النبذة ← جدول التفاصيل (بالأسفل) ← الشرح التفصيلي ← زر «قدّم في هذا المسار».',
        }),
    )

    def _done(self, request, n, msg):
        from .site_cache import clear_home_bundle
        clear_home_bundle()
        self.message_user(request, f'{msg}: {n}')

    @admin.action(description='تمكين المسارات المحددة')
    def enable_tracks(self, request, qs):
        self._done(request, qs.update(is_active=True), 'تم تمكين')

    @admin.action(description='تعطيل المسارات المحددة')
    def disable_tracks(self, request, qs):
        self._done(request, qs.update(is_active=False), 'تم تعطيل')

    @admin.action(description='إظهار شريط الملاحظة للمحدد')
    def show_notice(self, request, qs):
        self._done(request, qs.update(notice_enabled=True), 'تم إظهار الشريط')

    @admin.action(description='إخفاء شريط الملاحظة للمحدد')
    def hide_notice(self, request, qs):
        self._done(request, qs.update(notice_enabled=False), 'تم إخفاء الشريط')

    @admin.display(description='بنود التفاصيل')
    def details_count(self, obj):
        return obj.details.count()

    @admin.display(description='الصفحة')
    def view_link(self, obj):
        return format_html('<a href="{}" target="_blank">عرض ↗</a>', obj.get_absolute_url())

    class Media:
        js = ('award/js/quill_init.js',)


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    fieldsets = (
        ('الشعار', {'fields': ('site_logo', ('logo_size', 'logo_size_scrolled', 'logo_size_mobile'))}),
        ('بطاقة الفيديو/الصور بجانب النص المتحرك', {
            'fields': ('slide_seconds', 'slide_show_timer', 'hero_side_video', 'hero_side_video_url', 'hero_side_image'),
            'description': mark_safe(
                'لعرض عدة صور وفيديوهات تتبدّل: أضفها من '
                '<a href="/admin/award/heroslide/"><b>بطاقة الفيديو والصور — الشرائح</b></a>. '
                'الحقول بالأسفل تُستخدم فقط إذا لم توجد شرائح. '
                'النص تحت البطاقة من: <a href="/admin/award/herocard/"><b>النص تحت الفيديو/الصورة</b></a>.'),
        }),
        ('العداد التنازلي', {'fields': ('registration_deadline', ('cd_show_days', 'cd_show_hours', 'cd_show_minutes', 'cd_show_seconds'))}),
    )

    def has_add_permission(self, request):
        return not SiteSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ('thumb', '__str__', 'media_type', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_display_links = ('thumb', '__str__')
    list_filter = ('media_type', 'is_active')
    actions = ['make_active', 'make_hidden']
    fields = ('media_type', 'media_file', 'youtube_url', 'poster', 'title', 'caption', 'show_caption', 'click_action', 'link_url', 'order', 'is_active')

    @admin.display(description='معاينة')
    def thumb(self, obj):
        k = obj.kind
        if k == 'image':
            return format_html('<img src="{}" style="height:48px;width:86px;object-fit:cover;border-radius:6px">', obj.media_file.url)
        if k == 'youtube':
            return format_html('<img src="https://i.ytimg.com/vi/{}/mqdefault.jpg" style="height:48px;width:86px;object-fit:cover;border-radius:6px">', obj.youtube_id)
        if k == 'video':
            if obj.poster:
                return format_html('<img src="{}" style="height:48px;width:86px;object-fit:cover;border-radius:6px">', obj.poster.url)
            return format_html('<span style="font-size:22px">🎬</span>')
        return '—'

    @admin.action(description='إظهار الشرائح المحددة')
    def make_active(self, request, qs):
        qs.update(is_active=True)
        from .site_cache import clear_home_bundle
        clear_home_bundle()

    @admin.action(description='إخفاء الشرائح المحددة')
    def make_hidden(self, request, qs):
        qs.update(is_active=False)
        from .site_cache import clear_home_bundle
        clear_home_bundle()


@admin.register(TimelineEvent)
class TimelineEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'order', 'is_highlighted')
    list_editable = ('order', 'is_highlighted')
    list_display_links = ('title',)


@admin.register(Judge)
class JudgeAdmin(admin.ModelAdmin):
    list_display = ('name', 'title', 'order')
    list_editable = ('order',)
    list_display_links = ('name',)


class FontSelect(forms.Select):
    """قائمة خطوط + نموذج حيّ بالخط المختار تحتها"""

    def render(self, name, value, attrs=None, renderer=None):
        from .fonts import all_font_urls
        html = super().render(name, value, attrs, renderer)
        sid = (attrs or {}).get('id', name)
        links = ''.join(f'<link rel="stylesheet" href="{u}">' for _n, u in all_font_urls())
        script = (
            '<script>(function(){if(window.__iajFonts)return;window.__iajFonts=1;'
            f'document.head.insertAdjacentHTML("beforeend",{links!r});'
            'function upd(sel){var f=sel.value||(document.getElementById("id_font_body")||{}).value||"Cairo";'
            'var s=document.getElementById(sel.id+"_sample");if(s)s.style.fontFamily="\'"+f+"\', Cairo, sans-serif";}'
            'document.addEventListener("DOMContentLoaded",function(){var all=document.querySelectorAll("select.iaj-font");'
            'all.forEach(function(sel){[].forEach.call(sel.options,function(o){if(o.value)o.style.fontFamily="\'"+o.value+"\'";});'
            'upd(sel);sel.addEventListener("change",function(){all.forEach(upd);});});});})();</script>')
        sample = (f'<div id="{sid}_sample" class="iaj-font-sample" style="margin-top:6px;padding:8px 12px;border:1px dashed #c5a059;'
                  'border-radius:8px;font-size:20px;line-height:1.6;max-width:520px">جائزة انتصار عباس جردانة للثقافة والتعليم — 1448هـ / 2026م</div>')
        return mark_safe(html + sample + script)

    def __init__(self, attrs=None, choices=()):
        attrs = {**(attrs or {}), 'class': 'iaj-font'}
        super().__init__(attrs, choices)


@admin.register(ThemeSetting)
class ThemeSettingAdmin(admin.ModelAdmin):
    fieldsets = (
        ('الألوان', {'fields': ('primary_color', 'secondary_color', 'gold_color')}),
        ('الخطوط — اختر خطاً لكل عنصر', {
            'fields': ('font_body', 'font_headings', 'font_site_title', 'font_nav', 'font_ticker', 'font_hero',
                       'font_cards', 'font_buttons', 'font_numbers', 'font_footer', 'font_size'),
            'description': 'تحت كل قائمة نموذج حيّ للخط. «نفس خط النص الأساسي» = يتبع الخط الأول. '
                           'استخدم زر «👁 معاينة قبل الحفظ» بالأسفل لرؤية الموقع بالخطوط الجديدة قبل نشرها.',
        }),
        ('النمط العام', {'fields': ('site_style', 'flip_style')}),
        ('CSS مخصص (للمدير التقني)', {'fields': ('custom_css',), 'classes': ('collapse',)}),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name.startswith('font_') and db_field.name != 'font_size':
            from .fonts import FONT_CHOICES, INHERIT_CHOICES
            kwargs['widget'] = FontSelect(choices=FONT_CHOICES if db_field.name == 'font_body' else INHERIT_CHOICES)
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def has_add_permission(self, request):
        return not ThemeSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HomeContent)
class HomeContentAdmin(admin.ModelAdmin):
    fieldsets = (
        ('النص المتحرك أعلى الصفحة', {
            'fields': ('hero_title', 'hero_subtitle'),
            'description': 'العنوان والنص اللذان يتحركان للأعلى فوق الصورة الرئيسية.',
        }),
        ('أزرار التسجيل', {'fields': ('btn_navbar', 'btn_hero')}),
        ('قسم «عن الجائزة»', {'fields': ('title_about', 'about_text', 'vision_text', 'mission_text'),
                               'description': 'النص يحترم الأسطر والفقرات كما تكتبها. بطاقات المبادئ تُدار من: «مبادئ الجائزة».'}),
        ('عناوين الأقسام', {'fields': ('title_fields', 'title_timeline', 'title_judges', 'title_sponsors'), 'classes': ('collapse',)}),
        ('قسم «طلب التقديم» — الشروط والخطوات', {'fields': ('title_apply', 'condition_1', 'condition_2', 'condition_3', 'condition_4', 'condition_5',
                                                            'step_1', 'step_2', 'step_3', 'step_4', 'step_5'), 'classes': ('collapse',)}),
        ('قسم «الجوائز»', {'fields': ('title_prizes', 'prize_1_desc', 'prize_2_desc', 'prize_3_desc'), 'classes': ('collapse',)}),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'hero_title' in form.base_fields:
            form.base_fields['hero_title'].widget.attrs.update({'rows': 5, 'style': 'width:600px'})
        if 'hero_subtitle' in form.base_fields:
            form.base_fields['hero_subtitle'].widget.attrs.update({'rows': 5, 'style': 'width:600px'})
        return form

    def has_add_permission(self, request):
        return not HomeContent.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FooterContent)
class FooterContentAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not FooterContent.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SuccessPageContent)
class SuccessPageContentAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SuccessPageContent.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SectionBackground)
class SectionBackgroundAdmin(admin.ModelAdmin):
    list_display = ('section_id', 'bg_color', 'heading_color', 'text_color', 'is_parallax')
    list_editable = ('is_parallax',)
    list_display_links = ('section_id',)

    fieldsets = (
        ('القسم', {
            'fields': ('section_id',),
            'description': 'اختر القسم اللي تبي تتحكم بتصميمه',
        }),
        ('خلفية القسم', {
            'fields': (
                'bg_image', 'bg_color', 'bg_color_2',
                'enable_overlay', 'overlay_color', 'overlay_color_2', 'overlay_opacity',
                'is_parallax',
            ),
            'classes': ('wide',),
        }),
        ('لون وحجم العنوان الرئيسي (h2)', {
            'fields': ('heading_color', 'heading_size', 'gold_line_color'),
            'description': 'التحكم بلون وحجم عنوان القسم الكبير والخط الذهبي تحته',
            'classes': ('collapse',),
        }),
        ('لون وحجم العناوين الفرعية (h3, h4, h5)', {
            'fields': ('sub_heading_color', 'sub_heading_size'),
            'description': 'للعناوين الداخلية داخل القسم',
            'classes': ('collapse',),
        }),
        ('لون وحجم النصوص', {
            'fields': ('text_color', 'text_size'),
            'description': 'للفقرات والنصوص العامة داخل القسم',
            'classes': ('collapse',),
        }),
    )


@admin.register(Sponsor)
class SponsorAdmin(admin.ModelAdmin):
    list_display = ('name', 'tier', 'order')
    list_editable = ('order',)
    list_display_links = ('name',)


class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'order')
    list_editable = ('order',)
    list_display_links = ('question',)


@admin.register(WinnerCategory)
class WinnerCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_display_links = ('name',)


@admin.register(Winner)
class WinnerAdmin(admin.ModelAdmin):
    list_display = ('school_name', 'category', 'year', 'project_title', 'rank', 'is_active')
    list_editable = ('is_active',)
    list_display_links = ('school_name',)
    list_filter = ('category', 'year')
    search_fields = ('school_name', 'project_title')


class MediaGalleryAdmin(admin.ModelAdmin):
    list_display = ('title', 'media_type', 'order')
    list_editable = ('order',)
    list_display_links = ('title',)


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at', 'is_active')
    list_editable = ('is_active',)
    list_display_links = ('title',)
    search_fields = ('title',)


class NewsAdminForm(forms.ModelForm):
    class Meta:
        model = News
        fields = '__all__'
        widgets = {
            'content': QuillEditorWidget(attrs={'rows': 10, 'style': 'width:100%'}),
        }


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    form = NewsAdminForm
    list_display = ('title', 'date', 'is_published')
    list_editable = ('is_published',)
    list_display_links = ('title',)
    fieldsets = (
        (None, {
            'fields': ('title', 'image', 'content', 'date', 'cycle', 'is_published')
        }),
    )

    class Media:
        js = ('award/js/quill_init.js',)


class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'is_read', 'created_at')
    list_editable = ('is_read',)
    list_display_links = ('name',)


@admin.register(TickerItem)
class TickerItemAdmin(admin.ModelAdmin):
    list_display = ('message_html', 'is_active', 'order')
    list_editable = ('is_active', 'order')
    list_display_links = ('message_html',)


class SlideshowCardAdmin(admin.ModelAdmin):
    list_display = ('card_type', 'order', 'heading', 'is_active')
    list_filter = ('card_type', 'is_active')
    list_editable = ('order', 'is_active')
    list_display_links = ('card_type',)


@admin.register(HeroTextSlide)
class HeroTextSlideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'effect', 'effect_speed', 'seconds', 'order', 'is_active')
    list_editable = ('effect', 'effect_speed', 'seconds', 'order', 'is_active')
    list_filter = ('is_active', 'effect')
    search_fields = ('heading', 'body_text')
    fieldsets = (
        (None, {'fields': ('heading', 'body_text')}),
        ('الحركة والمدة', {'fields': ('effect', 'effect_speed', 'seconds'),
                           'description': 'اختر حركة ظهور هذا النص وسرعتها، ومدة بقائه قبل الانتقال للنص التالي.'}),
        ('العرض', {'fields': ('order', 'is_active')}),
    )
    actions = ['make_active', 'make_inactive']

    @admin.action(description='إظهار النصوص المحددة')
    def make_active(self, request, qs):
        for o in qs: o.is_active = True; o.save(update_fields=['is_active'])

    @admin.action(description='إخفاء النصوص المحددة')
    def make_inactive(self, request, qs):
        for o in qs: o.is_active = False; o.save(update_fields=['is_active'])

    def changelist_view(self, request, extra_context=None):
        card = HeroCard.objects.first()
        if card is not None and not card.is_enabled:
            from django.contrib import messages
            messages.warning(request, mark_safe('بطاقة النصوص <b>مخفية</b> حالياً، لذلك لا تظهر هذه النصوص في الموقع. '
                                                'فعّلها من <a href="/admin/award/herocard/">البطاقة الشفافة في الهيرو</a> ← «إظهار بطاقة النصوص تحت الفيديو».'))
        return super().changelist_view(request, extra_context)


@admin.register(HeroCard)
class HeroCardAdmin(admin.ModelAdmin):
    fieldsets = (
        ('تفعيل / إيقاف', {
            'fields': ('is_enabled',),
            'description': 'عند التفعيل تظهر بطاقة النصوص تحت الفيديو/الصورة الجانبية (أو فوق الصورة الرئيسية إن لم يوجد فيديو/صورة). عند الإلغاء تختفي كل النصوص.',
        }),
        ('محتوى البطاقة', {
            'fields': ('heading', 'body_text'),
            'classes': ('wide',),
        }),
        ('عدة نصوص تتبدّل', {
            'fields': ('text_effect', 'reading_speed', 'min_seconds', 'show_arrows'),
            'description': mark_safe('النص أعلاه هو الأول ويأخذ الحركة الافتراضية. لإضافة نصوص أخرى وتحديد <b>حركة ومدة لكل نص</b>: '
                                     '<a href="/admin/award/herotextslide/"><b>النصوص المتبدّلة تحت الفيديو</b></a>.'),
        }),
        ('تصميم البطاقة', {
            'fields': ('card_bg_color', 'card_opacity', 'font_color', 'font_size', 'font_weight', 'border_radius'),
            'classes': ('collapse',),
            'description': 'تحكم بمظهر البطاقة الشفافة (اللون، الشفافية، الخط، الاستدارة)',
        }),
    )

    def has_add_permission(self, request):
        return not HeroCard.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TickerSetting)
class TickerSettingAdmin(admin.ModelAdmin):
    fieldsets = (
        ('تشغيل', {'fields': ('is_enabled',)}),
        ('السرعة والحجم والألوان', {'fields': ('scroll_speed', 'font_size', 'bar_height', 'font_color', 'bg_color', 'bg_opacity', 'fade_width')}),
        ('الصور في الشريط', {
            'fields': ('logo_size', 'separator_image', 'sep_pulse', 'sep_pulse_seconds', 'sep_fade', 'sep_fade_seconds', 'effects_on_logos'),
            'description': 'الصورة الفاصلة تظهر في الوسط بين كل خبرين. النبض والتلاشي يمكن تشغيل كل منهما وحده.',
        }),
    )

    def has_add_permission(self, request):
        return not TickerSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_display_links = ('title',)
    search_fields = ('title',)


@admin.register(SuccessStory)
class SuccessStoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'is_active')
    list_editable = ('is_active',)
    list_display_links = ('title',)
    search_fields = ('title',)


@admin.register(StoredFile)
class StoredFileAdmin(admin.ModelAdmin):
    """الصور المحفوظة في قاعدة البيانات (للاطلاع فقط — تُضاف تلقائياً عند رفع أي صورة)"""
    list_display = ('preview', 'name', 'size_kb', 'created_at')
    list_display_links = ('name',)
    search_fields = ('name',)
    readonly_fields = ('preview', 'name', 'content_type', 'size', 'created_at')
    exclude = ('content',)

    def get_queryset(self, request):
        return super().get_queryset(request).defer('content')

    @admin.display(description='معاينة')
    def preview(self, obj):
        return format_html('<img src="/media/{}" style="height:50px;max-width:90px;object-fit:contain;">', obj.name)

    @admin.display(description='الحجم (KB)', ordering='size')
    def size_kb(self, obj):
        return round((obj.size or 0) / 1024, 1)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# =====================================================================
#   تنظيم لوحة التحكم: أقسام واضحة بترتيب ظهورها في الموقع
# =====================================================================
from .roles import ADMIN_SECTIONS, ROLE_LABELS  # الأقسام والأدوار معرّفة في roles.py

_original_get_app_list = admin.AdminSite.get_app_list


def _grouped_app_list(self, request, app_label=None):
    apps = _original_get_app_list(self, request)
    award = next((a for a in apps if a['app_label'] == 'award'), None)
    if award is None:
        return apps
    by_name = {m['object_name']: m for m in award['models']}
    grouped, used = [], set()
    for title, role, items in ADMIN_SECTIONS:
        title = f'{title}  ·  {ROLE_LABELS[role]}'
        models_ = []
        for obj_name, label in items:
            m = by_name.get(obj_name)
            if m:
                m = dict(m, name=label)
                models_.append(m)
                used.add(obj_name)
        if models_:
            grouped.append(dict(award, name=title, app_label='award', models=models_))
    leftovers = [m for n, m in by_name.items() if n not in used]
    if leftovers:
        grouped.append(dict(award, name='أخرى', models=leftovers))
    others = [a for a in apps if a['app_label'] != 'award']
    result = grouped + others
    if app_label:
        return [a for a in result if a['app_label'] == app_label]
    return result


admin.AdminSite.get_app_list = _grouped_app_list
admin.site.site_header = 'لوحة تحكم جائزة انتصار عباس جردانة'
admin.site.site_title = 'لوحة التحكم'
admin.site.index_title = 'لوحة Django'


@admin.register(Principle)
class PrincipleAdmin(admin.ModelAdmin):
    list_display = ('title', 'icon', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_display_links = ('title',)
    search_fields = ('title',)


# =====================================================================
#   بحث في كل جدول: أي جدول بدون حقول بحث يأخذ حقوله النصية تلقائياً
# =====================================================================
def _auto_search_fields():
    from django.db import models as m
    for model, ma in admin.site._registry.items():
        if model._meta.app_label != 'award' or ma.search_fields:
            continue
        names = [f.name for f in model._meta.concrete_fields
                 if isinstance(f, (m.CharField, m.TextField)) and not isinstance(f, m.FileField)]
        if names:
            ma.search_fields = tuple(names[:8])


_auto_search_fields()

from . import admin_portal  # noqa: E402,F401  التسجيل والتحكيم
