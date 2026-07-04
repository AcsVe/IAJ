from django.shortcuts import render, redirect, get_object_or_404
from .models import (
    Field, SiteSetting, HeroSlide, TimelineEvent, Judge, Submission,
    ThemeSetting, HomeContent, FooterContent, SuccessPageContent,
    SectionBackground, Sponsor, SlideshowCard, News, Video, SuccessStory,
    HeroCard
)
from .forms import SubmissionForm

# دالة مساعدة لجلب أو إنشاء البيانات بدون تكرار
def get_or_none(model):
    obj = model.objects.first()
    if not obj:
        obj = model.objects.create()
    return obj

def home(request):
    settings = get_or_none(SiteSetting)
    theme = get_or_none(ThemeSetting)
    content = get_or_none(HomeContent)
    footer = get_or_none(FooterContent)

    fields = Field.objects.all()
    slides = HeroSlide.objects.filter(is_active=True)
    timeline = TimelineEvent.objects.all()
    judges = Judge.objects.all()
    sponsors = Sponsor.objects.all()
    slideshow_cards = SlideshowCard.objects.filter(is_active=True)
    hero_card = get_or_none(HeroCard)

    # بناء قاموس خلفيات الأقسام
    section_bgs = {}
    for sb in SectionBackground.objects.all():
        section_bgs[sb.section_id] = sb

    total_submissions = Submission.objects.count()
    accepted_submissions = Submission.objects.filter(status='accepted').count()

    context = {
        'fields': fields,
        'settings': settings,
        'slides': slides,
        'timeline': timeline,
        'judges': judges,
        'sponsors': sponsors,
        'slideshow_cards': slideshow_cards,
        'hero_card': hero_card,
        'section_bgs': section_bgs,
        'total_submissions': total_submissions,
        'accepted_submissions': accepted_submissions,
        'theme': theme,      
        'content': content,  
        'footer': footer,  
        'latest_news': News.objects.filter(is_published=True)[:3],        
    }
    return render(request, 'award/home.html', context)


def submit_project(request):
    success_content = get_or_none(SuccessPageContent)
    content = get_or_none(HomeContent)
    settings = get_or_none(SiteSetting)
    theme = get_or_none(ThemeSetting)
    footer = get_or_none(FooterContent)
    
    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return render(request, 'award/success.html', {
                'success_content': success_content, 
                'content': content, 
                'settings': settings, 
                'theme': theme,
                'footer': footer
            })
    else:
        form = SubmissionForm()
    
    return render(request, 'award/submit.html', {
        'form': form, 
        'content': content, 
        'settings': settings, 
        'theme': theme,
        'footer': footer
    })

# ====================================================
# أضف هذه الـ Views في award/views.py
# تأكد من استيراد: News, Video, SuccessStory, MediaGallery
# ====================================================

def news_list(request):
    """صفحة قائمة الأخبار"""
    all_news = News.objects.filter(is_published=True).order_by('-date')
    return render(request, 'award/news_list.html', {
        'all_news': all_news,
    })

def news_detail(request, pk):
    """صفحة تفاصيل الخبر"""
    news = get_object_or_404(News, pk=pk, is_published=True)
    return render(request, 'award/news_detail.html', {
        'news': news,
    })

def photos_page(request):
    """صفحة الصور"""
    photos = MediaGallery.objects.filter(media_type='image', is_active=True).order_by('-created_at')
    return render(request, 'award/photos.html', {
        'photos': photos,
    })

def videos_page(request):
    """مكتبة الفيديو"""
    videos = Video.objects.filter(is_active=True).order_by('order')
    return render(request, 'award/videos.html', {
        'videos': videos,
    })

def success_stories_page(request):
    """قصص النجاح"""
    stories = SuccessStory.objects.filter(is_active=True).order_by('-date')
    return render(request, 'award/success_stories.html', {
        'stories': stories,
    })

def statistics_page(request):
    """صفحة الإحصائيات"""
    total_submissions = Submission.objects.count()
    accepted_submissions = Submission.objects.filter(status='accepted').count()
    return render(request, 'award/statistics.html', {
        'total_submissions': total_submissions,
        'accepted_submissions': accepted_submissions,
    })
