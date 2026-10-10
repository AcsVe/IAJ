from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


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
    ('draft', 'مسودة'),
    ('submitted', 'مُرسل — بانتظار التدقيق'),
    ('screening', 'قيد التدقيق'),
    ('revision', 'مطلوب استكمال / تعديل'),
    ('on_hold', 'معلّق'),
    ('judging', 'قيد التحكيم'),
    ('accepted', 'مقبول'),
    ('rejected', 'غير مقبول'),
    ('winner', 'فائز'),
    ('withdrawn', 'مسحوب'),
)
FINAL_STATUSES = ('accepted', 'rejected', 'winner')
EDITABLE_STATUSES = ('draft', 'revision')


def submission_upload(instance, filename):
    """ملفات الطلبات في مجلد خاص لا يُفتح إلا لأصحاب الصلاحية"""
    import os
    base, ext = os.path.splitext(os.path.basename(filename))
    folder = instance.ref or (f'u{instance.owner_id}' if instance.owner_id else 'new')
    return f'private/submissions/{folder}/{base[:60]}{ext.lower()}'


class Submission(models.Model):
    ref = models.CharField(max_length=30, unique=True, null=True, blank=True, verbose_name="رقم الطلب")
    cycle = models.ForeignKey('AwardCycle', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='submissions', verbose_name="الدورة")
    owner = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='submissions', verbose_name="حساب المدرسة")
    school_name = models.CharField(max_length=255, verbose_name="اسم المدرسة")
    contact_person = models.CharField(max_length=255, verbose_name="ضابط الارتباط")
    email = models.EmailField(verbose_name="البريد الإلكتروني")
    phone = models.CharField(max_length=30, verbose_name="رقم الهاتف")
    field = models.ForeignKey(Field, on_delete=models.SET_NULL, null=True, verbose_name="المجال")
    track = models.ForeignKey(Track, on_delete=models.SET_NULL, null=True, verbose_name="المسار")
    project_title = models.CharField(max_length=500, verbose_name="عنوان المشروع/البحث")
    abstract = models.TextField(blank=True, default='', verbose_name="ملخص المشروع",
                                help_text="فقرة تشرح فكرة المشروع وأهدافه ونتائجه.")
    team_members = models.TextField(blank=True, default='', verbose_name="أسماء الطلبة المشاركين",
                                    help_text="كل اسم في سطر.")
    supervisor = models.CharField(max_length=255, blank=True, default='', verbose_name="المعلم المشرف")
    document = models.FileField(max_length=500, upload_to=submission_upload, blank=True,
                                verbose_name="ملف البحث (PDF)")
    attachment = models.FileField(max_length=500, upload_to=submission_upload, blank=True,
                                  verbose_name="مرفق إضافي (اختياري)",
                                  help_text="صور، عرض تقديمي، ملف مضغوط…")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="الحالة")
    school_note = models.TextField(blank=True, default='', verbose_name="ملاحظة للمدرسة (تظهر لها)",
                                   help_text="مثلاً: المطلوب تعديله. تُرسل مع إشعار تغيير الحالة.")
    internal_note = models.TextField(blank=True, default='', verbose_name="ملاحظات داخلية (للإدارة فقط)")
    revision_deadline = models.DateTimeField(null=True, blank=True, verbose_name="آخر موعد للتعديل")
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ الإرسال")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")

    class Meta:
        verbose_name = "طلب ترشح"
        verbose_name_plural = "طلبات الترشح"
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.ref or '#'+str(self.pk)} — {self.school_name} — {self.project_title}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.ref:
            year = self.cycle.year if self.cycle_id and self.cycle else self.submitted_at.year
            self.ref = f'IAJ-{year}-{self.pk:04d}'
            Submission.objects.filter(pk=self.pk).update(ref=self.ref)

    def get_absolute_url(self):
        return f'/portal/submissions/{self.pk}/'

    # ---------- ما تراه المدرسة ----------
    @property
    def results_hidden(self):
        """النتيجة النهائية لا تظهر للمدرسة قبل «نشر النتائج» في الدورة"""
        return self.status in FINAL_STATUSES and not (self.cycle and self.cycle.results_published)

    @property
    def public_status(self):
        return 'judging' if self.results_hidden else self.status

    @property
    def public_status_label(self):
        return dict(STATUS_CHOICES).get(self.public_status, self.public_status)

    @property
    def can_edit(self):
        if self.status == 'draft':
            return bool(self.cycle and self.cycle.is_open)
        if self.status == 'revision':
            from django.utils import timezone
            return not self.revision_deadline or timezone.now() <= self.revision_deadline
        return False

    @property
    def can_withdraw(self):
        return self.status in ('draft', 'submitted', 'screening', 'revision', 'on_hold')

    @property
    def can_add_files(self):
        """المدرسة تضيف ملفات/وسائط في أي وقت قبل النتيجة النهائية"""
        return self.status not in ('accepted', 'rejected', 'winner', 'withdrawn')

    # ---------- التحكيم ----------
    @property
    def avg_score(self):
        totals = [a.total for a in self.assignments.all() if a.is_done]
        return round(sum(totals) / len(totals), 1) if totals else None

    @property
    def judging_progress(self):
        items = list(self.assignments.all())
        return f"{sum(1 for a in items if a.is_done)}/{len(items)}" if items else '—'


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

def current_cycle_id():
    """الدورة الحالية — تُستخدم افتراضياً للمواد الجديدة (صور، فيديو، أخبار…)"""
    try:
        from django.apps import apps
        C = apps.get_model('award', 'AwardCycle')
        return C.objects.filter(is_current=True).values_list('pk', flat=True).first()
    except Exception:
        return None


def _cycle_fk():
    return models.ForeignKey('AwardCycle', on_delete=models.SET_NULL, null=True, blank=True, default=current_cycle_id,
                             verbose_name="الدورة", help_text="تُختار الدورة الحالية تلقائياً. فارغ = عام لكل الدورات.")


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
    caption = models.CharField(max_length=200, blank=True, default='', verbose_name="نص الشرح أعلى الصورة (اختياري)",
                               help_text="يظهر بجانب شعار الجائزة أعلى الصورة/الفيديو. فارغ = العنوان.")
    show_caption = models.BooleanField(default=True, verbose_name="إظهار نص الشرح أعلى الصورة؟")
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
    cycle = _cycle_fk()

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
    
