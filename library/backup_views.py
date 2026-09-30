# library/backup_views.py
"""
API Backup و Restore - با پشتیبانی از ZIP و عکس‌ها
"""
import json
import os
import zipfile
import tempfile
from io import BytesIO
from pathlib import Path

from django.http import HttpResponse, JsonResponse
from django.core import serializers
from django.core.files.base import ContentFile
from django.utils import timezone
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Book, Member, Loan, Notification


# ==================== Backup Export (ZIP) ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def backup_export(request):
    """
    خروجی کامل دیتابیس به صورت ZIP (JSON + عکس‌ها)
    """
    # ساخت data.json
    data = {
        'version': '2.0',
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

    # ساخت ZIP در حافظه
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # نوشتن data.json
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        zipf.writestr('data.json', json_data)

        # اضافه کردن عکس‌های جلد
        covers_count = 0
        for book in Book.objects.all():
            if book.cover_image and book.cover_image.name:
                try:
                    file_path = book.cover_image.path
                    if os.path.exists(file_path):
                        # مسیر در ZIP
                        arcname = f'covers/{os.path.basename(file_path)}'
                        zipf.write(file_path, arcname)
                        covers_count += 1
                except Exception as e:
                    print(f"خطا در اضافه کردن عکس {book.pk}: {e}")

        # اضافه کردن QR Code ها
        qrcodes_count = 0
        for book in Book.objects.all():
            if book.qr_code and book.qr_code.name:
                try:
                    file_path = book.qr_code.path
                    if os.path.exists(file_path):
                        arcname = f'qrcodes/{os.path.basename(file_path)}'
                        zipf.write(file_path, arcname)
                        qrcodes_count += 1
                except Exception as e:
                    print(f"خطا در اضافه کردن QR {book.pk}: {e}")

    # پاسخ
    zip_buffer.seek(0)

    response = HttpResponse(
        zip_buffer.read(),
        content_type='application/zip'
    )
    filename = f'library_backup_{timezone.now().strftime("%Y%m%d_%H%M%S")}.zip'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # آمار در هدر
    response['X-Covers-Count'] = str(covers_count)
    response['X-QRCodes-Count'] = str(qrcodes_count)

    return response


# ==================== Backup Import (ZIP) ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def backup_import(request):
    """
    بازیابی از فایل ZIP (JSON + عکس‌ها)
    """
    if 'file' not in request.FILES:
        return Response({'error': 'فایلی ارسال نشده'}, status=400)

    mode = request.POST.get('mode', 'merge')
    uploaded_file = request.FILES['file']

    stats = {
        'books_created': 0,
        'books_updated': 0,
        'books_skipped': 0,
        'members_created': 0,
        'members_updated': 0,
        'members_skipped': 0,
        'loans_created': 0,
        'loans_skipped': 0,
        'covers_saved': 0,
        'qrcodes_saved': 0,
        'errors': []
    }

    try:
        # تشخیص نوع فایل (ZIP یا JSON)
        file_content = uploaded_file.read()

        if uploaded_file.name.endswith('.zip'):
            # ==================== فایل ZIP ====================
            with zipfile.ZipFile(BytesIO(file_content), 'r') as zipf:
                # خواندن data.json
                if 'data.json' not in zipf.namelist():
                    return Response({'error': 'فایل data.json در ZIP یافت نشد'}, status=400)

                with zipf.open('data.json') as f:
                    data = json.loads(f.read().decode('utf-8'))

                # پاک کردن در حالت replace
                if mode == 'replace':
                    Loan.objects.all().delete()
                    Member.objects.all().delete()
                    Book.objects.all().delete()

                # بازیابی کتاب‌ها
                for book_data in data.get('books', []):
                    try:
                        result = process_book(book_data, mode)
                        stats[f'books_{result}'] += 1
                    except Exception as e:
                        stats['errors'].append(f'کتاب: {str(e)}')

                # بازیابی اعضا
                for member_data in data.get('members', []):
                    try:
                        result = process_member(member_data, mode)
                        stats[f'members_{result}'] += 1
                    except Exception as e:
                        stats['errors'].append(f'عضو: {str(e)}')

                # بازیابی امانت‌ها
                for loan_data in data.get('loans', []):
                    try:
                        result = process_loan(loan_data, mode)
                        stats[f'loans_{result}'] += 1
                    except Exception as e:
                        stats['errors'].append(f'امانت: {str(e)}')

                # بازیابی عکس‌ها
                for name in zipf.namelist():
                    if name.startswith('covers/') and not name.endswith('/'):
                        try:
                            filename = os.path.basename(name)

                            # پیدا کردن کتاب مربوطه
                            book = find_book_by_cover_name(filename, data)

                            if book:
                                # ذخیره عکس
                                with zipf.open(name) as img_file:
                                    img_data = img_file.read()

                                    # حذف عکس قبلی
                                    if book.cover_image:
                                        try:
                                            book.cover_image.delete(save=False)
                                        except:
                                            pass

                                    # ذخیره عکس جدید
                                    book.cover_image.save(filename, ContentFile(img_data), save=True)
                                    stats['covers_saved'] += 1
                        except Exception as e:
                            stats['errors'].append(f'عکس {name}: {str(e)}')

                    elif name.startswith('qrcodes/') and not name.endswith('/'):
                        try:
                            filename = os.path.basename(name)
                            book = find_book_by_qr_name(filename, data)

                            if book:
                                with zipf.open(name) as img_file:
                                    img_data = img_file.read()

                                    if book.qr_code:
                                        try:
                                            book.qr_code.delete(save=False)
                                        except:
                                            pass

                                    book.qr_code.save(filename, ContentFile(img_data), save=True)
                                    stats['qrcodes_saved'] += 1
                        except Exception as e:
                            stats['errors'].append(f'QR {name}: {str(e)}')

        else:
            # ==================== فایل JSON (سازگاری با نسخه قبل) ====================
            data = json.loads(file_content.decode('utf-8'))

            if mode == 'replace':
                Loan.objects.all().delete()
                Member.objects.all().delete()
                Book.objects.all().delete()

            for book_data in data.get('books', []):
                try:
                    result = process_book(book_data, mode)
                    stats[f'books_{result}'] += 1
                except Exception as e:
                    stats['errors'].append(f'کتاب: {str(e)}')

            for member_data in data.get('members', []):
                try:
                    result = process_member(member_data, mode)
                    stats[f'members_{result}'] += 1
                except Exception as e:
                    stats['errors'].append(f'عضو: {str(e)}')

            for loan_data in data.get('loans', []):
                try:
                    result = process_loan(loan_data, mode)
                    stats[f'loans_{result}'] += 1
                except Exception as e:
                    stats['errors'].append(f'امانت: {str(e)}')

        # پیام نتیجه
        message = (
            f"کتاب‌ها: {stats['books_created']} جدید، {stats['books_updated']} ویرایش، {stats['books_skipped']} نادیده | "
            f"اعضا: {stats['members_created']} جدید، {stats['members_updated']} ویرایش | "
            f"امانت‌ها: {stats['loans_created']} جدید | "
            f"عکس‌ها: {stats['covers_saved']} ذخیره شد"
        )

        return Response({
            'success': True,
            'stats': stats,
            'message': message
        })

    except zipfile.BadZipFile:
        return Response({'error': 'فایل ZIP نامعتبر است'}, status=400)
    except json.JSONDecodeError as e:
        return Response({'error': f'فایل JSON نامعتبر است: {str(e)}'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'error': str(e)}, status=500)


def process_book(book_data, mode):
    """پردازش یک کتاب"""
    fields = book_data.get('fields', {})
    isbn = fields.get('isbn')
    pk = book_data.get('pk')
    nbn = fields.get('national_biblio_number')

    # بررسی تکراری
    existing = None
    if mode == 'merge':
        if isbn:
            existing = Book.objects.filter(isbn=isbn).first()
        if not existing and nbn:
            existing = Book.objects.filter(national_biblio_number=nbn).first()
        if not existing and pk:
            existing = Book.objects.filter(pk=pk).first()

    if existing:
        # به‌روزرسانی (بدون تغییر cover_image)
        for key, value in fields.items():
            if hasattr(existing, key) and key not in ['id', 'created_at', 'cover_image', 'qr_code']:
                setattr(existing, key, value)
        existing.save()
        return 'updated'
    else:
        # ایجاد جدید
        allowed = {k: v for k, v in fields.items() if hasattr(Book, k) and k not in ['id']}
        Book.objects.create(**allowed)
        return 'created'


def process_member(member_data, mode):
    """پردازش یک عضو"""
    fields = member_data.get('fields', {})
    national_id = fields.get('national_id')
    member_code = fields.get('member_code')
    pk = member_data.get('pk')

    existing = None
    if mode == 'merge':
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
        return 'updated'
    else:
        allowed = {k: v for k, v in fields.items() if hasattr(Member, k) and k not in ['id']}
        Member.objects.create(**allowed)
        return 'created'


def process_loan(loan_data, mode):
    """پردازش یک امانت"""
    fields = loan_data.get('fields', {})
    pk = loan_data.get('pk')

    existing = None
    if mode == 'merge' and pk:
        existing = Loan.objects.filter(pk=pk).first()

    if existing:
        return 'skipped'
    else:
        allowed = {k: v for k, v in fields.items() if hasattr(Loan, k) and k not in ['id']}
        Loan.objects.create(**allowed)
        return 'created'


def find_book_by_cover_name(filename, data):
    """پیدا کردن کتاب بر اساس نام فایل عکس"""
    # الگو: book_22.png یا cover_xxx.jpg
    import re

    # استخراج ID از نام فایل
    match = re.search(r'book_(\d+)', filename)
    if match:
        book_id = int(match.group(1))
        return Book.objects.filter(pk=book_id).first()

    # جستجو در داده‌ها
    for book_data in data.get('books', []):
        fields = book_data.get('fields', {})
        cover_image = fields.get('cover_image', '')
        if cover_image and os.path.basename(cover_image) == filename:
            pk = book_data.get('pk')
            return Book.objects.filter(pk=pk).first()

    return None


def find_book_by_qr_name(filename, data):
    """پیدا کردن کتاب بر اساس نام فایل QR"""
    import re

    match = re.search(r'book_(\d+)', filename)
    if match:
        book_id = int(match.group(1))
        return Book.objects.filter(pk=book_id).first()

    for book_data in data.get('books', []):
        fields = book_data.get('fields', {})
        qr_code = fields.get('qr_code', '')
        if qr_code and os.path.basename(qr_code) == filename:
            pk = book_data.get('pk')
            return Book.objects.filter(pk=pk).first()

    return None


# ==================== Backup Merge (ادغام چند بکاپ) ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def backup_merge(request):
    """ادغام چند فایل بکاپ"""
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
        'covers_saved': 0,
        'files_processed': 0,
        'files_failed': 0,
        'errors': []
    }

    for f in files:
        try:
            file_content = f.read()

            # تشخیص نوع
            if f.name.endswith('.zip'):
                with zipfile.ZipFile(BytesIO(file_content), 'r') as zipf:
                    with zipf.open('data.json') as json_file:
                        data = json.loads(json_file.read().decode('utf-8'))

                    # پردازش کتاب‌ها
                    for book_data in data.get('books', []):
                        try:
                            result = process_book(book_data, 'merge')
                            total_stats[f'books_{result}'] += 1
                        except Exception as e:
                            total_stats['errors'].append(f'{f.name}: {str(e)}')

                    # پردازش اعضا
                    for member_data in data.get('members', []):
                        try:
                            result = process_member(member_data, 'merge')
                            total_stats[f'members_{result}'] += 1
                        except Exception as e:
                            total_stats['errors'].append(f'{f.name}: {str(e)}')

                    # پردازش عکس‌ها
                    for name in zipf.namelist():
                        if name.startswith('covers/') and not name.endswith('/'):
                            try:
                                filename = os.path.basename(name)
                                book = find_book_by_cover_name(filename, data)
                                if book:
                                    with zipf.open(name) as img_file:
                                        img_data = img_file.read()
                                        book.cover_image.save(filename, ContentFile(img_data), save=True)
                                        total_stats['covers_saved'] += 1
                            except:
                                pass

                    total_stats['files_processed'] += 1
            else:
                # JSON ساده
                data = json.loads(file_content.decode('utf-8'))

                for book_data in data.get('books', []):
                    try:
                        result = process_book(book_data, 'merge')
                        total_stats[f'books_{result}'] += 1
                    except Exception as e:
                        total_stats['errors'].append(f'{f.name}: {str(e)}')

                for member_data in data.get('members', []):
                    try:
                        result = process_member(member_data, 'merge')
                        total_stats[f'members_{result}'] += 1
                    except Exception as e:
                        total_stats['errors'].append(f'{f.name}: {str(e)}')

                total_stats['files_processed'] += 1

        except Exception as e:
            total_stats['files_failed'] += 1
            total_stats['errors'].append(f'{f.name}: {str(e)}')

    message = (
        f"پردازش {total_stats['files_processed']} فایل انجام شد. "
        f"کتاب: {total_stats['books_created']} جدید، {total_stats['books_updated']} ویرایش. "
        f"عکس: {total_stats['covers_saved']} ذخیره شد."
    )

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

        # ساخت ZIP
        response = backup_export(request)

        # ذخیره در فایل موقت
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.zip', delete=False) as f:
            f.write(response.content)
            temp_path = f.name

        try:
            folder_id = request.data.get('folder_id')
            result = upload_to_drive(temp_path, folder_id)

            return Response({
                'success': True,
                'file_id': result['id'],
                'file_name': result['name'],
                'link': result.get('webViewLink', ''),
            })
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except ImportError:
        return Response({
            'error': 'کتابخانه Google Drive نصب نیست'
        }, status=500)
    except Exception as e:
        return Response({'error': str(e)}, status=500)