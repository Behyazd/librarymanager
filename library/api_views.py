# library/api_views.py
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.db.models import Q
from .models import Book, Member, Loan, Notification
from .serializers import (
    BookSerializer, MemberSerializer, LoanSerializer,
    NotificationSerializer, RegisterSerializer, UserSerializer
)
from .marc_parser import parse_marc_file


# ==================== Book ViewSet ====================

class BookViewSet(viewsets.ModelViewSet):
    """API برای مدیریت کتاب‌ها"""
    queryset = Book.objects.all().order_by('title')
    serializer_class = BookSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'author', 'isbn', 'publisher']
    ordering_fields = ['title', 'author', 'created_at']

    @action(detail=True, methods=['get'])
    def loans(self, request, pk=None):
        book = self.get_object()
        loans = Loan.objects.filter(book=book)
        serializer = LoanSerializer(loans, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def borrow(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')

        if not member_id:
            return Response(
                {'error': 'member_id الزامی است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            member = Member.objects.get(pk=member_id, is_active=True)
        except Member.DoesNotExist:
            return Response(
                {'error': 'عضو یافت نشد یا غیرفعال است'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not book.is_available:
            return Response(
                {'error': 'این کتاب در حال حاضر موجود نیست'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not member.can_borrow:
            return Response(
                {'error': 'عضو نمی‌تواند کتاب بیشتری امانت بگیرد'},
                status=status.HTTP_400_BAD_REQUEST
            )

        loan = Loan.objects.create(book=book, member=member)
        serializer = LoanSerializer(loan)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ==================== Member ViewSet ====================

class MemberViewSet(viewsets.ModelViewSet):
    """API برای مدیریت اعضا"""
    queryset = Member.objects.all().order_by('last_name', 'first_name')
    serializer_class = MemberSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'national_id', 'phone', 'member_code']
    ordering_fields = ['first_name', 'last_name', 'join_date']

    @action(detail=True, methods=['get'])
    def loans(self, request, pk=None):
        member = self.get_object()
        loans = Loan.objects.filter(member=member)
        serializer = LoanSerializer(loans, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def active_loans(self, request, pk=None):
        member = self.get_object()
        loans = Loan.objects.filter(member=member, status='active')
        serializer = LoanSerializer(loans, many=True)
        return Response(serializer.data)


# ==================== Loan ViewSet ====================

class LoanViewSet(viewsets.ModelViewSet):
    """API برای مدیریت امانت‌ها"""
    queryset = Loan.objects.all().order_by('-loan_date')
    serializer_class = LoanSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['book__title', 'member__first_name', 'member__last_name']
    ordering_fields = ['loan_date', 'due_date', 'status']

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        loan = self.get_object()
        if loan.status == 'returned':
            return Response(
                {'error': 'این کتاب قبلاً برگشت داده شده است'},
                status=status.HTTP_400_BAD_REQUEST
            )
        loan.return_book()
        serializer = LoanSerializer(loan)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def renew(self, request, pk=None):
        loan = self.get_object()
        if loan.status != 'active':
            return Response(
                {'error': 'فقط امانت‌های فعال قابل تمدید هستند'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not loan.can_renew():
            return Response(
                {'error': 'امکان تمدید وجود ندارد'},
                status=status.HTTP_400_BAD_REQUEST
            )
        loan.renew()
        serializer = LoanSerializer(loan)
        return Response(serializer.data)


# ==================== Notification ViewSet ====================

class NotificationViewSet(viewsets.ModelViewSet):
    """API برای مدیریت اعلان‌ها"""
    queryset = Notification.objects.all().order_by('-created_at')
    serializer_class = NotificationSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'message']

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        Notification.objects.filter(is_read=False).update(is_read=True)
        return Response({'message': 'همه اعلان‌ها خوانده شدند'})


# ==================== Auth ViewSet ====================

class AuthViewSet(viewsets.ViewSet):
    """API برای احراز هویت"""

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def login(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response(
                {'error': 'نام کاربری و رمز عبور الزامی است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {'error': 'نام کاربری یا رمز عبور اشتباه است'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.check_password(password):
            return Response(
                {'error': 'نام کاربری یا رمز عبور اشتباه است'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })


# ==================== Simple Login ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def simple_login(request):
    """ورود ساده با username و password"""
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response(
            {'error': 'نام کاربری و رمز عبور الزامی است'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return Response(
            {'error': 'نام کاربری یا رمز عبور اشتباه است'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not user.check_password(password):
        return Response(
            {'error': 'نام کاربری یا رمز عبور اشتباه است'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    refresh = RefreshToken.for_user(user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': UserSerializer(user).data,
    })


# ==================== MARC Parser Views ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def parse_marc(request):
    """دریافت یک یا چند فایل MARC و برگرداندن فیلدهای استخراج شده"""
    files = request.FILES.getlist('files')

    if not files:
        if 'file' in request.FILES:
            files = [request.FILES['file']]
        else:
            return Response(
                {'error': 'فایل MARC ارسال نشده است'},
                status=status.HTTP_400_BAD_REQUEST
            )

    all_records = []
    errors = []

    for uploaded_file in files:
        if not uploaded_file.name.endswith(('.txt', '.mrc', '.marc')):
            errors.append(f"فرمت فایل {uploaded_file.name} پشتیبانی نمی‌شود")
            continue

        try:
            file_bytes = uploaded_file.read()
            records = parse_marc_file(file_bytes)

            # اضافه کردن نام فایل به هر رکورد
            for record in records:
                record['source_file'] = uploaded_file.name

            all_records.extend(records)
        except Exception as e:
            errors.append(f"خطا در پردازش {uploaded_file.name}: {str(e)}")

    if not all_records:
        return Response(
            {'error': 'هیچ رکورد MARC معتبری یافت نشد', 'errors': errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    return Response({
        'count': len(all_records),
        'files_count': len(files),
        'records': all_records,
        'errors': errors,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_marc(request):
    """دریافت فایل MARC و ذخیره همه رکوردها در دیتابیس"""
    files = request.FILES.getlist('files')

    if not files:
        if 'file' in request.FILES:
            files = [request.FILES['file']]
        else:
            return Response(
                {'error': 'فایل MARC ارسال نشده است'},
                status=status.HTTP_400_BAD_REQUEST
            )

    # ✅ تابع پاکسازی کاراکتر NUL
    def clean_text(text):
        if not text:
            return ''
        return ''.join(c for c in str(text) if c != '\x00')

    imported_count = 0
    skipped_count = 0
    total_records = 0
    errors = []
    imported_books = []

    for uploaded_file in files:
        if not uploaded_file.name.endswith(('.txt', '.mrc', '.marc')):
            errors.append(f"فرمت فایل {uploaded_file.name} پشتیبانی نمی‌شود")
            continue

        try:
            file_bytes = uploaded_file.read()
            records = parse_marc_file(file_bytes)
            total_records += len(records)

            for record in records:
                try:
                    isbn = clean_text(record.get('isbn', '')).strip()
                    nbn = clean_text(record.get('national_biblio_number', '')).strip()

                    # بررسی تکراری
                    existing = None
                    if isbn:
                        existing = Book.objects.filter(isbn=isbn).first()
                    if not existing and nbn:
                        existing = Book.objects.filter(national_biblio_number=nbn).first()

                    if existing:
                        skipped_count += 1
                        continue

                    # ✅ پاکسازی همه فیلدهای متنی
                    book = Book.objects.create(
                        title=clean_text(record.get('title', 'بدون عنوان')) or 'بدون عنوان',
                        subtitle=clean_text(record.get('subtitle', '')),
                        author=clean_text(record.get('author', '')),
                        author_dates=clean_text(record.get('author_dates', '')),
                        isbn=isbn if isbn else None,
                        publisher=clean_text(record.get('publisher', '')),
                        publish_place=clean_text(record.get('publish_place', '')),
                        publish_year=clean_text(record.get('publish_year', '')),
                        pages=clean_text(record.get('pages', '')),
                        dimensions=clean_text(record.get('dimensions', '')),
                        dewey_class=clean_text(record.get('dewey_class', '')),
                        lcc_class=clean_text(record.get('lcc_class', '')),
                        national_biblio_number=nbn,
                        subject=clean_text(record.get('subject', '')),
                        notes=clean_text(record.get('notes', '')),
                        fapa=clean_text(record.get('fapa', '')),
                        marc_record=clean_text(record.get('marc_record', '')),
                        statement_of_responsibility=clean_text(record.get('statement_of_responsibility', '')),
                        added_by=request.user,
                    )
                    imported_count += 1
                    imported_books.append({
                        'id': book.id,
                        'title': book.title,
                        'author': book.author,
                    })

                except Exception as e:
                    errors.append(f"خطا در ذخیره رکورد: {str(e)}")
                    import traceback
                    traceback.print_exc()

        except Exception as e:
            errors.append(f"خطا در پردازش {uploaded_file.name}: {str(e)}")
            import traceback
            traceback.print_exc()

    return Response({
        'success': True,
        'total': total_records,
        'files_count': len(files),
        'imported': imported_count,
        'skipped': skipped_count,
        'errors': errors,
        'books': imported_books,
    })