from .fonts import FONT_CHOICES, INHERIT_CHOICES  # noqa: E402


class ThemeSetting(models.Model):
    primary_color = models.CharField(max_length=7, default='#0a1632', verbose_name="اللون الأساسي (لون الهيدر والقوائم)")
    secondary_color = models.CharField(max_length=7, default='#122450', verbose_name="اللون الثانوي")
    gold_color = models.CharField(max_length=7, default='#c5a059', verbose_name="اللون الذهبي")
    font_size = models.CharField(max_length=4, default='16px', verbose_name="حجم الخط الأساسي (مثال: 16px أو 18px)")
    STYLE_CHOICES = (('classic', 'الكلاسيكي — أقسام بيضاء ورمادية'), ('glass', 'تدرّج لوني وزجاجي في كل الموقع'))
    site_style = models.CharField(max_length=10, choices=STYLE_CHOICES, default='classic', verbose_name="نمط الموقع",
                                  help_text="يمكنك الرجوع للنمط الكلاسيكي في أي وقت.")
    FLIP_CHOICES = (('navy', 'كحلي مع ذهبي'), ('gold', 'معكوس: ذهبي مع كحلي'))
    flip_style = models.CharField(max_length=10, choices=FLIP_CHOICES, default='navy', verbose_name="ألوان البطاقات القلابة (المجالات)")
    # -- الخطوط: خط لكل عنصر (القائمة في award/fonts.py) --
    font_body = models.CharField(max_length=40, blank=True, default='Cairo', choices=FONT_CHOICES, verbose_name="خط النص الأساسي لكل الموقع")
    font_headings = models.CharField(max_length=40, blank=True, default='', choices=INHERIT_CHOICES, verbose_name="خط عناوين الأقسام والصفحات")
    font_site_title = models.CharField(max_length=40, blank=True, default='Noto Kufi Arabic', choices=INHERIT_CHOICES, verbose_name="خط اسم الجائزة في الهيدر")
    font_nav = models.CharField(max_length=40, blank=True, default='', choices=INHERIT_CHOICES, verbose_name="خط روابط القائمة الرئيسية")
    font_ticker = models.CharField(max_length=40, blank=True, default='', choices=INHERIT_CHOICES, verbose_name="خط شريط الأخبار")
    font_hero = models.CharField(max_length=40, blank=True, default='', choices=INHERIT_CHOICES, verbose_name="خط نصوص أعلى الصفحة وبطاقة النصوص")
    font_cards = models.CharField(max_length=40, blank=True, default='', choices=INHERIT_CHOICES, verbose_name="خط البطاقات (المجالات، الجوائز، الجدول الزمني)")
    font_buttons = models.CharField(max_length=40, blank=True, default='', choices=INHERIT_CHOICES, verbose_name="خط الأزرار")
    font_numbers = models.CharField(max_length=40, blank=True, default='', choices=INHERIT_CHOICES, verbose_name="خط العداد التنازلي والأرقام")
    font_footer = models.CharField(max_length=40, blank=True, default='', choices=INHERIT_CHOICES, verbose_name="خط الفوتر (أسفل الصفحة)")
    # -- ألوان النصوص: لون لكل عنصر (فارغ = اللون الأصلي) --
    color_body = models.CharField(max_length=9, blank=True, default='', verbose_name="لون: النص العام في الصفحات")
    color_headings = models.CharField(max_length=9, blank=True, default='', verbose_name="لون: عناوين الأقسام (كل الأقسام)")
    color_site_title = models.CharField(max_length=9, blank=True, default='', verbose_name="لون: اسم الجائزة في الهيدر")
    color_nav = models.CharField(max_length=9, blank=True, default='', verbose_name="لون: روابط القائمة الرئيسية")
    color_hero = models.CharField(max_length=9, blank=True, default='', verbose_name="لون: النص المتحرك أعلى الصفحة (العنوان)")
    color_hero_text = models.CharField(max_length=9, blank=True, default='', verbose_name="لون: النص المتحرك أعلى الصفحة (النص)")
    color_tl_title = models.CharField(max_length=9, blank=True, default='', verbose_name="لون: عناوين مراحل الجدول الزمني")
    color_tl_date = models.CharField(max_length=9, blank=True, default='', verbose_name="لون: تواريخ الجدول الزمني")
    color_prize_title = models.CharField(max_length=9, blank=True, default='', verbose_name="لون: عناوين بطاقات الجوائز")
    color_prize_text = models.CharField(max_length=9, blank=True, default='', verbose_name="لون: نص بطاقات الجوائز")
    color_buttons = models.CharField(max_length=9, blank=True, default='', verbose_name="لون: نص الأزرار")
    color_numbers = models.CharField(max_length=9, blank=True, default='', verbose_name="لون: أرقام العداد التنازلي")
    color_footer_title = models.CharField(max_length=9, blank=True, default='', verbose_name="لون: عناوين الفوتر")
    color_footer_text = models.CharField(max_length=9, blank=True, default='', verbose_name="لون: نصوص وروابط الفوتر")
    color_links = models.CharField(max_length=9, blank=True, default='', verbose_name="لون: الروابط داخل النصوص")
    custom_css = models.TextField(blank=True, null=True, verbose_name="CSS مخصص (لتغيير ألوان صفحات أو أحجام خطوط معينة)", help_text="اكتب أو الصق أكواد CSS هنا لتغيير تصميم الموقع بدون لمس الكود الأساسي")

    class Meta:
        verbose_name = "إعدادات الألوان والتصميم"
        verbose_name_plural = "إعدادات الألوان والتصميم"

    def __str__(self):
        return "ألوان وتصميم الموقع"
 
