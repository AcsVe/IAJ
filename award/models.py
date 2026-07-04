from django.db import models


def video_storage():
    from django.core.files.storage import storages
    return storages['videos']

def raw_storage():
    from django.core.files.storage import storages
    return storages['raw']


class Field(models.Model):
    name_ar = models.CharField(max_length=200, verbose_name="اسم المجال (عربي)")
    name_en = models.CharField(max_length=200, verbose_name="اسم المجال (إنجليزي)")
    def __str__(self): return self.name_ar

class Track(models.Model):
    field = models.ForeignKey(Field, on_delete=models.CASCADE, verbose_name="المجال")
    name_ar = models.CharField(max_length=200, verbose_name="اسم المسار (عربي)")
    name_en = models.CharField(max_length=200, verbose_name="اسم المسار (إنجليزي)")
    description_ar = models.TextField(verbose_name="شرح المسار (عربي)", blank=True, null=True)
    description_en = models.TextField(verbose_name="شرح المسار (إنجليزي)", blank=True, null=True)
    def __str__(self): return self.name_ar

STATUS_CHOICES = (
    ('pending', 'قيد المراجعة'), ('reviewed', 'تمت المراجعة'), 
    ('accepted', 'مقبول'), ('rejected', 'مرفوض'),
)
class Submission(models.Model):
    school_name = models.CharField(max_length=255, verbose_name="اسم المدرسة")
    contact_person = models.CharField(max_length=255, verbose_name="ضابط الارتباط")
    email = models.EmailField(verbose_name="البريد الإلكتروني")
    phone = models.CharField(max_length=20, verbose_name="رقم الهاتف")
    field = models.ForeignKey(Field, on_delete=models.SET_NULL, null=True, verbose_name="المجال")
    track = models.ForeignKey(Track, on_delete=models.SET_NULL, null=True, verbose_name="المسار")
    project_title = models.CharField(max_length=500, verbose_name="عنوان المشروع/البحث")
    document = models.FileField(upload_to='submissions/', storage=raw_storage, verbose_name="ملف البحث (PDF)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="الحالة")
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ التقدم")
    def __str__(self): return f"{self.school_name} - {self.project_title}"

class SiteSetting(models.Model):
    hero_background = models.ImageField(upload_to='site_media/', verbose_name="خلفية الصفحة الرئيسية (صورة)", blank=True, null=True)
    hero_video = models.FileField(upload_to='site_media/', verbose_name="خلفية الصفحة الرئيسية (فيديو)", blank=True, null=True)
    site_logo = models.ImageField(upload_to='site_media/', verbose_name="شعار الموقع", blank=True, null=True)
    registration_deadline = models.DateTimeField(verbose_name="موعد إغلاق التسجيل", blank=True, null=True)
    class Meta:
        verbose_name = "إعداد الموقع"
        verbose_name_plural = "إعدادات الموقع"
    def __str__(self): return "إعدادات الصفحة الرئيسية"

class HeroSlide(models.Model):
    MEDIA_TYPE_CHOICES = (('image', 'صورة'), ('video', 'فيديو'),)
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default='image', verbose_name="نوع الملف")
    media_file = models.FileField(upload_to='hero_slideshow/', verbose_name="الملف (صورة أو فيديو)")
    order = models.IntegerField(default=0, verbose_name="ترتيب العرض")
    is_active = models.BooleanField(default=True, verbose_name="مفعل؟")
    class Meta:
        verbose_name = "شريحة العرض"
        verbose_name_plural = "شرائح العرض الرئيسية"
        ordering = ['order']
    def __str__(self): return f"شريحة {self.order}"

