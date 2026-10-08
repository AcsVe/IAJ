from django.http import Http404, HttpResponse, HttpResponseNotModified
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET

from .models import (
    Field, SiteSetting, HeroSlide, TimelineEvent, Judge, Submission,
    ThemeSetting, HomeContent, FooterContent, SuccessPageContent,
    SectionBackground, Sponsor, SlideshowCard, News, Video, SuccessStory,
    HeroCard, Winner, WinnerCategory, Photo, StoredFile,
)
from .site_cache import get_site_bundle, clear_site_bundle, get_home_bundle


# دالة مساعدة لجلب أو إنشاء البيانات بدون تكرار
def get_or_none(model):
    obj = model.objects.first()
    if not obj:
        obj = model.objects.create()
    return obj


def _site_objects():
    """الإعدادات العامة (من الذاكرة المؤقتة) — تُنشأ تلقائياً أول مرة لو مش موجودة"""
    b = get_site_bundle()
    if not all(b[k] for k in ('settings', 'theme', 'content', 'footer', 'hero_card')):
        for m in (SiteSetting, ThemeSetting, HomeContent, FooterContent, HeroCard):
            get_or_none(m)
        clear_site_bundle()
        b = get_site_bundle()
    return {k: b[k] for k in ('settings', 'theme', 'content', 'footer')}


def home(request):
    site = _site_objects()
    b = get_site_bundle()

    context = {
        **site,
        **get_home_bundle(),
        'hero_card': b['hero_card'],
        'hero_text_items': b['hero_text_items'],
        'section_bgs': b['section_bgs'],
    }
    return render(request, 'award/home.html', context)


def submit_project(request):
    """«سجّل الآن» — يمر عبر حساب المدرسة"""
    from .portal_views import submit_entry
    return submit_entry(request)


def _cycle_filter(request, qs):
    """تصفية حسب الدورة (?cycle=ID) + أعداد كل دورة لأزرار التصفية"""
    from django.db.models import Count
    from .models import AwardCycle
    counts = dict(qs.order_by().values('cycle').annotate(n=Count('pk')).values_list('cycle', 'n'))
    cycles = [{'c': c, 'n': counts.get(c.pk, 0)} for c in AwardCycle.objects.all() if counts.get(c.pk)]
    sel = request.GET.get('cycle', '')
    if sel.isdigit():
        qs = qs.filter(Q(cycle_id=int(sel)) | Q(cycle__isnull=True))
    ctx = {'cycle_tabs': cycles, 'cycle_sel': sel, 'cycle_total': sum(counts.values()),
           'cycle_general': counts.get(None, 0)}
    return qs, ctx


def news_list(request):
    """صفحة قائمة الأخبار"""
    all_news, cctx = _cycle_filter(request, News.objects.filter(is_published=True).order_by('-date'))
    return render(request, 'award/news_list.html', {
        'news_list': all_news,
        'all_news': all_news,
        **cctx,
    })


def news_detail(request, pk):
    """صفحة تفاصيل الخبر"""
    article = get_object_or_404(News, pk=pk, is_published=True)
    return render(request, 'award/news_detail.html', {
        'article': article,
        'news': article,
    })


def photos_page(request):
    """صفحة الصور (موديل Photo — فيه is_active و created_at)"""
    photos, cctx = _cycle_filter(request, Photo.objects.filter(is_active=True).order_by('-created_at'))
    return render(request, 'award/photos.html', {'photos': photos, **cctx})


def videos_page(request):
    """مكتبة الفيديو"""
    videos, cctx = _cycle_filter(request, Video.objects.filter(is_active=True).order_by('order'))
    return render(request, 'award/videos.html', {'videos': videos, **cctx})


def success_stories_page(request):
    """قصص النجاح"""
    stories, cctx = _cycle_filter(request, SuccessStory.objects.filter(is_active=True).order_by('-date'))
    return render(request, 'award/success_stories.html', {'stories': stories, **cctx})


def winners_page(request):
    """صفحة الفائزون"""
    categories = WinnerCategory.objects.filter(is_active=True).prefetch_related('winners')
    winners, cctx = _cycle_filter(request, Winner.objects.filter(is_active=True).select_related('category'))
    years = winners.values_list('year', flat=True).distinct().order_by('-year')
    return render(request, 'award/winners.html', {
        'categories': categories,
        'winners': winners,
        'years': years,
        **cctx,
    })


