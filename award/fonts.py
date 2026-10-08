"""قائمة الخطوط العربية المتاحة في الموقع (Google Fonts).

كل خط يُحمَّل برابط مستقل — لو تعذّر تحميل خط واحد يبقى الباقي يعمل ويُستخدم Cairo بدلاً منه."""

# (الاسم في Google Fonts، الاسم الظاهر، الأوزان المطلوبة)
FONTS = [
    ('Cairo',               'Cairo — القاهرة (خط الموقع الأساسي)',           '300;400;600;700;900'),
    ('Noto Kufi Arabic',    'Noto Kufi Arabic — كوفي (عنوان الهيدر حالياً)',  '400;700;800;900'),
    ('Tajawal',             'Tajawal — تجوال',                                '400;500;700;800;900'),
    ('Almarai',             'Almarai — المراعي',                              '300;400;700;800'),
    ('IBM Plex Sans Arabic','IBM Plex Sans Arabic — آي بي إم',               '400;500;600;700'),
    ('Noto Sans Arabic',    'Noto Sans Arabic — نوتو سانس',                   '400;500;600;700;800'),
    ('Readex Pro',          'Readex Pro — ريدكس',                             '400;500;600;700'),
    ('Vazirmatn',           'Vazirmatn — وزير',                               '400;500;600;700;800'),
    ('Rubik',               'Rubik — روبيك',                                  '400;500;600;700;800'),
    ('Changa',              'Changa — تشانجا',                                '400;500;600;700;800'),
    ('Mada',                'Mada — مدى',                                     '400;500;600;700;900'),
    ('Kufam',               'Kufam — كوفام',                                  '400;500;600;700;800'),
    ('El Messiri',          'El Messiri — المسيري',                           '400;500;600;700'),
    ('Reem Kufi',           'Reem Kufi — ريم كوفي',                           '400;500;600;700'),
    ('Baloo Bhaijaan 2',    'Baloo Bhaijaan 2 — بالو (دائري ودود)',            '400;500;600;700;800'),
    ('Marhey',              'Marhey — مرحي (يدوي ودود)',                       '400;500;600;700'),
    ('Lalezar',             'Lalezar — لاله‌زار (عريض للعناوين فقط)',          '400'),
    ('Noto Naskh Arabic',   'Noto Naskh Arabic — نسخ',                         '400;500;600;700'),
    ('Amiri',               'Amiri — الأميري (نسخ كلاسيكي)',                   '400;700'),
    ('Scheherazade New',    'Scheherazade New — شهرزاد (نسخ)',                 '400;700'),
    ('Markazi Text',        'Markazi Text — مركزي (نسخ حديث)',                 '400;500;600;700'),
    ('Lateef',              'Lateef — لطيف (نسخ)',                             '400;700'),
    ('Harmattan',           'Harmattan — هرمتان',                              '400;700'),
    ('Aref Ruqaa',          'Aref Ruqaa — عارف رقعة (زخرفي)',                  '400;700'),
]
FONT_CHOICES = [(n, label) for n, label, _w in FONTS]
INHERIT_CHOICES = [('', '— نفس خط النص الأساسي —')] + FONT_CHOICES
_WEIGHTS = {n: w for n, _l, w in FONTS}


def font_url(name):
    if name not in _WEIGHTS:
        return ''
    return 'https://fonts.googleapis.com/css2?family=%s:wght@%s&display=swap' % (name.replace(' ', '+'), _WEIGHTS[name])


def all_font_urls():
    return [(n, font_url(n)) for n, _l, _w in FONTS]


# العناصر التي يمكن اختيار خط لكل منها: (اسم الحقل، المتغيّر في CSS، الاسم الظاهر، المحددات)
FONT_TARGETS = [
    ('font_body',      '--f-body',   'النص الأساسي لكل الموقع', None),
    ('font_headings',  '--f-head',   'عناوين الأقسام والصفحات', 'h1,h2,h3,h4,h5,h6,.section-header h2,.media-page-header h1'),
    ('font_site_title','--f-title',  'اسم الجائزة في الهيدر', '.nav-award-title'),
    ('font_nav',       '--f-nav',    'روابط القائمة الرئيسية', '.navbar-royal .nav-link,.navbar-royal .dropdown-item,.navbar-royal .nav-account,.navbar-royal .nav-register'),
    ('font_ticker',    '--f-ticker', 'شريط الأخبار المتحرك', '#tickerWrapper,#tickerWrapper *'),
    ('font_hero',      '--f-hero',   'نصوص أعلى الصفحة وبطاقة النصوص', '.hero-transparent-card,.hero-transparent-card h3,.hero-transparent-card p,.sc-heading,.sc-text'),
    ('font_cards',     '--f-cards',  'البطاقات (المجالات، الجوائز، الجدول الزمني)', '.flip-card,.flip-card *,.prize-box,.prize-box *,.timeline-title,.timeline-date,.tl-pop,.tl-pop *,.tl-sheet,.tl-sheet *'),
    ('font_buttons',   '--f-btn',    'الأزرار', '.btn,button,input[type=submit]'),
    ('font_numbers',   '--f-num',    'العداد التنازلي والأرقام', '.countdown-panel,.countdown-panel *,.countdown-toggle,.stat-number,.counter'),
    ('font_footer',    '--f-footer', 'الفوتر (أسفل الصفحة)', '#siteFooter,#siteFooter *'),
]
DEFAULTS = {'font_body': 'Cairo', 'font_site_title': 'Noto Kufi Arabic'}


