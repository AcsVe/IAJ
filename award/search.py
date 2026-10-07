"""
البحث في الموقع ولوحة التحكم — يتعامل مع الكتابة العربية بمرونة:
  أ / إ / آ / ا  — ة / ه  — ى / ي  — التشكيل والتطويل لا تؤثر على النتيجة.
"""
import html
import re

from django.utils.html import strip_tags

_TASHKEEL = re.compile('[ؗ-ًؚ-ْٰـ]')
_VARIANTS = {
    'ا': '[اأإآٱ]', 'أ': '[اأإآٱ]', 'إ': '[اأإآٱ]', 'آ': '[اأإآٱ]', 'ٱ': '[اأإآٱ]',
    'ه': '[هة]', 'ة': '[هة]', 'ي': '[يى]', 'ى': '[يى]', 'و': '[وؤ]', 'ؤ': '[وؤ]',
}
_OPT_MARKS = '[ً-ْـ]*'   # تشكيل أو تطويل اختياري بين الحروف


def normalize(text):
    text = html.unescape(strip_tags(text or ''))
    text = _TASHKEEL.sub('', text)
    text = re.sub('[أإآٱ]', 'ا', text).replace('ة', 'ه').replace('ى', 'ي').replace('ؤ', 'و')
    return re.sub(r'\s+', ' ', text).strip().lower()


def words(q):
    return [w for w in normalize(q).split(' ') if len(w) >= 2][:6]


def word_pattern(word):
    """نمط regex يطابق الكلمة بكل أشكال كتابتها (يُستخدم في القاعدة وفي التظليل)"""
    parts = []
    for ch in word:
        parts.append(_VARIANTS.get(ch, re.escape(ch)))
    return _OPT_MARKS.join(parts)


