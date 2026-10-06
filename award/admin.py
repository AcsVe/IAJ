from django.contrib import admin
from django import forms
from .models import (
    Field, Track, Submission, SiteSetting, HeroSlide, TimelineEvent,
    Judge, ThemeSetting, HomeContent, FooterContent, SuccessPageContent,
    SectionBackground, Sponsor, FAQ, Winner, WinnerCategory, MediaGallery,
    ContactMessage, TickerItem, SlideshowCard, TickerSetting, News,
    Photo, Video, SuccessStory, HeroCard, StoredFile
)
from django.utils.html import format_html


@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = ('name_ar', 'name_en')
    list_display_links = ('name_ar',)


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ('name_ar', 'name_en', 'field')
    list_filter = ('field',)
    list_display_links = ('name_ar',)


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('school_name', 'project_title', 'status', 'submitted_at')
    list_filter = ('status', 'field', 'track')
    list_display_links = ('school_name',)
    search_fields = ('school_name', 'project_title', 'email')
    readonly_fields = ('submitted_at',)


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ('media_type', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_display_links = ('media_type',)


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


@admin.register(ThemeSetting)
class ThemeSettingAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not ThemeSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HomeContent)
class HomeContentAdmin(admin.ModelAdmin):
    fieldsets = (
        ('نص الهيرو المتحرك', {
            'fields': ('hero_title', 'hero_subtitle'),
            'classes': ('wide',),
            'description': 'العنوان والنص المتحرك في قسم الهيرو (يظهر على شكل شارة أفلام)',
        }),
        ('محتوى الصفحة الرئيسية', {
            'fields': (
                'about_text', 'vision_text', 'mission_text',
                'principle_1', 'principle_2', 'principle_3', 'principle_4',
                'condition_1', 'condition_2', 'condition_3', 'condition_4', 'condition_5',
                'step_1', 'step_2', 'step_3', 'step_4', 'step_5',
                'prize_1_desc', 'prize_2_desc', 'prize_3_desc',
                'title_about', 'title_fields', 'title_timeline',
                'title_apply', 'title_prizes', 'title_judges',
                'btn_hero', 'btn_navbar',
            ),
            'classes': ('collapse',),
        }),
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
                'bg_image', 'bg_color',
                'enable_overlay', 'overlay_color', 'overlay_opacity',
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


@admin.register(FAQ)
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


@admin.register(MediaGallery)
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
            'fields': ('title', 'image', 'content', 'date', 'is_published')
        }),
    )

    class Media:
        js = ('award/js/quill_init.js',)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'is_read', 'created_at')
    list_editable = ('is_read',)
    list_display_links = ('name',)


@admin.register(TickerItem)
class TickerItemAdmin(admin.ModelAdmin):
    list_display = ('message_html', 'is_active', 'order')
    list_editable = ('is_active', 'order')
    list_display_links = ('message_html',)


@admin.register(SlideshowCard)
class SlideshowCardAdmin(admin.ModelAdmin):
    list_display = ('card_type', 'order', 'heading', 'is_active')
    list_filter = ('card_type', 'is_active')
    list_editable = ('order', 'is_active')
    list_display_links = ('card_type',)


@admin.register(HeroCard)
class HeroCardAdmin(admin.ModelAdmin):
    fieldsets = (
        ('تفعيل / إيقاف', {
            'fields': ('is_enabled',),
            'description': 'فعّل لإظهار بطاقة شفافة على يسار الهيرو في الصفحة الرئيسية',
        }),
        ('محتوى البطاقة', {
            'fields': ('heading', 'body_text'),
            'classes': ('wide',),
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
