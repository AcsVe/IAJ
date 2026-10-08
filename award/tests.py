"""اختبار دورة التسجيل كاملة:  python manage.py test award"""
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import (AwardCycle, Assignment, Criterion, EmailLog, Field, Notification, Profile,
                     Submission, Track)
from . import workflow

TMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TMP_MEDIA, EMAIL_HOST='', EMAIL_ENABLED=False, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RegistrationFlowTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        # البريد في الاختبار متزامن
        import award.notify as n
        self._orig = n.threading.Thread
        class Sync:
            def __init__(self, target, args=(), daemon=None): self.t, self.a = target, args
            def start(self): self.t(*self.a)
        n.threading.Thread = Sync
        import django.db
        self._close = django.db.connection.close
        django.db.connection.close = lambda: None

        from django.core.cache import cache
        cache.clear()
        self.field = Field.objects.create(name_ar='العلوم', name_en='Science')
        self.track = Track.objects.create(field=self.field, name_ar='الطاقة', name_en='Energy')
        AwardCycle.objects.all().delete()
        self.cycle = AwardCycle.objects.create(name='الدورة الأولى', year=2026, is_current=True,
                                               opens_at=timezone.now() - timedelta(days=1),
                                               closes_at=timezone.now() + timedelta(days=30))
        self.admin = User.objects.create_superuser('admin', 'admin@x.org', 'Adm1n-pass!')

    def tearDown(self):
        import award.notify as n, django.db
        n.threading.Thread = self._orig
        django.db.connection.close = self._close

    def _pdf(self, name='research.pdf'):
        return SimpleUploadedFile(name, b'%PDF-1.4 test', content_type='application/pdf')

    def test_full_cycle(self):
        c = self.client
        # 1) زر «سجل الآن» يحوّل للتسجيل
        r = c.get(f'/submit/?field={self.field.pk}&track={self.track.pk}')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/signup/', r['Location'])

        # 2) إنشاء حساب مدرسة (بدون بريد مضبوط = تفعيل فوري)
        from .models import Governorate, Area, Directorate
        gov = Governorate.objects.get(name='إربد')
        other = Governorate.objects.get(name='العقبة')
        area = Area.objects.get(governorate=gov, name='الرمثا')
        base = {'school_name': 'مدرسة الأمل', 'contact_person': 'سارة أحمد', 'email': 'School@Example.com',
                'phone': '0790000000', 'password1': 'Strong-Pass-2026', 'password2': 'Strong-Pass-2026',
                'next': '/portal/submissions/new/'}
        r = c.post('/accounts/signup/', {**base, 'governorate': other.pk, 'area': area.pk, 'directorate': area.directorate_id})
        self.assertContains(r, 'لا يتبع المحافظة')
        r = c.post('/accounts/signup/', {**base, 'governorate': gov.pk, 'area': area.pk, 'directorate': area.directorate_id})
        self.assertEqual(r.status_code, 302, r.content.decode()[:2000])
        school = User.objects.get(email='school@example.com')
        self.assertTrue(school.is_active)
        self.assertEqual(school.profile.role, 'school')
        self.assertEqual(school.profile.directorate.name, 'لواء الرمثا')

        # 3) مسودة ثم إرسال بدون ملف ← خطأ
        data = {'field': self.field.pk, 'track': self.track.pk, 'project_title': 'ألواح شمسية للمدرسة',
                'abstract': 'ملخص', 'team_members': 'طالب 1\nطالب 2', 'supervisor': 'أ. خالد',
                'contact_person': 'سارة أحمد', 'phone': '0790000000'}
        r = c.post('/portal/submissions/new/', {**data, 'action': 'draft'})
        self.assertEqual(r.status_code, 302)
        sub = Submission.objects.get(owner=school)
        self.assertEqual(sub.status, 'draft')
        self.assertTrue(sub.ref.startswith('IAJ-2026-'))
        r = c.post(f'/portal/submissions/{sub.pk}/edit/', {**data, 'action': 'submit'})
        self.assertEqual(r.status_code, 200)   # ملف البحث مطلوب
        self.assertContains(r, 'مطلوب قبل الإرسال')

        # ملف غير PDF مرفوض
        r = c.post(f'/portal/submissions/{sub.pk}/edit/', {**data, 'action': 'submit',
                   'document': SimpleUploadedFile('x.exe', b'MZ')})
        self.assertContains(r, 'الصيغ المسموحة')

        r = c.post(f'/portal/submissions/{sub.pk}/edit/', {**data, 'action': 'submit', 'document': self._pdf()})
        self.assertEqual(r.status_code, 302)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'submitted')
        self.assertIsNotNone(sub.sent_at)
        self.assertTrue(sub.document.name.startswith('private/submissions/'))

        # إشعارات: المدرسة + الإدارة
        self.assertTrue(Notification.objects.filter(user=school, title__contains='تم استلام').exists())
        self.assertTrue(Notification.objects.filter(user=self.admin, title__contains='طلب جديد').exists())
        self.assertTrue(EmailLog.objects.filter(to__contains='school@example.com').exists())

        # 4) الملف خاص
        url = sub.document.url
        self.assertEqual(c.get(url).status_code, 200)
        other = self.client_class()
        self.assertEqual(other.get(url).status_code, 404)

        # لا يمكن التعديل بعد الإرسال
        r = c.get(f'/portal/submissions/{sub.pk}/edit/')
        self.assertEqual(r.status_code, 302)

        # 5) الإدارة تطلب تعديل
        workflow.change_status(sub, 'revision', by=self.admin, note='أضيفوا صور التنفيذ')
        sub.refresh_from_db()
        self.assertIsNotNone(sub.revision_deadline)
        r = c.get(f'/portal/submissions/{sub.pk}/')
        self.assertContains(r, 'أضيفوا صور التنفيذ')
        r = c.post(f'/portal/submissions/{sub.pk}/edit/', {**data, 'action': 'submit'})
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'submitted')
        self.assertTrue(Notification.objects.filter(user=self.admin, title__contains='تعديل على الطلب').exists())

        # 6) التحكيم
        judge = User.objects.create_user('j@x.org', 'j@x.org', 'Judge-pass-2026', first_name='د. علي')
        Profile.objects.create(user=judge, role='judge')
        Criterion.objects.all().delete()
        c1 = Criterion.objects.create(name='الابتكار', max_score=10)
        c2 = Criterion.objects.create(name='الأثر', max_score=20, weight=2)
        workflow.change_status(sub, 'judging', by=self.admin)
        self.assertEqual(workflow.auto_assign([sub], per_submission=1), 1)
        a = Assignment.objects.get(submission=sub)
        self.assertTrue(Notification.objects.filter(user=judge, title__contains='للتحكيم').exists())

        jc = self.client_class()
        jc.login(username='j@x.org', password='Judge-pass-2026')
        r = jc.get('/judge/')
        self.assertContains(r, sub.project_title)
        r = jc.get(f'/judge/{a.pk}/')
        self.assertNotContains(r, 'مدرسة الأمل')   # تحكيم بدون أسماء
        self.assertEqual(jc.get(url).status_code, 200)   # المحكّم يفتح الملف
        r = jc.post(f'/judge/{a.pk}/', {f'c{c1.pk}': '8', f'c{c2.pk}': '25', 'action': 'finish'})
        self.assertContains(r, 'يجب أن تكون بين')
        r = jc.post(f'/judge/{a.pk}/', {f'c{c1.pk}': '8', f'c{c2.pk}': '15', 'action': 'finish', 'recommendation': 'yes'})
        self.assertEqual(r.status_code, 302)
        a.refresh_from_db()
        self.assertTrue(a.is_done)
        # (8/10*1 + 15/20*2) / 3 * 100 = 76.7
        self.assertEqual(a.total, 76.7)
        self.assertEqual(sub.avg_score, 76.7)
        self.assertTrue(Notification.objects.filter(user=self.admin, title__contains='اكتمل تحكيم').exists())

        # 7) النتيجة مخفية حتى النشر
        n_before = Notification.objects.filter(user=school).count()
        workflow.change_status(sub, 'winner', by=self.admin)
        sub.refresh_from_db()
        self.assertTrue(sub.results_hidden)
        self.assertEqual(sub.public_status, 'judging')
        self.assertEqual(Notification.objects.filter(user=school).count(), n_before)
        r = c.get(f'/portal/submissions/{sub.pk}/')
        self.assertNotContains(r, 'pt-status st-winner')
        self.assertContains(r, 'pt-status st-judging')
        self.assertEqual(workflow.publish_results(self.cycle), 1)
        sub.refresh_from_db()
        self.assertFalse(sub.results_hidden)
        self.assertTrue(Notification.objects.filter(user=school, title__contains='مبارك').exists())

        # 8) الإشعارات والجرس
        r = c.get('/portal/notifications/')
        self.assertContains(r, 'مبارك')
        r = c.get('/')
        self.assertContains(r, 'nav-bell-n')

    def test_login_logout_and_admin_pages(self):
        u = User.objects.create_user('s@x.org', 's@x.org', 'Strong-Pass-2026')
        Profile.objects.create(user=u, school_name='مدرسة')
        r = self.client.post('/accounts/login/', {'email': 'S@X.org', 'password': 'Strong-Pass-2026'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get('/portal/').status_code, 200)
        self.client.post('/accounts/logout/')
        self.assertEqual(self.client.get('/portal/').status_code, 302)

        self.client.login(username='admin', password='Adm1n-pass!')
        for path in ('/admin/', '/admin/award/submission/', '/admin/award/awardcycle/', '/admin/award/profile/',
                     '/admin/award/profile/add/', '/admin/award/assignment/', '/admin/award/criterion/',
                     '/admin/award/notification/', '/admin/award/emaillog/', '/admin/award/governorate/', '/admin/award/sociallink/', f'/admin/award/portalsetting/{__import__("award.models").models.PortalSetting.get().pk}/change/', '/admin/award/governorate/1/change/', '/admin/award/directorate/', '/admin/award/area/', '/portal/profile/', f'/admin/award/awardcycle/{self.cycle.pk}/change/'):
            self.assertEqual(self.client.get(path).status_code, 200, path)

        # إضافة محكّم بدعوة
        r = self.client.post('/admin/award/profile/add/', {
            'role': 'judge', 'email': 'judge2@x.org', 'contact_person': 'د. منى', 'send_invite': 'on',
            'school_name': '', 'phone': '', 'city': '', 'specialty': 'فيزياء'})
        self.assertEqual(r.status_code, 302, r.content.decode()[-3000:])
        self.assertTrue(Profile.objects.filter(user__email='judge2@x.org', role='judge').exists())
        self.assertTrue(EmailLog.objects.filter(to='judge2@x.org').exists())

        # تغيير حالة بالجملة من لوحة التحكم
        s = Submission.objects.create(owner=u, cycle=self.cycle, school_name='مدرسة', contact_person='x',
                                      email='s@x.org', phone='1', project_title='مشروع', status='submitted')
        self.assertEqual(self.client.get(f'/admin/award/submission/{s.pk}/change/').status_code, 200)
        r = self.client.post('/admin/award/submission/', {'action': 'change_status_action', '_selected_action': [s.pk]})
        self.assertContains(r, 'الحالة الجديدة')
        r = self.client.post('/admin/award/submission/', {'action': 'change_status_action', '_selected_action': [s.pk],
                                                          'apply': '1', 'status': 'revision', 'note': 'ناقص',
                                                          'notify_school': 'on'})
        self.assertEqual(r.status_code, 302)
        s.refresh_from_db()
        self.assertEqual(s.status, 'revision')
        self.assertTrue(Notification.objects.filter(user=u, title__contains='مطلوب تعديل').exists())
        r = self.client.post('/admin/award/submission/', {'action': 'export_csv', '_selected_action': [s.pk]})
        self.assertIn('IAJ-', r.content.decode('utf-8'))

    def test_password_reset_and_closed_cycle(self):
        u = User.objects.create_user('s@x.org', 's@x.org', 'Strong-Pass-2026')
        Profile.objects.create(user=u, school_name='مدرسة')
        r = self.client.post('/accounts/password-reset/', {'email': 's@x.org'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(EmailLog.objects.filter(subject__contains='استعادة').exists())

        self.cycle.closes_at = timezone.now() - timedelta(hours=1)
        self.cycle.save()
        self.client.login(username='s@x.org', password='Strong-Pass-2026')
        r = self.client.get('/portal/submissions/new/')
        self.assertEqual(r.status_code, 302)
        r = self.client.get('/portal/')
        self.assertContains(r, 'انتهت فترة التسجيل')


class GraphBackendTest(TestCase):
    @override_settings(MS_TENANT_ID='t', MS_CLIENT_ID='c', MS_CLIENT_SECRET='s', MS_SENDER='info@iajaward.org')
    def test_graph_payload(self):
        from unittest import mock
        from django.core.mail import EmailMultiAlternatives
        from award import mail_graph
        mail_graph._token.update(value=None, exp=0)
        calls = []

        class R:
            def __init__(self, code, data=None): self.status_code, self._d, self.text = code, data or {}, ''
            def json(self): return self._d

        def fake_post(url, **kw):
            calls.append((url, kw))
            if 'login.microsoftonline.com' in url:
                return R(200, {'access_token': 'TOKEN', 'expires_in': 3600})
            return R(202)
        with mock.patch.object(mail_graph.requests, 'post', fake_post):
            m = EmailMultiAlternatives('عنوان', 'نص', 'x@y', ['a@b.com'], reply_to=['info@iajaward.org'])
            m.attach_alternative('<b>html</b>', 'text/html')
            self.assertEqual(mail_graph.GraphEmailBackend().send_messages([m]), 1)
        url, kw = calls[1]
        self.assertIn('/users/info@iajaward.org/sendMail', url)
        self.assertEqual(kw['headers']['Authorization'], 'Bearer TOKEN')
        self.assertEqual(kw['json']['message']['body']['contentType'], 'HTML')
        self.assertEqual(kw['json']['message']['toRecipients'][0]['emailAddress']['address'], 'a@b.com')


@override_settings(EMAIL_ENABLED=False)
class CyclesArchiveTest(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        AwardCycle.objects.all().delete()
        self.old = AwardCycle.objects.create(name='الدورة الثالثة عشرة', short_name='الدورة 13', year=2025,
                                             opens_at=timezone.now() - timedelta(days=400), closes_at=timezone.now() - timedelta(days=300))
        self.cur = AwardCycle.objects.create(name='الدورة الرابعة عشرة', short_name='الدورة 14', year=2026, hijri_year='1448',
                                             is_current=True, opens_at=timezone.now() - timedelta(days=1),
                                             closes_at=timezone.now() + timedelta(days=20))
        self.admin = User.objects.create_superuser('admin', 'admin@x.org', 'Adm1n-pass!')

    def test_media_cycle_and_archive(self):
        from .models import Photo, TimelineEvent
        p_new = Photo.objects.create(title='صورة جديدة', image='photos/a.jpg')
        self.assertEqual(p_new.cycle_id, self.cur.pk)            # الدورة الحالية تلقائياً
        Photo.objects.create(title='صورة قديمة', image='photos/b.jpg', cycle=self.old)
        r = self.client.get('/photos/')
        self.assertContains(r, 'كل الدورات')
        self.assertContains(r, 'صورة قديمة')
        r = self.client.get(f'/photos/?cycle={self.cur.pk}')
        self.assertContains(r, 'صورة جديدة')
        self.assertNotContains(r, 'صورة قديمة')
        self.assertContains(self.client.get('/cycles/'), 'الدورة الثالثة عشرة')
        r = self.client.get(f'/cycles/{self.cur.pk}/')
        self.assertContains(r, '1448هـ/2026م')
        # الجدول الزمني في الرئيسية: الدورة الحالية فقط
        TimelineEvent.objects.create(title='خطوة قديمة', cycle=self.old)
        TimelineEvent.objects.create(title='خطوة حالية', cycle=self.cur)
        from .site_cache import clear_home_bundle
        clear_home_bundle()
        r = self.client.get('/')
        self.assertContains(r, 'خطوة حالية')
        self.assertNotContains(r, 'خطوة قديمة')
        self.assertContains(r, 'استقبال طلبات الدورة 14')

    def test_admin_cycle_actions(self):
        from .models import Photo
        self.client.login(username='admin', password='Adm1n-pass!')
        r = self.client.post('/admin/award/awardcycle/', {'action': 'clone_cycle', '_selected_action': [self.cur.pk]})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(AwardCycle.objects.filter(year=2027, hijri_year='1449').exists())
        ph = Photo.objects.create(title='x', image='photos/c.jpg')
        r = self.client.post('/admin/award/photo/', {'action': 'move_to_cycle', '_selected_action': [ph.pk],
                                                     'apply': '1', 'cycle': self.old.pk})
        self.assertEqual(r.status_code, 302)
        ph.refresh_from_db()
        self.assertEqual(ph.cycle_id, self.old.pk)
        for path in ('/admin/award/photo/', '/admin/award/video/', '/admin/award/news/', '/admin/award/winner/',
                     '/admin/award/timelineevent/', f'/admin/award/awardcycle/{self.cur.pk}/change/', '/admin/award/heroslide/add/'):
            self.assertEqual(self.client.get(path).status_code, 200, path)
