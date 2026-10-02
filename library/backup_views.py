# library/backup_views.py
"""
API Backup و Restore - نسخه ۵
با رفع مشکل NOT NULL در PostgreSQL
"""
import json
import os
import zipfile
import tempfile
import re
from io import BytesIO
from pathlib import Path

from django.http import HttpResponse
from django.core import serializers
from django.core.files.base import ContentFile
from django.utils import timezone
from django.conf import settings

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Book, Member, Loan, Notification


# ==================== Helper: تبدیل None به مقادیر پیش‌فرض ====================

def safe_str(value, default=''):
    """تبدیل None به رشته خالی"""
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def safe_int(value, default=1):
    """تبدیل None به عدد صحیح"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_bool(value, default=False):
    """تبدیل None به Boolean"""
    if value is None:
        return default
    return bool(value)


def clean_book_fields(fields):
    """
    پاکسازی فیلدهای کتاب برای جلوگیری از خطای NOT NULL
    """
    # فیلدهای اجباری (NOT NULL) در دیتابیس
    required_fields = {
        'title': '',
        'author': '',
        'subtitle': '',
        'statement_of_responsibility': '',
        'author_dates': '',
        'isbn': None,  # این می‌تواند None باشد
        'national_biblio_number': '',
        'publisher': '',
        'publish_place': '',
        'publish_year': '',
        'pages': '',
        'dimensions': '',
        'dewey_class': '',
        'lcc_class': '',
        'subject': '',
        'notes': '',
        'fapa': '',
        'volume': '',
        'series': '',
        'series_number': None,
        'language': 'فارسی',
        'cover_image': '',
        'qr_code': '',
        'condition': 'good',
        'location': '',
        'copy_number': 1,
        'total_copies': 1,
        'marc_record': '',
    }

    cleaned = {}

    for field, default in required_fields.items():
        value = fields.get(field)

        # اگر None بود، مقدار پیش‌فرض
        if value is None:
            cleaned[field] = default
        # اگر رشته خالی بود برای فیلدهای اجباری، جایگزین کن
        elif isinstance(value, str) and value.strip() == '' and default == '':
            cleaned[field] = ''
        else:
            cleaned[field] = value

    # پردازش فیلدهای خاص
    # isbn: اگر خالی بود None
    if cleaned.get('isbn') == '':
        cleaned['isbn'] = None

    # series_number: تبدیل به عدد
    if cleaned.get('series_number'):
        cleaned['series_number'] = safe_int(cleaned['series_number'], None)
    else:
        cleaned['series_number'] = None

    # copy_number و total_copies: تبدیل به عدد
    cleaned['copy_number'] = safe_int(cleaned.get('copy_number'), 1)
    cleaned['total_copies'] = safe_int(cleaned.get('total_copies'), 1)

    return cleaned


# ==================== Backup Export ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def backup_export(request):
    """خروجی ZIP با JSON + عکس‌ها"""

    data = {
        'version': '3.0',
        'exported_at': timezone.now().isoformat(),
        'exported_by': request.user.username,
        'stats': {
            'books': Book.objects.count(),
            'members': Member.objects.count(),
            'loans': Loan.objects.count(),
        },
        'books': [],
        'members': json.loads(serializers.serialize('json', Member.objects.all())),
        'loans': json.loads(serializers.serialize('json', Loan.objects.all())),
    }

    covers_count = 0
    qrcodes_count = 0
    cover_files = []

    # جمع‌آوری کتاب‌ها
    for book in Book.objects.all():
        book_data = {
            'model': 'library.book',
            'pk': book.pk,
            'fields': {
                'isbn': book.isbn,
                'national_biblio_number': book.national_biblio_number or '',
                'title': book.title or '',
                'subtitle': book.subtitle or '',
                'statement_of_responsibility': book.statement_of_responsibility or '',
                'author': book.author or '',
                'author_dates': book.author_dates or '',
                'publisher': book.publisher or '',
                'publish_place': book.publish_place or '',
                'publish_year': book.publish_year or '',
                'pages': book.pages or '',
                'dimensions': book.dimensions or '',
                'dewey_class': book.dewey_class or '',
                'lcc_class': book.lcc_class or '',
                'subject': book.subject or '',
                'notes': book.notes or '',
                'fapa': book.fapa or '',
                'volume': book.volume or '',
                'series': book.series or '',
                'series_number': book.series_number,
                'language': book.language or 'فارسی',
                'condition': book.condition or 'good',
                'location': book.location or '',
                'copy_number': book.copy_number or 1,
                'total_copies': book.total_copies or 1,
                'marc_record': book.marc_record or '',
                'cover_image': '',
                'qr_code': '',
            }
        }

        if book.cover_image and book.cover_image.name:
            try:
                file_path = book.cover_image.path
                if os.path.exists(file_path):
                    ext = os.path.splitext(file_path)[1]
                    filename = f'cover_{book.pk}{ext}'
                    book_data['fields']['cover_image'] = f'covers/{filename}'
                    cover_files.append((book.pk, filename, file_path))
            except Exception as e:
                print(f"خطا در عکس {book.pk}: {e}")

        if book.qr_code and book.qr_code.name:
            try:
                file_path = book.qr_code.path
                if os.path.exists(file_path):
                    ext = os.path.splitext(file_path)[1]
                    filename = f'qr_{book.pk}{ext}'
                    book_data['fields']['qr_code'] = f'qrcodes/{filename}'
            except Exception as e:
                print(f"خطا در QR {book.pk}: {e}")

        data['books'].append(book_data)

    # ساخت ZIP
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        zipf.writestr('data.json', json_data)

        for book_pk, filename, file_path in cover_files:
            try:
                zipf.write(file_path, f'covers/{filename}')
                covers_count += 1
            except Exception as e:
                print(f"خطا در ZIP عکس {book_pk}: {e}")

        for book in Book.objects.all():
            if book.qr_code and book.qr_code.name:
                try:
                    file_path = book.qr_code.path
                    if os.path.exists(file_path):
                        ext = os.path.splitext(file_path)[1]
                        filename = f'qr_{book.pk}{ext}'
                        zipf.write(file_path, f'qrcodes/{filename}')
                        qrcodes_count += 1
                except Exception as e:
                    print(f"خطا در ZIP QR {book.pk}: {e}")

    zip_buffer.seek(0)

    response = HttpResponse(zip_buffer.read(), content_type='application/zip')
    filename = f'library_backup_{timezone.now().strftime("%Y%m%d_%H%M%S")}.zip'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    print(f"\n📊 آمار ZIP:")
    print(f"   کتاب: {len(data['books'])}")
    print(f"   عکس: {covers_count}")
    print(f"   QR: {qrcodes_count}")

    return response


# ==================== Backup Import ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def backup_import(request):
    """بازیابی از ZIP یا JSON"""
    if 'file' not in request.FILES:
        return Response({'error': 'فایلی ارسال نشده'}, status=400)

    mode = request.POST.get('mode', 'merge')
    uploaded_file = request.FILES['file']

    stats = {
        'books_created': 0,
        'books_updated': 0,
        'members_created': 0,
        'members_updated': 0,
        'loans_created': 0,
        'loans_skipped': 0,
        'covers_saved': 0,
        'qrcodes_saved': 0,
        'errors': []
    }

    pk_map = {}
    member_pk_map = {}
    cover_files = {}

    try:
        file_content = uploaded_file.read()

        if uploaded_file.name.endswith('.zip'):
            with zipfile.ZipFile(BytesIO(file_content), 'r') as zipf:
                if 'data.json' not in zipf.namelist():
                    return Response({'error': 'data.json یافت نشد'}, status=400)

                with zipf.open('data.json') as f:
                    data = json.loads(f.read().decode('utf-8'))

                # استخراج عکس‌ها
                for name in zipf.namelist():
                    if (name.startswith('covers/') or name.startswith('qrcodes/')) and not name.endswith('/'):
                        with zipf.open(name) as img_file:
                            filename = os.path.basename(name)
                            cover_files[filename] = img_file.read()

                print(f"\n📦 فایل‌های موجود در ZIP:")
                print(f"   عکس‌ها: {len(cover_files)}")

                if mode == 'replace':
                    Loan.objects.all().delete()
                    Member.objects.all().delete()
                    Book.objects.all().delete()

                # ==================== کتاب‌ها ====================
                for book_data in data.get('books', []):
                    try:
                        fields = book_data.get('fields', {})
                        old_pk = book_data.get('pk')

                        # پاکسازی فیلدها
                        clean_fields = clean_book_fields(fields)

                        # ایجاد یا به‌روزرسانی
                        book, action = process_book_safe(clean_fields, mode)

                        if book:
                            pk_map[old_pk] = book
                            stats[f'books_{action}'] += 1

                            # ذخیره عکس
                            cover_field = fields.get('cover_image', '')
                            if cover_field:
                                filename = os.path.basename(cover_field)
                                if filename in cover_files:
                                    save_book_cover(book, filename, cover_files[filename], stats)

                    except Exception as e:
                        stats['errors'].append(f'کتاب: {str(e)}')
                        print(f"❌ خطا در کتاب: {e}")

                # ==================== اعضا ====================
                for member_data in data.get('members', []):
                    try:
                        fields = member_data.get('fields', {})
                        old_pk = member_data.get('pk')

                        member, action = process_member_safe(fields, mode)
                        if member:
                            member_pk_map[old_pk] = member
                            stats[f'members_{action}'] += 1

                    except Exception as e:
                        stats['errors'].append(f'عضو: {str(e)}')

                # ==================== امانت‌ها ====================
                for loan_data in data.get('loans', []):
                    try:
                        fields = loan_data.get('fields', {})
                        old_book_pk = fields.get('book')
                        old_member_pk = fields.get('member')

                        if old_book_pk in pk_map:
                            fields['book'] = pk_map[old_book_pk].pk
                        if old_member_pk in member_pk_map:
                            fields['member'] = member_pk_map[old_member_pk].pk

                        result = process_loan(fields, mode)
                        stats[f'loans_{result}'] += 1

                    except Exception as e:
                        stats['errors'].append(f'امانت: {str(e)}')

        else:
            # ==================== JSON ====================
            data = json.loads(file_content.decode('utf-8'))

            if mode == 'replace':
                Loan.objects.all().delete()
                Member.objects.all().delete()
                Book.objects.all().delete()

            for book_data in data.get('books', []):
                try:
                    fields = book_data.get('fields', {})
                    old_pk = book_data.get('pk')

                    clean_fields = clean_book_fields(fields)
                    book, action = process_book_safe(clean_fields, mode)

                    if book:
                        pk_map[old_pk] = book
                        stats[f'books_{action}'] += 1
                except Exception as e:
                    stats['errors'].append(f'کتاب: {str(e)}')

            for member_data in data.get('members', []):
                try:
                    fields = member_data.get('fields', {})
                    old_pk = member_data.get('pk')

                    member, action = process_member_safe(fields, mode)
                    if member:
                        member_pk_map[old_pk] = member
                        stats[f'members_{action}'] += 1
                except Exception as e:
                    stats['errors'].append(f'عضو: {str(e)}')

            for loan_data in data.get('loans', []):
                try:
                    fields = loan_data.get('fields', {})
                    old_book_pk = fields.get('book')
                    old_member_pk = fields.get('member')

                    if old_book_pk in pk_map:
                        fields['book'] = pk_map[old_book_pk].pk
                    if old_member_pk in member_pk_map:
                        fields['member'] = member_pk_map[old_member_pk].pk

                    result = process_loan(fields, mode)
                    stats[f'loans_{result}'] += 1
                except Exception as e:
                    stats['errors'].append(f'امانت: {str(e)}')

        # پیام نتیجه
        message = (
            f"کتاب‌ها: {stats['books_created']} جدید، {stats['books_updated']} ویرایش | "
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
        return Response({'error': f'JSON نامعتبر: {str(e)}'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'error': str(e)}, status=500)


def save_book_cover(book, filename, img_data, stats):
    """ذخیره عکس جلد کتاب"""
    try:
        if book.cover_image:
            try:
                book.cover_image.delete(save=False)
            except:
                pass

        book.cover_image.save(filename, ContentFile(img_data), save=True)
        stats['covers_saved'] += 1
        print(f"✅ عکس ذخیره شد: {filename} → کتاب {book.pk} ({book.title[:30]})")
        return True
    except Exception as e:
        stats['errors'].append(f'عکس {filename}: {str(e)}')
        print(f"❌ خطا در عکس {filename}: {e}")
        return False


def process_book_safe(clean_fields, mode):
    """پردازش کتاب با فیلدهای پاکسازی‌شده - با حفظ داده‌های موجود"""
    isbn = clean_fields.get('isbn')
    nbn = clean_fields.get('national_biblio_number')
    title = clean_fields.get('title', '')
    author = clean_fields.get('author', '')

    # بررسی تکراری
    existing = None
    if mode == 'merge':
        if isbn:
            existing = Book.objects.filter(isbn=isbn).first()
        if not existing and nbn:
            existing = Book.objects.filter(national_biblio_number=nbn).first()
        if not existing and title:
            existing = Book.objects.filter(title=title, author=author).first()

    if existing:
        # ✅ به‌روزرسانی: فقط فیلدهایی که مقدار دارند
        for key, value in clean_fields.items():
            if hasattr(existing, key) and key not in ['id', 'created_at', 'cover_image', 'qr_code']:
                # ✅ اگر مقدار جدید خالی است، فیلد قبلی را دست نزن
                if value is None or (isinstance(value, str) and value.strip() == ''):
                    continue  # ← این خط حیاتی است

                # ✅ اگر مقدار جدید = مقدار قبلی، نیازی به تغییر نیست
                old_value = getattr(existing, key, None)
                if old_value == value:
                    continue

                setattr(existing, key, value)

        existing.save()
        return existing, 'updated'
    else:
        # ایجاد جدید
        allowed = {}
        for k, v in clean_fields.items():
            if hasattr(Book, k) and k not in ['id', 'cover_image', 'qr_code']:
                allowed[k] = v

        book = Book.objects.create(**allowed)
        print(f"🆕 کتاب جدید: {book.pk} - {book.title[:40]}")
        return book, 'created'


def process_member_safe(fields, mode):
    """پردازش عضو - با حفظ داده‌های موجود"""
    clean_fields = {
        'first_name': safe_str(fields.get('first_name')),
        'last_name': safe_str(fields.get('last_name')),
        'national_id': safe_str(fields.get('national_id')),
        'phone': safe_str(fields.get('phone')),
        'address': safe_str(fields.get('address')),
        'member_code': safe_str(fields.get('member_code')),
        'join_date': fields.get('join_date'),
        'is_active': safe_bool(fields.get('is_active'), True),
        'max_loans': safe_int(fields.get('max_loans'), 3),
        'notes': safe_str(fields.get('notes')),
    }

    national_id = clean_fields.get('national_id')
    member_code = clean_fields.get('member_code')

    existing = None
    if mode == 'merge':
        if national_id:
            existing = Member.objects.filter(national_id=national_id).first()
        if not existing and member_code:
            existing = Member.objects.filter(member_code=member_code).first()

    if existing:
        # ✅ فقط فیلدهای پر را به‌روزرسانی کن
        for key, value in clean_fields.items():
            if hasattr(existing, key) and key not in ['id', 'created_at']:
                if value is None or (isinstance(value, str) and value.strip() == ''):
                    continue

                old_value = getattr(existing, key, None)
                if old_value == value:
                    continue

                setattr(existing, key, value)

        existing.save()
        return existing, 'updated'
    else:
        allowed = {k: v for k, v in clean_fields.items() if hasattr(Member, k) and k not in ['id']}
        member = Member.objects.create(**allowed)
        return member, 'created'


def process_loan(fields, mode):
    """پردازش امانت"""
    book_id = fields.get('book')
    member_id = fields.get('member')
    loan_date = fields.get('loan_date')

    if mode == 'merge':
        existing = Loan.objects.filter(
            book_id=book_id,
            member_id=member_id,
            loan_date=loan_date
        ).first()
        if existing:
            return 'skipped'

    allowed = {k: v for k, v in fields.items() if hasattr(Loan, k) and k not in ['id']}
    try:
        Loan.objects.create(**allowed)
        return 'created'
    except:
        return 'skipped'


# ==================== Backup Merge ====================

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

            if f.name.endswith('.zip'):
                with zipfile.ZipFile(BytesIO(file_content), 'r') as zipf:
                    with zipf.open('data.json') as json_file:
                        data = json.loads(json_file.read().decode('utf-8'))

                    pk_map = {}
                    cover_files = {}

                    for name in zipf.namelist():
                        if name.startswith('covers/') and not name.endswith('/'):
                            with zipf.open(name) as img:
                                cover_files[os.path.basename(name)] = img.read()

                    for book_data in data.get('books', []):
                        fields = book_data.get('fields', {})
                        old_pk = book_data.get('pk')

                        clean_fields = clean_book_fields(fields)
                        book, action = process_book_safe(clean_fields, 'merge')

                        if book:
                            pk_map[old_pk] = book
                            total_stats[f'books_{action}'] += 1

                            cover_field = fields.get('cover_image', '')
                            if cover_field:
                                filename = os.path.basename(cover_field)
                                if filename in cover_files:
                                    save_book_cover(book, filename, cover_files[filename], total_stats)

                    for member_data in data.get('members', []):
                        fields = member_data.get('fields', {})
                        member, action = process_member_safe(fields, 'merge')
                        if member:
                            total_stats[f'members_{action}'] += 1

                    total_stats['files_processed'] += 1

        except Exception as e:
            total_stats['files_failed'] += 1
            total_stats['errors'].append(f'{f.name}: {str(e)}')

    message = f"پردازش {total_stats['files_processed']} فایل. کتاب: {total_stats['books_created']} جدید، {total_stats['books_updated']} ویرایش. عکس: {total_stats['covers_saved']}"

    return Response({
        'success': True,
        'stats': total_stats,
        'message': message
    })


# ==================== Backup to Cloud ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def backup_to_drive(request):
    """آپلود به Google Drive"""
    try:
        from .cloud_backup import upload_to_drive

        response = backup_export(request)

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
        return Response({'error': 'Google Drive نصب نیست'}, status=500)
    except Exception as e:
        return Response({'error': str(e)}, status=500)