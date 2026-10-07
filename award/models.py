from django.db import models


class Field(models.Model):
    name_ar = models.CharField(max_length=200, verbose_name="اسم المجال (عربي)")
    name_en = models.CharField(max_length=200, verbose_name="اسم المجال (إنجليزي)")
    cover_image = models.ImageField(max_length=500, upload_to='fields/', blank=True, null=True,
                                    verbose_name="صورة خلفية غلاف البطاقة (اختياري)",
                                    help_text="تظهر على الوجه الأمامي للبطاقة القلابة مع طبقة داكنة ليبقى العنوان واضحاً.")
    cover_overlay = models.DecimalField(max_digits=3, decimal_places=2, default=0.55,
                                        verbose_name="تعتيم صورة الغلاف (0 = بدون، 1 = معتم)")
    def __str__(self): return self.name_ar

class Track(models.Model):
    field = models.ForeignKey(Field, on_delete=models.CASCADE, verbose_name="المجال")
    name_ar = models.CharField(max_length=200, verbose_name="اسم المسار (عربي)")
    name_en = models.CharField(max_length=200, verbose_name="اسم المسار (إنجليزي)")
    description_ar = models.TextField(verbose_name="نبذة قصيرة عن المسار (عربي)", blank=True, null=True,
                                      help_text="فقرة قصيرة تظهر أعلى الشرح وفي نتائج البحث.")
    description_en = models.TextField(verbose_name="شرح المسار (إنجليزي)", blank=True, null=True)
    details_html = models.TextField(blank=True, default='', verbose_name="شرح تفصيلي (نص منسّق)",
                                    help_text="شرح مطوّل بعناوين وقوائم وصور — يظهر في صفحة المسار بعد جدول التفاصيل.")
    order = models.IntegerField(default=0, verbose_name="الترتيب")
    is_active = models.BooleanField(default=True, verbose_name="مفعّل؟",
                                    help_text="المسار المعطّل يختفي من البطاقات والبحث ونموذج التسجيل.")
    notice_enabled = models.BooleanField(default=False, verbose_name="إظهار شريط الملاحظة؟")
    notice_text = models.CharField(max_length=500, blank=True, default='', verbose_name="نص شريط الملاحظة",
                                   help_text="شريط متحرك أعلى شرح المسار — لإشعار فوري، مثل: «تم تمديد التقديم لهذا المسار حتى 30 نوفمبر».")
    notice_speed = models.PositiveSmallIntegerField(default=50, verbose_name="سرعة الشريط (بكسل/ثانية)",
                                                    help_text="رقم أكبر = أسرع. المقترح 40–70.")

    class Meta:
        verbose_name = "مسار"
        verbose_name_plural = "المسارات"
        ordering = ['field', 'order', 'id']

    def __str__(self):
        return self.name_ar + ('' if self.is_active else ' (معطّل)')

    @property
    def show_notice(self):
        return self.notice_enabled and bool((self.notice_text or '').strip())

    def get_absolute_url(self):
        return f'/tracks/{self.pk}/'


