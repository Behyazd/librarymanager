# library/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, OuterRef, Subquery, IntegerField
from django.utils import timezone
from django.contrib import messages
from django.views.generic import ListView
from django.http import JsonResponse
from .models import Book, Member, Loan, Notification
from .scrapers import search_book


# ── Helper: Normalize Persian text ──────────────────────────────────────────

def normalize_persian(text):
    """نرمال‌سازی متن فارسی برای جستجو"""
    if not text:
        return ''
    text = text.replace('\u200c', ' ')
    text = text.replace('ي', 'ی').replace('ك', 'ک')
    text = text.replace('٠', '۰').replace('١', '۱').replace('٢', '۲').replace('٣', '۳').replace('٤', '۴')
    text = text.replace('٥', '۵').replace('٦', '۶').replace('٧', '۷').replace('٨', '۸').replace('٩', '۹')
    text = ' '.join(text.split())
    return text


def build_search_q(field, value):
    """ساخت Q object برای جستجوی نرمال‌شده"""
    normalized = normalize_persian(value)
    words = normalized.split()

    q = Q()
    for word in words:
        if word:
            q &= Q(**{f'{field}__icontains': word})

    return q if words else Q()


# ── Book list & search ──────────────────────────────────────────────────────

class BookListView(ListView):
    model = Book
    template_name = 'library/book_list.html'
    context_object_name = 'books'
    paginate_by = 20

    def get_queryset(self):
        qs = Book.objects.all()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(author__icontains=q) |
                Q(isbn__icontains=q)
            )

        active_loans = Loan.objects.filter(
            book=OuterRef('pk'), status='active'
        ).values('book').annotate(c=Count('id')).values('c')

        qs = qs.annotate(
            on_loan=Subquery(active_loans, output_field=IntegerField())
        )
        return qs.order_by('title')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        return ctx


@login_required
def book_list(request):
    query = request.GET.get('q', '')
    books = Book.objects.all()
    if query:
        books = books.filter(
            Q(title__icontains=query) |
            Q(author__icontains=query) |
            Q(isbn__icontains=query)
        )
    return render(request, 'library/book_list.html', {'books': books, 'query': query})


@login_required
def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    active_loan = Loan.objects.filter(book=book, status='active').first()
    return render(request, 'library/book_detail.html', {
        'book': book,
        'active_loan': active_loan,
    })


@login_required
def book_search_online(request):
    query = request.GET.get('q', '')
    results = []
    if query:
        results = search_book(query)
    return render(request, 'library/book_search.html', {
        'results': results,
        'query': query,
    })


@login_required
def book_import(request):
    if request.method == 'POST':
        book, created = Book.objects.get_or_create(
            isbn=request.POST.get('isbn') or None,
            defaults={
                'title': request.POST['title'],
                'author': request.POST.get('author', ''),
                'publisher': request.POST.get('publisher', ''),
                'publish_year': request.POST.get('year') or None,
                'isbn': request.POST.get('isbn') or None,
            }
        )
        if created:
            messages.success(request, f'کتاب «{book.title}» اضافه شد.')
        else:
            messages.info(request, 'این کتاب قبلاً در سیستم موجود است.')
        return redirect('library:book_detail', pk=book.pk)
    return redirect('library:book_search_online')


