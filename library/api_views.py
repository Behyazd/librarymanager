# library/api_views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.files.uploadedfile import UploadedFile
from .marc_parser import parse_marc_file

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from .models import Book, Member, Loan, Notification
from .serializers import (
    BookSerializer, MemberSerializer, LoanSerializer,
    NotificationSerializer, RegisterSerializer, UserSerializer
)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def parse_marc(request):
    """
    دریافت فایل MARC و برگرداندن فیلدهای استخراج شده به JSON
    """
    if 'file' not in request.FILES:
        return Response(
            {'error': 'فایل MARC ارسال نشده است'},
            status=status.HTTP_400_BAD_REQUEST
        )

    uploaded_file = request.FILES['file']

    # بررسی پسوند فایل
    if not uploaded_file.name.endswith(('.txt', '.mrc', '.marc')):
        return Response(
            {'error': 'فرمت فایل باید txt، mrc یا marc باشد'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        file_bytes = uploaded_file.read()
        records = parse_marc_file(file_bytes)

        if not records:
            return Response(
                {'error': 'هیچ رکورد MARC معتبری یافت نشد'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            'count': len(records),
            'records': records,
        })

    except Exception as e:
        return Response(
            {'error': f'خطا در پردازش فایل: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

class AuthViewSet(viewsets.ViewSet):
    # library/api_views.py (در AuthViewSet)
    @action(detail=False, methods=['post'])
    def simple_login(self, request):
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
            'user': UserSerializer(user).data
        })


    @action(detail=False, methods=['post'])
    def register(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ========== Book ViewSet ==========
class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all().order_by('title')
    serializer_class = BookSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'author', 'isbn', 'publisher']
    ordering_fields = ['title', 'author', 'created_at']

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


# ========== Member ViewSet ==========
class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all().order_by('last_name', 'first_name')
    serializer_class = MemberSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'national_id', 'phone', 'member_code']
    ordering_fields = ['first_name', 'last_name', 'join_date']


# ========== Loan ViewSet ==========
class LoanViewSet(viewsets.ModelViewSet):
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


# ========== Notification ViewSet ==========
class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all().order_by('-created_at')
    serializer_class = NotificationSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'message']

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        Notification.objects.filter(is_read=False).update(is_read=True)
        return Response({'message': 'همه اعلان‌ها خوانده شدند'})


# library/api_views.py (در انتهای فایل)

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json


@csrf_exempt
def simple_login(request):
    """یک ویو ساده برای تست ورود"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)

    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return JsonResponse({'error': 'Username and password required'}, status=400)

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=401)

    if not user.check_password(password):
        return JsonResponse({'error': 'Wrong password'}, status=401)

    refresh = RefreshToken.for_user(user)
    return JsonResponse({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
        }
    })