class TrackDetail(models.Model):
    """صف في جدول تفاصيل المسار (مثل: الفئة المستهدفة، أمثلة، معايير التقييم…)"""
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='details', verbose_name="المسار")
    title = models.CharField(max_length=200, verbose_name="البند")
    content = models.TextField(verbose_name="التفاصيل", help_text="كل سطر جديد يظهر كنقطة منفصلة.")
    icon = models.CharField(max_length=60, blank=True, default='', verbose_name="أيقونة (اختياري)",
                            help_text="مثال: fa-users — fa-lightbulb — fa-list-check — fa-scale-balanced")
    order = models.IntegerField(default=0, verbose_name="الترتيب")

    class Meta:
        verbose_name = "بند تفاصيل"
        verbose_name_plural = "جدول تفاصيل المسار"
        ordering = ['order', 'id']

    def __str__(self):
        return self.title

    @property
    def lines(self):
        return [l.strip(' •-–\t') for l in (self.content or '').splitlines() if l.strip(' •-–\t')]

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
    document = models.FileField(max_length=500, upload_to='submissions/', verbose_name="ملف البحث (PDF)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="الحالة")
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ التقدم")
    def __str__(self): return f"{self.school_name} - {self.project_title}"

class SiteSetting(models.Model):
    hero_background = models.ImageField(max_length=500, upload_to='site_media/', verbose_name="خلفية الصفحة الرئيسية (صورة)", blank=True, null=True)
    hero_video = models.FileField(max_length=500, upload_to='site_media/', verbose_name="خلفية الصفحة الرئيسية (فيديو)", blank=True, null=True)
    site_logo = models.ImageField(max_length=500, upload_to='site_media/', verbose_name="شعار الموقع (Logo) - يظهر في الهيدر والفوتر", blank=True, null=True)
    registration_deadline = models.DateTimeField(verbose_name="موعد إغلاق التسجيل (للعداد التنازلي)", blank=True, null=True)
    hero_side_image = models.ImageField(max_length=500, 
        upload_to='site_media/', blank=True, null=True,
        verbose_name="صورة جانبية بجانب الصورة الرئيسية (الهيرو)",
        help_text="تظهر بجانب صورة الخلفية الرئيسية (يسار على الكمبيوتر، وتحتها على الموبايل). اتركها فارغة لعرض الصورة الرئيسية بعرض كامل.",
    )
    hero_side_video = models.FileField(max_length=500, 
        upload_to='site_media/videos/', blank=True, null=True,
        verbose_name="فيديو جانبي (رفع ملف mp4)",
        help_text="يُستخدم فقط إذا لم تُضف شرائح. يعمل عند الضغط عليه.",
    )
    hero_side_video_url = models.URLField(
        blank=True, null=True,
        verbose_name="أو رابط فيديو يوتيوب للجانب",
        help_text="مثال: https://www.youtube.com/watch?v=XXXX — يُستخدم إذا لم يُرفع ملف فيديو.",
    )
    logo_size = models.PositiveSmallIntegerField(default=50, verbose_name="حجم الشعار على الكمبيوتر (بكسل)",
                                                 help_text="المقترح بين 40 و 80")
    logo_size_scrolled = models.PositiveSmallIntegerField(default=44, verbose_name="حجم الشعار بعد النزول في الصفحة (بكسل)")
    logo_size_mobile = models.PositiveSmallIntegerField(default=38, verbose_name="حجم الشعار على الموبايل (بكسل)")
    cd_show_days = models.BooleanField(default=True, verbose_name="العداد: إظهار الأيام")
    cd_show_hours = models.BooleanField(default=True, verbose_name="العداد: إظهار الساعات")
    cd_show_minutes = models.BooleanField(default=True, verbose_name="العداد: إظهار الدقائق")
    cd_show_seconds = models.BooleanField(default=True, verbose_name="العداد: إظهار الثواني")
    slide_seconds = models.PositiveSmallIntegerField(
        default=6, verbose_name="مدة عرض كل صورة (ثوانٍ)",
        help_text="في بطاقة الشرائح. الفيديو لا يتبدّل أثناء تشغيله.",
    )
    slide_show_timer = models.BooleanField(
        default=True, verbose_name="إظهار شريط الوقت أعلى بطاقة الشرائح",
        help_text="خط رفيع يمتلئ حتى تتبدّل الشريحة التالية.",
    )

    class Meta:
        verbose_name = "إعداد الموقع"
        verbose_name_plural = "إعدادات الموقع"

    def __str__(self): 
        return "إعدادات الصفحة الرئيسية"

    @property
    def side_youtube_embed(self):
        """رابط تضمين يوتيوب يعمل تلقائياً بدون صوت (بدون تكرار)"""
        url = (self.hero_side_video_url or '').strip()
        if not url:
            return ''
        vid = ''
        for key in ('watch?v=', 'youtu.be/', '/embed/', '/shorts/'):
            if key in url:
                vid = url.split(key, 1)[1].split('&')[0].split('?')[0].split('/')[0]
                break
        if not vid:
            return ''
        return f'https://www.youtube.com/embed/{vid}?controls=1&modestbranding=1&playsinline=1&rel=0'

    @property
    def has_hero_side(self):
        return bool(self.hero_side_video or self.side_youtube_embed or self.hero_side_image)

def shade(hex_color, amount):
    """تفتيح (+) أو تغميق (-) لون hex — لصنع تدرّج تلقائي من لون واحد"""
    h = (hex_color or '').lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    if len(h) != 6:
        return hex_color or '#000000'
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return hex_color
    if amount < 0:
        r, g, b = (int(c * (1 + amount)) for c in (r, g, b))
    else:
        r, g, b = (int(c + (255 - c) * amount) for c in (r, g, b))
    return '#%02x%02x%02x' % (r, g, b)


def youtube_id(url):
    """استخراج رقم فيديو يوتيوب من أي شكل رابط"""
    url = (url or '').strip()
    for key in ('watch?v=', 'youtu.be/', '/embed/', '/shorts/', '/live/'):
        if key in url:
            return url.split(key, 1)[1].split('&')[0].split('?')[0].split('/')[0]
    return ''


class HeroSlide(models.Model):
    """شرائح بطاقة الفيديو/الصور أعلى الصفحة الرئيسية (تتبدّل تلقائياً)"""
    MEDIA_TYPE_CHOICES = (('image', 'صورة'), ('video', 'فيديو (ملف)'), ('youtube', 'فيديو يوتيوب'))
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default='image', verbose_name="النوع")
    media_file = models.FileField(max_length=500, upload_to='hero_slideshow/', blank=True,
                                  verbose_name="الملف (صورة أو فيديو mp4)",
                                  help_text="للصورة أو الفيديو. اتركه فارغاً إذا كان النوع «فيديو يوتيوب».")
    youtube_url = models.URLField(blank=True, default='', verbose_name="رابط يوتيوب",
                                  help_text="مثال: https://www.youtube.com/watch?v=XXXX")
    poster = models.ImageField(max_length=500, upload_to='hero_slideshow/', blank=True, null=True,
                               verbose_name="صورة غلاف للفيديو (اختياري)",
                               help_text="تظهر قبل الضغط على تشغيل. بدونها يظهر أول مشهد من الفيديو.")
    title = models.CharField(max_length=200, blank=True, default='', verbose_name="عنوان صغير على الشريحة (اختياري)")
    CLICK_CHOICES = (('zoom', 'تكبير الصورة بملء الشاشة'), ('link', 'فتح رابط'), ('none', 'لا شيء'))
    click_action = models.CharField(max_length=10, choices=CLICK_CHOICES, default='zoom',
                                    verbose_name="عند الضغط على الصورة",
                                    help_text="للصور فقط. الفيديو يعمل دائماً عند الضغط عليه.")
    link_url = models.CharField(max_length=500, blank=True, default='', verbose_name="الرابط (إذا اخترت «فتح رابط»)",
                                help_text="مثال: /submit/  أو  /news/  أو رابط كامل https://...")
    order = models.IntegerField(default=0, verbose_name="الترتيب")
    is_active = models.BooleanField(default=True, verbose_name="ظاهرة؟")

    class Meta:
        verbose_name = "شريحة (صورة / فيديو)"
        verbose_name_plural = "بطاقة الفيديو والصور — الشرائح"
        ordering = ['order', 'id']

    def __str__(self):
        return self.title or f"{self.get_media_type_display()} {self.order}"

    @property
    def youtube_id(self):
        return youtube_id(self.youtube_url)

    @property
    def kind(self):
        """نوع العرض الفعلي حسب ما تم رفعه"""
        if self.media_type == 'youtube' or (not self.media_file and self.youtube_url):
            return 'youtube' if self.youtube_id else ''
        if not self.media_file:
            return ''
        from .storage import is_image_name
        return 'image' if is_image_name(self.media_file.name.split('?')[0]) else 'video'