@login_required
def book_add(request):
    if request.method == 'POST':
        try:
            title = request.POST.get('title', '').strip()
            isbn = request.POST.get('isbn', '').strip() or None

            if not title:
                messages.error(request, 'عنوان کتاب الزامی است.')
                return render(request, 'library/book_add.html')

            if isbn:
                existing = Book.objects.filter(isbn=isbn).first()
                if existing:
                    messages.error(request, f'کتابی با این شابک قبلاً ثبت شده: {existing.title}')
                    return render(request, 'library/book_add.html')

            book = Book.objects.create(
                title=title,
                subtitle=request.POST.get('subtitle', ''),
                author=request.POST.get('author', ''),
                author_dates=request.POST.get('author_dates', ''),
                isbn=isbn,
                publisher=request.POST.get('publisher', ''),
                publish_place=request.POST.get('publish_place', ''),
                publish_year=request.POST.get('publish_year', ''),
                pages=request.POST.get('pages', ''),
                dimensions=request.POST.get('dimensions', ''),
                dewey_class=request.POST.get('dewey_class', ''),
                lcc_class=request.POST.get('lcc_class', ''),
                national_biblio_number=request.POST.get('national_biblio_number', ''),
                subject=request.POST.get('subject', ''),
                notes=request.POST.get('notes', ''),
                fapa=request.POST.get('fapa', ''),
                marc_record=request.POST.get('marc_record', ''),
                total_copies=int(request.POST.get('total_copies', 1)),
                added_by=request.user,
                volume=request.POST.get('volume', ''),
                series=request.POST.get('series', ''),
                series_number=request.POST.get('series_number') or None,
            )

            messages.success(request, f'کتاب «{book.title}» با موفقیت اضافه شد.')
            return redirect('library:book_detail', pk=book.pk)

        except Exception as e:
            messages.error(request, f'خطا در ذخیره کتاب: {str(e)}')
            return render(request, 'library/book_add.html')

    return render(request, 'library/book_add.html')


@login_required
def book_edit(request, pk):
    book = get_object_or_404(Book, pk=pk)

    if request.method == 'POST':
        try:
            title = request.POST.get('title', '').strip()
            isbn = request.POST.get('isbn', '').strip() or None

            if not title:
                messages.error(request, 'عنوان کتاب الزامی است.')
                return render(request, 'library/book_edit.html', {'book': book})

            if isbn:
                existing = Book.objects.filter(isbn=isbn).exclude(pk=pk).first()
                if existing:
                    messages.error(request, f'کتابی با این شابک قبلاً ثبت شده: {existing.title}')
                    return render(request, 'library/book_edit.html', {'book': book})

            book.title = title
            book.subtitle = request.POST.get('subtitle', '')
            book.author = request.POST.get('author', '')
            book.author_dates = request.POST.get('author_dates', '')
            book.isbn = isbn
            book.national_biblio_number = request.POST.get('national_biblio_number', '')
            book.publisher = request.POST.get('publisher', '')
            book.publish_place = request.POST.get('publish_place', '')
            book.publish_year = request.POST.get('publish_year', '')
            book.pages = request.POST.get('pages', '')
            book.dimensions = request.POST.get('dimensions', '')
            book.dewey_class = request.POST.get('dewey_class', '')
            book.lcc_class = request.POST.get('lcc_class', '')
            book.fapa = request.POST.get('fapa', '')
            book.location = request.POST.get('location', '')
            book.subject = request.POST.get('subject', '')
            book.notes = request.POST.get('notes', '')
            book.total_copies = int(request.POST.get('total_copies', 1))
            book.save()
            book.volume = request.POST.get('volume', '')
            book.series = request.POST.get('series', '')
            book.series_number = request.POST.get('series_number') or None

            messages.success(request, f'کتاب «{book.title}» با موفقیت ویرایش شد.')
            return redirect('library:book_detail', pk=book.pk)

        except Exception as e:
            messages.error(request, f'خطا در ویرایش کتاب: {str(e)}')
            return render(request, 'library/book_edit.html', {'book': book})

    return render(request, 'library/book_edit.html', {'book': book})


# ── Advanced Search ─────────────────────────────────────────────────────────

