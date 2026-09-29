# library/backup_views.py
"""
API Backup و Restore
"""
import json
import os
import tempfile
from django.http import HttpResponse, JsonResponse
from django.core import serializers
from django.utils import timezone
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Book, Member, Loan, Notification


# ==================== Backup Export ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def backup_export(request):
    """خروجی کامل دیتابیس به JSON"""
    data = {
        'version': '1.0',
        'exported_at': timezone.now().isoformat(),
        'exported_by': request.user.username,
        'stats': {
            'books': Book.objects.count(),
            'members': Member.objects.count(),
            'loans': Loan.objects.count(),
        },
        'books': json.loads(serializers.serialize('json', Book.objects.all())),
        'members': json.loads(serializers.serialize('json', Member.objects.all())),
        'loans': json.loads(serializers.serialize('json', Loan.objects.all())),
    }

    response = HttpResponse(
        json.dumps(data, ensure_ascii=False, indent=2),
        content_type='application/json; charset=utf-8'
    )
    response['Content-Disposition'] = f'attachment; filename="backup_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'
    return response


# ==================== Backup Import ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def backup_import(request):
    """بازیابی از فایل JSON"""
    if 'file' not in request.FILES:
        return Response({'error': 'فایلی ارسال نشده'}, status=400)

    mode = request.POST.get('mode', 'merge')

    try:
        file_content = request.FILES['file'].read().decode('utf-8')
        data = json.loads(file_content)

        stats = {
            'books_created': 0,
            'books_updated': 0,
            'books_skipped': 0,
            'members_created': 0,
            'members_updated': 0,
            'members_skipped': 0,
            'loans_created': 0,
            'loans_skipped': 0,
            'errors': []
        }

        if mode == 'replace':
            # پاک کردن همه چیز
            Loan.objects.all().delete()
            Member.objects.all().delete()
            Book.objects.all().delete()

        # بازیابی کتاب‌ها
        for book_data in data.get('books', []):
            try:
                fields = book_data['fields']
                isbn = fields.get('isbn')
                pk = book_data.get('pk')

                if mode == 'merge':
                    # بررسی تکراری با ISBN
                    if isbn:
                        existing = Book.objects.filter(isbn=isbn).first()
                        if existing:
                            for key, value in fields.items():
                                if hasattr(existing, key) and key not in ['id', 'created_at']:
                                    setattr(existing, key, value)
                            existing.save()
                            stats['books_updated'] += 1
                            continue

                    # بررسی تکراری با pk
                    if pk:
                        existing = Book.objects.filter(pk=pk).first()
                        if existing:
                            for key, value in fields.items():
                                if hasattr(existing, key) and key not in ['id', 'created_at']:
                                    setattr(existing, key, value)
                            existing.save()
                            stats['books_updated'] += 1
                            continue

                # حذف فیلدهای غیرمجاز
                allowed = {k: v for k, v in fields.items() if hasattr(Book, k) and k not in ['id']}

                # اگر pk مشخص است، از آن استفاده کن
                if pk and mode == 'replace':
                    try:
                        Book.objects.create(pk=pk, **allowed)
                    except:
                        Book.objects.create(**allowed)
                else:
                    Book.objects.create(**allowed)

                stats['books_created'] += 1
            except Exception as e:
                stats['errors'].append(f'کتاب: {str(e)}')

        # بازیابی اعضا
        for member_data in data.get('members', []):
            try:
                fields = member_data['fields']
                national_id = fields.get('national_id')
                member_code = fields.get('member_code')
                pk = member_data.get('pk')

                if mode == 'merge':
                    existing = None
                    if national_id:
                        existing = Member.objects.filter(national_id=national_id).first()
                    if not existing and member_code:
                        existing = Member.objects.filter(member_code=member_code).first()
                    if not existing and pk:
                        existing = Member.objects.filter(pk=pk).first()

                    if existing:
                        for key, value in fields.items():
                            if hasattr(existing, key) and key not in ['id', 'created_at']:
                                setattr(existing, key, value)
                        existing.save()
                        stats['members_updated'] += 1
                        continue

                allowed = {k: v for k, v in fields.items() if hasattr(Member, k) and k not in ['id']}

                if pk and mode == 'replace':
                    try:
                        Member.objects.create(pk=pk, **allowed)
                    except:
                        Member.objects.create(**allowed)
                else:
                    Member.objects.create(**allowed)

                stats['members_created'] += 1
            except Exception as e:
                stats['errors'].append(f'عضو: {str(e)}')

        # بازیابی امانت‌ها
        for loan_data in data.get('loans', []):
            try:
                fields = loan_data['fields']
                pk = loan_data.get('pk')

                if mode == 'merge':
                    if pk:
                        existing = Loan.objects.filter(pk=pk).first()
                        if existing:
                            stats['loans_skipped'] += 1
                            continue

                allowed = {k: v for k, v in fields.items() if hasattr(Loan, k) and k not in ['id']}

                if pk and mode == 'replace':
                    try:
                        Loan.objects.create(pk=pk, **allowed)
                    except:
                        Loan.objects.create(**allowed)
                else:
                    Loan.objects.create(**allowed)

                stats['loans_created'] += 1
            except Exception as e:
                stats['errors'].append(f'امانت: {str(e)}')

        return Response({
            'success': True,
            'stats': stats,
            'message': f"کتاب: {stats['books_created']} جدید، {stats['books_updated']} ویرایش | اعضا: {stats['members_created']} جدید، {stats['members_updated']} ویرایش"
        })

    except json.JSONDecodeError as e:
        return Response({'error': f'فایل JSON نامعتبر است: {str(e)}'}, status=400)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