class HomeContent(models.Model):
    # -- قسم الهيرو --
    hero_title = models.CharField(max_length=1000, default="جائزة انتصار عباس جردانة", verbose_name="العنوان الرئيسي الكبير")
    hero_subtitle = models.TextField(default="للثقافة والتعليم", verbose_name="نص الشارة المتحركة (عدة فقرات)",
                                     help_text="سطر فارغ بين فقرتين = فقرة جديدة. سطر يبدأ بـ # = عنوان فرعي. مثال:\n# رؤيتنا\nنص الفقرة الأولى…")
    
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
    submission = models.OneToOneField('Submission', on_delete=models.SET_NULL, null=True, blank=True, related_name='winner_entry', verbose_name="الطلب المرتبط")
    cycle = _cycle_fk()
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
    cycle = _cycle_fk()
    class Meta: verbose_name = "صورة/فيديو"; verbose_name_plural = "معرض الصور"; ordering = ['order']
    def __str__(self): return self.title

class Photo(models.Model):
    title = models.CharField(max_length=255, verbose_name="العنوان")
    image = models.FileField(max_length=500, upload_to='photos/', verbose_name="الصورة")
    description = models.TextField(blank=True, verbose_name="الوصف")
    is_active = models.BooleanField(default=True, verbose_name="مفعّل")
    cycle = _cycle_fk()
    caption = models.CharField(max_length=200, blank=True, default='', verbose_name="نص الشرح أعلى الصورة (اختياري)",
                               help_text="يظهر بجانب شعار الجائزة أعلى الصورة/الفيديو. فارغ = العنوان.")
    show_caption = models.BooleanField(default=True, verbose_name="إظهار نص الشرح أعلى الصورة؟")
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
    cycle = _cycle_fk()
    caption = models.CharField(max_length=200, blank=True, default='', verbose_name="نص الشرح أعلى الصورة (اختياري)",
                               help_text="يظهر بجانب شعار الجائزة أعلى الصورة/الفيديو. فارغ = العنوان.")
    show_caption = models.BooleanField(default=True, verbose_name="إظهار نص الشرح أعلى الصورة؟")
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
    cycle = _cycle_fk()
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
    cycle = _cycle_fk()
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
    heading = models.CharField(max_length=120, blank=True, default='', verbose_name="العنوان (اختياري)",
                               help_text="يظهر قبل النص داخل شارة ملوّنة. مثال: عاجل — جديد — تذكير")
    heading_color = models.CharField(max_length=9, blank=True, default='', verbose_name="لون خط العنوان",
                                     help_text="فارغ = لون داكن تلقائي")
    heading_bg = models.CharField(max_length=9, blank=True, default='', verbose_name="لون خلفية العنوان",
                                  help_text="فارغ = لون خط الشريط (الذهبي)")
    message_html = models.TextField(verbose_name="النص (يدعم HTML)")
    text_color = models.CharField(max_length=9, blank=True, default='', verbose_name="لون النص",
                                  help_text="فارغ = لون خط الشريط من «إعدادات الشريط»")
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
    EFFECT_CHOICES = (('', 'نفس حركة البطاقة (الافتراضي)'),) + (
        ('fade', 'تلاشي ناعم'), ('slide', 'انزلاق جانبي'), ('up', 'صعود من الأسفل'), ('down', 'نزول من الأعلى'),
        ('zoom', 'تكبير'), ('blur', 'ضبابية ثم وضوح'), ('flip', 'قلب'), ('none', 'بدون حركة'))
    effect = models.CharField(max_length=10, choices=EFFECT_CHOICES, blank=True, default='', verbose_name="حركة ظهور هذا النص")
    effect_speed = models.FloatField(default=0.6, validators=[MinValueValidator(0.1), MaxValueValidator(5)],
                                     verbose_name="مدة حركة الظهور (ثوانٍ)",
                                     help_text="كم ثانية تستغرق حركة دخول النص. مثال: 0.3 سريعة — 0.6 عادية — 1.5 بطيئة.")
    roll_speed = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(200)],
                                                  verbose_name="سرعة مرور النص الطويل (بكسل/ثانية)",
                                                  help_text="للنص الأطول من الصندوق (يمرّ مثل شارة الأفلام). رقم أصغر = أبطأ. "
                                                            "مثال: 12 بطيء — 22 عادي — 40 سريع. 0 = سرعة البطاقة العامة.")
    heading_color = models.CharField(max_length=9, blank=True, default='', verbose_name="لون العنوان (اختياري)",
                                     help_text="فارغ = لون البطاقة.")
    body_color = models.CharField(max_length=9, blank=True, default='', verbose_name="لون النص (اختياري)",
                                  help_text="فارغ = لون البطاقة.")
    seconds = models.PositiveSmallIntegerField(default=0, verbose_name="مدة بقاء النص (ثوانٍ)",
                                               help_text="0 = تلقائي حسب طول النص (من إعدادات البطاقة).")
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
    is_enabled = models.BooleanField(default=True, verbose_name="إظهار بطاقة النصوص تحت الفيديو؟")
    heading = models.CharField(max_length=300, blank=True, default='', verbose_name="العنوان")
    body_text = models.TextField(blank=True, default='', verbose_name="النص الداخلي")
    card_bg_color = models.CharField(max_length=7, default='#3b2614', verbose_name="لون خلفية البطاقة")
    card_opacity = models.DecimalField(max_digits=3, decimal_places=2, default=0.55, verbose_name="شفافية البطاقة (0=شفافة، 1=معتمة)")
    font_color = models.CharField(max_length=7, default='#ffffff', verbose_name="لون الخط")
    heading_color = models.CharField(max_length=9, blank=True, default='', verbose_name="لون العناوين داخل البطاقة",
                                     help_text="فارغ = نفس «لون الخط».")
    font_size = models.CharField(max_length=6, default='1.1rem', verbose_name="حجم الخط")
    font_weight = models.CharField(max_length=3, default='600', verbose_name="وزن الخط")
    border_radius = models.CharField(max_length=6, default='0px', verbose_name="استدارة الزوايا")
    EFFECT_CHOICES = (('fade', 'تلاشي ناعم'), ('slide', 'انزلاق جانبي'), ('up', 'صعود من الأسفل'), ('down', 'نزول من الأعلى'),
                      ('zoom', 'تكبير'), ('blur', 'ضبابية ثم وضوح'), ('flip', 'قلب'), ('none', 'بدون حركة'))
    text_effect = models.CharField(max_length=10, choices=EFFECT_CHOICES, default='fade', verbose_name="الحركة الافتراضية بين النصوص",
                                   help_text="لكل نص حركته الخاصة من «النصوص المتبدّلة»؛ هذه تُستخدم للنص الأول وللنصوص التي لم تُحدَّد لها حركة.")
    reading_speed = models.PositiveSmallIntegerField(default=14, verbose_name="سرعة القراءة (حرف في الثانية)",
                                                     help_text="مدة كل نص تُحسب من طوله: رقم أصغر = وقت أطول للقراءة. المقترح 12–18.")
    min_seconds = models.PositiveSmallIntegerField(default=4, verbose_name="أقل مدة لكل نص (ثوانٍ)")
    effect_speed = models.FloatField(default=0.6, validators=[MinValueValidator(0.1), MaxValueValidator(5)],
                                     verbose_name="مدة حركة الظهور للنص الأول (ثوانٍ)", help_text="مثال: 0.3 سريعة — 0.6 عادية — 1.5 بطيئة.")
    roll_speed = models.PositiveSmallIntegerField(default=22, validators=[MinValueValidator(4), MaxValueValidator(200)],
                                                  verbose_name="سرعة مرور النص الطويل (بكسل/ثانية)",
                                                  help_text="العامة لكل النصوص. رقم أصغر = أبطأ. مثال: 12 بطيء — 22 عادي — 40 سريع.")
    roll_pause = models.FloatField(default=2.5, validators=[MinValueValidator(0), MaxValueValidator(20)],
                                   verbose_name="وقفة قبل بدء مرور النص الطويل (ثوانٍ)",
                                   help_text="ليقرأ الزائر أول النص قبل أن يصعد. بعد خروج النص كاملاً يظهر النص التالي مباشرة.")
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