@login_required
def advanced_search(request):
    """جستجوی پیشرفته با نرمال‌سازی متن فارسی"""
    books = Book.objects.all()
    query_params = {}

    title = request.GET.get('title', '').strip()
    author = request.GET.get('author', '').strip()
    isbn = request.GET.get('isbn', '').strip()
    publisher = request.GET.get('publisher', '').strip()
    publish_year = request.GET.get('publish_year', '').strip()
    subject = request.GET.get('subject', '').strip()
    dewey_from = request.GET.get('dewey_from', '').strip()
    dewey_to = request.GET.get('dewey_to', '').strip()
    only_available = request.GET.get('only_available', '')

    if title:
        books = books.filter(build_search_q('title', title) | build_search_q('subtitle', title))
        query_params['title'] = title
    if author:
        books = books.filter(build_search_q('author', author))
        query_params['author'] = author
    if isbn:
        books = books.filter(isbn__icontains=isbn)
        query_params['isbn'] = isbn
    if publisher:
        books = books.filter(build_search_q('publisher', publisher))
        query_params['publisher'] = publisher
    if publish_year:
        books = books.filter(publish_year__icontains=publish_year)
        query_params['publish_year'] = publish_year
    if subject:
        books = books.filter(build_search_q('subject', subject))
        query_params['subject'] = subject
    if dewey_from:
        books = books.filter(dewey_class__gte=dewey_from)
        query_params['dewey_from'] = dewey_from
    if dewey_to:
        books = books.filter(dewey_class__lte=dewey_to)
        query_params['dewey_to'] = dewey_to
    if only_available:
        books = [b for b in books if b.available_copies > 0]
        query_params['only_available'] = only_available

    sort_by = request.GET.get('sort_by', 'title')
    if sort_by in ['title', 'author', 'publish_year', 'created_at']:
        if not only_available:
            books = books.order_by(sort_by)

    total_count = len(books) if only_available else books.count()

    return render(request, 'library/advanced_search.html', {
        'books': books,
        'query_params': query_params,
        'total_count': total_count,
        'is_search': any([title, author, isbn, publisher, publish_year, subject, dewey_from, dewey_to, only_available]),
    })


# ── Reports ─────────────────────────────────────────────────────────────────

@login_required
def reports(request):
    """صفحه گزارش‌گیری"""
    today = timezone.now().date()

    total_books = Book.objects.count()
    total_copies = sum(b.total_copies for b in Book.objects.all())
    total_members = Member.objects.count()
    active_members = Member.objects.filter(is_active=True).count()

    active_loans = Loan.objects.filter(status='active').count()
    overdue_loans = Loan.objects.filter(
        status='active',
        due_date__lt=today
    ).count()
    returned_loans = Loan.objects.filter(status='returned').count()

    available_books = 0
    for book in Book.objects.all():
        if book.available_copies > 0:
            available_books += 1

    overdue_loan_list = Loan.objects.filter(
        status='active',
        due_date__lt=today
    ).select_related('book', 'member').order_by('due_date')

    popular_books = Book.objects.annotate(
        loan_count=Count('loans')
    ).filter(loan_count__gt=0).order_by('-loan_count')[:10]

    active_member_list = Member.objects.annotate(
        loan_count=Count('loans', filter=Q(loans__status='active'))
    ).order_by('-loan_count')[:10]

    recent_loans = Loan.objects.select_related('book', 'member').order_by('-loan_date')[:10]

    context = {
        'total_books': total_books,
        'total_copies': total_copies,
        'available_books': available_books,
        'total_members': total_members,
        'active_members': active_members,
        'active_loans': active_loans,
        'overdue_loans': overdue_loans,
        'returned_loans': returned_loans,
        'overdue_loan_list': overdue_loan_list,
        'popular_books': popular_books,
        'active_member_list': active_member_list,
        'recent_loans': recent_loans,
    }

    return render(request, 'library/reports.html', context)


# ── Reports Detail Pages ────────────────────────────────────────────────────

@login_required
def report_books(request):
    books = Book.objects.all().order_by('title')
    return render(request, 'library/report_list.html', {
        'title': '📚 همه کتاب‌ها',
        'items': books,
        'type': 'books',
        'count': books.count(),
    })


