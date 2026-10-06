from django.db import migrations

# ملاحظة: كانت هذه الهجرة تضيف أعمدة ألوان الأقسام بأوامر SQL خاصة بـ Postgres.
# أصبحت الإضافة تتم بشكل آمن (ولكل قواعد البيانات) داخل 0026.
# على السيرفر الحالي هذه الهجرة مطبّقة مسبقاً فلا تأثير لهذا التعديل.


class Migration(migrations.Migration):

    dependencies = [
        ('award', '0022_photo_winnercategory_delete_newsitem_and_more'),
    ]

    operations = []