class TimelineEvent(models.Model):
    date_text = models.CharField(max_length=100, verbose_name="التاريخ (مثال: 17 سبتمبر 2025) - اتركه فارغاً لو مش تاريخ", blank=True, default="")
    title = models.CharField(max_length=200, verbose_name="عنوان الخطوة/الحدث")
    description = models.TextField(verbose_name="وصف مختصر للخطوة", blank=True, default="")
    modal_image = models.ImageField(max_length=500, upload_to='timeline/', verbose_name="صورة البطاقة المنبثقة", blank=True, null=True)
    icon = models.CharField(max_length=50, verbose_name="أيقونة FontAwesome (مثال: fa-bullhorn)", default="fa-check-circle", blank=True)
    is_highlighted = models.BooleanField(default=False, verbose_name="مميز؟ (مثل حفل الختام)")
    order = models.IntegerField(default=0, verbose_name="الترتيب")

    class Meta:
        verbose_name = "حدث زمني / خطوة"
        verbose_name_plural = "الجدول الزمني ورحلة الترشح"
        ordering = ['order']

    def __str__(self):
        return self.title

class Judge(models.Model):
    name = models.CharField(max_length=200, verbose_name="اسم عضو اللجنة")
    title = models.CharField(max_length=200, verbose_name="الصفة/المنصب")
    image = models.ImageField(max_length=500, upload_to='judges/', verbose_name="الصورة الشخصية")
    order = models.IntegerField(default=0, verbose_name="الترتيب")
    description = models.TextField(verbose_name="نبذة عن العضو", blank=True, default="")
    
    class Meta:
        verbose_name = "عضو تحكيم"
        verbose_name_plural = "لجنة التحكيم"
        ordering = ['order']

    def __str__(self): 
        return self.name
    
class ThemeSetting(models.Model):
    primary_color = models.CharField(max_length=7, default='#0a1632', verbose_name="اللون الأساسي (الأزرق الداكن)")
    secondary_color = models.CharField(max_length=7, default='#122450', verbose_name="اللون الثانوي")
    gold_color = models.CharField(max_length=7, default='#c5a059', verbose_name="اللون الذهبي")
    font_size = models.CharField(max_length=4, default='16px', verbose_name="حجم الخط الأساسي (مثال: 16px أو 18px)")
    STYLE_CHOICES = (('classic', 'الكلاسيكي — أقسام بيضاء ورمادية'), ('glass', 'تدرّج لوني وزجاجي في كل الموقع'))
    site_style = models.CharField(max_length=10, choices=STYLE_CHOICES, default='classic', verbose_name="نمط الموقع",
                                  help_text="يمكنك الرجوع للنمط الكلاسيكي في أي وقت.")
    FLIP_CHOICES = (('navy', 'كحلي مع ذهبي'), ('gold', 'معكوس: ذهبي مع كحلي'))
    flip_style = models.CharField(max_length=10, choices=FLIP_CHOICES, default='navy', verbose_name="ألوان البطاقات القلابة (المجالات)")
    custom_css = models.TextField(blank=True, null=True, verbose_name="CSS مخصص (لتغيير ألوان صفحات أو أحجام خطوط معينة)", help_text="اكتب أو الصق أكواد CSS هنا لتغيير تصميم الموقع بدون لمس الكود الأساسي")

    class Meta:
        verbose_name = "إعدادات الألوان والتصميم"
        verbose_name_plural = "إعدادات الألوان والتصميم"

    def __str__(self):
        return "ألوان وتصميم الموقع"
 
