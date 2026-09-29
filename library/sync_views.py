# library/sync_views.py
"""
API Sync بین کلاینت و سرور
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
import json

from .models import (
    Book, Member, Loan, SyncLog, SyncQueue, Device, Conflict
)
from .serializers import BookSerializer, MemberSerializer, LoanSerializer


# ==================== Utility ====================

def get_client_ip(request):
    """دریافت IP کاربر"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


# ==================== Device Registration ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_device(request):
    """ثبت دستگاه جدید"""
    device_id = request.data.get('device_id')
    device_name = request.data.get('device_name', 'دستگاه ناشناخته')
    device_type = request.data.get('device_type', 'mobile')

    if not device_id:
        return Response({'error': 'device_id الزامی است'}, status=400)

    device, created = Device.objects.update_or_create(
        device_id=device_id,
        defaults={
            'device_name': device_name,
            'device_type': device_type,
            'user': request.user,
            'last_ip': get_client_ip(request),
            'is_active': True,
        }
    )

    return Response({
        'success': True,
        'device_id': device.device_id,
        'device_name': device.device_name,
        'created': created,
    })


# ==================== Push (ارسال به سرور) ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_push(request):
    """ارسال تغییرات از کلاینت به سرور"""
    changes = request.data.get('changes', [])
    device_id = request.data.get('device_id', 'unknown')

    if not changes:
        return Response({
            'success': True,
            'results': [],
            'message': 'تغییری برای ارسال نیست',
            'pushed_count': 0,
            'failed_count': 0,
        })

    # ثبت لاگ
    log = SyncLog.objects.create(
        device_identifier=device_id,
        user=request.user,
        action='push',
        status='in_progress'
    )

    results = []
    errors = []

    for change in changes:
        try:
            with transaction.atomic():
                result = process_change(change, request.user)
                results.append(result)
        except Exception as e:
            errors.append({
                'queue_id': change.get('queue_id'),
                'error': str(e)
            })

    # به‌روزرسانی لاگ
    log.pushed_count = len(results)
    log.conflict_count = len(errors)
    log.status = 'completed' if not errors else 'failed'
    log.completed_at = timezone.now()
    log.error_message = '\n'.join([e['error'] for e in errors])
    log.save()

    return Response({
        'success': len(errors) == 0,
        'results': results,
        'errors': errors,
        'server_time': int(timezone.now().timestamp()),
        'pushed_count': len(results),
        'failed_count': len(errors),
    })


def process_change(change, user):
    """پردازش یک تغییر"""
    model_name = change.get('model_name')
    action = change.get('action')
    data = change.get('data', {})
    server_id = change.get('server_id')
    queue_id = change.get('queue_id')

    # حذف فیلدهای محلی
    data.pop('local_id', None)
    data.pop('sync_status', None)
    data.pop('sync_action', None)

    if model_name == 'book':
        return process_book_change(action, data, server_id, queue_id, user)
    elif model_name == 'member':
        return process_member_change(action, data, server_id, queue_id, user)
    elif model_name == 'loan':
        return process_loan_change(action, data, server_id, queue_id, user)

    raise ValueError(f'مدل ناشناخته: {model_name}')