class TimelineEvent(models.Model):
    date_text = models.CharField(max_length=100, verbose_name="التاريخ", blank=True, default="")
    title = models.CharField(max_length=200, verbose_name="عنوان الخطوة/الحدث")
    description = models.TextField(verbose_name="وصف مختصر للخطوة", blank=True, default="")
    modal_image = models.ImageField(upload_to='timeline/', verbose_name="صورة البطاقة المنبثقة", blank=True, null=True)
    icon = models.CharField(max_length=50, verbose_name="أيقونة FontAwesome", default="fa-check-circle", blank=True)
    is_highlighted = models.BooleanField(default=False, verbose_name="مميز؟")
    order = models.IntegerField(default=0, verbose_name="الترتيب")
    class Meta:
        verbose_name = "حدث زمني / خطوة"
        verbose_name_plural = "الجدول الزمني ورحلة الترشح"
        ordering = ['order']
    def __str__(self): return self.title

class Judge(models.Model):
    name = models.CharField(max_length=200, verbose_name="اسم عضو اللجنة")
    title = models.CharField(max_length=200, verbose_name="الصفة/المنصب")
    image = models.ImageField(upload_to='judges/', verbose_name="الصورة الشخصية")
    order = models.IntegerField(default=0, verbose_name="الترتيب")
    description = models.TextField(verbose_name="نبذة عن العضو", blank=True, default="")
    class Meta:
        verbose_name = "عضو تحكيم"
        verbose_name_plural = "لجنة التحكيم"
        ordering = ['order']
    def __str__(self): return self.name
    
class ThemeSetting(models.Model):
    primary_color = models.CharField(max_length=7, default='#0a1632', verbose_name="اللون الأساسي")
    secondary_color = models.CharField(max_length=7, default='#122450', verbose_name="اللون الثانوي")
    gold_color = models.CharField(max_length=7, default='#c5a059', verbose_name="اللون الذهبي")
    font_size = models.CharField(max_length=4, default='16px', verbose_name="حجم الخط")
    custom_css = models.TextField(blank=True, null=True, verbose_name="CSS مخصص")
    class Meta:
        verbose_name = "إعدادات الألوان والتصميم"
        verbose_name_plural = "إعدادات الألوان والتصميم"
    def __str__(self): return "ألوان وتصميم الموقع"
 
