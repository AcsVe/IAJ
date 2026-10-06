from django.http import Http404, HttpResponse, HttpResponseNotModified
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET

from .models import (
    Field, SiteSetting, HeroSlide, TimelineEvent, Judge, Submission,
    ThemeSetting, HomeContent, FooterContent, SuccessPageContent,
    SectionBackground, Sponsor, SlideshowCard, News, Video, SuccessStory,
    HeroCard, Winner, WinnerCategory, Photo, StoredFile,
)
from .forms import SubmissionForm


# دالة مساعدة لجلب أو إنشاء البيانات بدون تكرار
def get_or_none(model):
    obj = model.objects.first()
    if not obj:
        obj = model.objects.create()
    return obj


def _site_objects():
    """الإعدادات العامة — تُنشأ تلقائياً أول مرة لو مش موجودة"""
    return {
        'settings': get_or_none(SiteSetting),
        'theme': get_or_none(ThemeSetting),
        'content': get_or_none(HomeContent),
        'footer': get_or_none(FooterContent),
    }


def home(request):
    section_bgs = {sb.section_id: sb for sb in SectionBackground.objects.all()}

    context = {
        **_site_objects(),
        'fields': Field.objects.prefetch_related('track_set'),
        'slides': HeroSlide.objects.filter(is_active=True),
        'timeline': TimelineEvent.objects.all(),
        'judges': Judge.objects.all(),
        'sponsors': Sponsor.objects.all(),
        'slideshow_cards': SlideshowCard.objects.filter(is_active=True),
        'hero_card': get_or_none(HeroCard),
        'section_bgs': section_bgs,
        'total_submissions': Submission.objects.count(),
        'accepted_submissions': Submission.objects.filter(status='accepted').count(),
        'latest_news': News.objects.filter(is_published=True)[:3],
    }
    return render(request, 'award/home.html', context)


def submit_project(request):
    ctx = _site_objects()
    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            ctx['success_content'] = get_or_none(SuccessPageContent)
            return render(request, 'award/success.html', ctx)
    else:
        form = SubmissionForm()
    ctx['form'] = form
    return render(request, 'award/submit.html', ctx)


def news_list(request):
    """صفحة قائمة الأخبار"""
    all_news = News.objects.filter(is_published=True).order_by('-date')
    return render(request, 'award/news_list.html', {
        'news_list': all_news,
        'all_news': all_news,
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
    photos = Photo.objects.filter(is_active=True).order_by('-created_at')
    return render(request, 'award/photos.html', {'photos': photos})


def videos_page(request):
    """مكتبة الفيديو"""
    videos = Video.objects.filter(is_active=True).order_by('order')
    return render(request, 'award/videos.html', {'videos': videos})


def success_stories_page(request):
    """قصص النجاح"""
    stories = SuccessStory.objects.filter(is_active=True).order_by('-date')
    return render(request, 'award/success_stories.html', {'stories': stories})


def winners_page(request):
    """صفحة الفائزون"""
    categories = WinnerCategory.objects.filter(is_active=True).prefetch_related('winners')
    winners = Winner.objects.filter(is_active=True).select_related('category')
    years = winners.values_list('year', flat=True).distinct().order_by('-year')
    return render(request, 'award/winners.html', {
        'categories': categories,
        'winners': winners,
        'years': years,
    })


def statistics_page(request):
    """صفحة الإحصائيات"""
    return render(request, 'award/statistics.html', {
        'total_submissions': Submission.objects.count(),
        'accepted_submissions': Submission.objects.filter(status='accepted').count(),
    })


# ====================================================
#   عرض الصور المخزّنة في قاعدة البيانات
# ====================================================
@require_GET
def serve_db_media(request, name):
    full_name = 'db/' + name
    meta = StoredFile.objects.filter(name=full_name).values('pk', 'size', 'content_type').first()
    if not meta:
        raise Http404("الملف غير موجود")

    etag = f'"sf-{meta["pk"]}-{meta["size"]}"'
    cache = 'public, max-age=31536000, immutable'
    if request.META.get('HTTP_IF_NONE_MATCH') == etag:
        resp = HttpResponseNotModified()
        resp['ETag'] = etag
        resp['Cache-Control'] = cache
        return resp

    data = StoredFile.objects.filter(pk=meta['pk']).values_list('content', flat=True).first()
    resp = HttpResponse(bytes(data), content_type=meta['content_type'] or 'application/octet-stream')
    resp['Content-Length'] = str(len(data))
    resp['ETag'] = etag
    resp['Cache-Control'] = cache
    resp['X-Content-Type-Options'] = 'nosniff'
    if (meta['content_type'] or '').startswith('image/svg'):
        resp['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    return resp