class HomeContent(models.Model):
    # -- قسم الهيرو --
    hero_title = models.CharField(max_length=1000, default="جائزة انتصار عباس جردانة", verbose_name="العنوان الرئيسي الكبير")
    hero_subtitle = models.TextField(default="للثقافة والتعليم", verbose_name="العنوان الفرعي (النص المتحرك)")
    
    # -- قسم عن الجائزة --
    about_text = models.TextField(default="تخليداً لذكرى السيدة انتصار عباس جردانة، أُطلقت هذه الجائزة لتكريم المبادرات التطوعية...", verbose_name="نص عن الجائزة")
    vision_text = models.TextField(default="مجتمع نابض بالشغف والعطاء، يحتضن المبادرات.", verbose_name="نص الرؤية")
    mission_text = models.TextField(default="تكريم القدرات التطوعية ودعم المبادرات كفعل نهضوي.", verbose_name="نص الرسالة")
    
    # -- المبادئ --
    principle_1 = models.CharField(max_length=1000, default="العطاء", verbose_name="المبدأ الأول")
    principle_2 = models.CharField(max_length=1000, default="الريادة والابتكار", verbose_name="المبدأ الثاني")
    principle_3 = models.CharField(max_length=1000, default="الاستدامة", verbose_name="المبدأ الثالث")
    principle_4 = models.CharField(max_length=1000, default="الأثر والتأثر", verbose_name="المبدأ الرابع")
    
    # -- شروط التقدم --
    condition_1 = models.CharField(max_length=1000, default="نطاق العمل داخل المملكة الأردنية الهاشمية.", verbose_name="الشرط الأول")
    condition_2 = models.CharField(max_length=1000, default="مراعاة المبادئ العامة ومجالات الجائزة.", verbose_name="الشرط الثاني")
    condition_3 = models.CharField(max_length=1000, default="الالتزام بالميثاق الأخلاقي للعمل التطوعي.", verbose_name="الشرط الثالث")
    condition_4 = models.CharField(max_length=1000, default="الفئة المستهدفة: طلبة التاسع - الثاني عشر.", verbose_name="الشرط الرابع")
    condition_5 = models.CharField(max_length=1000, default="تقديم البحث بصيغة PDF (15-20 صفحة).", verbose_name="الشرط الخامس")
    
    # -- خطوات الترشح --
    step_1 = models.CharField(max_length=1000, default="الاطلاع على دليل الجائزة ومعايير التحكيم.", verbose_name="الخطوة الأولى")
    step_2 = models.CharField(max_length=1000, default="حضور اللقاء التعريفي بالمدرسة.", verbose_name="الخطوة الثانية")
    step_3 = models.CharField(max_length=1000, default="تعبئة طلب الترشح الإلكتروني.", verbose_name="الخطوة الثالثة")
    step_4 = models.CharField(max_length=1000, default="تقديم البحث والصور والفيديوهات.", verbose_name="الخطوة الرابعة")
    step_5 = models.CharField(max_length=1000, default="تحديد ضابط ارتباط للمتابعة والتحكيم.", verbose_name="الخطوة الخامسة")

    # -- الجوائز --
    prize_1_desc = models.CharField(max_length=1000, default="1500 دينار + درع العمل التطوعي المتميز", verbose_name="وصف الجائزة الأولى")
    prize_2_desc = models.CharField(max_length=1000, default="1000 دينار + درع الاستدامة والتأثير", verbose_name="وصف الجائزة الثانية")
    prize_3_desc = models.CharField(max_length=1000, default="500 دينار + درع أفضل فكرة ريادية", verbose_name="وصف الجائزة الثالثة")
    
    # -- عناوين الأقسام --
    title_about = models.CharField(max_length=1000, default="عن الجائزة", verbose_name="عنوان قسم عن الجائزة")
    title_fields = models.CharField(max_length=1000, default="مجالات العمل التطوعي", verbose_name="عنوان قسم المجالات")
    title_timeline = models.CharField(max_length=1000, default="الإطار الزمني لمراحل الجائزة", verbose_name="عنوان قسم الجدول الزمني")
    title_apply = models.CharField(max_length=1000, default="طلب التقديم للجائزة", verbose_name="عنوان قسم التقديم")
    title_prizes = models.CharField(max_length=1000, default="قيمة الجوائز", verbose_name="عنوان قسم الجوائز")
    title_judges = models.CharField(max_length=1000, default="لجنة التحكيم", verbose_name="عنوان قسم لجنة التحكيم")
    title_sponsors = models.CharField(max_length=1000, default="رعاة وشركاء النجاح", verbose_name="عنوان قسم الرعاة والشركاء")
    
    # -- نصوص الأزرار --
    btn_hero = models.CharField(max_length=1000, default="تقدم لمشروعك الآن", verbose_name="زر الصفحة الرئيسية")
    btn_navbar = models.CharField(max_length=1000, default="سجل الآن", verbose_name="زر النافبار العلوي")

    class Meta:
        verbose_name = "تحرير محتوى الصفحة الرئيسية (A to Z)"
        verbose_name_plural = "تحرير محتوى الصفحة الرئيسية (A to Z)"

    def __str__(self):
        return "تعديل نصوص وأوصاف الموقع"

class Principle(models.Model):
    """بطاقات «المبادئ العامة للجائزة» في قسم عن الجائزة — تضاف بأي عدد"""
    title = models.CharField(max_length=150, verbose_name="اسم المبدأ")
    description = models.TextField(blank=True, default='', verbose_name="شرح مختصر (اختياري)")
    icon = models.CharField(max_length=60, default='fa-star', verbose_name="أيقونة FontAwesome",
                            help_text="مثال: fa-hand-holding-heart أو fa-lightbulb — القائمة: fontawesome.com/icons")
    order = models.IntegerField(default=0, verbose_name="الترتيب")
    is_active = models.BooleanField(default=True, verbose_name="ظاهر؟")

    class Meta:
        verbose_name = "مبدأ"
        verbose_name_plural = "مبادئ الجائزة (بطاقات عن الجائزة)"
        ordering = ['order', 'pk']

    def __str__(self):
        return self.title


