from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import qrcode
import io
from django.core.files.base import ContentFile


class Book(models.Model):
    # شناسه‌ها
    isbn = models.CharField('شابک', max_length=20, blank=True, null=True, unique=True)
    national_biblio_number = models.CharField('شماره کتابشناسی ملی', max_length=30, blank=True)

    # اطلاعات اصلی
    title = models.CharField('عنوان', max_length=500)
    subtitle = models.CharField('زیرعنوان', max_length=500, blank=True)
    author = models.CharField('پدیدآور', max_length=300)
    translator = models.CharField('مترجم', max_length=300, blank=True)
    editor = models.CharField('ویراستار', max_length=300, blank=True)

    # مشخصات نشر
    publisher = models.CharField('ناشر', max_length=200, blank=True)
    publish_place = models.CharField('محل نشر', max_length=100, blank=True)
    publish_year = models.CharField('سال نشر', max_length=10, blank=True)
    edition = models.CharField('چاپ', max_length=50, blank=True)
    pages = models.PositiveIntegerField('تعداد صفحه', null=True, blank=True)
    volume = models.CharField('جلد', max_length=20, blank=True)
    series = models.CharField('مجموعه', max_length=200, blank=True)

    # رده‌بندی
    dewey_class = models.CharField('رده دیویی', max_length=50, blank=True)
    lcc_class = models.CharField('رده کنگره', max_length=100, blank=True)
    subject = models.TextField('موضوعات', blank=True)  # با خط جدید جدا می‌شود

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
    notes = models.TextField('یادداشت', blank=True)
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
        """آیا حداقل یک نسخه موجود است؟"""
        active_loans = self.loans.filter(status='active').count()
        return active_loans < self.total_copies

    @property
    def available_copies(self):
        active_loans = self.loans.filter(status='active').count()
        return max(0, self.total_copies - active_loans)

    def generate_qr(self):
        """تولید QR Code برای این کتاب"""
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

    # اطلاعات شخصی
    first_name = models.CharField('نام', max_length=100)
    last_name = models.CharField('نام خانوادگی', max_length=100)
    national_id = models.CharField('کد ملی', max_length=10, unique=True, blank=True)
    phone = models.CharField('تلفن', max_length=15, blank=True)
    address = models.TextField('آدرس', blank=True)

    # عضویت
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
            # تولید کد عضویت خودکار
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

    # تاریخ‌ها
    loan_date = models.DateField('تاریخ امانت', default=timezone.now)
    due_date = models.DateField('تاریخ بازگشت')
    returned_date = models.DateField('تاریخ برگشت واقعی', null=True, blank=True)

    # وضعیت
    status = models.CharField('وضعیت', max_length=20, choices=STATUS_CHOICES, default='active')
    renewal_count = models.PositiveIntegerField('تعداد تمدید', default=0)
    max_renewals = models.PositiveIntegerField('حداکثر تمدید مجاز', default=2)

    # ثبت‌کننده
    issued_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='issued_loans', verbose_name='صادرکننده'
    )
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