# ========================================= #
#   الدورات، الحسابات، التحكيم، الإشعارات    #
# ========================================= #

class AwardCycle(models.Model):
    name = models.CharField(max_length=200, verbose_name="اسم الدورة", help_text="مثال: الدورة الأولى")
    year = models.PositiveIntegerField(verbose_name="السنة")
    opens_at = models.DateTimeField(verbose_name="بداية التسجيل")
    closes_at = models.DateTimeField(verbose_name="نهاية التسجيل",
                                     help_text="بعدها لا تُقبل طلبات جديدة. العداد التنازلي في الموقع يستخدم هذا الموعد.")
    is_current = models.BooleanField(default=False, verbose_name="الدورة الحالية؟",
                                     help_text="دورة واحدة فقط تكون حالية — اختيارها يلغي غيرها.")
    tracks = models.ManyToManyField(Track, blank=True, verbose_name="المسارات المتاحة",
                                    help_text="اتركها فارغة = كل المسارات المفعّلة.")
    max_per_school = models.PositiveSmallIntegerField(default=0, verbose_name="أقصى عدد طلبات للمدرسة",
                                                      help_text="0 = بلا حد.")
    revision_days = models.PositiveSmallIntegerField(default=7, verbose_name="مهلة التعديل (أيام)",
                                                     help_text="عند طلب تعديل من المدرسة يُحدَّد آخر موعد تلقائياً.")
    judges_per_submission = models.PositiveSmallIntegerField(default=2, verbose_name="عدد المحكّمين لكل طلب",
                                                             help_text="يُستخدم عند «توزيع تلقائي على المحكّمين».")
    short_name = models.CharField(max_length=60, blank=True, default='', verbose_name="اسم مختصر",
                                  help_text="مثال: الدورة 14 — يظهر في بطاقة العداد: «استقبال طلبات الدورة 14».")
    countdown_title = models.CharField(max_length=120, blank=True, default='', verbose_name="عنوان بطاقة العداد (اختياري)",
                                       help_text="فارغ = «استقبال طلبات» + الاسم المختصر.")
    summary = models.TextField(blank=True, default='', verbose_name="نبذة عن الدورة (تظهر في صفحة الدورات السابقة)")
    cover = models.ImageField(max_length=500, upload_to='cycles/', blank=True, null=True, verbose_name="صورة الدورة (اختياري)")
    hijri_year = models.CharField(max_length=10, blank=True, default='', verbose_name="السنة الهجرية",
                                  help_text="مثال: 1448 — تظهر في بطاقة الدورة: «الدورة الرابعة عشرة (1448هـ/2026م)».")
    show_card = models.BooleanField(default=True, verbose_name="إظهار بطاقة الدورة عند المرور على اسم الجائزة وزر التسجيل؟")
    card_note = models.TextField(blank=True, default='', verbose_name="سطر إضافي في بطاقة الدورة (اختياري)",
                                 help_text="مثال: «تم تمديد التسجيل حتى نهاية الشهر».")
    blind_judging = models.BooleanField(default=True, verbose_name="تحكيم بدون أسماء؟",
                                        help_text="المحكّم لا يرى اسم المدرسة ولا أسماء الطلبة والمشرف.")
    results_date = models.DateField(null=True, blank=True, verbose_name="تاريخ إعلان الفائزين",
                                    help_text="يظهر في صفحة الفائزين قبل الإعلان: «يُعلن الفائزون في …».")
    results_published = models.BooleanField(default=False, verbose_name="النتائج منشورة؟",
                                            help_text="قبل النشر ترى المدارس «قيد التحكيم» حتى لو حدّدتم النتيجة. "
                                                      "عند النشر تُرسل الإشعارات للجميع.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "دورة"
        verbose_name_plural = "دورات الجائزة"
        ordering = ['-year', '-opens_at']

    def __str__(self):
        return f"{self.name} ({self.year})" + (' — الحالية' if self.is_current else '')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_current:
            AwardCycle.objects.exclude(pk=self.pk).filter(is_current=True).update(is_current=False)
        from django.core.cache import cache
        cache.delete('iaj_current_cycle')

    def delete(self, *args, **kwargs):
        from django.core.cache import cache
        cache.delete('iaj_current_cycle')
        return super().delete(*args, **kwargs)

    @classmethod
    def current(cls):
        return cls.objects.filter(is_current=True).first()

    @property
    def is_open(self):
        from django.utils import timezone
        now = timezone.now()
        return bool(self.opens_at and self.closes_at and self.opens_at <= now <= self.closes_at)

    @property
    def cd_title(self):
        return self.countdown_title or f"استقبال طلبات {self.short_name or self.name}"

    @property
    def card_title(self):
        years = f"{self.hijri_year}هـ/{self.year}م" if self.hijri_year else f"{self.year}م"
        return f"{self.name} ({years})"

    @property
    def phase(self):
        from django.utils import timezone
        now = timezone.now()
        if now < self.opens_at:
            return 'upcoming'
        if now <= self.closes_at:
            return 'open'
        return 'results' if self.results_published else 'closed'

    def available_tracks(self):
        qs = self.tracks.filter(is_active=True) if self.pk and self.tracks.exists() else Track.objects.filter(is_active=True)
        return qs.select_related('field')


class Governorate(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="المحافظة")
    order = models.PositiveSmallIntegerField(default=0, verbose_name="الترتيب")

    class Meta:
        verbose_name = "محافظة"
        verbose_name_plural = "المحافظات"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Directorate(models.Model):
    governorate = models.ForeignKey(Governorate, on_delete=models.CASCADE, null=True, blank=True,
                                    related_name='directorates', verbose_name="المحافظة",
                                    help_text="فارغ = يظهر في كل المحافظات (مثل: وكالة الغوث، أخرى).")
    name = models.CharField(max_length=150, verbose_name="مديرية التربية والتعليم")
    order = models.PositiveSmallIntegerField(default=0, verbose_name="الترتيب")
    is_active = models.BooleanField(default=True, verbose_name="ظاهرة؟")

    class Meta:
        verbose_name = "مديرية تربية"
        verbose_name_plural = "مديريات التربية والتعليم"
        ordering = ['governorate__order', 'order', 'name']

    def __str__(self):
        return self.name


class Area(models.Model):
    governorate = models.ForeignKey(Governorate, on_delete=models.CASCADE, related_name='areas', verbose_name="المحافظة")
    name = models.CharField(max_length=100, verbose_name="اللواء / المدينة")
    directorate = models.ForeignKey(Directorate, on_delete=models.SET_NULL, null=True, blank=True,
                                    verbose_name="المديرية التابعة لها (اختياري)",
                                    help_text="عند اختيار هذه المدينة تُختار المديرية تلقائياً (يمكن للمدرسة تغييرها).")
    order = models.PositiveSmallIntegerField(default=0, verbose_name="الترتيب")

    class Meta:
        verbose_name = "لواء / مدينة"
        verbose_name_plural = "الألوية والمدن"
        ordering = ['governorate__order', 'order', 'name']

    def __str__(self):
        return self.name


ROLE_CHOICES = (('school', 'مدرسة'), ('judge', 'محكّم'), ('manager', 'إداري الجائزة'))


class Profile(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='profile', verbose_name="المستخدم")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='school', verbose_name="النوع")
    school_name = models.CharField(max_length=255, blank=True, default='', verbose_name="اسم المدرسة")
    contact_person = models.CharField(max_length=255, blank=True, default='', verbose_name="الاسم / ضابط الارتباط")
    phone = models.CharField(max_length=30, blank=True, default='', verbose_name="الهاتف")
    city = models.CharField(max_length=100, blank=True, default='', verbose_name="المدينة / المنطقة (نص)")
    governorate = models.ForeignKey(Governorate, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="المحافظة")
    area = models.ForeignKey(Area, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="اللواء / المدينة")
    directorate = models.ForeignKey(Directorate, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="مديرية التربية")
    specialty = models.CharField(max_length=255, blank=True, default='', verbose_name="التخصص (للمحكّم)")
    judge_fields = models.ManyToManyField(Field, blank=True, verbose_name="مجالات التحكيم",
                                          help_text="التوزيع التلقائي يُسند للمحكّم طلبات هذه المجالات فقط (فارغ = كل المجالات).")
    email_notifications = models.BooleanField(default=True, verbose_name="استلام الإشعارات بالبريد")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ التسجيل")

    class Meta:
        verbose_name = "حساب"
        verbose_name_plural = "حسابات المدارس والمحكّمين"
        ordering = ['-created_at']

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.school_name or self.contact_person or self.user.get_full_name() or self.user.email or self.user.username