class FooterContent(models.Model):
    about_text = models.TextField(default="مبادرة تهدف لتكريم العطاء التطوعي للشباب اليافع في الأردن، تخليداً لمسيرة السيدة انتصار عباس جردانة.", verbose_name="نص عن الجائزة في الفوتر")
    email = models.CharField(max_length=100, default="info@iaj-award.jo", verbose_name="البريد الإلكتروني")
    phone = models.CharField(max_length=20, default="+962 7X XXX XXXX", verbose_name="رقم الهاتف")
    address = models.CharField(max_length=1000, default="المملكة الأردنية الهاشمية", verbose_name="العنوان")
    copyright_text = models.CharField(max_length=1000, default="جميع الحقوق محفوظة 2025 جائزة انتصار عباس جردانة للثقافة والتعليم", verbose_name="نص حقوق النشر")

    class Meta:
        verbose_name = "تحرير محتوى الفوتر (أسفل الصفحة)"
        verbose_name_plural = "تحرير محتوى الفوتر (أسفل الصفحة)"

    def __str__(self):
        return "تعديل نصوص وأوصاف الفوتر"
        
class SuccessPageContent(models.Model):
    main_title = models.CharField(max_length=200, default="تم إرسال طلبك بنجاح!", verbose_name="العنوان الرئيسي")
    sub_text = models.TextField(default="شكراً لمشاركتكم في جائزة انتصار عباس جردانة. سيتم مراجعة الطلب.", verbose_name="النص الفرعي")
    btn_text = models.CharField(max_length=100, default="العودة للرئيسية", verbose_name="نص زر العودة")

    class Meta:
        verbose_name = "تحرير صفحة النجاح (بعد التسجيل)"
        verbose_name_plural = "تحرير صفحة النجاح (بعد التسجيل)"

    def __str__(self):
        return "تعديل نصوص صفحة النجاح"

# ========================================= #
#   الموديلات الاحترافية الجديدة (CMS)       #
# ========================================= #

class SectionBackground(models.Model):
    SECTION_CHOICES = [
        ('home', 'أعلى الصفحة الرئيسية (الصورة الكبيرة)'), ('stats', 'الإحصائيات'),
        ('about', 'عن الجائزة'), ('fields', 'مجالات العمل التطوعي'),
        ('timeline', 'الجدول الزمني'), ('apply', 'طلب التقديم'),
        ('prizes', 'الجوائز'), ('judges', 'لجنة التحكيم'), ('sponsors', 'رعاة وشركاء النجاح'), ('footer', 'الفوتر'),
    ]
    section_id = models.CharField(max_length=20, choices=SECTION_CHOICES, unique=True, verbose_name="اختر القسم")
    bg_image = models.ImageField(max_length=500, upload_to='backgrounds/', verbose_name="صورة الخلفية", blank=True, null=True)
    bg_color = models.CharField(max_length=7, default='', blank=True, verbose_name="لون خلفية بديل (بدون صورة)")
    bg_color_2 = models.CharField(max_length=7, default='', blank=True, verbose_name="لون التدرّج الثاني (اختياري)",
                                  help_text="مع «لون خلفية بديل» يصبح القسم تدرّجاً بين اللونين. (قسم المجالات متدرّج تلقائياً)")
    enable_overlay = models.BooleanField(default=True, verbose_name="تفعيل الطبقة الشفافة؟")
    overlay_color = models.CharField(max_length=7, default='#000000', verbose_name="لون الطبقة")
    overlay_color_2 = models.CharField(max_length=7, default='', blank=True, verbose_name="لون الطبقة الثاني (تدرّج، اختياري)")
    overlay_opacity = models.DecimalField(max_digits=3, decimal_places=2, default=0.70, verbose_name="نسبة الشفافية")
    heading_color = models.CharField(max_length=7, default='', blank=True, verbose_name="لون العنوان الرئيسي (h2)")
    heading_size = models.CharField(max_length=6, default='', blank=True, verbose_name="حجم العنوان الرئيسي (مثال: 2.2rem)")
    sub_heading_color = models.CharField(max_length=7, default='', blank=True, verbose_name="لون العناوين الفرعية (h3, h4, h5)")
    sub_heading_size = models.CharField(max_length=6, default='', blank=True, verbose_name="حجم العناوين الفرعية")
    text_color = models.CharField(max_length=7, default='', blank=True, verbose_name="لون النصوص (p, li)")
    text_size = models.CharField(max_length=6, default='', blank=True, verbose_name="حجم النصوص")
    gold_line_color = models.CharField(max_length=7, default='', blank=True, verbose_name="لون الخط الذهبي تحت العنوان")
    is_parallax = models.BooleanField(default=True, verbose_name="تفعيل الحركة (Parallax)؟")
    class Meta: verbose_name = "خلفية القسم"; verbose_name_plural = "إدارة خلفيات الأقسام"
    def __str__(self): return self.get_section_id_display()

    @property
    def _gradient(self):
        """التدرّج تلقائي في قسم المجالات فقط؛ باقي الأقسام عند اختيار لون ثانٍ"""
        return self.section_id == 'fields'

    @property
    def bg_css(self):
        c1 = self.bg_color or '#0a1632'
        if not (self._gradient or self.bg_color_2):
            return f'background-color: {c1};'
        c2 = self.bg_color_2 or shade(c1, -0.35)
        return f'background: radial-gradient(90% 70% at 85% 0%, {shade(c1, 0.18)}66 0%, transparent 60%), linear-gradient(145deg, {c1} 0%, {c2} 100%);'

    @property
    def overlay_css(self):
        c1 = self.overlay_color or '#000000'
        if not (self._gradient or self.overlay_color_2):
            return f'background-color: {c1};'
        c2 = self.overlay_color_2 or shade(c1, -0.45)
        return f'background: linear-gradient(160deg, {c1} 0%, {c2} 100%);'

