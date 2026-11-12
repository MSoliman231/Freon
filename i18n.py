import calendar
import json
from pathlib import Path

from PySide6.QtCore import Qt

SETTINGS_FILE = Path(__file__).resolve().parent / "app_settings.json"

LANGUAGES = {"en": "English", "ar": "العربية"}

MONTHS_AR = [
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]
# Monday first, same order as Python's weekday()
DAYS_AR = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]

HINT = (
    "Click a day to cycle: Present → Late-1 → Late-2 → Absent → empty   |   "
    "Right-click a day to add a note   |   Click a name to outline their month"
    "Click a day to cycle: Present → Late-1 → Late-2 → Absent → empty   |   "
    "Right-click a day to add a note   |   Click a name to outline their month   |   "
    "Double-click a name to edit it"
)


# English text -> Arabic text. Anything missing here stays in English.
AR = {
    # ----- lock screen -----
    "Type your password": "اكتب كلمة المرور",
    "Show password": "إظهار كلمة المرور",
    "Wrong password": "كلمة المرور غير صحيحة",
        "Set up your password": "إعداد كلمة المرور",
    "Enter your email and choose a password for the app.":
        "أدخل بريدك الإلكتروني واختر كلمة مرور للتطبيق.",
    "New password": "كلمة المرور الجديدة",
    "Confirm password": "تأكيد كلمة المرور",
    "Save and continue": "حفظ ومتابعة",
    "The password must be at least {count} characters.":
        "يجب ألا تقل كلمة المرور عن {count} أحرف.",
    "The passwords do not match.": "كلمتا المرور غير متطابقتين.",
    "Could not save the password ({error}).": "تعذر حفظ كلمة المرور ({error}).",
        "Edit name": "تعديل الاسم",
    'Enter the new name for "{name}":': 'أدخل الاسم الجديد لـ "{name}":',
    '"{name}" already exists.': '"{name}" موجود بالفعل.',

    # ----- attendance page -----
    "Lock": "قفل",
    "Settings": "الإعدادات",
    "Type a name and press Enter": "اكتب الاسم ثم اضغط Enter",
    "Monthly salary": "الراتب الشهري",
    "Salary for {days}/{total} days": "الراتب عن الأيام ({days}/{total})",
HINT: (
        "اضغط على اليوم للتبديل: حاضر ← تأخير 1 ← تأخير 2 ← غائب ← فارغ   |   "
        "اضغط بزر الفأرة الأيمن على اليوم لإضافة ملاحظة   |   "
        "اضغط على الاسم لإبراز شهره   |   اضغط مرتين على الاسم لتعديله"
    ),
    "Delete name": "حذف اسم",
    "Export": "طباعه",
    "Present": "حاضر",
    "Late-1": "تأخير 1",
    "Late-2": "تأخير 2",
    "Absent": "غائب",
    "Click a name on the left first, then press Delete name.":
        "اضغط على اسم أولاً، ثم اضغط حذف اسم.",
    "Confirm delete": "تأكيد الحذف",
    'Enter the password to delete "{name}" and all of their records:':
        'أدخل كلمة المرور لحذف "{name}" وجميع سجلاته:',
    "Wrong password. Nothing was deleted.":
        "كلمة المرور غير صحيحة. لم يتم حذف أي شيء.",
    "Add note": "إضافة ملاحظة",
    "Edit note": "تعديل الملاحظة",
    "Remove note": "حذف الملاحظة",
    "Money {name} borrowed on {day} {month}\n(it will be subtracted from their salary):":
        "المبلغ الذي اقترضه {name} يوم {day} {month}\n(سيتم خصمه من راتبه):",
    "Borrowed: {amount}": "السلفة: {amount}",
    "Choose the names to export:": "اختر الأسماء المراد تصديرها:",
    "Select all": "تحديد الكل",
    "OK": "موافق",
    "Cancel": "إلغاء",
    "Yes": "نعم",
    "No": "لا",
    "Salary missing": "الراتب غير محدد",
    "{names} doesn't have a salary yet.": "{names} ليس لديه راتب محدد بعد.",
    "{names} don't have a salary yet.": "{names} ليس لديهم راتب محدد بعد.",
    "Proceed anyway?": "هل تريد المتابعة على أي حال؟",

    # ----- settings -----
    "Change password": "تغيير كلمة المرور",
    "Attendance rules (salary)": "قواعد الحضور (الراتب)",
    "← Back": "→ رجوع",
    "Enter the email that should receive the new password.":
        "أدخل البريد الإلكتروني الذي ستصله كلمة المرور الجديدة.",
    "Generate and send new password": "إنشاء كلمة مرور جديدة وإرسالها",
    "Please enter a valid email address.": "يرجى إدخال بريد إلكتروني صحيح.",
    "The sender email is not set up yet. Fill it in at the top of settings.py.":
        "بريد الإرسال غير مُعدّ بعد. أدخله في أعلى ملف settings.py.",
    "Sending...": "جارٍ الإرسال...",
    "New password sent to {email}. Use it the next time you unlock.":
        "تم إرسال كلمة المرور الجديدة إلى {email}. استخدمها في المرة القادمة عند فتح القفل.",
    "The email was sent but the password could not be saved ({error}). The old password is still active.":
        "تم إرسال البريد لكن تعذر حفظ كلمة المرور ({error}). كلمة المرور القديمة ما زالت فعّالة.",
    "Your password was not changed.": "لم يتم تغيير كلمة المرور.",
    "Login failed. Check the sender email and app password in settings.py.":
        "فشل تسجيل الدخول. تحقق من بريد الإرسال وكلمة مرور التطبيق في settings.py.",
    "Could not send the email: {error}": "تعذر إرسال البريد الإلكتروني: {error}",
    "FREON - your new password": "FREON - كلمة المرور الجديدة",
    "Your new FREON password is: {password}":
        "كلمة المرور الجديدة لتطبيق FREON هي: {password}",
    "Select a name:": "اختر اسماً:",
    "Salary:": "الراتب:",
    "Select a name on the left": "اختر اسماً من القائمة",
    "No names yet. Add names on the attendance page.":
        "لا توجد أسماء بعد. أضف الأسماء في صفحة الحضور.",
    "Salary for {name}": "راتب {name}",
    "Rules for all names (amount deducted each time)":
        "قواعد تنطبق على جميع الأسماء (المبلغ المخصوم في كل مرة)",

    # ----- export / payslip -----
    "Attendance": "الحضور",
    "Discounts": "الخصومات",
    "Salary": "الراتب",
    "Days in month": "أيام الشهر",
    "Late days": "أيام التأخير",
    "Not marked": "غير مسجل",
    "Borrowed": "السلفة",
    "Total discount": "إجمالي الخصم",
    "Salary before": "الراتب قبل الخصم",
    "Discount": "الخصم",
    "Salary after": "الراتب بعد الخصم",
    "Not set": "غير محدد",
    "Month:": "الشهر:",
    "Printed:": "تاريخ الطباعة:",
    "Page": "صفحة",
    "{count} name(s) on {pages} A4 page(s)": "{count} اسم على {pages} صفحة A4",
    "Save image": "حفظ كصورة",
    "Save PDF": "حفظ PDF",
    "Print": "طباعة",
    "Close": "إغلاق",
    "Could not start printing.": "تعذر بدء الطباعة.",
    "Could not save {path}": "تعذر حفظ {path}",
}

_language = "en"


def _load():
    global _language
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            code = json.load(f).get("language", "en")
        if code in LANGUAGES:
            _language = code
    except (OSError, ValueError, AttributeError):
        pass


_load()


def get_language():
    return _language


def set_language(code):
    """Changes the language and remembers it for the next start."""
    global _language
    if code not in LANGUAGES:
        return
    _language = code
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"language": code}, f)
    except OSError as e:
        print(f"Could not save language: {e}")


def is_rtl():
    return _language == "ar"


def direction():
    return Qt.RightToLeft if is_rtl() else Qt.LeftToRight


def tr(text, **kwargs):
    if _language == "ar":
        text = AR.get(text, text)
    return text.format(**kwargs) if kwargs else text


def month_name(month):
    if _language == "ar":
        return MONTHS_AR[month - 1]
    return calendar.month_name[month]


def day_abbr(weekday):
    if _language == "ar":
        return DAYS_AR[weekday]
    return calendar.day_abbr[weekday]