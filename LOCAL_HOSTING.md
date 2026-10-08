# تشغيل موقع الجائزة على جهاز Windows

## المتطلبات
- PostgreSQL مثبت (لديك 18.6) وتعرف كلمة مرور المستخدم `postgres`.
- Python 3.12 بنسخة 64-bit من python.org، مع تفعيل "Add python.exe to PATH".
- يُفضّل وضع المشروع في مجلد ثابت مثل `C:\IAJ` بدلاً من مجلد التنزيلات.
- ملف `.env` القديم (الذي يحتوي رابط Neon) بجانب `manage.py`، لنقل البيانات.

## الخطوات
1. **`1_setup.bat`** (مرة واحدة): يثبّت المكتبات، ثم يسألك عن كلمة مرور PostgreSQL وينشئ قاعدة اسمها `iaj`، ثم ينقل كل البيانات من Neon وينزّل كل الصور والفيديوهات من Cloudinary إلى مجلد `media`.
2. **`2_start.bat`**: يشغّل الموقع لتجربته. افتح http://localhost:8000
3. **`3_autostart.bat`** (كليك يمين ← Run as administrator): يجعل الموقع يعمل تلقائياً مع تشغيل Windows، ويضيف نسخة احتياطية يومية الساعة 2 فجراً، ويمنع الجهاز من النوم ما دام موصولاً بالكهرباء.

## نشر الموقع على الإنترنت (Cloudflare Tunnel، مجاني وبدون فتح منافذ في الراوتر)
1. أضف الدومين إلى حساب Cloudflare مجاني، وغيّر الـ Nameservers عند مزوّد الدومين حسب تعليمات Cloudflare.
2. ثبّت cloudflared على الجهاز من PowerShell:  `winget install --id Cloudflare.cloudflared`
3. من لوحة Cloudflare افتح Zero Trust ← Networks ← Tunnels ← Create a tunnel ← Cloudflared، ثم اختر Windows وانسخ الأمر `cloudflared.exe service install ...` وشغّله في نافذة Administrator.
4. في قسم Public Hostname اختر الدومين (مثلاً `award.yourdomain.com`)، واكتب في Service: النوع `HTTP` والعنوان `localhost:8000`.
5. اكتب نفس العنوان في `.env` بهذا الشكل: `SITE_URL=https://award.yourdomain.com` ثم أعد تشغيل الجهاز أو الموقع.

> مسميات لوحة Cloudflare قد تتغير، لكن الفكرة واحدة: Tunnel يوجّه الدومين إلى `http://localhost:8000`.
> الخطة المجانية في Cloudflare تحدّ حجم الرفع بـ 100MB للملف الواحد. ارفع الفيديوهات الكبيرة من نفس الجهاز عبر http://localhost:8000/admin

## النسخ الاحتياطي
- يدوياً: `backup_now.bat`. النسخ تُحفظ في `backups\db` (القاعدة) و`backups\media` (الملفات).
- يُفضّل نقلها لمكان آخر بإضافة هذا السطر إلى `.env`:  `BACKUP_DIR=D:\IAJ-backups` (أو مجلد OneDrive).
- للاسترجاع:  `venv\Scripts\python manage.py restore_site backups\db\iaj-....dump --yes`

## قبل إلغاء Neon و Cloudinary و Render
1. تأكد أن كل الصفحات والصور والفيديوهات تظهر من الجهاز، وأن الدومين يعمل.
2. لا تضف بيانات جديدة على الموقع القديم بعد النقل. وإذا أضفت، أعد تشغيل النقل بهذين الأمرين، مع العلم أنهما **يستبدلان** بيانات الجهاز بالكامل:
   `venv\Scripts\python manage.py import_from_cloud --yes`  ثم  `venv\Scripts\python manage.py localize_media --cleanup`
3. بعد التأكد: احذف سطر `CLOUD_DATABASE_URL` من `.env`، ثم احذف خدمة Render وقاعدة Neon وحساب Cloudinary.

## ملفات مهمة
- `.env`: إعدادات الجهاز وكلمة مرور القاعدة. لا تشاركه.
- `media\`: كل الصور والفيديوهات.
- `logs\server.log`: سجل الموقع عند حدوث مشكلة.

## تحديث الموقع من GitHub
- الكود محفوظ في https://github.com/AcsVe/IAJ — البيانات والصور تبقى على الجهاز فقط.
- لأخذ آخر تحديث: شغّل **`update.bat`** (كمسؤول إذا كان الموقع يعمل تلقائياً مع Windows).
- يحتاج برنامج Git مرة واحدة: https://git-scm.com/download/win

## التسجيل والإشعارات والتحكيم
**المسار:** المدرسة تنشئ حساباً ← تقدّم مشروعاً (مسودة ثم إرسال) ← تدقيق ← (مطلوب تعديل) ← تحكيم ← النتيجة.

- **لوحة التحكم ← ٤. التسجيل والتحكيم**
  - **دورات الجائزة**: موعد بداية ونهاية التسجيل (العداد في الموقع يتبعها)، المسارات المتاحة، الحد الأقصى للطلبات، مهلة التعديل، عدد المحكّمين لكل طلب، التحكيم بدون أسماء، و**نشر النتائج**.
  - **طلبات الترشح**: حدّد الطلبات ثم اختر من الإجراءات: تغيير الحالة (مع ملاحظة وإشعار)، توزيع تلقائي على المحكّمين، رسالة للمدارس، تصدير Excel.
  - **حسابات المدارس والمحكّمين**: «إضافة» ← النوع: محكّم ← البريد ← تصله دعوة ليختار كلمة المرور.
  - **معايير التحكيم**: الدرجة القصوى والوزن لكل معيار.
- النتيجة (مقبول/غير مقبول/فائز) **لا تظهر للمدرسة** قبل تفعيل «النتائج منشورة» في الدورة — عندها تُرسل الإشعارات للجميع.
- ملفات الطلبات خاصة: تفتحها الإدارة والمدرسة صاحبة الطلب والمحكّم المُسند إليه فقط.
- صفحات الموقع: `/accounts/signup/` `/accounts/login/` `/portal/` (المدرسة) `/judge/` (المحكّم).

### إعداد البريد (noreply@iajaward.org)
أضف إلى `.env` ثم أعد تشغيل الموقع، وجرّب بـ `test_email.bat`:
```
DEFAULT_FROM_EMAIL=جائزة انتصار عباس جردانة <noreply@iajaward.org>
ADMIN_NOTIFY_EMAILS=your@email.com
EMAIL_HOST=...
EMAIL_PORT=587
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
```
| الخدمة | EMAIL_HOST | PORT | USER | PASSWORD |
|---|---|---|---|---|
| Cloudflare Email Sending (خطة Workers المدفوعة) | smtp.mx.cloudflare.net | 465 | api_token | API Token بصلاحية Email Sending: Edit |
| Brevo (مجاني 300 رسالة/يوم) | smtp-relay.brevo.com | 587 | بريد حساب Brevo (SMTP login) | SMTP key |

بدون `EMAIL_HOST` تُحفظ الرسائل في `logs\emails` ويُفعَّل حساب المدرسة فوراً دون رسالة تفعيل. كل رسالة تظهر في «سجل رسائل البريد».
