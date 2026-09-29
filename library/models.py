# library/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import qrcode
import io
from django.core.files.base import ContentFile


class Book(models.Model):
    # شناسه‌ها
    isbn = models.CharField('شابک', max_length=50, blank=True, null=True, unique=True)
    national_biblio_number = models.CharField('شماره کتابشناسی ملی', max_length=30, blank=True)

    # اطلاعات اصلی
    title = models.CharField('عنوان', max_length=500)
    subtitle = models.CharField('عنوان فرعی', max_length=500, blank=True)
    statement_of_responsibility = models.CharField('عنوان و نام پدیدآور', max_length=500, blank=True)

    # پدیدآور
    author = models.CharField('نویسنده', max_length=300)
    author_dates = models.CharField('تاریخ نویسنده', max_length=100, blank=True)

    # مشخصات نشر
    publisher = models.CharField('ناشر', max_length=200, blank=True)
    publish_place = models.CharField('محل نشر', max_length=100, blank=True)
    publish_year = models.CharField('سال نشر', max_length=10, blank=True)

    # مشخصات ظاهری
    pages = models.CharField('تعداد صفحه', max_length=50, blank=True)
    dimensions = models.CharField('ابعاد', max_length=100, blank=True)

    # رده‌بندی
    dewey_class = models.CharField('رده دیویی', max_length=50, blank=True)
    lcc_class = models.CharField('رده کنگره', max_length=100, blank=True)

    # موضوعات
    subject = models.TextField('موضوعات', blank=True)
    notes = models.TextField('یادداشت', blank=True)
    fapa = models.CharField('وضعیت فهرست‌نویسی', max_length=100, blank=True)

    # کتاب چندجلدی
    volume = models.CharField('شماره جلد', max_length=20, blank=True)
    series = models.CharField('نام مجموعه', max_length=200, blank=True)
    series_number = models.PositiveIntegerField('شماره در مجموعه', null=True, blank=True)

    # فیزیکی
    language = models.CharField('زبان', max_length=50, default='فارسی')
    cover_image = models.ImageField('تصویر جلد', upload_to='covers/', blank=True, null=True)
    qr_code = models.ImageField('QR Code', upload_to='qrcodes/', blank=True, null=True)

    # وضعیت
    CONDITION_CHOICES = [
        ('excellent', 'عالی'),
        ('good', 'خوب'),
        ('fair', 'متوسط'),
        ('poor', 'ضعیف'),
    ]
    condition = models.CharField('وضعیت فیزیکی', max_length=20, choices=CONDITION_CHOICES, default='good')
    location = models.CharField('محل قفسه', max_length=100, blank=True)
    copy_number = models.PositiveIntegerField('شماره نسخه', default=1)
    total_copies = models.PositiveIntegerField('تعداد کل نسخه‌ها', default=1)

    # متا
    marc_record = models.TextField('رکورد MARC خام', blank=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='added_books')
    created_at = models.DateTimeField('تاریخ افزودن', auto_now_add=True)
    updated_at = models.DateTimeField('آخرین ویرایش', auto_now=True)

    class Meta:
        verbose_name = 'کتاب'
        verbose_name_plural = 'کتاب‌ها'
        ordering = ['title']

    def __str__(self):
        return f"{self.title} — {self.author}"

    @property
    def is_available(self):
        active_loans = self.loans.filter(status='active').count()
        return active_loans < self.total_copies

    @property
    def available_copies(self):
        active_loans = self.loans.filter(status='active').count()
        return max(0, self.total_copies - active_loans)

    def generate_qr(self):
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(f"BOOK:{self.pk}:{self.isbn or self.title}")
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        filename = f'book_{self.pk}.png'
        self.qr_code.save(filename, ContentFile(buffer.getvalue()), save=False)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.qr_code:
            self.generate_qr()
            super().save(update_fields=['qr_code'])