@login_required
def report_available_books(request):
    books = [b for b in Book.objects.all() if b.available_copies > 0]
    return render(request, 'library/report_list.html', {
        'title': '✅ کتاب‌های موجود',
        'items': books,
        'type': 'books',
        'count': len(books),
    })


@login_required
def report_members(request):
    members = Member.objects.all().order_by('last_name', 'first_name')
    return render(request, 'library/report_list.html', {
        'title': '👥 همه اعضا',
        'items': members,
        'type': 'members',
        'count': members.count(),
    })


@login_required
def report_active_loans(request):
    loans = Loan.objects.filter(status='active').select_related('book', 'member').order_by('due_date')
    return render(request, 'library/report_list.html', {
        'title': '📋 امانت‌های فعال',
        'items': loans,
        'type': 'loans',
        'count': loans.count(),
    })


@login_required
def report_overdue_loans(request):
    today = timezone.now().date()
    loans = Loan.objects.filter(
        status='active',
        due_date__lt=today
    ).select_related('book', 'member').order_by('due_date')
    return render(request, 'library/report_list.html', {
        'title': '⏰ امانت‌های سررسید گذشته',
        'items': loans,
        'type': 'loans',
        'count': loans.count(),
    })


# ── Autocomplete API ────────────────────────────────────────────────────────

@login_required
def autocomplete_books(request):
    """جستجوی لحظه‌ای کتاب‌ها"""
    query = request.GET.get('q', '').strip()

    if not query or len(query) < 2:
        return JsonResponse({'results': []})

    normalized = normalize_persian(query)
    words = normalized.split()

    q = Q()
    for word in words:
        if word:
            q &= (Q(title__icontains=word) | Q(author__icontains=word) | Q(isbn__icontains=word))

    books = Book.objects.filter(q)[:10]

    results = []
    for book in books:
        results.append({
            'id': book.id,
            'title': book.title,
            'author': book.author,
            'isbn': book.isbn or '',
            'available': book.available_copies,
            'total': book.total_copies,
        })

    return JsonResponse({'results': results})


# ── Member ──────────────────────────────────────────────────────────────────

@login_required
def member_list(request):
    query = request.GET.get('q', '')
    members = Member.objects.all()
    if query:
        members = members.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(national_id__icontains=query) |
            Q(phone__icontains=query)
        )
    return render(request, 'library/member_list.html', {
        'members': members, 'query': query,
    })


@login_required
def member_detail(request, pk):
    member = get_object_or_404(Member, pk=pk)
    loans = Loan.objects.filter(member=member).select_related('book').order_by('-loan_date')
    return render(request, 'library/member_detail.html', {
        'member': member, 'loans': loans,
    })


# ── Loan ────────────────────────────────────────────────────────────────────

@login_required
def loan_create(request, book_pk):
    book = get_object_or_404(Book, pk=book_pk)
    if request.method == 'POST':
        member = get_object_or_404(Member, pk=request.POST['member_id'])
        if Loan.objects.filter(book=book, status='active').exists():
            messages.error(request, 'این کتاب در حال حاضر امانت داده شده است.')
        else:
            Loan.objects.create(book=book, member=member)
            messages.success(request, f'امانت «{book.title}» به {member.full_name} ثبت شد.')
        return redirect('library:book_detail', pk=book.pk)
    members = Member.objects.filter(is_active=True)
    return render(request, 'library/loan_create.html', {'book': book, 'members': members})


@login_required
def loan_list(request):
    loans = Loan.objects.all().select_related('book', 'member').order_by('-loan_date')

    status = request.GET.get('status', '')
    if status:
        loans = loans.filter(status=status)

    q = request.GET.get('q', '')
    if q:
        loans = loans.filter(
            Q(book__title__icontains=q) |
            Q(member__first_name__icontains=q) |
            Q(member__last_name__icontains=q)
        )

    return render(request, 'library/loan_list.html', {
        'loans': loans,
        'status': status,
        'q': q,
    })