def cycles_archive(request):
    """الدورات السابقة: كل دورة مع أعداد الطلبات والفائزين والصور والفيديو"""
    from django.db.models import Count
    from .models import AwardCycle
    cycles = AwardCycle.objects.annotate(
        n_subs=Count('submissions', filter=~Q(submissions__status__in=('draft', 'withdrawn')), distinct=True),
        n_winners=Count('winner', filter=Q(winner__is_active=True), distinct=True),
        n_photos=Count('photo', filter=Q(photo__is_active=True), distinct=True),
        n_videos=Count('video', filter=Q(video__is_active=True), distinct=True),
        n_news=Count('news', filter=Q(news__is_published=True), distinct=True),
    ).order_by('-year', '-opens_at')
    return render(request, 'award/cycles.html', {'cycles': cycles})


def cycle_detail(request, pk):
    from .models import AwardCycle
    c = get_object_or_404(AwardCycle, pk=pk)
    return render(request, 'award/cycle_detail.html', {
        'cycle': c,
        'winners': Winner.objects.filter(is_active=True, cycle=c).select_related('category').order_by('rank'),
        'photos': Photo.objects.filter(is_active=True, cycle=c).order_by('-created_at')[:24],
        'videos': Video.objects.filter(is_active=True, cycle=c).order_by('order')[:12],
        'news': News.objects.filter(is_published=True, cycle=c).order_by('-date')[:6],
        'timeline': c.timelineevent_set.all() if hasattr(c, 'timelineevent_set') else [],
        'n_subs': c.submissions.exclude(status__in=('draft', 'withdrawn')).count(),
    })


def statistics_page(request):
    """صفحة الإحصائيات"""
    return render(request, 'award/statistics.html', {
        'total_submissions': Submission.objects.exclude(status__in=('draft', 'withdrawn')).count(),
        'accepted_submissions': Submission.objects.filter(status__in=('accepted', 'winner')).filter(
            Q(cycle__isnull=True) | Q(cycle__results_published=True)).count(),
    })