class Sponsor(models.Model):
    TIER_CHOICES = (('platinum', 'بلاتيني'), ('gold', 'ذهبي'), ('silver', 'فضي'), ('bronze', 'برونزي'))
    name = models.CharField(max_length=200, verbose_name="اسم الجهة")
    logo = models.ImageField(max_length=500, upload_to='sponsors/', verbose_name="شعار الجهة")
    website = models.URLField(blank=True, null=True, verbose_name="رابط الموقع")
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='gold', verbose_name="مستوى الرعاية")
    order = models.IntegerField(default=0, verbose_name="الترتيب")
    class Meta: verbose_name = "شريك"; verbose_name_plural = "الشركاء والرعاة"; ordering = ['order']
    def __str__(self): return self.name

class FAQ(models.Model):
    question = models.CharField(max_length=500, verbose_name="السؤال")
    answer = models.TextField(verbose_name="الإجابة")
    order = models.IntegerField(default=0, verbose_name="الترتيب")
    class Meta: verbose_name = "سؤال شائع"; verbose_name_plural = "الأسئلة الشائعة"; ordering = ['order']
    def __str__(self): return self.question

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

class Winner(models.Model):
    category = models.ForeignKey(WinnerCategory, on_delete=models.CASCADE, related_name='winners', verbose_name="الفئة", null=True, blank=True)
    year = models.IntegerField(verbose_name="سنة الفوز")
    school_name = models.CharField(max_length=255, verbose_name="اسم المدرسة")
    project_title = models.CharField(max_length=500, verbose_name="عنوان المشروع")
    rank = models.IntegerField(verbose_name="المركز")
    image = models.ImageField(max_length=500, upload_to='winners/', blank=True, null=True, verbose_name="الصورة")
    description = models.TextField(blank=True, null=True, verbose_name="النبذة")
    order = models.IntegerField(default=0, verbose_name="الترتيب")
    is_active = models.BooleanField(default=True, verbose_name="مفعّل")
    class Meta: verbose_name = "فائز"; verbose_name_plural = "الفائزون"; ordering = ['-year', 'rank']
    def __str__(self): return f"{self.school_name} - المركز {self.rank}"

class MediaGallery(models.Model):
    MEDIA_TYPE_CHOICES = (('image', 'صورة'), ('video', 'فيديو'))
    title = models.CharField(max_length=200, verbose_name="العنوان")
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default='image', verbose_name="النوع")
    image = models.ImageField(max_length=500, upload_to='gallery/', blank=True, null=True, verbose_name="الصورة")
    video_url = models.URLField(blank=True, null=True, verbose_name="رابط يوتيوب")
    category = models.CharField(max_length=100, blank=True, null=True, verbose_name="التصنيف")
    order = models.IntegerField(default=0, verbose_name="الترتيب")
    class Meta: verbose_name = "صورة/فيديو"; verbose_name_plural = "معرض الصور"; ordering = ['order']
    def __str__(self): return self.title

class Photo(models.Model):
    title = models.CharField(max_length=255, verbose_name="العنوان")
    image = models.FileField(max_length=500, upload_to='photos/', verbose_name="الصورة")
    description = models.TextField(blank=True, verbose_name="الوصف")
    is_active = models.BooleanField(default=True, verbose_name="مفعّل")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "صورة"
        verbose_name_plural = "معرض الصور"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

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
        url = self.youtube_url
        if 'watch?v=' in url:
            video_id = url.split('watch?v=')[-1].split('&')[0]
            return f'https://www.youtube.com/embed/{video_id}'
        elif 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[-1].split('?')[0]
            return f'https://www.youtube.com/embed/{video_id}'
        return url

class SuccessStory(models.Model):
    title = models.CharField(max_length=255, verbose_name="العنوان")
    content = models.TextField(verbose_name="النص")
    image = models.FileField(max_length=500, upload_to='success_stories/', blank=True, verbose_name="الصورة")
    date = models.DateField(verbose_name="التاريخ")
    is_active = models.BooleanField(default=True, verbose_name="مفعّل")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "قصة نجاح"
        verbose_name_plural = "قصص النجاح"
        ordering = ['-date']

    def __str__(self):
        return self.title

class News(models.Model):
    title = models.CharField(max_length=300, verbose_name="العنوان")
    image = models.ImageField(max_length=500, upload_to='news/', blank=True, null=True, verbose_name="الصورة")
    content = models.TextField(verbose_name="المحتوى")
    date = models.DateField(verbose_name="التاريخ")
    is_published = models.BooleanField(default=True, verbose_name="منشور؟")
    class Meta: verbose_name = "خبر"; verbose_name_plural = "الأخبار"; ordering = ['-date']
    def __str__(self): return self.title

