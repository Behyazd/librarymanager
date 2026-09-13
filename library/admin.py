# library/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Book, Member, Loan, Notification


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'isbn', 'available_copies', 'qr_preview', 'created_at')
    list_filter = ('created_at', 'language', 'condition')
    search_fields = ('title', 'author', 'isbn', 'publisher')
    readonly_fields = ('qr_code', 'qr_preview', 'created_at', 'updated_at')
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('title', 'subtitle', 'author', 'translator', 'editor', 'isbn', 'national_biblio_number')
        }),
        ('مشخصات نشر', {
            'fields': ('publisher', 'publish_place', 'publish_year', 'edition', 'pages', 'volume', 'series')
        }),
        ('رده‌بندی', {
            'fields': ('dewey_class', 'lcc_class', 'subject')
        }),
        ('وضعیت فیزیکی', {
            'fields': ('language', 'condition', 'location', 'copy_number', 'total_copies', 'cover_image', 'qr_code')
        }),
        ('متا', {
            'fields': ('notes', 'added_by', 'created_at', 'updated_at')
        }),
    )

    def available_copies(self, obj):
        active_loans = obj.loans.filter(status='active').count()
        return max(0, obj.total_copies - active_loans)
    available_copies.short_description = 'نسخه‌های موجود'

    def qr_preview(self, obj):
        if obj.qr_code:
            return format_html('<img src="{}" width="60" height="60" />', obj.qr_code.url)
        return '—'
    qr_preview.short_description = 'QR Code'


class LoanInline(admin.TabularInline):
    model = Loan
    extra = 0
    fields = ('book', 'loan_date', 'due_date', 'status', 'returned_date')
    readonly_fields = ('loan_date',)


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'national_id', 'phone', 'member_code', 'is_active', 'active_loans_count', 'join_date')
    list_filter = ('is_active', 'join_date')
    search_fields = ('first_name', 'last_name', 'national_id', 'phone', 'member_code')
    readonly_fields = ('member_code', 'join_date', 'created_at')
    inlines = [LoanInline]
    fieldsets = (
        ('اطلاعات شخصی', {
            'fields': ('first_name', 'last_name', 'national_id', 'phone', 'address')
        }),
        ('عضویت', {
            'fields': ('user', 'member_code', 'join_date', 'is_active', 'max_loans')
        }),
        ('متا', {
            'fields': ('notes', 'created_at')
        }),
    )

    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'نام کامل'
    full_name.admin_order_field = 'last_name'

    def active_loans_count(self, obj):
        return obj.active_loans_count
    active_loans_count.short_description = 'امانت فعال'


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('book', 'member', 'loan_date', 'due_date', 'status', 'is_overdue_display')
    list_filter = ('status', 'loan_date', 'due_date')
    search_fields = ('book__title', 'member__first_name', 'member__last_name', 'member__national_id')
    readonly_fields = ('loan_date', 'created_at')
    date_hierarchy = 'loan_date'
    fieldsets = (
        ('اطلاعات امانت', {
            'fields': ('book', 'member', 'loan_date', 'due_date', 'status')
        }),
        ('تمدید', {
            'fields': ('renewal_count', 'max_renewals')
        }),
        ('بازگشت', {
            'fields': ('returned_date',)
        }),
        ('متا', {
            'fields': ('issued_by', 'notes', 'created_at')
        }),
    )

    def is_overdue_display(self, obj):
        if obj.status == 'active' and obj.due_date < timezone.now().date():
            days = (timezone.now().date() - obj.due_date).days
            return format_html('<span style="color:red;">⚠ {} روز تأخیر</span>', days)
        if obj.status == 'returned':
            return '✅ برگشت داده شده'
        return '—'
    is_overdue_display.short_description = 'وضعیت'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('book', 'member')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'type', 'is_read', 'created_at')
    list_filter = ('is_read', 'type', 'created_at')
    search_fields = ('title', 'message', 'user__username')
    readonly_fields = ('created_at',)
    actions = ['mark_as_read']
    fieldsets = (
        ('اطلاعات اعلان', {
            'fields': ('user', 'loan', 'type', 'title', 'message')
        }),
        ('وضعیت', {
            'fields': ('is_read', 'created_at')
        }),
    )

    @admin.action(description='علامت‌گذاری به عنوان خوانده شده')
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f'{updated} اعلان به عنوان خوانده شده علامت‌گذاری شد.')