def process_book_change(action, data, server_id, queue_id, user):
    """پردازش تغییر کتاب"""

    # فیلدهای مجاز
    allowed_fields = [
        'title', 'subtitle', 'author', 'author_dates', 'isbn',
        'national_biblio_number', 'publisher', 'publish_place', 'publish_year',
        'pages', 'dimensions', 'dewey_class', 'lcc_class', 'subject',
        'notes', 'fapa', 'volume', 'series', 'series_number',
        'language', 'condition', 'location', 'total_copies',
        'statement_of_responsibility', 'marc_record'
    ]

    clean_data = {k: v for k, v in data.items() if k in allowed_fields}

    # تبدیل series_number به عدد یا None
    if 'series_number' in clean_data:
        if clean_data['series_number'] == '' or clean_data['series_number'] is None:
            clean_data['series_number'] = None
        else:
            try:
                clean_data['series_number'] = int(clean_data['series_number'])
            except (ValueError, TypeError):
                clean_data['series_number'] = None

    # تبدیل total_copies
    if 'total_copies' in clean_data:
        try:
            clean_data['total_copies'] = int(clean_data['total_copies'])
        except (ValueError, TypeError):
            clean_data['total_copies'] = 1

    # حذف فیلدهای خالی برای isbn
    if clean_data.get('isbn') == '':
        clean_data['isbn'] = None

    if action == 'create':
        # بررسی تکراری با ISBN
        isbn = clean_data.get('isbn')
        if isbn:
            existing = Book.objects.filter(isbn=isbn).first()
            if existing:
                # به‌روزرسانی
                for key, value in clean_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                existing.save()
                return {
                    'queue_id': queue_id,
                    'server_id': existing.id,
                    'action': 'updated',
                    'local_id': data.get('local_id'),
                }

        book = Book.objects.create(
            **clean_data,
            added_by=user
        )
        return {
            'queue_id': queue_id,
            'server_id': book.id,
            'action': 'created',
            'local_id': data.get('local_id'),
        }

    elif action == 'update':
        if not server_id:
            raise ValueError('server_id برای ویرایش لازم است')

        book = Book.objects.filter(pk=server_id).first()
        if not book:
            raise ValueError(f'کتاب با شناسه {server_id} یافت نشد')

        # بررسی تعارض
        local_updated = data.get('updated_at')
        if local_updated and book.updated_at:
            try:
                local_time = timezone.datetime.fromisoformat(local_updated.replace('Z', '+00:00'))
                if book.updated_at > local_time:
                    # تعارض
                    conflict = Conflict.objects.create(
                        model_name='book',
                        object_id=str(server_id),
                        local_data=data,
                        remote_data=BookSerializer(book).data,
                        local_updated_at=local_time,
                        remote_updated_at=book.updated_at,
                    )
                    return {
                        'queue_id': queue_id,
                        'server_id': server_id,
                        'action': 'conflict',
                        'conflict_id': conflict.id,
                        'local_id': data.get('local_id'),
                    }
            except (ValueError, AttributeError):
                pass

        # به‌روزرسانی
        for key, value in clean_data.items():
            if hasattr(book, key):
                setattr(book, key, value)
        book.save()

        return {
            'queue_id': queue_id,
            'server_id': book.id,
            'action': 'updated',
            'local_id': data.get('local_id'),
        }

    elif action == 'delete':
        if not server_id:
            raise ValueError('server_id برای حذف لازم است')

        Book.objects.filter(pk=server_id).delete()
        return {
            'queue_id': queue_id,
            'server_id': server_id,
            'action': 'deleted',
        }

    raise ValueError(f'عملیات ناشناخته: {action}')