class StatusLog(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='logs')
    old_status = models.CharField(max_length=20, blank=True, default='', verbose_name="من")
    new_status = models.CharField(max_length=20, verbose_name="إلى")
    note = models.TextField(blank=True, default='', verbose_name="ملاحظة")
    by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="بواسطة")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="التاريخ")

    class Meta:
        verbose_name = "سجل حالة"
        verbose_name_plural = "سجل الحالات"
        ordering = ['created_at', 'id']

    @property
    def old_label(self):
        return dict(STATUS_CHOICES).get(self.old_status, self.old_status or '—')

    @property
    def new_label(self):
        return dict(STATUS_CHOICES).get(self.new_status, self.new_status)


class Criterion(models.Model):
    cycle = models.ForeignKey(AwardCycle, on_delete=models.CASCADE, null=True, blank=True,
                              related_name='criteria', verbose_name="الدورة",
                              help_text="فارغ = يُستخدم في كل الدورات.")
    track = models.ForeignKey(Track, on_delete=models.CASCADE, null=True, blank=True, verbose_name="خاص بمسار",
                              help_text="فارغ = لكل المسارات.")
    name = models.CharField(max_length=255, verbose_name="المعيار")
    description = models.TextField(blank=True, default='', verbose_name="شرح للمحكّم")
    max_score = models.PositiveSmallIntegerField(default=10, verbose_name="الدرجة القصوى")
    weight = models.DecimalField(max_digits=4, decimal_places=2, default=1, verbose_name="الوزن",
                                 help_text="1 = عادي، 2 = ضعف الأهمية.")
    order = models.IntegerField(default=0, verbose_name="الترتيب")

    class Meta:
        verbose_name = "معيار تحكيم"
        verbose_name_plural = "معايير التحكيم"
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.name} (/{self.max_score})"

    @classmethod
    def for_submission(cls, sub):
        from django.db.models import Q
        qs = cls.objects.filter(Q(cycle__isnull=True) | Q(cycle_id=sub.cycle_id))
        return qs.filter(Q(track__isnull=True) | Q(track_id=sub.track_id))