# ====================================================
#   عرض الصور المخزّنة في قاعدة البيانات
# ====================================================
@require_GET
def serve_db_media(request, name):
    from django.core.cache import cache
    full_name = 'db/' + name
    ckey = 'iaj:file:' + full_name
    hit = cache.get(ckey)
    if hit is None:
        row = (StoredFile.objects
               .filter(name__in=[full_name, full_name.replace('/', '\\'), 'db/' + name.replace('/', '\\')])
               .values_list('pk', 'size', 'content_type', 'content').first())
        if not row:
            raise Http404("الملف غير موجود")
        hit = (row[0], row[1], row[2] or 'application/octet-stream', bytes(row[3]))
        if len(hit[3]) <= 3 * 1024 * 1024:   # الصور حتى 3MB تبقى بالذاكرة
            cache.set(ckey, hit, 24 * 3600)
    pk, size, ctype, data = hit

    etag = f'"sf-{pk}-{size}"'
    cache_hdr = 'public, max-age=31536000, immutable'
    if request.META.get('HTTP_IF_NONE_MATCH') == etag:
        resp = HttpResponseNotModified()
        resp['ETag'] = etag
        resp['Cache-Control'] = cache_hdr
        return resp
    resp = HttpResponse(data, content_type=ctype)
    resp['Content-Length'] = str(len(data))
    resp['ETag'] = etag
    resp['Cache-Control'] = cache_hdr
    resp['X-Content-Type-Options'] = 'nosniff'
    if ctype.startswith('image/svg'):
        resp['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    return resp


# ====================================================
#   عرض الملفات المرفوعة من مجلد media (صور، فيديو، PDF)
#   يدعم Range حتى يعمل تقديم/تأخير الفيديو في كل المتصفحات
# ====================================================
import mimetypes as _mimetypes
import os as _os
import re as _re

from django.conf import settings as _settings
from django.http import FileResponse, HttpResponse as _HttpResponse
from django.utils.http import http_date as _http_date

_RANGE_RE = _re.compile(r'bytes=(\d*)-(\d*)')


class _RangeFile:
    """يقرأ جزءاً محدداً من الملف على دفعات"""
    def __init__(self, f, start, length, block=64 * 1024):
        self.f, self.remaining, self.block = f, length, block
        f.seek(start)

    def __iter__(self):
        while self.remaining > 0:
            chunk = self.f.read(min(self.block, self.remaining))
            if not chunk:
                break
            self.remaining -= len(chunk)
            yield chunk

    def close(self):
        self.f.close()


@require_GET
def serve_media(request, path):
    root = _os.path.realpath(_settings.MEDIA_ROOT)
    full = _os.path.realpath(_os.path.join(root, path))
    if not full.startswith(root + _os.sep) or not _os.path.isfile(full):
        raise Http404("الملف غير موجود")
    # ملفات الطلبات خاصة: الإدارة + المدرسة صاحبة الطلب + المحكّم المُسند إليه فقط
    rel = _os.path.relpath(full, root).replace(_os.sep, '/')
    private = rel.startswith('private/') or rel.startswith('submissions/')
    if private:
        from .portal_views import can_view_private_file
        if not can_view_private_file(request.user, rel):
            raise Http404("الملف غير موجود")

    st = _os.stat(full)
    size = st.st_size
    ctype = _mimetypes.guess_type(full)[0]
    if not ctype:   # ملف بلا امتداد — نعرف نوعه من محتواه
        from .storage import sniff_ext
        with open(full, 'rb') as fh:
            ext = sniff_ext(fh.read(64))
        ctype = _mimetypes.guess_type('x' + ext)[0] if ext else None
        ctype = ctype or ('image/svg+xml' if ext == '.svg' else 'application/octet-stream')
    etag = f'"m-{int(st.st_mtime)}-{size}"'
    headers = {
        'ETag': etag,
        'Last-Modified': _http_date(st.st_mtime),
        'Cache-Control': 'private, no-store' if private else 'public, max-age=2592000',
        'Accept-Ranges': 'bytes',
        'X-Content-Type-Options': 'nosniff',
    }
    if request.META.get('HTTP_IF_NONE_MATCH') == etag:
        resp = HttpResponseNotModified()
        for k, v in headers.items():
            resp[k] = v
        return resp

    m = _RANGE_RE.fullmatch(request.META.get('HTTP_RANGE', '').strip())
    if m and (m.group(1) or m.group(2)):
        if m.group(1):
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else size - 1
        else:                       # bytes=-500 → آخر 500 بايت
            start = max(0, size - int(m.group(2)))
            end = size - 1
        end = min(end, size - 1)
        if start >= size or start > end:
            resp = _HttpResponse(status=416)
            resp['Content-Range'] = f'bytes */{size}'
            return resp
        length = end - start + 1
        from django.http import StreamingHttpResponse
        resp = StreamingHttpResponse(_RangeFile(open(full, 'rb'), start, length),
                                     status=206, content_type=ctype)
        resp['Content-Length'] = str(length)
        resp['Content-Range'] = f'bytes {start}-{end}/{size}'
    else:
        resp = FileResponse(open(full, 'rb'), content_type=ctype)
        resp['Content-Length'] = str(size)
    for k, v in headers.items():
        resp[k] = v
    if ctype.startswith('image/svg'):
        resp['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    return resp


def favicon(request):
    """أيقونة المتصفح = شعار الموقع"""
    from django.http import HttpResponseRedirect
    from .site_cache import get_site_bundle
    st = get_site_bundle().get('settings')
    if st and st.site_logo:
        resp = HttpResponseRedirect(st.site_logo.url)
        resp['Cache-Control'] = 'public, max-age=86400'
        return resp
    return HttpResponse(status=204)


# ====================================================
#   البحث
# ====================================================
def search(request):
    from django.http import JsonResponse
    from .search import site_search
    q = (request.GET.get('q') or '').strip()[:100]
    results = site_search(q) if q else []
    if request.GET.get('ajax'):
        return JsonResponse({'q': q, 'results': results[:12], 'total': len(results)})
    groups = {}
    for r in results:
        groups.setdefault(r['group'], []).append(r)
    return render(request, 'award/search.html', {'q': q, 'groups': groups, 'total': len(results)})


def admin_global_search(request):
    from django.contrib import admin as dj_admin
    from django.contrib.admin.views.decorators import staff_member_required
    from .search import admin_search

    @staff_member_required
    def _view(request):
        q = (request.GET.get('q') or '').strip()[:100]
        groups = admin_search(q, request) if q else []
        ctx = {**dj_admin.site.each_context(request), 'title': 'بحث في لوحة التحكم', 'q': q,
               'groups': groups, 'total': sum(g['total'] for g in groups)}
        return render(request, 'admin/iaj_search.html', ctx)
    return _view(request)


def track_detail(request, pk):
    """صفحة المسار: النبذة + جدول التفاصيل + الشرح التفصيلي + زر التقديم"""
    from .models import Track
    track = get_object_or_404(Track.objects.select_related('field').prefetch_related('details'), pk=pk, is_active=True)
    siblings = Track.objects.filter(field_id=track.field_id, is_active=True).exclude(pk=track.pk) if track.field_id else []
    return render(request, 'award/track_detail.html', {'track': track, 'siblings': siblings})
