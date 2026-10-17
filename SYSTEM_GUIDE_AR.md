# دليل نظام جائزة انتصار عباس جردانة (IAJ)

> دليل تقني موحّد: أين يعمل النظام، كيف تُعدّله وتحدّثه، بروتوكول الاتصال، التثبيت، التشغيل، والنسخ الاحتياطي.

---

## 1) نظرة عامة وأين يعمل

| البند | القيمة |
|---|---|
| الوصف | موقع جائزة (استعراض فائزين، أعمال، صور/فيديو) |
| التقنية | **Django** (بايثون) + خادم **Waitress** للإنتاج على ويندوز |
| قاعدة البيانات | **PostgreSQL** محلية (قاعدة باسم `iaj`) |
| الملفات (صور/فيديو) | مجلد `media` على القرص (نُقلت من Cloudinary) |
| يعمل على | كمبيوتر المدرسة (ويندوز)، مجلد ثابت مثل `C:\IAJ` |
| المنفذ المحلي | `8000` |
| العنوان العام | عبر Cloudflare Tunnel إلى `localhost:8000` |
| المستودع | `https://github.com/AcsVe/IAJ` — الفرع `main` |

هذا النظام هو «الأصل» الذي بُنيت على طريقته أنظمة التذاكر والحجوزات والحضور. الفرق الجوهري: **IAJ على Django + PostgreSQL**، والثلاثة الأخرى على **Flask + SQLite**.

---

## 2) بنية المشروع والملفات

- `manage.py` — أوامر Django.
- `core/` — الإعدادات (`core/settings.py`) و WSGI.
- `award/` — تطبيق الجائزة (النماذج، الصفحات، القوالب).
- `serve.py` — تشغيل الإنتاج عبر Waitress (`DJANGO_SETTINGS_MODULE=core.settings`، المنفذ من `.env` أو 8000).
- `requirements.txt` / `runtime.txt` — المكتبات وإصدار بايثون.
- `media/` — الصور والفيديوهات (لا تُرفع إلى GitHub).
- `backups/` — النسخ الاحتياطية (`db` و`media`).
- `.env` — الإعدادات السرية (لا يُرفع): `SITE_URL`, كلمة مرور PostgreSQL، `BACKUP_DIR`…
- ملفات `.bat` للتشغيل والصيانة (انظر الأقسام أدناه).

---

## 3) طريقة التعديل والإضافة والتحديث (مهم)

**القاعدة المتّبعة:** التعديلات تُكتب وتُدفع إلى GitHub، وأنت تشغّل **التحديث** فقط على الكمبيوتر — لا رفع يدوي للملفات.

1. يُعدَّل الكود ويُدفع إلى `AcsVe/IAJ` فرع `main`.
2. على الكمبيوتر: شغّل **`update.bat`** — يسحب آخر كود من GitHub ويعيد التشغيل.
3. إن كان التعديل يمسّ قاعدة البيانات (نماذج Django)، فـ`update.bat` يطبّق `migrate` تلقائياً؛ وإلا طبّقها يدوياً:
   `venv\Scripts\python manage.py migrate`

> لا تعدّل الملفات مباشرة على الكمبيوتر، حتى لا تتعارض مع `git`؛ أي تعديل محلي يُفقد عند `update.bat`.

---

## 4) بروتوكول الاتصال والنشر

- **Cloudflare Tunnel** (مجاني، بلا فتح منافذ في الراوتر): يوجّه الدومين إلى `http://localhost:8000`.
- التثبيت لمرة واحدة: `winget install --id Cloudflare.cloudflared` ثم إنشاء Tunnel من لوحة Cloudflare (Zero Trust ← Networks ← Tunnels)، وربط Public Hostname بالخدمة `HTTP → localhost:8000`.
- يُكتب العنوان في `.env`: `SITE_URL=https://award.yourdomain.com`.
- حدّ الرفع في الخطة المجانية 100MB للملف؛ الفيديوهات الكبيرة تُرفع من نفس الكمبيوتر عبر `http://localhost:8000/admin`.

---

## 5) التثبيت (مرة واحدة)