_NOT_ICON = ':not(i):not(.fa):not(.fas):not(.far):not(.fab):not(.fa-solid):not(.fa-brands)'


def _expand(sel):
    """«X *» لا يجب أن يغيّر خط الأيقونات (Font Awesome)"""
    return ','.join(part.strip()[:-1] + '*' + _NOT_ICON if part.strip().endswith(' *') else part.strip()
                    for part in sel.split(','))


def theme_fonts(theme):
    """ما يحتاجه القالب: روابط الخطوط المختارة فقط + متغيرات CSS + القواعد"""
    picked = {}
    for field, var, _label, _sel in FONT_TARGETS:
        val = (getattr(theme, field, '') if theme else '') or DEFAULTS.get(field, '')
        picked[field] = val
    body = picked['font_body'] or 'Cairo'
    names = sorted({v for v in picked.values() if v})
    urls = [font_url(n) for n in names if font_url(n)]
    fallback = "'Cairo', Tahoma, 'Segoe UI', Arial, sans-serif"
    vars_css, rules = [], []
    for field, var, _label, sel in FONT_TARGETS:
        val = picked[field] or body
        vars_css.append(f"{var}: '{val}', {fallback};")
        if sel and picked[field]:
            rules.append(f"{_expand(sel)}{{font-family:var({var}) !important;}}")
    rules.insert(0, "body{font-family:var(--f-body) !important;}")
    return {'urls': urls, 'vars': ' '.join(vars_css), 'rules': '\n'.join(rules)}


# ===================== ألوان النصوص =====================
# (اسم الحقل، الاسم الظاهر، المحددات) — فارغ = اللون الأصلي في التصميم
COLOR_TARGETS = [
    ('color_body',         'النص العام في الصفحات', 'body,body p,body li'),
    ('color_headings',     'عناوين الأقسام (كل الأقسام)', '.section-header h2,.media-page-header h1'),
    ('color_site_title',   'اسم الجائزة في الهيدر', '.navbar-royal .nav-award-title'),
    ('color_nav',          'روابط القائمة الرئيسية', '.navbar-royal .nav-link,.navbar-royal .dropdown-item'),
    ('color_hero',         'النص المتحرك أعلى الصفحة (العنوان)', '.side-credits .sc-heading'),
    ('color_hero_text',    'النص المتحرك أعلى الصفحة (النص)', '.side-credits .sc-text'),
    ('color_tl_title',     'عناوين مراحل الجدول الزمني', 'section#timeline .timeline-title'),
    ('color_tl_date',      'تواريخ الجدول الزمني', 'section#timeline .timeline-date'),
    ('color_prize_title',  'عناوين بطاقات الجوائز', '.prize-box h4'),
    ('color_prize_text',   'نص بطاقات الجوائز', '.prize-box p'),
    ('color_buttons',      'نص الأزرار', '.btn,.nav-register'),
    ('color_numbers',      'أرقام العداد التنازلي', '.cd-box b,.countdown-toggle'),
    ('color_footer_title', 'عناوين الفوتر', '#siteFooter .footer-title'),
    ('color_footer_text',  'نصوص وروابط الفوتر', '#siteFooter p,#siteFooter .footer-links a,#siteFooter .ft-copy'),
    ('color_links',        'الروابط داخل النصوص', 'main a:not(.btn),.news-content a,.article-body a'),
]


def theme_colors(theme):
    rules = []
    for field, _label, sel in COLOR_TARGETS:
        val = (getattr(theme, field, '') or '').strip() if theme else ''
        if val and all(ch not in val for ch in ';{}<>'):
            rules.append(','.join('html ' + x.strip() for x in sel.split(',')) + '{color:' + val + ' !important;}')
    return '\n'.join(rules)