RECOMMEND_CHOICES = (('', '—'), ('strong', 'أوصي بشدة'), ('yes', 'أوصي'), ('maybe', 'محايد'), ('no', 'لا أوصي'))


class Assignment(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='assignments', verbose_name="الطلب")
    judge = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='assignments', verbose_name="المحكّم")
    assigned_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإسناد")
    comment = models.TextField(blank=True, default='', verbose_name="ملاحظات المحكّم العامة")
    recommendation = models.CharField(max_length=10, blank=True, default='', choices=RECOMMEND_CHOICES, verbose_name="التوصية")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ إنهاء التقييم")

    class Meta:
        verbose_name = "إسناد تحكيم"
        verbose_name_plural = "إسناد الطلبات للمحكّمين"
        unique_together = ('submission', 'judge')
        ordering = ['-assigned_at']

    def __str__(self):
        return f"{self.submission.ref} ← {self.judge.get_full_name() or self.judge.email}"

    @property
    def is_done(self):
        return self.completed_at is not None

    @property
    def total(self):
        """الدرجة من 100 (مع الأوزان)"""
        num = den = 0
        for sc in self.scores.all():
            c = sc.criterion
            w = float(c.weight or 1)
            num += float(sc.value) / (c.max_score or 1) * w
            den += w
        return round(num / den * 100, 1) if den else 0


class Score(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='scores')
    criterion = models.ForeignKey(Criterion, on_delete=models.CASCADE, verbose_name="المعيار")
    value = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="الدرجة")
    note = models.CharField(max_length=500, blank=True, default='', verbose_name="ملاحظة")

    class Meta:
        verbose_name = "درجة"
        verbose_name_plural = "الدرجات"
        unique_together = ('assignment', 'criterion')


class Notification(models.Model):
    LEVELS = (('info', 'معلومة'), ('success', 'نجاح'), ('warning', 'تنبيه'))
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='notifications', verbose_name="المستخدم")
    title = models.CharField(max_length=255, verbose_name="العنوان")
    body = models.TextField(blank=True, default='', verbose_name="النص")
    url = models.CharField(max_length=500, blank=True, default='', verbose_name="الرابط")
    level = models.CharField(max_length=10, choices=LEVELS, default='info')
    is_read = models.BooleanField(default=False, verbose_name="مقروء؟")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="التاريخ")

    class Meta:
        verbose_name = "إشعار"
        verbose_name_plural = "الإشعارات"
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class EmailLog(models.Model):
    STATUS = (('sent', 'أُرسل'), ('saved', 'محفوظ (البريد غير مضبوط)'), ('failed', 'فشل'))
    to = models.CharField(max_length=500, verbose_name="إلى")
    subject = models.CharField(max_length=255, verbose_name="الموضوع")
    status = models.CharField(max_length=10, choices=STATUS, verbose_name="الحالة")
    error = models.TextField(blank=True, default='', verbose_name="الخطأ")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="التاريخ")

    class Meta:
        verbose_name = "رسالة بريد"
        verbose_name_plural = "سجل رسائل البريد"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.subject} → {self.to}"


SOCIAL_PLATFORMS = (
    ('facebook', 'Facebook'), ('x', 'X (Twitter)'), ('instagram', 'Instagram'), ('youtube', 'YouTube'),
    ('linkedin', 'LinkedIn'), ('snapchat', 'Snapchat'), ('tiktok', 'TikTok'), ('whatsapp', 'WhatsApp'),
    ('telegram', 'Telegram'), ('threads', 'Threads'), ('website', 'موقع إلكتروني'), ('email', 'بريد إلكتروني'),
    ('other', 'أخرى'),
)
SOCIAL_ICONS = {
    'facebook': 'fab fa-facebook-f', 'x': 'fab fa-x-twitter', 'instagram': 'fab fa-instagram',
    'youtube': 'fab fa-youtube', 'linkedin': 'fab fa-linkedin-in', 'snapchat': 'fab fa-snapchat',
    'tiktok': 'fab fa-tiktok', 'whatsapp': 'fab fa-whatsapp', 'telegram': 'fab fa-telegram',
    'threads': 'fab fa-threads', 'website': 'fas fa-globe', 'email': 'fas fa-envelope', 'other': 'fas fa-link',
}


class SocialLink(models.Model):
    platform = models.CharField(max_length=20, choices=SOCIAL_PLATFORMS, verbose_name="المنصة")
    url = models.CharField(max_length=500, blank=True, default='', verbose_name="الرابط",
                           help_text="مثال: https://www.instagram.com/iajaward — للبريد اكتب العنوان فقط، وللواتساب الرقم الدولي (9627xxxxxxxx).")
    icon = models.CharField(max_length=60, blank=True, default='', verbose_name="أيقونة مخصصة (اختياري)",
                            help_text="اتركها فارغة لاستخدام أيقونة المنصة. مثال: fab fa-facebook-f")
    color = models.CharField(max_length=7, blank=True, default='', verbose_name="لون الأيقونة (اختياري)",
                             help_text="فارغ = لون الموقع الأساسي.")
    order = models.PositiveSmallIntegerField(default=0, verbose_name="الترتيب")
    is_active = models.BooleanField(default=True, verbose_name="ظاهر؟")

    class Meta:
        verbose_name = "رابط تواصل اجتماعي"
        verbose_name_plural = "روابط التواصل الاجتماعي"
        ordering = ['order', 'id']

    def __str__(self):
        return self.get_platform_display()

    def save(self, *a, **kw):
        super().save(*a, **kw)
        from django.core.cache import cache
        cache.delete('iaj_social')

    def delete(self, *a, **kw):
        from django.core.cache import cache
        cache.delete('iaj_social')
        return super().delete(*a, **kw)

    @property
    def icon_class(self):
        return self.icon or SOCIAL_ICONS.get(self.platform, 'fas fa-link')

    @property
    def href(self):
        u = (self.url or '').strip()
        if self.platform == 'email' and u and not u.startswith('mailto:'):
            return 'mailto:' + u
        if self.platform == 'whatsapp' and u and not u.startswith('http'):
            return 'https://wa.me/' + ''.join(c for c in u if c.isdigit())
        if u and not u.startswith(('http://', 'https://', 'mailto:', 'tel:')):
            return 'https://' + u
        return u