المتطلبات: PostgreSQL مثبّت وتعرف كلمة مرور `postgres`، وPython 3.12 (64-bit) مع «Add to PATH».

1. **`1_setup.bat`** — يثبّت المكتبات، ينشئ قاعدة `iaj`، وينقل البيانات من Neon وينزّل الوسائط من Cloudinary إلى `media`.
2. **`2_start.bat`** — تشغيل للتجربة: `http://localhost:8000`.
3. **`3_autostart.bat`** (كمسؤول) — تشغيل تلقائي مع ويندوز + نسخة احتياطية يومية 2 فجراً + منع النوم.

---

## 6) طريقة التشغيل والصيانة

| الملف | العمل |
|---|---|
| `iaj_on.bat` / `iaj_off.bat` | تشغيل / إيقاف الموقع |
| `update.bat` | تحديث من GitHub وإعادة التشغيل |
| `site_where.bat` | أين يعمل الموقع + تشخيص |
| `switch_to_server.bat` | إرجاع الموقع للكمبيوتر فوراً |
| `back_to_server.bat` | بعد الطوارئ: أخذ بيانات الهاتف ثم إرجاع الموقع |
| `test_email.bat` | اختبار إرسال البريد |

**الطوارئ (الهاتف):** مجلد `standby/` فيه `phone.sh` يشغّل الموقع من هاتف Termux عند انقطاع الكمبيوتر، مع نفق Cloudflare خاص.

---

## 8) إعادة بناء هاتف الطوارئ (بعد إعادة ضبط المصنع أو هاتف جديد)

الإجراء واحد في الحالتين، وبأمر واحد عبر `standby/restore.sh` الذي يُعيد بناء **الأنظمة الأربعة** معاً.

**أولاً — ثبّت من F-Droid (مرة واحدة):** `Termux` · `Termux:Widget` · `Termux:API` · `Termux:Boot`.

**ثانياً — في Termux، نفّذ:**
```
pkg install -y git && git clone https://github.com/AcsVe/IAJ ~/iaj 2>/dev/null; bash ~/iaj/standby/restore.sh
```

السكربت يقوم تلقائياً بـ:
1. طلب **رمز GitHub** مرة واحدة وحفظه (`~/.iaj_github_token`).
2. تثبيت الأدوات: `git · python · rclone · cloudflared · termux-api`.
3. تنزيل الأكواد الأربعة إلى `~/iaj` و`~/attendance` و`~/rastkt` و`~/venues` (دون إبقاء الرمز داخل إعدادات git).
4. تشغيل `setup` ثم `configure` لكل نظام (IAJ أولاً لأنه مصدر الرموز المشتركة) — فيُنشئ أزرار الشاشة في `~/.shortcuts` ويجلب رموز الأنفاق من Cloudflare.
5. ربط **Google Drive** عبر `rclone config` (الاسم: `gdrive`) — الخطوة الوحيدة التي تتطلب تسجيل دخول.

**ثالثاً:** حدّث أداة Termux:Widget على الشاشة الرئيسية لتظهر الأزرار (IAJ / ATT / …)، وتحقّق بـ `bash ~/iaj/standby/phone.sh status`.

> الرموز التي ستحتاجها جاهزة بين يديك: **رمز GitHub** (Contents: Read)، و**رمز Cloudflare API** (يطلبه `configure`)، وحساب **Google** المربوط بـ Drive. والشرط المسبق أن تكون الأنفاق منشأة على Cloudflare (يُنشئها `1_setup.bat` على الكمبيوتر).

---

## 7) النسخ الاحتياطي والاسترجاع

- يدوي: **`backup_now.bat`** → النسخ في `backups\db` (القاعدة) و`backups\media` (الملفات).
- يُفضّل توجيهها لمجلد خارجي/سحابي عبر `.env`: `BACKUP_DIR=D:\IAJ-backups` (أو مجلد OneDrive/Drive).
- الاسترجاع:
  `venv\Scripts\python manage.py restore_site backups\db\iaj-....dump --yes`
- نسخة احتياطية تلقائية يومية الساعة 2 فجراً (من `3_autostart.bat`).
