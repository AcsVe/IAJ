from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from award import views, portal_views as pv, manage_views as mv
from award.portal_forms import SafePasswordResetForm

_reset = dict(
    template_name='award/portal/password_reset.html',
    form_class=SafePasswordResetForm,
    success_url='/accounts/password-reset/sent/',
)

urlpatterns = [
    path('admin/search/', views.admin_global_search, name='admin_global_search'),
    path('admin/', admin.site.urls),
    path('search/', views.search, name='search'),
    path('tracks/<int:pk>/', views.track_detail, name='track_detail'),
    path('', views.home, name='home'),
    path('favicon.ico', views.favicon),
    path('submit/', views.submit_project, name='submit_project'),

    # ---------- الحسابات ----------
    path('accounts/signup/', pv.signup, name='signup'),
    path('accounts/login/', pv.login_view, name='login'),
    path('accounts/logout/', pv.logout_view, name='logout'),
    path('accounts/activate/<uidb64>/<token>/', pv.activate, name='activate'),
    path('accounts/activate/resend/', pv.resend_activation, name='resend_activation'),
    path('accounts/password-reset/', auth_views.PasswordResetView.as_view(**_reset), name='password_reset'),
    path('accounts/password-reset/sent/', auth_views.PasswordResetDoneView.as_view(
        template_name='award/portal/password_reset_sent.html'), name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='award/portal/password_reset_confirm.html', success_url='/accounts/reset/done/'),
        name='password_reset_confirm'),
    path('accounts/reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='award/portal/password_reset_done.html'), name='password_reset_complete'),
    path('accounts/password/', auth_views.PasswordChangeView.as_view(
        template_name='award/portal/password_change.html', success_url='/accounts/password/done/',
        extra_context={'tab': 'password'}),
        name='password_change'),
    path('accounts/password/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='award/portal/password_change_done.html', extra_context={'tab': 'password'}), name='password_change_done'),

    # ---------- بوابة المدرسة ----------
    path('portal/', pv.portal_home, name='portal_home'),
    path('portal/profile/', pv.profile_edit, name='profile_edit'),
    path('portal/submissions/new/', pv.submission_new, name='submission_new'),
    path('portal/submissions/<int:pk>/', pv.submission_detail, name='submission_detail'),
    path('portal/submissions/<int:pk>/edit/', pv.submission_edit, name='submission_edit'),
    path('portal/submissions/<int:pk>/withdraw/', pv.submission_withdraw, name='submission_withdraw'),
    path('portal/submissions/<int:pk>/files/', pv.submission_add_files, name='submission_add_files'),
    path('portal/submissions/<int:pk>/message/', pv.submission_message, name='submission_message'),
    path('portal/notifications/', pv.notifications, name='notifications'),
    path('portal/notifications/<int:pk>/', pv.notification_go, name='notification_go'),

    # ---------- إدارة الجائزة ----------
    path('manage/', mv.dashboard, name='mg_dashboard'),
    path('manage/submissions/', mv.submissions, name='mg_submissions'),
    path('manage/submissions/<int:pk>/', mv.submission_detail, name='mg_submission'),
    path('manage/results/', mv.results, name='mg_results'),
    path('manage/judges/', mv.judges, name='mg_judges'),
    path('manage/committees/', mv.committees, name='mg_committees'),
    path('manage/committees/<int:pk>/', mv.committees, name='mg_committee'),
    path('manage/announcements/', mv.announcements, name='mg_announcements'),
    path('manage/announcements/<int:pk>/', mv.announcements, name='mg_announcement'),
    path('manage/schools/', mv.schools, name='mg_schools'),

    # ---------- المحكّمون ----------
    path('judge/', pv.judge_home, name='judge_home'),
    path('judge/<int:pk>/', pv.judge_review, name='judge_review'),

    path('news/', views.news_list, name='news_list'),
    path('news/<int:pk>/', views.news_detail, name='news_detail'),
    path('photos/', views.photos_page, name='photos_page'),
    path('videos/', views.videos_page, name='videos_page'),
    path('success-stories/', views.success_stories_page, name='success_stories_page'),
    path('statistics/', views.statistics_page, name='statistics_page'),
    path('winners/', views.winners_page, name='winners_page'),
    path('cycles/', views.cycles_archive, name='cycles_archive'),
    path('announcements/', views.announcements_page, name='announcements'),
    path('announcements/<int:pk>/', views.announcement_detail, name='announcement_detail'),
    path('cycles/<int:pk>/', views.cycle_detail, name='cycle_detail'),
    # الصور المخزّنة في قاعدة البيانات
    path('media/db/<path:name>', views.serve_db_media, name='db_media'),
    # الملفات المرفوعة على الجهاز (مجلد media)
    path('media/<path:path>', views.serve_media, name='media'),
]
