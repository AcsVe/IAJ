"""الأدوار في موقع الجائزة — تعريف واحد يُستخدم في كل مكان.

  المدير التقني      = حساب Django «مدير كامل الصلاحيات» (superuser): السيرفر والتحديث والإعدادات التقنية والمستخدمين.
  محرر محتوى الموقع  = حساب «فريق عمل» (staff) ضمن مجموعة «محرر محتوى الموقع»: النصوص والصور والأخبار في لوحة Django.
  مدير الجائزة       = حساب بدور «إداري الجائزة» أو ضمن مجموعة «مدير الجائزة»: الطلبات والتحكيم والنتائج من لوحة /manage/.
  المحكّم / المدرسة  = حسابات من بوابة الموقع (دور في الملف الشخصي).
"""
from django.db.models import Q

GROUP_EDITOR = 'محرر محتوى الموقع'
GROUP_AWARD = 'مدير الجائزة'

ROLE_LABELS = {
    'tech': 'المدير التقني',
    'editor': 'محرر محتوى الموقع',
    'award': 'مدير الجائزة',
}

# أقسام لوحة Django: (العنوان، الدور المسؤول، [(اسم الجدول، الاسم الظاهر)])
ADMIN_SECTIONS = [
    ('١. الصفحة الرئيسية — أعلى الصفحة', 'editor', [
        ('HomeContent',       'نصوص الصفحة الرئيسية والنص المتحرك'),
        ('CreditsBlock',      'شارة الأفلام — الفقرات (عنوان + لون + حجم)'),
        ('SiteSetting',       'الشعار + مدة الشرائح + العداد'),
        ('SectionBackground', 'صورة أعلى الصفحة وخلفيات الأقسام'),
        ('HeroSlide',         'بطاقة الفيديو والصور — الشرائح'),
        ('HeroCard',          'بطاقة النصوص تحت الفيديو (الإظهار والتصميم)'),
        ('HeroTextSlide',     'النصوص المتبدّلة تحت الفيديو (الحركة لكل نص)'),
        ('TickerItem',        'شريط الأخبار — الرسائل'),
        ('TickerSetting',     'شريط الأخبار — السرعة والألوان'),
    ]),
    ('٢. أقسام الجائزة', 'editor', [
        ('Principle',      'مبادئ الجائزة (بطاقات «عن الجائزة»)'),
        ('Field',          'المجالات (البطاقات المقلوبة)'),
        ('Track',          'المسارات داخل كل مجال'),
        ('TrackDetail',    'تفاصيل المسارات'),
        ('TimelineEvent',  'الجدول الزمني'),
        ('Judge',          'لجنة التحكيم (التعريف في الموقع)'),
        ('Sponsor',        'الرعاة والشركاء'),
        ('WinnerCategory', 'فئات الفائزين'),
        ('Winner',         'الفائزون'),
    ]),
    ('٣. المركز الإعلامي', 'editor', [
        ('News',         'الأخبار'),
        ('Photo',        'معرض الصور'),
        ('Video',        'مكتبة الفيديو'),
        ('SuccessStory', 'قصص النجاح'),
        ('MediaGallery', 'ألبومات الوسائط'),
    ]),
    ('٤. الفوتر والتواصل', 'editor', [
        ('FooterContent', 'الفوتر (أسفل الصفحة)'),
        ('SocialLink',    'روابط التواصل الاجتماعي'),
    ]),
    ('٥. إدارة الجائزة: الدورات والطلبات والتحكيم', 'award', [
        ('AwardCycle',        'دورات الجائزة (مواعيد التسجيل ونشر النتائج)'),
        ('Submission',        'طلبات الترشح'),
        ('Profile',           'حسابات المدارس والمحكّمين'),
        ('Assignment',        'إسناد الطلبات للمحكّمين والتقييمات'),
        ('JudgingCommittee',  'لجان التحكيم'),
        ('SubmissionMessage', 'مراسلات الطلبات'),
        ('Announcement',      'الإعلانات (بطاقات نصية ووسائط)'),
        ('Criterion',         'معايير التحكيم'),
    ]),
    ('٦. التصميم والإعدادات التقنية', 'tech', [
        ('ThemeSetting',  'الألوان والخطوط و CSS مخصص'),
        ('PortalSetting', 'أزرار الهيدر ونصوص الحسابات والعلامة المائية'),
        ('Notification',  'الإشعارات المرسلة (سجل)'),
        ('EmailLog',      'سجل رسائل البريد'),
        ('Governorate',   'المحافظات (بيانات مرجعية)'),
        ('Directorate',   'مديريات التربية (بيانات مرجعية)'),
        ('Area',          'الألوية والمدن (بيانات مرجعية)'),
        ('StoredFile',    'الصور المخزّنة (للاطلاع)'),
    ]),
]

# جداول مرتبطة تُدار من داخل غيرها (نماذج فرعية) — تأخذ نفس الدور
EXTRA_MODELS = {
    'editor': ['AnnouncementMedia'],
    'award': ['SubmissionFile', 'Score', 'StatusLog', 'AnnouncementMedia', 'Winner', 'WinnerCategory'],
}


def section_models(role):
    names = [n for _t, r, items in ADMIN_SECTIONS if r == role for n, _l in items]
    return names + EXTRA_MODELS.get(role, [])


def role_of_model(object_name):
    for _t, r, items in ADMIN_SECTIONS:
        if any(n == object_name for n, _l in items):
            return r
    return 'tech'


def is_award_manager(user):
    """مدير الجائزة: المدير التقني، أو دور «إداري الجائزة»، أو عضو مجموعة «مدير الجائزة»"""
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    prof = getattr(user, 'profile', None)
    if prof and prof.role == 'manager':
        return True
    return user.groups.filter(name=GROUP_AWARD).exists()


def award_manager_users():
    from django.contrib.auth.models import User
    return User.objects.filter(Q(is_superuser=True) | Q(profile__role='manager') | Q(groups__name=GROUP_AWARD),
                               is_active=True).distinct()


def sync_role_groups(**kwargs):
    """إنشاء/تحديث مجموعتي الصلاحيات بعد كل migrate (المدير التقني لا يحتاج مجموعة: هو superuser)"""
    from django.apps import apps
    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType
    for gname, role in ((GROUP_EDITOR, 'editor'), (GROUP_AWARD, 'award')):
        group, _ = Group.objects.get_or_create(name=gname)
        perms = []
        for name in section_models(role):
            try:
                model = apps.get_model('award', name)
            except LookupError:
                continue
            ct = ContentType.objects.get_for_model(model)
            perms += list(Permission.objects.filter(content_type=ct))
        if role == 'editor':   # المحرر يرى الصور المخزّنة فقط
            try:
                ct = ContentType.objects.get_for_model(apps.get_model('award', 'StoredFile'))
                perms += list(Permission.objects.filter(content_type=ct, codename__startswith='view_'))
            except LookupError:
                pass
        group.permissions.set(perms)