class ContactMessage(models.Model):
    name = models.CharField(max_length=200, verbose_name="الاسم")
    email = models.EmailField(verbose_name="البريد")
    subject = models.CharField(max_length=300, verbose_name="الموضوع")
    message = models.TextField(verbose_name="الرسالة")
    is_read = models.BooleanField(default=False, verbose_name="تمت القراءة؟")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: verbose_name = "رسالة"; verbose_name_plural = "رسائل التواصل"; ordering = ['-created_at']
    def __str__(self): return f"رسالة من {self.name}"

class TickerItem(models.Model):
    message_html = models.TextField(verbose_name="النص (يدعم HTML)")
    logo = models.ImageField(max_length=500, upload_to='ticker/', blank=True, null=True, verbose_name="لوغو (اختياري)")
    is_active = models.BooleanField(default=True, verbose_name="مفعّل؟")
    order = models.IntegerField(default=0, verbose_name="الترتيب")
    class Meta: verbose_name = "رسالة شريط"; verbose_name_plural = "رسائل الشريط الإخباري"; ordering = ['order']
    def __str__(self): return self.message_html

# ========================================= #
#   بطاقات العرض الشفافة (Slideshow Cards)     #
# ========================================= #

class SlideshowCard(models.Model):
    CARD_TYPE_CHOICES = (
        ('image', 'صورة فقط'),
        ('video', 'فيديو (يوتيوب أو رفع ملف)'),
        ('text', 'نص فقط'),
        ('image_text', 'صورة + نص'),
        ('video_text', 'فيديو + نص'),
    )
    FONT_WEIGHT_CHOICES = (
        ('300', 'خفيف (300)'),
        ('400', 'عادي (400)'),
        ('600', 'شبه سميك (600)'),
        ('700', 'سميك (Bold)'),
        ('900', 'أسود سميك (900)'),
    )
    TEXT_ALIGN_CHOICES = (
        ('center', 'وسط'),
        ('right', 'يمين'),
        ('left', 'يسار'),
    )

    card_type = models.CharField(max_length=12, choices=CARD_TYPE_CHOICES, default='image_text', verbose_name="نوع البطاقة")
    image = models.ImageField(max_length=500, upload_to='slideshow/', verbose_name="الصورة", blank=True, null=True, help_text="مطلوبة لنوع (صورة) و(صورة+نص)")
    video_url = models.URLField(blank=True, null=True, verbose_name="رابط فيديو (يوتيوب أو Vimeo)", help_text="مثال: https://www.youtube.com/embed/VIDEO_ID")
    video_file = models.FileField(max_length=500, upload_to='slideshow/videos/', verbose_name="ملف فيديو (رفع مباشر)", blank=True, null=True, help_text="بديل عن رابط يوتيوب — mp4/webm")
    heading = models.CharField(max_length=300, blank=True, default='', verbose_name="العنوان")
    body_text = models.TextField(blank=True, default='', verbose_name="النص")
    font_size = models.CharField(max_length=6, default='1rem', verbose_name="حجم الخط (مثال: 1rem أو 18px أو 1.2em)")
    font_color = models.CharField(max_length=7, default='#ffffff', verbose_name="لون الخط")
    font_weight = models.CharField(max_length=3, choices=FONT_WEIGHT_CHOICES, default='400', verbose_name="وزن الخط")
    text_align = models.CharField(max_length=6, choices=TEXT_ALIGN_CHOICES, default='center', verbose_name="محاذاة النص")
    card_bg_color = models.CharField(max_length=7, default='#000000', verbose_name="لون خلفية البطاقة")
    card_opacity = models.DecimalField(max_digits=3, decimal_places=2, default=0.45, verbose_name="شفافية البطاقة (0.0 = شفافة تماماً، 1.0 = معتمة)")
    border_radius = models.CharField(max_length=6, default='16px', verbose_name="استدارة الزوايا (مثال: 16px أو 0 أو 50%)")
    order = models.IntegerField(default=0, verbose_name="الترتيب")
    is_active = models.BooleanField(default=True, verbose_name="مفعّلة؟")

    class Meta:
        verbose_name = "بطاقة عرض شفافة"
        verbose_name_plural = "بطاقات العرض الشفافة (Slideshow)"
        ordering = ['order']

    def __str__(self):
        return f"بطاقة {self.order}: {self.heading or self.card_type}"

    def bg_rgb(self):
        """تحويل لون hex إلى أرقام RGB للاستخدام في rgba()"""
        hex_color = self.card_bg_color.replace('#', '')
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return f"{r},{g},{b}"
        return "0,0,0"


