"""بوابة أنظمة العمل:  python manage.py test award.test_systems_portal"""
import re
from unittest import mock

from django.test import TestCase

from award import systems_portal as sp

URLS = ['https://1.iajaward.org', 'https://2.iajaward.org', 'https://3.iajaward.org', 'https://4.iajaward.org',
        'https://5.iajaward.org', 'https://6.iajaward.org', 'https://8.iajaward.org', 'https://9.iajaward.org']
# كلمات تقنية لا يجوز أن تظهر للزائر
TECH = re.compile(r'\b(Flask|Django|Python|SQLite|PostgreSQL|API|server|database|port|JavaScript)\b|'
                  r'خادم|قاعدة البيانات|برمجة|برمجي|منفذ', re.I)


class SystemsPortalTest(TestCase):
    def setUp(self):
        sp._cache.update(at=0.0, data=None)

    def _visible_text(self, html):
        html = re.sub(r'<(script|style)\b.*?</\1>', ' ', html, flags=re.S)
        return re.sub(r'<[^>]+>', ' ', html)

    def test_arabic_page(self):
        r = self.client.get('/systems/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('lang="ar" dir="rtl"', html)
        self.assertIn('بوابة أنظمة العمل', html)
        for u in URLS:
            self.assertIn(f'href="{u}"', html)
        self.assertEqual(html.count('<dialog class="sys"'), 8)
        self.assertIn('Trolley Reservation', html)
        self.assertNotRegex(self._visible_text(html), TECH)
        self.assertNotRegex(html, r'عربة|عربات|حواسيب')

    def test_english_page_and_cookie(self):
        r = self.client.get('/systems/?lang=en')
        html = r.content.decode()
        self.assertIn('lang="en" dir="ltr"', html)
        self.assertIn('Work Systems Portal', html)
        self.assertNotRegex(self._visible_text(html), TECH)
        self.assertEqual(r.cookies[sp.LANG_COOKIE].value, 'en')
        # اللغة المحفوظة تبقى عند العودة دون ?lang
        self.assertIn('lang="en" dir="ltr"', self.client.get('/systems/').content.decode())

    def test_unknown_lang_falls_back_to_arabic(self):
        self.assertIn('lang="ar" dir="rtl"', self.client.get('/systems/?lang=xx').content.decode())

    def test_ticker_proxies_venues_and_sanitizes(self):
        payload = {'enabled': True, 'html': '<p>خبر <b>مهم</b><script>alert(1)</script></p>'
                   '<p onclick="x()"><a href="javascript:alert(1)">رابط</a></p>',
                   'htmlEn': '<p>News</p>', 'rssItems': [{'title': 'T', 'link': 'javascript:x'}],
                   'speedSeconds': 30, 'bgColor': 'red;x', 'textColor': '#ffffff', 'secret': 'no'}
        resp = mock.Mock(status_code=200, json=mock.Mock(return_value=payload))
        with mock.patch.object(sp.requests, 'get', return_value=resp):
            d = self.client.get('/systems/ticker.json').json()
        self.assertTrue(d['enabled'])
        self.assertNotIn('script', d['html'])
        self.assertNotIn('onclick', d['html'])
        self.assertNotIn('javascript', d['html'])
        self.assertIn('<b>مهم</b>', d['html'])
        self.assertEqual(d['rssItems'][0]['link'], '')
        self.assertEqual(d['bgColor'], '')
        self.assertNotIn('secret', d)

    def test_ticker_hidden_when_venues_unreachable(self):
        with mock.patch.object(sp.requests, 'get', side_effect=OSError):
            self.assertEqual(self.client.get('/systems/ticker.json').json(), {'enabled': False})

    def test_footer_links_to_portal(self):
        self.assertIn('href="/systems/"', self.client.get('/').content.decode())