class HomeContent(models.Model):
    hero_title = models.CharField(max_length=200, default="جائزة انتصار عباس جردانة", verbose_name="العنوان الرئيسي")
    hero_subtitle = models.TextField(default="للثقافة والتعليم", verbose_name="العنوان الفرعي")
    about_text = models.TextField(default="تخليداً لذكرى السيدة انتصار عباس جردانة...", verbose_name="نص عن الجائزة")
    vision_text = models.TextField(default="مجتمع نابض بالشغف والعطاء...", verbose_name="نص الرؤية")
    mission_text = models.TextField(default="تكريم القدرات التطوعية...", verbose_name="نص الرسالة")
    principle_1 = models.CharField(max_length=100, default="العطاء", verbose_name="المبدأ الأول")
    principle_2 = models.CharField(max_length=100, default="الريادة والابتكار", verbose_name="المبدأ الثاني")
    principle_3 = models.CharField(max_length=100, default="الاستدامة", verbose_name="المبدأ الثالث")
    principle_4 = models.CharField(max_length=100, default="الأثر والتأثر", verbose_name="المبدأ الرابع")
    condition_1 = models.CharField(max_length=255, default="نطاق العمل داخل المملكة الأردنية الهاشمية.", verbose_name="الشرط الأول")
    condition_2 = models.CharField(max_length=255, default="مراعاة المبادئ العامة ومجالات الجائزة.", verbose_name="الشرط الثاني")
    condition_3 = models.CharField(max_length=255, default="الالتزام بالميثاق الأخلاقي للعمل التطوعي.", verbose_name="الشرط الثالث")
    condition_4 = models.CharField(max_length=255, default="الفئة المستهدفة: طلبة التاسع - الثاني عشر.", verbose_name="الشرط الرابع")
    condition_5 = models.CharField(max_length=255, default="تقديم البحث بصيغة PDF (15-20 صفحة).", verbose_name="الشرط الخامس")
    step_1 = models.CharField(max_length=255, default="الاطلاع على دليل الجائزة ومعايير التحكيم.", verbose_name="الخطوة الأولى")
    step_2 = models.CharField(max_length=255, default="حضور اللقاء التعريفي بالمدرسة.", verbose_name="الخطوة الثانية")
    step_3 = models.CharField(max_length=255, default="تعبئة طلب الترشح الإلكتروني.", verbose_name="الخطوة الثالثة")
    step_4 = models.CharField(max_length=255, default="تقديم البحث والصور والفيديوهات.", verbose_name="الخطوة الرابعة")
    step_5 = models.CharField(max_length=255, default="تحديد ضابط ارتباط للمتابعة والتحكيم.", verbose_name="الخطوة الخامسة")
    prize_1_desc = models.CharField(max_length=200, default="1500 دينار + درع العمل التطوعي المتميز", verbose_name="وصف الجائزة الأولى")
    prize_2_desc = models.CharField(max_length=200, default="1000 دينار + درع الاستدامة والتأثير", verbose_name="وصف الجائزة الثانية")
    prize_3_desc = models.CharField(max_length=200, default="500 دينار + درع أفضل فكرة ريادية", verbose_name="وصف الجائزة الثالثة")
    title_about = models.CharField(max_length=200, default="عن الجائزة", verbose_name="عنوان قسم عن الجائزة")
    title_fields = models.CharField(max_length=200, default="مجالات العمل التطوعي", verbose_name="عنوان قسم المجالات")
    title_timeline = models.CharField(max_length=200, default="الإطار الزمني لمراحل الجائزة", verbose_name="عنوان قسم الجدول الزمني")
    title_apply = models.CharField(max_length=200, default="طلب التقديم للجائزة", verbose_name="عنوان قسم التقديم")
    title_prizes = models.CharField(max_length=200, default="قيمة الجوائز", verbose_name="عنوان قسم الجوائز")
    title_judges = models.CharField(max_length=200, default="لجنة التحكيم", verbose_name="عنوان قسم لجنة التحكيم")
    btn_hero = models.CharField(max_length=100, default="تقدم لمشروعك الآن", verbose_name="زر الصفحة الرئيسية")
    btn_navbar = models.CharField(max_length=100, default="سجل الآن", verbose_name="زر النافبار")
    class Meta:
        verbose_name = "تحرير محتوى الصفحة الرئيسية"
        verbose_name_plural = "تحرير محتوى الصفحة الرئيسية"
    def __str__(self): return "تعديل نصوص وأوصاف الموقع"

class FooterContent(models.Model):
    about_text = models.TextField(default="مبادرة تهدف لتكريم العطاء التطوعي...", verbose_name="نص عن الجائزة في الفوتر")
    email = models.CharField(max_length=100, default="info@iaj-award.jo", verbose_name="البريد الإلكتروني")
    phone = models.CharField(max_length=20, default="+962 7X XXX XXXX", verbose_name="رقم الهاتف")
    address = models.CharField(max_length=200, default="المملكة الأردنية الهاشمية", verbose_name="العنوان")
    copyright_text = models.CharField(max_length=200, default="جميع الحقوق محفوظة 2025 جائزة انتصار عباس جردانة", verbose_name="نص حقوق النشر")
    class Meta:
        verbose_name = "تحرير محتوى الفوتر"
        verbose_name_plural = "تحرير محتوى الفوتر"
    def __str__(self): return "تعديل نصوص وأوصاف الفوتر"
        