def process_member_change(action, data, server_id, queue_id, user):
    """پردازش تغییر عضو"""
    allowed_fields = [
        'first_name', 'last_name', 'national_id', 'phone', 'address',
        'member_code', 'is_active', 'max_loans', 'notes'
    ]
    clean_data = {k: v for k, v in data.items() if k in allowed_fields}

    # حذف فیلدهای خالی
    if clean_data.get('national_id') == '':
        clean_data['national_id'] = None

    # تبدیل max_loans
    if 'max_loans' in clean_data:
        try:
            clean_data['max_loans'] = int(clean_data['max_loans'])
        except (ValueError, TypeError):
            clean_data['max_loans'] = 3

    if action == 'create':
        # بررسی تکراری با کد ملی
        national_id = clean_data.get('national_id')
        if national_id:
            existing = Member.objects.filter(national_id=national_id).first()
            if existing:
                for key, value in clean_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                existing.save()
                return {
                    'queue_id': queue_id,
                    'server_id': existing.id,
                    'action': 'updated',
                    'local_id': data.get('local_id'),
                }

        # بررسی تکراری با کد عضویت
        member_code = clean_data.get('member_code')
        if member_code:
            existing = Member.objects.filter(member_code=member_code).first()
            if existing:
                for key, value in clean_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                existing.save()
                return {
                    'queue_id': queue_id,
                    'server_id': existing.id,
                    'action': 'updated',
                    'local_id': data.get('local_id'),
                }

        member = Member.objects.create(**clean_data)
        return {
            'queue_id': queue_id,
            'server_id': member.id,
            'action': 'created',
            'local_id': data.get('local_id'),
        }

    elif action == 'update':
        if not server_id:
            raise ValueError('server_id برای ویرایش لازم است')

        member = Member.objects.filter(pk=server_id).first()
        if not member:
            raise ValueError(f'عضو با شناسه {server_id} یافت نشد')

        # بررسی تعارض
        local_updated = data.get('updated_at')
        if local_updated and member.created_at:
            try:
                local_time = timezone.datetime.fromisoformat(local_updated.replace('Z', '+00:00'))
                if member.created_at > local_time:
                    conflict = Conflict.objects.create(
                        model_name='member',
                        object_id=str(server_id),
                        local_data=data,
                        remote_data=MemberSerializer(member).data,
                        local_updated_at=local_time,
                        remote_updated_at=member.created_at,
                    )
                    return {
                        'queue_id': queue_id,
                        'server_id': server_id,
                        'action': 'conflict',
                        'conflict_id': conflict.id,
                        'local_id': data.get('local_id'),
                    }
            except (ValueError, AttributeError):
                pass

        for key, value in clean_data.items():
            if hasattr(member, key):
                setattr(member, key, value)
        member.save()

        return {
            'queue_id': queue_id,
            'server_id': member.id,
            'action': 'updated',
            'local_id': data.get('local_id'),
        }

    elif action == 'delete':
        if not server_id:
            raise ValueError('server_id برای حذف لازم است')

        Member.objects.filter(pk=server_id).delete()
        return {
            'queue_id': queue_id,
            'server_id': server_id,
            'action': 'deleted',
        }

    raise ValueError(f'عملیات ناشناخته: {action}')


def process_loan_change(action, data, server_id, queue_id, user):
    """پردازش تغییر امانت"""
    allowed_fields = [
        'book_id', 'member_id', 'loan_date', 'due_date',
        'returned_date', 'status', 'renewal_count', 'notes'
    ]
    clean_data = {k: v for k, v in data.items() if k in allowed_fields}

    if action == 'create':
        loan = Loan.objects.create(**clean_data, issued_by=user)
        return {
            'queue_id': queue_id,
            'server_id': loan.id,
            'action': 'created',
            'local_id': data.get('local_id'),
        }

    elif action == 'update':
        if not server_id:
            raise ValueError('server_id برای ویرایش لازم است')

        loan = Loan.objects.filter(pk=server_id).first()
        if not loan:
            raise ValueError(f'امانت با شناسه {server_id} یافت نشد')

        for key, value in clean_data.items():
            if hasattr(loan, key):
                setattr(loan, key, value)
        loan.save()

        return {
            'queue_id': queue_id,
            'server_id': loan.id,
            'action': 'updated',
            'local_id': data.get('local_id'),
        }

    elif action == 'delete':
        if not server_id:
            raise ValueError('server_id برای حذف لازم است')

        Loan.objects.filter(pk=server_id).delete()
        return {
            'queue_id': queue_id,
            'server_id': server_id,
            'action': 'deleted',
        }

    raise ValueError(f'عملیات ناشناخته: {action}')


# ==================== Pull (دریافت از سرور) ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sync_pull(request):
    """دریافت تغییرات از سرور"""
    since = request.GET.get('since')
    device_id = request.GET.get('device_id', 'unknown')

    if since:
        try:
            since_time = timezone.datetime.fromtimestamp(int(since), tz=timezone.utc)
        except (ValueError, TypeError):
            since_time = None
    else:
        since_time = None

    # دریافت داده‌ها
    if since_time:
        books = Book.objects.filter(updated_at__gt=since_time)
        members = Member.objects.filter(created_at__gt=since_time)
        loans = Loan.objects.filter(created_at__gt=since_time)
    else:
        books = Book.objects.all()
        members = Member.objects.all()
        loans = Loan.objects.all()

    # ثبت لاگ
    total_count = books.count() + members.count() + loans.count()
    SyncLog.objects.create(
        device_identifier=device_id,
        user=request.user,
        action='pull',
        status='completed',
        pulled_count=total_count,
        completed_at=timezone.now(),
    )

    # به‌روزرسانی آخرین Sync دستگاه
    Device.objects.filter(device_id=device_id).update(last_sync=timezone.now())

    return Response({
        'success': True,
        'books': BookSerializer(books, many=True).data,
        'members': MemberSerializer(members, many=True).data,
        'loans': LoanSerializer(loans, many=True).data,
        'server_time': int(timezone.now().timestamp()),
        'counts': {
            'books': books.count(),
            'members': members.count(),
            'loans': loans.count(),
        }
    })


