# تنسيقات العربية في الموقع: التاريخ بصيغة 2026-12-31 والوقت بنظام 24 ساعة، والفاصلة العشرية نقطة
# (تنسيقات Django العربية الافتراضية تجعلها فاصلة، فتفسد قيم الحقول الرقمية والدرجات).
DATE_FORMAT = 'Y-m-d'
SHORT_DATE_FORMAT = 'Y-m-d'
# «الساعة» بين التاريخ والوقت: في النص العربي يبقى التاريخ أولاً ثم الوقت (دون كلمة يظهر الوقت قبل التاريخ)
DATETIME_FORMAT = 'Y-m-d الساعة H:i'
SHORT_DATETIME_FORMAT = 'Y-m-d الساعة H:i'
TIME_FORMAT = 'H:i'
YEAR_MONTH_FORMAT = 'F Y'
MONTH_DAY_FORMAT = 'j F'
DATE_INPUT_FORMATS = ['%Y-%m-%d', '%d/%m/%Y']
DATETIME_INPUT_FORMATS = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M', '%Y-%m-%d']
DECIMAL_SEPARATOR = '.'
THOUSAND_SEPARATOR = ','
NUMBER_GROUPING = 0
FIRST_DAY_OF_WEEK = 6