@login_required
def loan_return(request, pk):
    loan = get_object_or_404(Loan, pk=pk, status='active')
    if request.method == 'POST':
        loan.returned_date = timezone.now().date()
        loan.status = 'returned'
        loan.save()
        messages.success(request, f'کتاب «{loan.book.title}» بازگشت داده شد.')
        return redirect('library:book_detail', pk=loan.book.pk)
    return render(request, 'library/loan_confirm_return.html', {'loan': loan})


@login_required
def loan_extend(request, pk):
    loan = get_object_or_404(Loan, pk=pk, status='active')
    if request.method == 'POST':
        if loan.can_renew():
            loan.renew()
            messages.success(request, 'تمدید امانت انجام شد.')
        else:
            messages.error(request, 'امکان تمدید این امانت وجود ندارد.')
        return redirect('library:member_detail', pk=loan.member.pk)
    return render(request, 'library/loan_confirm_extend.html', {'loan': loan})


# ==================== Export Views ====================

@login_required
def export_books_excel(request):
    """خروجی Excel از کتاب‌ها"""
    from .exports import export_books_to_excel

    books = Book.objects.all().order_by('title')

    q = request.GET.get('q', '').strip()
    if q:
        books = books.filter(
            Q(title__icontains=q) |
            Q(author__icontains=q) |
            Q(isbn__icontains=q)
        )

    if request.GET.get('only_available'):
        books = [b for b in books if b.available_copies > 0]

    library_name = request.GET.get('library_name', 'کتابخانه من')

    today = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f'books_{today}.xlsx'

    return export_books_to_excel(books, library_name, filename)


@login_required
def export_books_pdf(request):
    """خروجی PDF از کتاب‌ها"""
    from .exports import export_books_to_pdf

    books = Book.objects.all().order_by('title')

    q = request.GET.get('q', '').strip()
    if q:
        books = books.filter(
            Q(title__icontains=q) |
            Q(author__icontains=q) |
            Q(isbn__icontains=q)
        )

    if request.GET.get('only_available'):
        books = [b for b in books if b.available_copies > 0]

    library_name = request.GET.get('library_name', 'کتابخانه من')

    today = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f'books_{today}.pdf'

    return export_books_to_pdf(books, library_name, filename)


@login_required
def export_labels_pdf(request):
    """خروجی PDF برچسب‌های QR"""
    from .exports import export_labels_to_pdf

    book_ids = request.GET.getlist('book_ids')

    if book_ids:
        books = Book.objects.filter(pk__in=book_ids).order_by('title')
    else:
        books = Book.objects.all().order_by('title')

    if not books:
        messages.error(request, 'کتابی برای چاپ برچسب وجود ندارد.')
        return redirect('library:book_list')

    today = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f'labels_{today}.pdf'

    return export_labels_to_pdf(books, filename)


@login_required
def print_labels(request):
    """صفحه انتخاب کتاب برای چاپ برچسب"""
    books = Book.objects.all().order_by('title')
    return render(request, 'library/print_labels.html', {'books': books})


@login_required
def print_spines(request):
    """صفحه چاپ عطف کتاب"""
    books = Book.objects.all().order_by('title')
    return render(request, 'library/print_spine.html', {'books': books})


@login_required
def export_spine_pdf(request):
    """خروجی PDF عطف کتاب"""
    from .exports import export_spine_pdf as export_spine

    if request.method != 'POST':
        return redirect('library:print_spines')

    book_ids = request.POST.getlist('book_ids')

    if not book_ids:
        messages.error(request, 'هیچ کتابی انتخاب نشده است.')
        return redirect('library:print_spines')

    books = Book.objects.filter(pk__in=book_ids).order_by('title')

    if not books:
        messages.error(request, 'کتابی برای چاپ عطف وجود ندارد.')
        return redirect('library:print_spines')

    library_name = request.POST.get('library_name', 'کتابخانه')
    spine_height = int(request.POST.get('spine_height', 60))
    spine_width = int(request.POST.get('spine_width', 25))
    classification = request.POST.get('classification', 'dewey')

    options = {
        'show_title': 'show_title' in request.POST,
        'show_author': 'show_author' in request.POST,
        'show_volume': 'show_volume' in request.POST,
        'show_library': 'show_library' in request.POST,
    }

    today = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f'spines_{today}.pdf'

    return export_spine(
        books,
        library_name,
        spine_height,
        spine_width,
        classification,
        options,
        filename
    )


