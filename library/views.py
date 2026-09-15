# library/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone
from django.contrib import messages
from .models import Book, Member, Loan
from .scrapers import search_book
from django.db.models import Count, Q, OuterRef, Subquery, IntegerField
from django.views.generic import ListView


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
        # تعداد امانت فعال برای هر کتاب
        active_loans = Loan.objects.filter(
            book=OuterRef('pk'), status='active'
        ).values('book').annotate(c=Count('id')).values('c')

        qs = qs.annotate(
            on_loan=Subquery(active_loans, output_field=IntegerField())
        )
        return qs.order_by('title')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # نیازی به تغییر نیست، property به صورت خودکار در دسترس است
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
def book_add(request):
    """اضافه کردن کتاب جدید به صورت دستی یا از فایل MARC"""
    if request.method == 'POST':
        try:
            title = request.POST.get('title', '').strip()
            isbn = request.POST.get('isbn', '').strip() or None

            if not title:
                messages.error(request, 'عنوان کتاب الزامی است.')
                return render(request, 'library/book_add.html')

            # بررسی تکراری بودن شابک
            if isbn:
                existing = Book.objects.filter(isbn=isbn).first()
                if existing:
                    messages.error(request, f'کتابی با این شابک قبلاً ثبت شده: {existing.title}')
                    return render(request, 'library/book_add.html')

            # ایجاد کتاب با همه فیلدهای جدید
            book = Book.objects.create(
                title=title,
                subtitle=request.POST.get('subtitle', ''),
                author=request.POST.get('author', ''),
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
            )

            messages.success(request, f'کتاب «{book.title}» با موفقیت اضافه شد.')
            return redirect('library:book_detail', pk=book.pk)

        except Exception as e:
            messages.error(request, f'خطا در ذخیره کتاب: {str(e)}')
            return render(request, 'library/book_add.html')

    return render(request, 'library/book_add.html')

def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    active_loan = Loan.objects.filter(book=book, status='active').first()
    return render(request, 'library/book_detail.html', {
        'book': book,
        'active_loan': active_loan,
    })


@login_required
def book_search_online(request):
    """جستجو در کتابخانه ملی / ketab.ir و ذخیره نتیجه."""
    query = request.GET.get('q', '')
    results = []

    if query:
        results = search_book(query)
        if not results:
            messages.warning(request, 'کتابی با این مشخصات در منابع جستجو یافت نشد. لطفاً عبارت دیگری را امتحان کنید.')

    return render(request, 'library/book_search.html', {
        'results': results,
        'query': query,
    })


@login_required
def book_import(request):
    """ذخیره کتاب جستجوشده به پایگاه داده."""
    if request.method == 'POST':
        book, created = Book.objects.get_or_create(
            isbn=request.POST.get('isbn') or None,
            defaults={
                'title':     request.POST['title'],
                'author':    request.POST.get('author', ''),
                'publisher': request.POST.get('publisher', ''),
                'publish_year': request.POST.get('year') or None,
                'isbn':      request.POST.get('isbn') or None,
            }
        )
        if created:
            messages.success(request, f'کتاب «{book.title}» اضافه شد.')
        else:
            messages.info(request, 'این کتاب قبلاً در سیستم موجود است.')
        return redirect('library:book_detail', pk=book.pk)
    return redirect('library:book_search_online')


# ── Member ──────────────────────────────────────────────────────────────────

@login_required
def member_list(request):
    query = request.GET.get('q', '')
    members = Member.objects.all()
    if query:
        members = members.filter(
            Q(full_name__icontains=query) |
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


@login_required
def loan_list(request):
    """نمایش لیست تمام امانت‌ها"""
    loans = Loan.objects.all().select_related('book', 'member').order_by('-loan_date')

    # فیلتر بر اساس وضعیت
    status = request.GET.get('status', '')
    if status:
        loans = loans.filter(status=status)

    # جستجو
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
def book_add(request):
    """اضافه کردن کتاب جدید به صورت دستی"""
    if request.method == 'POST':
        try:
            title = request.POST.get('title')
            isbn = request.POST.get('isbn', '').strip()

            if not title:
                messages.error(request, 'عنوان کتاب الزامی است.')
                return render(request, 'library/book_add.html')

            # بررسی تکراری بودن شابک
            if isbn:
                existing_book = Book.objects.filter(isbn=isbn).first()
                if existing_book:
                    messages.error(request,
                                   f'❗ کتابی با این شابک ("{isbn}") قبلاً در سیستم ثبت شده است: "{existing_book.title}"')
                    return render(request, 'library/book_add.html')

            # ایجاد کتاب
            book = Book.objects.create(
                title=title,
                author=request.POST.get('author', ''),
                publisher=request.POST.get('publisher', ''),
                publish_year=request.POST.get('publish_year', ''),
                isbn=isbn if isbn else None,
                total_copies=int(request.POST.get('total_copies', 1)),
            )
            messages.success(request, f'کتاب «{book.title}» با موفقیت اضافه شد.')
            return redirect('library:book_detail', pk=book.pk)

        except Exception as e:
            messages.error(request, f'خطا در ذخیره کتاب: {str(e)}')
            return render(request, 'library/book_add.html')

    return render(request, 'library/book_add.html')

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
    return render(request, 'library/member_list.html', {  # ← نام قالب صحیح
        'members': members,
        'query': query,
    })


@login_required
def member_detail(request, pk):
    member = get_object_or_404(Member, pk=pk)
    loans = Loan.objects.filter(member=member).select_related('book').order_by('-loan_date')
    return render(request, 'library/member_detail.html', {  # ← نام قالب صحیح
        'member': member,
        'loans': loans,
    })


@login_required
def book_edit(request, pk):
    """ویرایش کتاب موجود"""
    book = get_object_or_404(Book, pk=pk)

    if request.method == 'POST':
        try:
            title = request.POST.get('title')
            isbn = request.POST.get('isbn', '').strip()

            if not title:
                messages.error(request, 'عنوان کتاب الزامی است.')
                return render(request, 'library/book_edit.html', {'book': book})

            # بررسی تکراری بودن شابک (به جز خود کتاب)
            if isbn:
                existing_book = Book.objects.filter(isbn=isbn).exclude(pk=pk).first()
                if existing_book:
                    messages.error(request,
                                   f'❗ کتابی با این شابک ("{isbn}") قبلاً در سیستم ثبت شده است: "{existing_book.title}"')
                    return render(request, 'library/book_edit.html', {'book': book})

            # به‌روزرسانی کتاب
            book.title = title
            book.author = request.POST.get('author', '')
            book.publisher = request.POST.get('publisher', '')
            book.publish_year = request.POST.get('publish_year', '')
            book.isbn = isbn if isbn else None
            book.total_copies = int(request.POST.get('total_copies', 1))
            book.save()

            messages.success(request, f'کتاب «{book.title}» با موفقیت ویرایش شد.')
            return redirect('library:book_detail', pk=book.pk)

        except Exception as e:
            messages.error(request, f'خطا در ویرایش کتاب: {str(e)}')
            return render(request, 'library/book_edit.html', {'book': book})

    return render(request, 'library/book_edit.html', {'book': book})