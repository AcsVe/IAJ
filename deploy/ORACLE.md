# تشغيل الموقع على Oracle Cloud (Always Free)

1. أنشئ خادم: Compute → Instances → Create — Ubuntu 24.04، الشكل Ampere A1 (أو VM.Standard.E2.1.Micro)، واحفظ مفتاح SSH.
2. انسخ النسخة الاحتياطية إلى الخادم في `~/iaj-transfer` (`db/*.dump` و `media/`).
3. على الخادم:
   ```bash
   curl -fsSL -o oracle_setup.sh https://raw.githubusercontent.com/AcsVe/IAJ/main/deploy/oracle_setup.sh
   bash oracle_setup.sh https://test.iajaward.org <CLOUDFLARE_TUNNEL_TOKEN>
   ```
4. التحديث لاحقاً: `bash /opt/iaj/deploy/oracle_update.sh`

لا حاجة لفتح أي منفذ في Oracle — النفق يتصل للخارج فقط.