# ==================== Cover Image Upload ====================

@login_required
def upload_cover(request, pk):
    """آپلود تصویر جلد کتاب"""
    book = get_object_or_404(Book, pk=pk)

    if request.method == 'POST':
        if 'cover_image' not in request.FILES:
            messages.error(request, 'فایلی انتخاب نشده است.')
            return redirect('library:book_detail', pk=book.pk)

        cover = request.FILES['cover_image']

        if not cover.content_type.startswith('image/'):
            messages.error(request, 'فقط فایل‌های تصویری مجاز هستند.')
            return redirect('library:book_detail', pk=book.pk)

        if cover.size > 5 * 1024 * 1024:
            messages.error(request, 'حجم فایل نباید بیشتر از ۵ مگابایت باشد.')
            return redirect('library:book_detail', pk=book.pk)

        if book.cover_image:
            try:
                book.cover_image.delete(save=False)
            except:
                pass

        book.cover_image = cover
        book.save()

        messages.success(request, 'تصویر جلد با موفقیت آپلود شد.')
        return redirect('library:book_detail', pk=book.pk)

    return render(request, 'library/upload_cover.html', {'book': book})


@login_required
def delete_cover(request, pk):
    """حذف تصویر جلد کتاب"""
    book = get_object_or_404(Book, pk=pk)

    if book.cover_image:
        book.cover_image.delete(save=False)
        book.cover_image = None
        book.save()
        messages.success(request, 'تصویر جلد حذف شد.')

    return redirect('library:book_detail', pk=book.pk)

# ==================== Barcode Scanner ====================

@login_required
def scan_barcode(request):
    """API اسکن بارکد از تصویر"""
    if request.method != 'POST':
        return JsonResponse({'error': 'فقط POST مجاز است'}, status=405)

    if 'image' not in request.FILES:
        return JsonResponse({'error': 'تصویری ارسال نشده است'}, status=400)

    try:
        import cv2
        import numpy as np
        from pyzbar.pyzbar import decode

        image_file = request.FILES['image']
        # خواندن تصویر از فایل
        image_bytes = image_file.read()
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            return JsonResponse({'error': 'تصویر نامعتبر است'}, status=400)

        # تشخیص بارکد
        barcodes = decode(img)

        if not barcodes:
            return JsonResponse({'error': 'بارکدی یافت نشد'}, status=404)

        # استخراج ISBN از بارکد (EAN-13 با 978 یا 979)
        isbn = None
        for barcode in barcodes:
            barcode_data = barcode.data.decode('utf-8')
            barcode_type = barcode.type

            # ISBN-13 با 978 یا 979
            if barcode_type == 'EAN13' and (barcode_data.startswith('978') or barcode_data.startswith('979')):
                isbn = barcode_data
                break
            # اگر ISBN-10 بود (نادر)
            elif barcode_type == 'EAN13' and len(barcode_data) == 13:
                isbn = barcode_data

        if not isbn:
            # اگر ISBN پیدا نشد، اولین بارکد را برگردان
            isbn = barcodes[0].data.decode('utf-8')

        return JsonResponse({
            'success': True,
            'isbn': isbn,
            'barcode_type': barcodes[0].type,
        })

    except ImportError:
        return JsonResponse({'error': 'کتابخانه pyzbar نصب نیست'}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'خطا در پردازش: {str(e)}'}, status=500)