class SuccessPageContent(models.Model):
    main_title = models.CharField(max_length=200, default="تم إرسال طلبك بنجاح!", verbose_name="العنوان الرئيسي")
    sub_text = models.TextField(default="شكراً لمشاركتكم...", verbose_name="النص الفرعي")
    btn_text = models.CharField(max_length=100, default="العودة للرئيسية", verbose_name="نص زر العودة")
    class Meta:
        verbose_name = "تحرير صفحة النجاح"
        verbose_name_plural = "تحرير صفحة النجاح"
    def __str__(self): return "تعديل نصوص صفحة النجاح"

# CMS Models

class SectionBackground(models.Model):
    SECTION_CHOICES = [
        ('home', 'الصفحة الرئيسية'), ('stats', 'الإحصائيات'),
        ('about', 'عن الجائزة'), ('fields', 'مجالات العمل التطوعي'),
        ('timeline', 'الجدول الزمني'), ('apply', 'طلب التقديم'),
        ('prizes', 'الجوائز'), ('judges', 'لجنة التحكيم'), ('footer', 'الفوتر'),
    ]
    section_id = models.CharField(max_length=20, choices=SECTION_CHOICES, unique=True, verbose_name="اختر القسم")

    # -- خلفية القسم --
    bg_image = models.ImageField(upload_to='backgrounds/', blank=True, null=True, verbose_name="صورة الخلفية")
    bg_color = models.CharField(max_length=7, default='', blank=True, verbose_name="لون الخلفية (مثال: #ffffff)")
    enable_overlay = models.BooleanField(default=True, verbose_name="تفعيل طبقة شفافة فوق الخلفية؟")
    overlay_color = models.CharField(max_length=7, default='#000000', verbose_name="لون الطبقة الشفافة")
    overlay_opacity = models.DecimalField(max_digits=3, decimal_places=2, default=0.70, verbose_name="شفافية الطبقة (0=شفاف تماماً 1=معتم)")
    is_parallax = models.BooleanField(default=True, verbose_name="حركة Parallax؟")

    # -- ألوان العناوين والنصوص --
    heading_color = models.CharField(max_length=7, default='', blank=True, verbose_name="لون عنوان القسم الرئيسي (h2)", help_text="اتركه فارغاً لاستخدام اللون الافتراضي")
    heading_size = models.CharField(max_length=7, default='', blank=True, verbose_name="حجم خط العنوان (مثال: 2.2rem)", help_text="اتركه فارغاً لاستخدام الحجم الافتراضي")
    text_color = models.CharField(max_length=7, default='', blank=True, verbose_name="لون النص الرئيسي", help_text="اتركه فارغاً لاستخدام اللون الافتراضي")
    text_size = models.CharField(max_length=7, default='', blank=True, verbose_name="حجم خط النص (مثال: 1.1rem)", help_text="اتركه فارغاً لاستخدام الحجم الافتراضي")
    sub_heading_color = models.CharField(max_length=7, default='', blank=True, verbose_name="لون العنوان الفرعي", help_text="للعناوين داخل القسم مثل h3, h4, h5")
    sub_heading_size = models.CharField(max_length=7, default='', blank=True, verbose_name="حجم خط العنوان الفرعي (مثال: 1.3rem)")
    gold_line_color = models.CharField(max_length=7, default='', blank=True, verbose_name="لون الخط الذهبي تحت العنوان", help_text="اتركه فارغاً لاستخدام اللون الذهبي الافتراضي")

    class Meta:
        verbose_name = "خلفية وتصميم القسم"
        verbose_name_plural = "إدارة خلفيات وتصميمات الأقسام"

    def __str__(self): return self.get_section_id_display()

class Sponsor(models.Model):
    TIER_CHOICES = (('platinum', 'بلاتيني'), ('gold', 'ذهبي'), ('silver', 'فضي'), ('bronze', 'برونزي'))
    name = models.CharField(max_length=200, verbose_name="اسم الجهة")
    logo = models.ImageField(upload_to='sponsors/')
    website = models.URLField(blank=True, null=True)
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='gold')
    order = models.IntegerField(default=0)
    class Meta: verbose_name = "شريك"; verbose_name_plural = "الشركاء والرعاة"; ordering = ['order']
    def __str__(self): return self.name