def snippet(text, ws, size=170):
    """مقطع قصير حول أول كلمة مطابقة، مع تظليل الكلمات"""
    plain = re.sub(r'\s+', ' ', html.unescape(strip_tags(text or ''))).strip()
    start = 0
    for w in ws:
        m = re.search(word_pattern(w), plain, re.I)
        if m:
            start = max(0, m.start() - size // 3)
            break
    piece = plain[start:start + size]
    if start > 0:
        piece = '… ' + piece
    if start + size < len(plain):
        piece += ' …'
    out = html.escape(piece)
    for w in ws:
        out = re.sub('(' + word_pattern(w) + ')', r'<mark>\1</mark>', out, flags=re.I)
    return out


def _matches(ws, *texts):
    blob = normalize(' '.join(t or '' for t in texts))
    return all(w in blob for w in ws)


# =====================================================================
#   البحث في الموقع (للزوار)
# =====================================================================
def site_search(q, limit=60):
    from . import models as M
    ws = words(q)
    if not ws:
        return []
    results = []

    def add(group, icon, title, body, url, extra=''):
        if _matches(ws, title, body, extra):
            score = 2 if _matches(ws, title) else 1
            results.append({'group': group, 'icon': icon, 'title': title, 'url': url,
                            'snippet': snippet(body or extra or title, ws), 'score': score})

    for n in M.News.objects.filter(is_published=True):
        add('الأخبار', 'fa-newspaper', n.title, n.content, f'/news/{n.pk}/')
    for f in M.Field.objects.all():
        add('مجالات العمل التطوعي', 'fa-layer-group', f.name_ar, f.name_en, '/#fields')
    for t in M.Track.objects.filter(is_active=True).select_related('field').prefetch_related('details'):
        extra = ' '.join([t.field.name_ar if t.field else '', t.details_html or ''] +
                         [d.title + ' ' + d.content for d in t.details.all()])
        add('المسارات', 'fa-route', t.name_ar, t.description_ar or '', f'/tracks/{t.pk}/', extra)
    for p in M.Principle.objects.filter(is_active=True):
        add('مبادئ الجائزة', 'fa-hand-holding-heart', p.title, p.description, '/#about')
    hc = M.HomeContent.objects.first()
    if hc:
        add('عن الجائزة', 'fa-circle-info', hc.title_about or 'عن الجائزة', hc.about_text, '/#about')
        add('عن الجائزة', 'fa-eye', 'الرؤية', hc.vision_text, '/#about')
        add('عن الجائزة', 'fa-bullseye', 'الرسالة', hc.mission_text, '/#about')
        conds = ' • '.join(getattr(hc, f'condition_{i}', '') for i in range(1, 6))
        steps = ' • '.join(getattr(hc, f'step_{i}', '') for i in range(1, 6))
        add('طلب التقديم', 'fa-clipboard-list', 'شروط التقديم', conds, '/#apply')
        add('طلب التقديم', 'fa-stairs', 'خطوات التقديم', steps, '/#apply')
        prizes = ' • '.join(getattr(hc, f'prize_{i}_desc', '') for i in range(1, 4))
        add('الجوائز', 'fa-trophy', hc.title_prizes or 'قيمة الجوائز', prizes, '/#prizes')
    for e in M.TimelineEvent.objects.all():
        add('الجدول الزمني', 'fa-calendar-days', e.title, e.description, '/#timeline', e.date_text)
    for j in M.Judge.objects.all():
        add('لجنة التحكيم', 'fa-user-tie', j.name, j.description, '/#judges', j.title)
    for w in M.Winner.objects.filter(is_active=True):
        add('الفائزون', 'fa-medal', f'{w.school_name} — {w.project_title}', w.description or '', '/winners/', str(w.year))
    for s in M.SuccessStory.objects.filter(is_active=True):
        add('قصص النجاح', 'fa-star', s.title, s.content, '/success-stories/')
    for v in M.Video.objects.filter(is_active=True):
        add('مكتبة الفيديو', 'fa-video', v.title, v.description, '/videos/')
    for ph in M.Photo.objects.filter(is_active=True):
        add('معرض الصور', 'fa-image', ph.title, ph.description, '/photos/')

    results.sort(key=lambda r: -r['score'])
    return results[:limit]


# =====================================================================
#   البحث في لوحة التحكم (لكل الجداول)
# =====================================================================
def admin_search(q, request, per_model=8):
    from django.contrib import admin
    from django.db import models
    from django.db.models import Q
    from django.urls import NoReverseMatch, reverse

    ws = words(q)
    if not ws:
        return []
    try:   # نفس الأسماء العربية الواضحة المستخدمة في قائمة لوحة التحكم
        from .admin import ADMIN_SECTIONS
        labels = {name: label for _, items in ADMIN_SECTIONS for name, label in items}
    except Exception:
        labels = {}
    groups = []
    for model, ma in admin.site._registry.items():
        if not ma.has_view_permission(request):
            continue
        fields = [f for f in model._meta.concrete_fields
                  if isinstance(f, (models.CharField, models.TextField)) and not isinstance(f, models.FileField)]
        if not fields:
            continue
        cond = Q()
        for w in ws:
            pat = word_pattern(w)
            one = Q()
            for f in fields:
                one |= Q(**{f'{f.name}__iregex': pat})
            cond &= one
        try:
            qs = model._default_manager.filter(cond)
            if model.__name__ == 'StoredFile':
                qs = qs.defer('content')
            total = qs.count()
            objs = list(qs[:per_model])
        except Exception:
            continue
        if not total:
            continue
        info = (model._meta.app_label, model._meta.model_name)
        items = []
        for o in objs:
            try:
                url = reverse('admin:%s_%s_change' % info, args=[o.pk])
            except NoReverseMatch:
                url = ''
            body = ' '.join(str(getattr(o, f.name) or '') for f in fields)
            items.append({'title': str(o)[:120] or f'#{o.pk}', 'url': url, 'snippet': snippet(body, ws, 140)})
        try:
            list_url = reverse('admin:%s_%s_changelist' % info)
        except NoReverseMatch:
            list_url = ''
        groups.append({'name': labels.get(model.__name__, model._meta.verbose_name_plural), 'total': total, 'items': items,
                       'list_url': list_url})
    groups.sort(key=lambda g: -g['total'])
    return groups