class PortalSetting(models.Model):
    """إعدادات أزرار الدخول وبطاقة الدورة وشريط التواصل الاجتماعي ونصوص صفحات الحساب"""
    show_login_btn = models.BooleanField(default=True, verbose_name="إظهار زر «دخول» في الهيدر")
    login_btn_text = models.CharField(max_length=40, default='دخول', verbose_name="نص زر الدخول")
    account_btn_text = models.CharField(max_length=40, default='حسابي', verbose_name="نص الزر بعد الدخول")
    show_register_btn = models.BooleanField(default=True, verbose_name="إظهار زر «سجل الآن» في الهيدر")
    social_in_footer = models.BooleanField(default=True, verbose_name="شريط التواصل في الفوتر")
    social_in_menu = models.BooleanField(default=True, verbose_name="شريط التواصل في قائمة الموبايل")
    social_title = models.CharField(max_length=100, blank=True, default='تابعونا', verbose_name="عنوان شريط التواصل (اختياري)")
    login_intro = models.CharField(max_length=300, default='لحسابات المدارس والمحكّمين.', verbose_name="نص صفحة الدخول")
    signup_title = models.CharField(max_length=100, default='حساب مدرسة جديد', verbose_name="عنوان صفحة التسجيل")
    signup_intro = models.CharField(max_length=500, default='أنشئوا حساباً مرة واحدة، ثم قدّموا مشاريعكم وتابعوا حالتها من مكان واحد.',
                                    verbose_name="نص صفحة التسجيل")
    submit_intro = models.TextField(blank=True, default='', verbose_name="تعليمات أعلى نموذج تقديم المشروع (اختياري)",
                                    help_text="مثال: شروط الملف، عدد الصفحات، آخر موعد…")
    show_spam_hint = models.BooleanField(default=True, verbose_name="تنبيه المدارس لتفقّد مجلد Spam")
    countdown_badge = models.CharField(max_length=40, default='التسجيل مفتوح', verbose_name="نص زر العداد قبل الحساب",
                                       help_text="يظهر لحظة تحميل الصفحة ثم يتحول إلى «باقي … يوماً».")
    wm_enabled = models.BooleanField(default=True, verbose_name="إظهار شعار الجائزة على الصور والفيديو")
    wm_position = models.CharField(max_length=10, default='right', choices=(('right', 'أعلى اليمين'), ('left', 'أعلى اليسار')),
                                   verbose_name="مكان الشعار")
    wm_size = models.PositiveSmallIntegerField(default=46, verbose_name="حجم الشعار (بكسل)")
    wm_opacity = models.DecimalField(max_digits=3, decimal_places=2, default=0.95, verbose_name="شفافية الشعار (0–1)")
    captions_enabled = models.BooleanField(default=True, verbose_name="إظهار نص الشرح بجانب الشعار (الصور والفيديو)")
    show_cycle_filter = models.BooleanField(default=True, verbose_name="تصفية الصور والفيديو والأخبار حسب الدورة في الموقع")
    show_hero_stats = models.BooleanField(default=True, verbose_name="إظهار أرقام الجائزة أعلى الصفحة الرئيسية (الكمبيوتر)",
                                          help_text="المدارس المسجّلة، المشاريع، المجالات، المسارات — الرقم صفر لا يظهر.")

    class Meta:
        verbose_name = "إعدادات الحسابات والهيدر والتواصل"
        verbose_name_plural = "إعدادات الحسابات والهيدر والتواصل"

    def __str__(self):
        return "إعدادات الحسابات والهيدر والتواصل"

    @classmethod
    def get(cls):
        from django.core.cache import cache
        obj = cache.get('iaj_portal_setting')
        if obj is None:
            obj = cls.objects.first() or cls.objects.create()
            cache.set('iaj_portal_setting', obj, 300)
        return obj

    def save(self, *a, **kw):
        super().save(*a, **kw)
        from django.core.cache import cache
        cache.delete('iaj_portal_setting')


# ========================================= #
#   ملفات إضافية، مراسلات، لجان، إعلانات     #
# ========================================= #