class FAQ(models.Model):
    question = models.CharField(max_length=500)
    answer = models.TextField()
    order = models.IntegerField(default=0)
    class Meta: verbose_name = "سؤال شائع"; verbose_name_plural = "الأسئلة الشائعة"; ordering = ['order']
    def __str__(self): return self.question

class Winner(models.Model):
    category = models.ForeignKey('WinnerCategory', on_delete=models.CASCADE, related_name='winners', verbose_name="الفئة", null=True, blank=True)
    year = models.IntegerField(verbose_name="السنة")
    school_name = models.CharField(max_length=255, verbose_name="اسم المدرسة")
    project_title = models.CharField(max_length=500, verbose_name="عنوان المشروع")
    rank = models.IntegerField(verbose_name="المرتبة")
    image = models.ImageField(upload_to='winners/', blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True, verbose_name="مفعّل")
    class Meta: verbose_name = "فائز"; verbose_name_plural = "الفائزون"; ordering = ['-year', 'rank']
    def __str__(self): return f"{self.school_name} - المركز {self.rank}"

class MediaGallery(models.Model):
    MEDIA_TYPE_CHOICES = (('image', 'صورة'), ('video', 'فيديو'))
    title = models.CharField(max_length=200)
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default='image')
    image = models.ImageField(upload_to='gallery/', blank=True, null=True)
    video_url = models.URLField(blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    order = models.IntegerField(default=0)
    class Meta: verbose_name = "صورة/فيديو"; verbose_name_plural = "معرض الصور"; ordering = ['order']
    def __str__(self): return self.title

class News(models.Model):
    title = models.CharField(max_length=300)
    image = models.ImageField(upload_to='news/', blank=True, null=True)
    content = models.TextField()
    date = models.DateField()
    is_published = models.BooleanField(default=True)
    class Meta: verbose_name = "خبر"; verbose_name_plural = "الأخبار"; ordering = ['-date']
    def __str__(self): return self.title

class ContactMessage(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField()
    subject = models.CharField(max_length=300)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: verbose_name = "رسالة"; verbose_name_plural = "رسائل التواصل"; ordering = ['-created_at']
    def __str__(self): return f"رسالة من {self.name}"

class TickerItem(models.Model):
    message_html = models.TextField()
    logo = models.ImageField(upload_to='ticker/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    class Meta: verbose_name = "رسالة شريط"; verbose_name_plural = "رسائل الشريط الإخباري"; ordering = ['order']
    def __str__(self): return self.message_html

# Slideshow Cards

class SlideshowCard(models.Model):
    CARD_TYPE_CHOICES = (
        ('image', 'صورة فقط'),
        ('video', 'فيديو (يوتيوب أو رفع ملف)'),
        ('text', 'نص فقط'),
        ('image_text', 'صورة + نص'),
        ('video_text', 'فيديو + نص'),
    )
    FONT_WEIGHT_CHOICES = (
        ('300', 'خفيف'), ('400', 'عادي'), ('600', 'شبه سميك'),
        ('700', 'سميك'), ('900', 'أسود سميك'),
    )
    TEXT_ALIGN_CHOICES = (('center', 'وسط'), ('right', 'يمين'), ('left', 'يسار'))

    card_type = models.CharField(max_length=12, choices=CARD_TYPE_CHOICES, default='image_text', verbose_name="نوع البطاقة")
    image = models.FileField(upload_to='slideshow/', verbose_name="الصورة أو الفيديو", blank=True, null=True, help_text="ارفع صورة (jpg/png/webp) أو فيديو (mp4/webm)")
    image_url = models.URLField(blank=True, null=True, verbose_name="رابط صورة خارجي", help_text="ألصق رابط صورة من Cloudinary أو Google Drive أو أي مصدر")
    video_url = models.URLField(blank=True, null=True, verbose_name="رابط فيديو (أي مصدر)", help_text="يوتيوب: https://www.youtube.com/watch?v=VIDEO_ID — Cloudinary: رابط video — Google Drive: رابط embed")
    video_file = models.FileField(upload_to='slideshow/videos/', storage=video_storage, verbose_name="ملف فيديو إضافي", blank=True, null=True, help_text="mp4/webm")
    heading = models.CharField(max_length=300, blank=True, default='', verbose_name="العنوان")
    body_text = models.TextField(blank=True, default='', verbose_name="النص")
    font_size = models.CharField(max_length=6, default='1rem', verbose_name="حجم الخط")
    font_color = models.CharField(max_length=7, default='#ffffff', verbose_name="لون الخط")
    font_weight = models.CharField(max_length=3, choices=FONT_WEIGHT_CHOICES, default='400', verbose_name="وزن الخط")
    text_align = models.CharField(max_length=6, choices=TEXT_ALIGN_CHOICES, default='center', verbose_name="محاذاة النص")
    card_bg_color = models.CharField(max_length=7, default='#000000', verbose_name="لون خلفية البطاقة")
    card_opacity = models.DecimalField(max_digits=3, decimal_places=2, default=0.45, verbose_name="شفافية البطاقة")
    border_radius = models.CharField(max_length=6, default='16px', verbose_name="استدارة الزوايا")
    order = models.IntegerField(default=0, verbose_name="الترتيب")
    is_active = models.BooleanField(default=True, verbose_name="مفعّلة؟")

    class Meta:
        verbose_name = "بطاقة عرض شفافة"
        verbose_name_plural = "بطاقات العرض الشفافة"
        ordering = ['order']

    def __str__(self):
        return f"بطاقة {self.order}: {self.heading or self.card_type}"

    def bg_rgb(self):
        hex_color = self.card_bg_color.replace('#', '')
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return f"{r},{g},{b}"
        return "0,0,0"

    def get_image_url(self):
        """يرجع رابط الصورة: الأولوية لـ image_url ثم image المرفوع"""
        if self.image_url:
            return self.image_url
        if self.image:
            return self.image.url
        return None

    def get_video_embed_url(self):
        """يرجع رابط embed للفيديو: يوتيوب أو Cloudinary أو أي مصدر آخر"""
        if not self.video_url:
            return None
        url = self.video_url
        # يوتيوب watch
        if 'watch?v=' in url:
            video_id = url.split('watch?v=')[-1].split('&')[0]
            return f'https://www.youtube.com/embed/{video_id}'
        # يوتيوب short
        if 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[-1].split('?')[0]
            return f'https://www.youtube.com/embed/{video_id}'
        # أي رابط آخر (Cloudinary embed, Google Drive embed, etc.) يرجع كما هو
        return url

    def has_image(self):
        return bool(self.image_url or self.image)

    def has_video(self):
        return bool(self.video_url or self.video_file)


# ===== البطاقة الشفافة في الهيرو (مستقلة عن السلايدشو) =====
class HeroCard(models.Model):
    """بطاقة شفافة واحدة تظهر على يسار الهيرو في الصفحة الرئيسية"""
    is_enabled = models.BooleanField(default=False, verbose_name="إظهار البطاقة الشفافة في الهيرو؟")
    heading = models.CharField(max_length=300, blank=True, default='', verbose_name="عنوان البطاقة")
    body_text = models.TextField(blank=True, default='', verbose_name="نص البطاقة")
    card_bg_color = models.CharField(max_length=7, default='#0a1632', verbose_name="لون خلفية البطاقة")
    card_opacity = models.DecimalField(max_digits=3, decimal_places=2, default=0.55, verbose_name="شفافية البطاقة (0=شفاف 1=معتم)")
    font_color = models.CharField(max_length=7, default='#ffffff', verbose_name="لون النص")
    font_size = models.CharField(max_length=6, default='1.1rem', verbose_name="حجم الخط")
    font_weight = models.CharField(max_length=3, default='600', verbose_name="وزن الخط (300/400/600/700/900)")
    border_radius = models.CharField(max_length=6, default='0px', verbose_name="استدارة الزوايا")

    class Meta:
        verbose_name = "البطاقة الشفافة في الهيرو"
        verbose_name_plural = "البطاقة الشفافة في الهيرو"

    def __str__(self):
        return "البطاقة الشفافة"

    def bg_rgb(self):
        hex_color = self.card_bg_color.replace('#', '')
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return f"{r},{g},{b}"
        return "10,22,50"


class TickerSetting(models.Model):
    is_enabled = models.BooleanField(default=True, verbose_name="تشغيل الشريط؟")
    font_color = models.CharField(max_length=7, default='#c5a059')
    bg_color = models.CharField(max_length=7, default='#0a1632')
    bg_opacity = models.DecimalField(max_digits=3, decimal_places=2, default=0.95)
    scroll_speed = models.IntegerField(default=30)
    fade_width = models.CharField(max_length=5, default='150px')
    class Meta: verbose_name = "إعدادات الشريط"; verbose_name_plural = "إعدادات الشريط"
    def __str__(self): return "إعدادات الشريط الإخباري"


# ===== فئات الفوز =====
class WinnerCategory(models.Model):
    name = models.CharField(max_length=255, verbose_name="اسم الفئة")
    description = models.TextField(blank=True, verbose_name="الوصف")
    order = models.IntegerField(default=0, verbose_name="الترتيب")
    is_active = models.BooleanField(default=True, verbose_name="مفعّل")

    class Meta:
        verbose_name = "فئة فوز"
        verbose_name_plural = "فئات الفوز"
        ordering = ['order']

    def __str__(self):
        return self.name


# ===== معرض الصور =====
class Photo(models.Model):
    title = models.CharField(max_length=255, verbose_name="العنوان")
    image = models.FileField(upload_to='photos/', verbose_name="الصورة")
    description = models.TextField(blank=True, verbose_name="الوصف")
    is_active = models.BooleanField(default=True, verbose_name="مفعّل")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "صورة"
        verbose_name_plural = "معرض الصور"
        ordering = ['-created_at']

    def __str__(self):
        return self.title


# ===== مكتبة الفيديو =====
class Video(models.Model):
    title = models.CharField(max_length=255, verbose_name="العنوان")
    youtube_url = models.URLField(verbose_name="رابط يوتيوب")
    description = models.TextField(blank=True, verbose_name="الوصف")
    order = models.IntegerField(default=0, verbose_name="الترتيب")
    is_active = models.BooleanField(default=True, verbose_name="مفعّل")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "فيديو"
        verbose_name_plural = "مكتبة الفيديو"
        ordering = ['order']

    def __str__(self):
        return self.title

    def get_embed_url(self):
        """تحويل رابط يوتيوب إلى embed URL"""
        url = self.youtube_url
        if 'watch?v=' in url:
            video_id = url.split('watch?v=')[-1].split('&')[0]
            return f'https://www.youtube.com/embed/{video_id}'
        elif 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[-1].split('?')[0]
            return f'https://www.youtube.com/embed/{video_id}'
        return url


# ===== قصص النجاح =====
class SuccessStory(models.Model):
    title = models.CharField(max_length=255, verbose_name="العنوان")
    content = models.TextField(verbose_name="النص")
    image = models.FileField(upload_to='success_stories/', blank=True, verbose_name="الصورة")
    date = models.DateField(verbose_name="التاريخ")
    is_active = models.BooleanField(default=True, verbose_name="مفعّل")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "قصة نجاح"
        verbose_name_plural = "قصص النجاح"
        ordering = ['-date']

    def __str__(self):
        return self.title