# ==================== Backup Merge ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def backup_merge(request):
    """ادغام چند بکاپ"""
    if 'files' not in request.FILES:
        return Response({'error': 'فایل‌ها ارسال نشدند'}, status=400)

    files = request.FILES.getlist('files')

    if not files:
        return Response({'error': 'هیچ فایلی ارسال نشده'}, status=400)

    total_stats = {
        'books_created': 0,
        'books_updated': 0,
        'books_skipped': 0,
        'members_created': 0,
        'members_updated': 0,
        'members_skipped': 0,
        'loans_created': 0,
        'loans_skipped': 0,
        'files_processed': 0,
        'files_failed': 0,
        'errors': []
    }

    for f in files:
        try:
            content = f.read().decode('utf-8')
            data = json.loads(content)
            total_stats['files_processed'] += 1

            # پردازش کتاب‌ها
            for book_data in data.get('books', []):
                try:
                    fields = book_data['fields']
                    isbn = fields.get('isbn')
                    pk = book_data.get('pk')

                    # بررسی تکراری
                    existing = None
                    if isbn:
                        existing = Book.objects.filter(isbn=isbn).first()
                    if not existing and pk:
                        existing = Book.objects.filter(pk=pk).first()

                    if existing:
                        # ادغام: به‌روزرسانی با داده جدیدتر
                        for key, value in fields.items():
                            if hasattr(existing, key) and key not in ['id', 'created_at']:
                                setattr(existing, key, value)
                        existing.save()
                        total_stats['books_updated'] += 1
                    else:
                        allowed = {k: v for k, v in fields.items() if hasattr(Book, k) and k not in ['id']}
                        Book.objects.create(**allowed)
                        total_stats['books_created'] += 1

                except Exception as e:
                    total_stats['errors'].append(f'{f.name} - کتاب: {str(e)}')

            # پردازش اعضا
            for member_data in data.get('members', []):
                try:
                    fields = member_data['fields']
                    national_id = fields.get('national_id')
                    member_code = fields.get('member_code')
                    pk = member_data.get('pk')

                    existing = None
                    if national_id:
                        existing = Member.objects.filter(national_id=national_id).first()
                    if not existing and member_code:
                        existing = Member.objects.filter(member_code=member_code).first()
                    if not existing and pk:
                        existing = Member.objects.filter(pk=pk).first()

                    if existing:
                        for key, value in fields.items():
                            if hasattr(existing, key) and key not in ['id', 'created_at']:
                                setattr(existing, key, value)
                        existing.save()
                        total_stats['members_updated'] += 1
                    else:
                        allowed = {k: v for k, v in fields.items() if hasattr(Member, k) and k not in ['id']}
                        Member.objects.create(**allowed)
                        total_stats['members_created'] += 1

                except Exception as e:
                    total_stats['errors'].append(f'{f.name} - عضو: {str(e)}')

            # پردازش امانت‌ها
            for loan_data in data.get('loans', []):
                try:
                    fields = loan_data['fields']
                    pk = loan_data.get('pk')

                    if pk and Loan.objects.filter(pk=pk).exists():
                        total_stats['loans_skipped'] += 1
                        continue

                    allowed = {k: v for k, v in fields.items() if hasattr(Loan, k) and k not in ['id']}
                    Loan.objects.create(**allowed)
                    total_stats['loans_created'] += 1

                except Exception as e:
                    total_stats['errors'].append(f'{f.name} - امانت: {str(e)}')

        except json.JSONDecodeError as e:
            total_stats['files_failed'] += 1
            total_stats['errors'].append(f'{f.name}: JSON نامعتبر - {str(e)}')
        except Exception as e:
            total_stats['files_failed'] += 1
            total_stats['errors'].append(f'{f.name}: {str(e)}')

    message = (
        f"پردازش {total_stats['files_processed']} فایل انجام شد. "
        f"کتاب: {total_stats['books_created']} جدید، {total_stats['books_updated']} ویرایش. "
        f"اعضا: {total_stats['members_created']} جدید، {total_stats['members_updated']} ویرایش."
    )

    if total_stats['files_failed'] > 0:
        message += f" {total_stats['files_failed']} فایل ناموفق."

    return Response({
        'success': True,
        'stats': total_stats,
        'message': message
    })


# ==================== Backup to Cloud ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def backup_to_drive(request):
    """آپلود بکاپ به Google Drive"""
    try:
        from .cloud_backup import upload_to_drive

        # ساخت بکاپ
        data = {
            'version': '1.0',
            'exported_at': timezone.now().isoformat(),
            'exported_by': request.user.username,
            'books': json.loads(serializers.serialize('json', Book.objects.all())),
            'members': json.loads(serializers.serialize('json', Member.objects.all())),
            'loans': json.loads(serializers.serialize('json', Loan.objects.all())),
        }

        # ذخیره در فایل موقت
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            temp_path = f.name

        try:
            # آپلود به Drive
            folder_id = request.data.get('folder_id')
            result = upload_to_drive(temp_path, folder_id)

            return Response({
                'success': True,
                'file_id': result['id'],
                'file_name': result['name'],
                'link': result.get('webViewLink', ''),
            })
        finally:
            # حذف فایل موقت
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except ImportError as e:
        return Response({
            'error': 'کتابخانه Google Drive نصب نیست. لطفاً google-api-python-client را نصب کنید.'
        }, status=500)
    except FileNotFoundError:
        return Response({
            'error': 'فایل credentials.json یافت نشد. لطفاً آن را در ریشه پروژه قرار دهید.'
        }, status=500)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


# ==================== Backup Stats ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def backup_stats(request):
    """آمار فعلی دیتابیس"""
    return Response({
        'books': Book.objects.count(),
        'members': Member.objects.count(),
        'loans': Loan.objects.count(),
        'notifications': Notification.objects.count(),
        'server_time': timezone.now().isoformat(),
    })