class Member(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    first_name = models.CharField('نام', max_length=100)
    last_name = models.CharField('نام خانوادگی', max_length=100)
    national_id = models.CharField('کد ملی', max_length=10, unique=True, blank=True)
    phone = models.CharField('تلفن', max_length=15, blank=True)
    address = models.TextField('آدرس', blank=True)
    member_code = models.CharField('کد عضویت', max_length=20, unique=True)
    join_date = models.DateField('تاریخ عضویت', default=timezone.now)
    is_active = models.BooleanField('فعال', default=True)
    max_loans = models.PositiveIntegerField('حداکثر امانت همزمان', default=3)
    notes = models.TextField('یادداشت', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'عضو'
        verbose_name_plural = 'اعضا'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.member_code})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def active_loans_count(self):
        return self.loans.filter(status='active').count()

    @property
    def can_borrow(self):
        return self.is_active and self.active_loans_count < self.max_loans

    def save(self, *args, **kwargs):
        if not self.member_code:
            import datetime
            year = datetime.datetime.now().year
            last = Member.objects.order_by('id').last()
            next_id = (last.id + 1) if last else 1
            self.member_code = f"M{year}{next_id:04d}"
        super().save(*args, **kwargs)


class Loan(models.Model):
    STATUS_CHOICES = [
        ('active', 'امانت فعال'),
        ('returned', 'برگشت داده شده'),
        ('overdue', 'تأخیر'),
        ('renewed', 'تمدید شده'),
        ('lost', 'مفقود'),
    ]

    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name='loans', verbose_name='کتاب')
    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name='loans', verbose_name='عضو')
    loan_date = models.DateField('تاریخ امانت', default=timezone.now)
    due_date = models.DateField('تاریخ بازگشت')
    returned_date = models.DateField('تاریخ برگشت واقعی', null=True, blank=True)
    status = models.CharField('وضعیت', max_length=20, choices=STATUS_CHOICES, default='active')
    renewal_count = models.PositiveIntegerField('تعداد تمدید', default=0)
    max_renewals = models.PositiveIntegerField('حداکثر تمدید مجاز', default=2)
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='issued_loans')
    notes = models.TextField('یادداشت', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'امانت'
        verbose_name_plural = 'امانت‌ها'
        ordering = ['-loan_date']

    def __str__(self):
        return f"{self.book.title} → {self.member.full_name}"

    @property
    def is_overdue(self):
        if self.status == 'active' and self.due_date < timezone.now().date():
            return True
        return False

    @property
    def days_overdue(self):
        if self.is_overdue:
            return (timezone.now().date() - self.due_date).days
        return 0

    @property
    def days_remaining(self):
        if self.status == 'active':
            delta = self.due_date - timezone.now().date()
            return delta.days
        return 0

    def can_renew(self):
        return self.status == 'active' and self.renewal_count < self.max_renewals

    def renew(self, extra_days=14):
        if self.can_renew():
            self.due_date = self.due_date + timezone.timedelta(days=extra_days)
            self.renewal_count += 1
            self.status = 'renewed'
            self.save()
            return True
        return False

    def return_book(self):
        self.returned_date = timezone.now().date()
        self.status = 'returned'
        self.save()


class Notification(models.Model):
    TYPE_CHOICES = [
        ('due_soon', 'نزدیک به پایان مهلت'),
        ('overdue', 'تأخیر در برگشت'),
        ('returned', 'برگشت کتاب'),
        ('new_loan', 'امانت جدید'),
        ('renewal', 'تمدید امانت'),
        ('system', 'سیستم'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    loan = models.ForeignKey(Loan, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.CharField('نوع', max_length=20, choices=TYPE_CHOICES)
    title = models.CharField('عنوان', max_length=200)
    message = models.TextField('پیام')
    is_read = models.BooleanField('خوانده شده', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'اعلان'
        verbose_name_plural = 'اعلان‌ها'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} — {self.user.username}"


# ==================== Sync Models ====================

class Device(models.Model):
    """دستگاه‌های متصل"""
    DEVICE_TYPES = [
        ('mobile', 'موبایل'),
        ('desktop', 'دسکتاپ'),
        ('web', 'وب'),
        ('tablet', 'تبلت'),
    ]

    device_id = models.CharField('شناسه دستگاه', max_length=100, unique=True)
    device_name = models.CharField('نام دستگاه', max_length=200)
    device_type = models.CharField('نوع', max_length=50, choices=DEVICE_TYPES, default='mobile')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    last_sync = models.DateTimeField('آخرین Sync', null=True, blank=True)
    last_ip = models.GenericIPAddressField('آخرین IP', null=True, blank=True)
    is_active = models.BooleanField('فعال', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'دستگاه'
        verbose_name_plural = 'دستگاه‌ها'
        ordering = ['-last_sync']

    def __str__(self):
        return f"{self.device_name} ({self.device_type})"


class SyncLog(models.Model):
    """گزارش هر عملیات Sync"""
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('in_progress', 'در حال انجام'),
        ('completed', 'تکمیل شده'),
        ('failed', 'ناموفق'),
    ]
    ACTION_CHOICES = [
        ('push', 'ارسال به سرور'),
        ('pull', 'دریافت از سرور'),
        ('full_sync', 'Sync کامل'),
    ]

    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True)
    device_identifier = models.CharField('شناسه دستگاه', max_length=100, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField('نوع', max_length=20, choices=ACTION_CHOICES)
    status = models.CharField('وضعیت', max_length=20, choices=STATUS_CHOICES, default='pending')

    pushed_count = models.IntegerField('تعداد ارسال شده', default=0)
    pulled_count = models.IntegerField('تعداد دریافت شده', default=0)
    conflict_count = models.IntegerField('تعداد تعارض', default=0)

    started_at = models.DateTimeField('شروع', auto_now_add=True)
    completed_at = models.DateTimeField('پایان', null=True, blank=True)

    details = models.TextField('جزئیات', blank=True)
    error_message = models.TextField('خطا', blank=True)

    class Meta:
        verbose_name = 'گزارش Sync'
        verbose_name_plural = 'گزارش‌های Sync'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.get_action_display()} - {self.get_status_display()} ({self.started_at})"


class SyncQueue(models.Model):
    """صف تغییرات"""
    ACTION_CHOICES = [
        ('create', 'ایجاد'),
        ('update', 'ویرایش'),
        ('delete', 'حذف'),
    ]
    MODEL_CHOICES = [
        ('book', 'کتاب'),
        ('member', 'عضو'),
        ('loan', 'امانت'),
    ]
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('synced', 'Sync شده'),
        ('failed', 'ناموفق'),
    ]

    device_id = models.CharField('شناسه دستگاه', max_length=100)
    model_name = models.CharField('مدل', max_length=20, choices=MODEL_CHOICES)
    object_id = models.CharField('شناسه شیء', max_length=100)
    action = models.CharField('عملیات', max_length=20, choices=ACTION_CHOICES)
    data = models.JSONField('داده‌ها')

    created_at = models.DateTimeField('زمان ایجاد', auto_now_add=True)
    synced_at = models.DateTimeField('زمان Sync', null=True, blank=True)
    status = models.CharField('وضعیت', max_length=20, choices=STATUS_CHOICES, default='pending')

    class Meta:
        verbose_name = 'صف Sync'
        verbose_name_plural = 'صف‌های Sync'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.model_name} - {self.action}"


class Conflict(models.Model):
    """تعارض‌های Sync"""
    RESOLUTION_CHOICES = [
        ('local', 'نسخه محلی'),
        ('remote', 'نسخه سرور'),
        ('merged', 'ادغام شده'),
        ('pending', 'در انتظار'),
    ]
    MODEL_CHOICES = [
        ('book', 'کتاب'),
        ('member', 'عضو'),
        ('loan', 'امانت'),
    ]

    model_name = models.CharField('مدل', max_length=20, choices=MODEL_CHOICES)
    object_id = models.CharField('شناسه شیء', max_length=100)

    local_data = models.JSONField('داده محلی')
    remote_data = models.JSONField('داده سرور')
    local_updated_at = models.DateTimeField('آخرین ویرایش محلی')
    remote_updated_at = models.DateTimeField('آخرین ویرایش سرور')

    resolution = models.CharField('راه حل', max_length=20, choices=RESOLUTION_CHOICES, default='pending')
    resolved_data = models.JSONField('داده نهایی', null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    resolved_at = models.DateTimeField('زمان حل', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'تعارض'
        verbose_name_plural = 'تعارض‌ها'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.model_name} - {self.object_id}"