FILE_KINDS = (('image', 'صورة'), ('video', 'فيديو'), ('audio', 'صوت'), ('doc', 'مستند'), ('archive', 'ملف مضغوط'), ('other', 'أخرى'))
_KIND_BY_EXT = {
    'image': {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif', '.bmp', '.tif', '.tiff', '.svg', '.avif'},
    'video': {'.mp4', '.mov', '.m4v', '.avi', '.mkv', '.webm', '.wmv', '.3gp', '.mpeg', '.mpg'},
    'audio': {'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.wma', '.amr'},
    'doc': {'.pdf', '.doc', '.docx', '.odt', '.rtf', '.txt', '.ppt', '.pptx', '.odp', '.pps', '.ppsx', '.xls', '.xlsx', '.ods', '.csv', '.key', '.pages', '.numbers'},
    'archive': {'.zip', '.rar', '.7z', '.tar', '.gz', '.tgz', '.bz2'},
}
ALLOWED_UPLOAD_EXTS = set().union(*_KIND_BY_EXT.values())


def file_kind(name):
    import os
    ext = os.path.splitext(name or '')[1].lower()
    for k, exts in _KIND_BY_EXT.items():
        if ext in exts:
            return k
    return 'other'


def extra_upload(instance, filename):
    import os
    base, ext = os.path.splitext(os.path.basename(filename))
    ref = instance.submission.ref if instance.submission_id else 'new'
    return f'private/submissions/{ref}/extra/{base[:60]}{ext.lower()}'


class SubmissionFile(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='files', verbose_name="الطلب")
    file = models.FileField(max_length=500, upload_to=extra_upload, verbose_name="الملف")
    title = models.CharField(max_length=200, blank=True, default='', verbose_name="وصف الملف")
    kind = models.CharField(max_length=10, choices=FILE_KINDS, default='other', verbose_name="النوع")
    size = models.PositiveBigIntegerField(default=0, verbose_name="الحجم")
    uploaded_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="رفعه")
    after_submit = models.BooleanField(default=False, verbose_name="أُضيف بعد الإرسال؟")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="التاريخ")

    class Meta:
        verbose_name = "ملف مرفق"
        verbose_name_plural = "ملفات الطلبات المرفقة"
        ordering = ['created_at', 'id']

    def __str__(self):
        return self.title or self.filename

    @property
    def filename(self):
        import os
        return os.path.basename(self.file.name or '')

    @property
    def size_label(self):
        n = self.size or 0
        return f"{n / 1048576:.1f} MB" if n >= 1048576 else f"{max(1, n // 1024)} KB"

    @property
    def icon(self):
        return {'image': 'fa-file-image', 'video': 'fa-file-video', 'audio': 'fa-file-audio', 'doc': 'fa-file-lines',
                'archive': 'fa-file-zipper'}.get(self.kind, 'fa-file')

    def save(self, *a, **kw):
        if self.file and not self.size:
            try:
                self.size = self.file.size
            except Exception:
                pass
        if self.file:
            self.kind = file_kind(self.file.name)
        super().save(*a, **kw)


def message_upload(instance, filename):
    import os
    base, ext = os.path.splitext(os.path.basename(filename))
    ref = instance.submission.ref if instance.submission_id else 'new'
    return f'private/submissions/{ref}/messages/{base[:60]}{ext.lower()}'


class SubmissionMessage(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='messages', verbose_name="الطلب")
    sender = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, verbose_name="المرسل")
    from_staff = models.BooleanField(default=False, verbose_name="من إدارة الجائزة؟")
    body = models.TextField(verbose_name="الرسالة")
    attachment = models.FileField(max_length=500, upload_to=message_upload, blank=True, verbose_name="مرفق")
    is_read = models.BooleanField(default=False, verbose_name="مقروءة؟")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="التاريخ")

    class Meta:
        verbose_name = "رسالة على طلب"
        verbose_name_plural = "مراسلات الطلبات"
        ordering = ['created_at', 'id']

    def __str__(self):
        return self.body[:60]


class JudgingCommittee(models.Model):
    name = models.CharField(max_length=200, verbose_name="اسم اللجنة")
    cycle = _cycle_fk()
    fields = models.ManyToManyField(Field, blank=True, verbose_name="المجالات", help_text="فارغ = كل المجالات.")
    tracks = models.ManyToManyField(Track, blank=True, verbose_name="المسارات (اختياري)")
    members = models.ManyToManyField('auth.User', blank=True, related_name='committees', verbose_name="الأعضاء (المحكّمون)",
                                     limit_choices_to={'profile__role': 'judge'})
    chair = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='chaired_committees',
                              verbose_name="رئيس اللجنة", limit_choices_to={'profile__role': 'judge'})
    notes = models.TextField(blank=True, default='', verbose_name="ملاحظات")

    class Meta:
        verbose_name = "لجنة تحكيم"
        verbose_name_plural = "لجان التحكيم"
        ordering = ['name']

    def __str__(self):
        return self.name

    def covers(self, sub):
        if self.tracks.exists():
            return self.tracks.filter(pk=sub.track_id).exists()
        if self.fields.exists():
            return self.fields.filter(pk=sub.field_id).exists()
        return True


ANN_TYPES = (('text', 'بطاقة نصية'), ('media', 'بطاقة وسائط (صور/فيديو)'))


class Announcement(models.Model):
    title = models.CharField(max_length=250, verbose_name="العنوان")
    kind = models.CharField(max_length=10, choices=ANN_TYPES, default='text', verbose_name="نوع البطاقة")
    body = models.TextField(blank=True, default='', verbose_name="النص")
    link_url = models.CharField(max_length=500, blank=True, default='', verbose_name="رابط زر (اختياري)")
    link_text = models.CharField(max_length=60, blank=True, default='', verbose_name="نص الزر")
    cycle = _cycle_fk()
    show_on_home = models.BooleanField(default=True, verbose_name="تظهر في الصفحة الرئيسية؟")
    is_published = models.BooleanField(default=True, verbose_name="منشور؟")
    pinned = models.BooleanField(default=False, verbose_name="مثبّت أولاً؟")
    publish_date = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ النشر", help_text="فارغ = تاريخ الإنشاء.")
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="بواسطة")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "إعلان"
        verbose_name_plural = "الإعلانات (بطاقات نصية ووسائط)"
        ordering = ['-pinned', '-publish_date', '-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return f'/announcements/{self.pk}/'

    @property
    def date(self):
        return self.publish_date or self.created_at


class AnnouncementMedia(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='media', verbose_name="الإعلان")
    file = models.FileField(max_length=500, upload_to='announcements/', blank=True, verbose_name="صورة أو فيديو")
    youtube_url = models.CharField(max_length=300, blank=True, default='', verbose_name="أو رابط يوتيوب")
    caption = models.CharField(max_length=200, blank=True, default='', verbose_name="نص الشرح")
    order = models.PositiveSmallIntegerField(default=0, verbose_name="الترتيب")

    class Meta:
        verbose_name = "وسائط الإعلان"
        verbose_name_plural = "وسائط الإعلان"
        ordering = ['order', 'id']

    @property
    def kind(self):
        if self.youtube_url:
            return 'youtube'
        return 'video' if file_kind(self.file.name) == 'video' else 'image'

    @property
    def yt(self):
        return youtube_id(self.youtube_url)