class TickerSetting(models.Model):
    is_enabled = models.BooleanField(default=True, verbose_name="تشغيل الشريط؟")
    font_color = models.CharField(max_length=7, default='#c5a059', verbose_name="لون الخط")
    bg_color = models.CharField(max_length=7, default='#0a1632', verbose_name="لون الخلفية")
    bg_opacity = models.DecimalField(max_digits=3, decimal_places=2, default=0.95, verbose_name="شفافية الخلفية")
    scroll_speed = models.IntegerField(
        default=60, verbose_name="السرعة (بكسل/ثانية)",
        help_text="رقم أكبر = أسرع. المقترح: 40 بطيء، 60 متوسط، 100 سريع (من 10 إلى 300).",
    )
    fade_width = models.CharField(max_length=5, default='150px', verbose_name="مسافة التلاشي")
    font_size = models.CharField(max_length=8, default='0.95rem', verbose_name="حجم الخط",
                                 help_text="مثال: 0.95rem (عادي) — 1.1rem (أكبر) — 16px")
    bar_height = models.PositiveSmallIntegerField(default=38, verbose_name="ارتفاع الشريط (بكسل)",
                                                  help_text="المقترح بين 32 و 60")
    logo_size = models.PositiveSmallIntegerField(default=24, verbose_name="حجم الصور في الشريط (بكسل)")
    separator_image = models.ImageField(max_length=500, upload_to='ticker/', blank=True, null=True,
                                        verbose_name="صورة فاصلة بين الأخبار (اختياري)",
                                        help_text="تظهر في الوسط بين كل خبرين بدل النجمة الصغيرة.")
    sep_pulse = models.BooleanField(default=True, verbose_name="نبض الصورة الفاصلة؟")
    sep_pulse_seconds = models.DecimalField(max_digits=3, decimal_places=1, default=1.6, verbose_name="سرعة النبض (ثوانٍ)",
                                            help_text="رقم أصغر = أسرع")
    sep_fade = models.BooleanField(default=False, verbose_name="تلاشي الصورة الفاصلة (يظهر ويختفي)؟")
    sep_fade_seconds = models.DecimalField(max_digits=3, decimal_places=1, default=2.4, verbose_name="سرعة التلاشي (ثوانٍ)",
                                           help_text="رقم أصغر = أسرع")
    effects_on_logos = models.BooleanField(default=False, verbose_name="تطبيق النبض والتلاشي على صور الأخبار أيضاً؟")
    class Meta: verbose_name = "إعدادات الشريط"; verbose_name_plural = "إعدادات الشريط"
    def __str__(self): return "إعدادات الشريط الإخباري"


class HeroTextSlide(models.Model):
    """نصوص إضافية تتبدّل داخل البطاقة الشفافة تحت الفيديو"""
    heading = models.CharField(max_length=300, blank=True, default='', verbose_name="العنوان")
    body_text = models.TextField(blank=True, default='', verbose_name="النص")
    order = models.IntegerField(default=0, verbose_name="الترتيب")
    is_active = models.BooleanField(default=True, verbose_name="ظاهر؟")

    class Meta:
        verbose_name = "نص متبدّل"
        verbose_name_plural = "النصوص المتبدّلة تحت الفيديو"
        ordering = ['order', 'id']

    def __str__(self):
        return self.heading or (self.body_text or '')[:60] or f'نص {self.pk}'


# ========================================= #
#   بطاقة الهيرو الشفافة (HeroCard)          #
# ========================================= #

class HeroCard(models.Model):
    is_enabled = models.BooleanField(default=False, verbose_name="تفعيل البطاقة؟")
    heading = models.CharField(max_length=300, blank=True, default='', verbose_name="العنوان")
    body_text = models.TextField(blank=True, default='', verbose_name="النص الداخلي")
    card_bg_color = models.CharField(max_length=7, default='#0a1632', verbose_name="لون خلفية البطاقة")
    card_opacity = models.DecimalField(max_digits=3, decimal_places=2, default=0.55, verbose_name="شفافية البطاقة (0=شفافة، 1=معتمة)")
    font_color = models.CharField(max_length=7, default='#ffffff', verbose_name="لون الخط")
    font_size = models.CharField(max_length=6, default='1.1rem', verbose_name="حجم الخط")
    font_weight = models.CharField(max_length=3, default='600', verbose_name="وزن الخط")
    border_radius = models.CharField(max_length=6, default='0px', verbose_name="استدارة الزوايا")
    EFFECT_CHOICES = (('fade', 'تلاشي ناعم'), ('slide', 'انزلاق جانبي'), ('up', 'صعود من الأسفل'),
                      ('zoom', 'تكبير'), ('blur', 'ضبابية ثم وضوح'), ('flip', 'قلب'))
    text_effect = models.CharField(max_length=10, choices=EFFECT_CHOICES, default='fade', verbose_name="حركة الانتقال بين النصوص")
    reading_speed = models.PositiveSmallIntegerField(default=14, verbose_name="سرعة القراءة (حرف في الثانية)",
                                                     help_text="مدة كل نص تُحسب من طوله: رقم أصغر = وقت أطول للقراءة. المقترح 12–18.")
    min_seconds = models.PositiveSmallIntegerField(default=4, verbose_name="أقل مدة لكل نص (ثوانٍ)")
    show_arrows = models.BooleanField(default=True, verbose_name="إظهار سهمي التنقل")

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
        return "0,0,0"


# ========================================= #
#   تخزين الصور داخل قاعدة البيانات          #
# ========================================= #

class StoredFile(models.Model):
    """
    الصور المرفوعة من لوحة التحكم تُحفظ هنا (Postgres) بدل Cloudinary
    وتُعرض عبر /media/db/<name>
    """
    name = models.CharField(max_length=255, unique=True, verbose_name="المسار")
    content = models.BinaryField(verbose_name="المحتوى")
    content_type = models.CharField(max_length=100, default='application/octet-stream')
    size = models.PositiveIntegerField(default=0, verbose_name="الحجم (بايت)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ملف مخزّن"
        verbose_name_plural = "الصور المخزّنة في قاعدة البيانات"
        ordering = ['-created_at']

    def __str__(self):
        return self.name