# ==================== Status ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sync_status(request):
    """وضعیت Sync"""
    device_id = request.GET.get('device_id')

    last_sync = SyncLog.objects.filter(user=request.user)
    if device_id:
        last_sync = last_sync.filter(device_identifier=device_id)
    last_sync = last_sync.first()

    pending_count = SyncQueue.objects.filter(status='pending').count()
    conflicts_count = Conflict.objects.filter(resolution='pending').count()

    return Response({
        'last_sync': last_sync.started_at if last_sync else None,
        'last_status': last_sync.status if last_sync else None,
        'pending_count': pending_count,
        'conflicts_count': conflicts_count,
        'server_time': int(timezone.now().timestamp()),
    })


# ==================== Conflict Resolution ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sync_conflicts(request):
    """لیست تعارض‌ها"""
    conflicts = Conflict.objects.filter(resolution='pending').order_by('-created_at')

    return Response({
        'conflicts': [
            {
                'id': c.id,
                'model_name': c.model_name,
                'object_id': c.object_id,
                'local_data': c.local_data,
                'remote_data': c.remote_data,
                'local_updated_at': c.local_updated_at.isoformat() if c.local_updated_at else None,
                'remote_updated_at': c.remote_updated_at.isoformat() if c.remote_updated_at else None,
                'created_at': c.created_at.isoformat() if c.created_at else None,
            }
            for c in conflicts
        ]
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resolve_conflict(request, conflict_id):
    """حل تعارض"""
    conflict = get_object_or_404(Conflict, pk=conflict_id)
    resolution = request.data.get('resolution')
    merged_data = request.data.get('data')

    if resolution == 'local':
        final_data = conflict.local_data
    elif resolution == 'remote':
        final_data = conflict.remote_data
    elif resolution == 'merged':
        final_data = merged_data or conflict.local_data
    else:
        return Response({'error': 'راه حل نامعتبر'}, status=400)

    # اعمال راه حل
    if conflict.model_name == 'book':
        book = Book.objects.filter(pk=conflict.object_id).first()
        if book:
            allowed_fields = [
                'title', 'subtitle', 'author', 'author_dates', 'isbn',
                'publisher', 'publish_place', 'publish_year', 'pages',
                'dimensions', 'dewey_class', 'lcc_class', 'subject',
                'notes', 'fapa', 'volume', 'series', 'series_number',
                'language', 'condition', 'location', 'total_copies'
            ]
            for key, value in final_data.items():
                if key in allowed_fields and hasattr(book, key):
                    setattr(book, key, value)
            book.save()

    elif conflict.model_name == 'member':
        member = Member.objects.filter(pk=conflict.object_id).first()
        if member:
            allowed_fields = [
                'first_name', 'last_name', 'national_id', 'phone',
                'address', 'is_active', 'max_loans', 'notes'
            ]
            for key, value in final_data.items():
                if key in allowed_fields and hasattr(member, key):
                    setattr(member, key, value)
            member.save()

    conflict.resolution = resolution
    conflict.resolved_data = final_data
    conflict.resolved_by = request.user
    conflict.resolved_at = timezone.now()
    conflict.save()

    return Response({'success': True})


# ==================== Web Pages ====================

@login_required
def sync_page(request):
    """صفحه Sync"""
    return render(request, 'library/sync.html')


@login_required
def backup_page(request):
    """صفحه بکاپ"""
    return render(request, 'library/backup.html')


@login_required
def conflicts_page(request):
    """صفحه تعارض‌ها"""
    conflicts = Conflict.objects.filter(resolution='pending').order_by('-created_at')
    return render(request, 'library/conflicts.html', {'conflicts': conflicts})