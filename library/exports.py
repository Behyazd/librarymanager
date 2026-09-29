# library/exports.py
"""
توابع خروجی Excel و PDF
"""
import io
import os
from datetime import datetime
from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.platypus import Frame, PageTemplate
from reportlab.lib.pagesizes import A4, landscape



# ==================== Persian Text Helper ====================

def reshape_persian(text):
    """اصلاح متن فارسی برای PDF (اتصال حروف)"""
    if not text:
        return ''
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except ImportError:
        return str(text)


# ==================== Font Registration ====================

def register_persian_font():
    """ثبت فونت فارسی برای PDF"""
    font_paths = [
        # فونت IRANSans (بهترین گزینه - اعداد فارسی هم دارد)
        ('C:/Windows/Fonts/IRANSans(FaNum)_0.ttf', 'IRANSans'),
        ('C:/Windows/Fonts/IranSans.ttf', 'IRANSans'),
        # فونت Tahoma (پشتیبان)
        ('C:/Windows/Fonts/tahoma.ttf', 'Tahoma'),
        ('C:/Windows/Fonts/tahomabd.ttf', 'Tahoma'),
        # فونت‌های لینوکس
        ('/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Regular.ttf', 'Vazirmatn'),
        ('/usr/share/fonts/truetype/tahoma/tahoma.ttf', 'Tahoma'),
    ]

    for path, name in font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont('Persian', path))
                print(f"✅ فونت ثبت شد: {path}")
                return 'Persian'
            except Exception as e:
                print(f"❌ خطا در ثبت {path}: {e}")
                continue

    print("⚠️ هیچ فونت فارسی پیدا نشد. از Helvetica استفاده می‌شود.")
    return 'Helvetica'


# ==================== Excel Export ====================

def export_books_to_excel(books, library_name='کتابخانه من', filename='books.xlsx'):
    """خروجی Excel از لیست کتاب‌ها"""
    import jdatetime

    wb = Workbook()
    ws = wb.active
    ws.title = 'کتاب‌ها'
    ws.sheet_view.rightToLeft = True

    # ==================== عنوان ====================
    title_cell = ws.cell(row=1, column=1, value=f'لیست کتاب‌های {library_name}')
    title_cell.font = Font(bold=True, size=14, color='0A76D6')
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=15)
    ws.row_dimensions[1].height = 25

    # ==================== تاریخ ====================
    today_gregorian = timezone.now()
    today_jalali = jdatetime.date.fromgregorian(date=today_gregorian.date())
    jalali_str = today_jalali.strftime('%Y/%m/%d')
    gregorian_str = today_gregorian.strftime('%Y/%m/%d')

    date_cell = ws.cell(row=2, column=1,
                        value=f'تاریخ: {jalali_str} ه‍.ش ({gregorian_str} میلادی) | تعداد: {len(books)} کتاب')
    date_cell.font = Font(size=11, color='666666')
    date_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=15)
    ws.row_dimensions[2].height = 20

    # ==================== هدرها ====================
    headers = [
        'ردیف', 'عنوان', 'عنوان فرعی', 'نویسنده', 'شابک',
        'ناشر', 'محل نشر', 'سال نشر', 'تعداد صفحه', 'ابعاد',
        'رده دیویی', 'رده کنگره', 'موضوعات', 'موجودی', 'کل نسخه‌ها'
    ]

    header_font = Font(bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='0A76D6', end_color='0A76D6', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)

    header_row = 4
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col_num, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
    ws.row_dimensions[header_row].height = 25

    # ==================== داده‌ها ====================
    for row_num, book in enumerate(books, header_row + 1):
        ws.cell(row=row_num, column=1, value=row_num - header_row)
        ws.cell(row=row_num, column=2, value=book.title)
        ws.cell(row=row_num, column=3, value=book.subtitle or '')
        ws.cell(row=row_num, column=4, value=book.author)
        ws.cell(row=row_num, column=5, value=book.isbn or '')
        ws.cell(row=row_num, column=6, value=book.publisher or '')
        ws.cell(row=row_num, column=7, value=book.publish_place or '')
        ws.cell(row=row_num, column=8, value=book.publish_year or '')
        ws.cell(row=row_num, column=9, value=book.pages or '')
        ws.cell(row=row_num, column=10, value=book.dimensions or '')
        ws.cell(row=row_num, column=11, value=book.dewey_class or '')
        ws.cell(row=row_num, column=12, value=book.lcc_class or '')
        ws.cell(row=row_num, column=13, value=book.subject or '')
        ws.cell(row=row_num, column=14, value=book.available_copies)
        ws.cell(row=row_num, column=15, value=book.total_copies)

    # عرض ستون‌ها
    column_widths = [6, 40, 30, 25, 18, 25, 15, 10, 12, 15, 12, 15, 40, 10, 12]
    for i, width in enumerate(column_widths, 1):
        col_letter = chr(64 + i) if i <= 26 else 'A'
        ws.column_dimensions[col_letter].width = width

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ==================== PDF Export ====================

def export_books_to_pdf(books, library_name='کتابخانه من', filename='books.pdf'):
    """خروجی PDF از کتاب‌ها (راست‌چین کامل)"""
    import jdatetime

    output = io.BytesIO()

    # اندازه صفحه
    pagesize = landscape(A4)
    page_width, page_height = pagesize

    doc = SimpleDocTemplate(
        output,
        pagesize=pagesize,
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    font_name = register_persian_font()

    # استایل‌ها
    title_style = ParagraphStyle(
        'PersianTitle',
        fontName=font_name,
        fontSize=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#0A76D6'),
        spaceAfter=5 * mm,
    )

    header_style = ParagraphStyle(
        'PersianHeader',
        fontName=font_name,
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.white,
    )

    cell_style_right = ParagraphStyle(
        'PersianCellRight',
        fontName=font_name,
        fontSize=9,
        alignment=TA_RIGHT,
        leading=11,
    )

    cell_style_center = ParagraphStyle(
        'PersianCellCenter',
        fontName=font_name,
        fontSize=9,
        alignment=TA_CENTER,
        leading=11,
    )

    date_style = ParagraphStyle(
        'PersianDate',
        fontName=font_name,
        fontSize=10,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#666666'),
    )

    story = []

    # عنوان
    title_text = f'لیست کتاب‌های {library_name} ({len(books)} کتاب)'
    story.append(Paragraph(reshape_persian(title_text), title_style))

    # تاریخ
    today_gregorian = timezone.now()
    today_jalali = jdatetime.date.fromgregorian(date=today_gregorian.date())

    jalali_str = today_jalali.strftime('%Y/%m/%d')
    gregorian_str = today_gregorian.strftime('%Y/%m/%d')

    date_text = f'تاریخ: {jalali_str} ه‍.ش ({gregorian_str} میلادی)'
    story.append(Paragraph(reshape_persian(date_text), date_style))
    story.append(Spacer(1, 5 * mm))

    # ==================== جدول ====================
    # هدرها به ترتیب از چپ به راست در PDF نمایش داده می‌شوند
    # اما ما می‌خواهیم از راست شروع شوند، پس ترتیب را برعکس می‌کنیم

    # ترتیب نمایش در PDF از چپ به راست:
    # [موجودی] [سال] [ناشر] [شابک] [نویسنده] [عنوان] [ردیف]
    # نتیجه: ردیف در سمت راست قرار می‌گیرد

    headers = ['موجودی', 'سال', 'ناشر', 'شابک', 'نویسنده', 'عنوان', 'ردیف']

    data = [[Paragraph(reshape_persian(h), header_style) for h in headers]]

    for i, book in enumerate(books, 1):
        row = [
            Paragraph(reshape_persian(f'{book.available_copies}/{book.total_copies}'), cell_style_center),  # موجودی
            Paragraph(reshape_persian(book.publish_year or ''), cell_style_center),  # سال
            Paragraph(reshape_persian(book.publisher[:30] if book.publisher else ''), cell_style_right),  # ناشر
            Paragraph(book.isbn or '', cell_style_center),  # شابک
            Paragraph(reshape_persian(book.author[:30] if book.author else ''), cell_style_right),  # نویسنده
            Paragraph(reshape_persian(book.title[:50] if book.title else ''), cell_style_right),  # عنوان
            Paragraph(reshape_persian(str(i)), cell_style_center),  # ردیف
        ]
        data.append(row)

    # عرض ستون‌ها به ترتیب هدرها
    col_widths = [20 * mm, 20 * mm, 50 * mm, 30 * mm, 50 * mm, 90 * mm, 15 * mm]

    table = Table(data, colWidths=col_widths, hAlign='RIGHT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0A76D6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    story.append(table)

    doc.build(story)
    output.seek(0)

    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ==================== QR Labels Export ====================

def export_labels_to_pdf(books, filename='labels.pdf'):
    """خروجی PDF برچسب‌های QR برای کتاب‌ها"""
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=8 * mm,
        leftMargin=8 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
    )

    font_name = register_persian_font()

    label_title_style = ParagraphStyle(
        'LabelTitle',
        fontName=font_name,
        fontSize=8,
        alignment=TA_CENTER,
        leading=10,
    )
    label_author_style = ParagraphStyle(
        'LabelAuthor',
        fontName=font_name,
        fontSize=7,
        alignment=TA_CENTER,
        leading=9,
        textColor=colors.HexColor('#333333'),
    )
    label_isbn_style = ParagraphStyle(
        'LabelISBN',
        fontName=font_name,
        fontSize=7,
        alignment=TA_CENTER,
        leading=9,
        textColor=colors.HexColor('#666666'),
    )

    story = []
    labels_per_row = 3
    rows = [books[i:i + labels_per_row] for i in range(0, len(books), labels_per_row)]

    import qrcode
    from reportlab.platypus import Image as RLImage

    for row_books in rows:
        row_cells = []

        for book in row_books:
            qr = qrcode.QRCode(version=1, box_size=3, border=1)
            qr.add_data(f"BOOK:{book.pk}:{book.isbn or book.title}")
            qr.make(fit=True)

            img = qr.make_image(fill='black', back_color='white')
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)

            qr_image = RLImage(img_buffer, width=22 * mm, height=22 * mm)

            cell_content = [
                [qr_image],
                [Paragraph(reshape_persian(book.title[:40] if book.title else ''), label_title_style)],
                [Paragraph(reshape_persian(book.author[:30] if book.author else ''), label_author_style)],
                [Paragraph(book.isbn or '', label_isbn_style)],
            ]

            cell_table = Table(cell_content, colWidths=[60 * mm])
            cell_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))

            row_cells.append(cell_table)

        while len(row_cells) < labels_per_row:
            row_cells.append('')

        row_table = Table([row_cells], colWidths=[63 * mm] * labels_per_row, rowHeights=[55 * mm])
        row_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ]))

        story.append(row_table)
        story.append(Spacer(1, 2 * mm))

    doc.build(story)
    output.seek(0)

    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ==================== Spine Label Export ====================

def split_dewey(dewey):
    """تقسیم رده دیویی به خطوط"""
    if not dewey:
        return []

    # مثال: 297/353 → ['۲۹۷', '۳۵۳']
    # مثال: 297.353 → ['۲۹۷', '۳۵۳']
    dewey = dewey.strip()

    # جایگزینی / و . با /
    dewey = dewey.replace('.', '/')

    if '/' in dewey:
        parts = dewey.split('/')
        return [p.strip() for p in parts if p.strip()]
    else:
        return [dewey]


def split_lcc(lcc):
    """تقسیم رده کنگره به خطوط"""
    if not lcc:
        return []

    # مثال: BP230/17 → ['BP', '۲۳۰/۱۷']
    # مثال: TA345/5 /الف8 → ['TA', '۳۴۵/۵', 'الف۸']
    import re

    lcc = lcc.strip()

    # حذف فاصله‌های اضافی
    lcc = ' '.join(lcc.split())

    # جدا کردن حروف اول (کلاس)
    match = re.match(r'^([A-Z]+)\s*(.*)$', lcc)
    if not match:
        return [lcc]

    letters = match.group(1)
    rest = match.group(2).strip()

    result = [letters]

    if not rest:
        return result

    # جدا کردن اعداد و بخش کاتر
    # مثال: 345/5 /الف8
    if '/' in rest:
        parts = rest.split('/')

        # بخش اول: اعداد
        first = parts[0].strip()
        if first:
            result.append(first)

        # بخش‌های بعدی: کاتر
        for p in parts[1:]:
            p = p.strip()
            if p:
                result.append(p)
    else:
        result.append(rest)

    return result


def export_spine_pdf(books, library_name, spine_height, spine_width, classification, options, filename='spines.pdf'):
    """
    خروجی PDF عطف کتاب (Spine Label)

    :param books: لیست کتاب‌ها
    :param library_name: نام کتابخانه (در بالای عطف)
    :param spine_height: ارتفاع عطف (mm)
    :param spine_width: عرض عطف (mm)
    :param classification: 'dewey', 'lcc', 'both', 'none'
    :param options: dict شامل show_title, show_author, show_volume
    """
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=5 * mm,
        leftMargin=5 * mm,
        topMargin=5 * mm,
        bottomMargin=5 * mm,
    )

    font_name = register_persian_font()

    # استایل‌ها
    library_style = ParagraphStyle(
        'SpineLibrary',
        fontName=font_name,
        fontSize=8,
        alignment=TA_CENTER,
        leading=9,
        textColor=colors.black,
    )
    class_line_style = ParagraphStyle(
        'SpineClassLine',
        fontName=font_name,
        fontSize=10,
        alignment=TA_CENTER,
        leading=12,
        textColor=colors.black,
    )
    title_style_spine = ParagraphStyle(
        'SpineTitle',
        fontName=font_name,
        fontSize=8,
        alignment=TA_CENTER,
        leading=10,
        textColor=colors.black,
    )
    author_style_spine = ParagraphStyle(
        'SpineAuthor',
        fontName=font_name,
        fontSize=7,
        alignment=TA_CENTER,
        leading=9,
        textColor=colors.HexColor('#333333'),
    )
    year_style_spine = ParagraphStyle(
        'SpineYear',
        fontName=font_name,
        fontSize=7,
        alignment=TA_CENTER,
        leading=9,
        textColor=colors.black,
    )
    volume_style_spine = ParagraphStyle(
        'SpineVolume',
        fontName=font_name,
        fontSize=8,
        alignment=TA_CENTER,
        leading=10,
        textColor=colors.black,
    )

    story = []

    # چیدمان
    spines_per_row = max(1, int(190 / (spine_width + 2)))
    rows_per_page = max(1, int(277 / (spine_height + 3)))
    spines_per_page = spines_per_row * rows_per_page

    book_groups = [books[i:i + spines_per_page] for i in range(0, len(books), spines_per_page)]

    for page_num, page_books in enumerate(book_groups):
        rows = [page_books[i:i + spines_per_row] for i in range(0, len(page_books), spines_per_row)]

        for row_books in rows:
            row_cells = []

            for book in row_books:
                content = []

                # ===== ۱. نام کتابخانه (بالا) =====
                if library_name:
                    content.append([Paragraph(reshape_persian(library_name), library_style)])
                    content.append([Spacer(1, 1.5 * mm)])

                # ===== ۲. رده‌بندی (هر خط جدا) =====
                if classification == 'dewey':
                    dewey_lines = split_dewey(book.dewey_class)
                    for line in dewey_lines:
                        content.append([Paragraph(reshape_persian(line), class_line_style)])
                        content.append([Spacer(1, 0.5 * mm)])
                elif classification == 'lcc':
                    lcc_lines = split_lcc(book.lcc_class)
                    for line in lcc_lines:
                        content.append([Paragraph(reshape_persian(line), class_line_style)])
                        content.append([Spacer(1, 0.5 * mm)])
                elif classification == 'both':
                    dewey_lines = split_dewey(book.dewey_class)
                    for line in dewey_lines:
                        content.append([Paragraph(reshape_persian(line), class_line_style)])
                    content.append([Spacer(1, 1 * mm)])
                    lcc_lines = split_lcc(book.lcc_class)
                    for line in lcc_lines:
                        content.append([Paragraph(reshape_persian(line), class_line_style)])
                        content.append([Spacer(1, 0.5 * mm)])

                # ===== ۳. فاصله =====
                content.append([Spacer(1, 2 * mm)])

                # ===== ۴. عنوان =====
                if options.get('show_title') and book.title:
                    title_text = book.title
                    if len(title_text) > 50:
                        title_text = title_text[:47] + '...'
                    content.append([Paragraph(reshape_persian(title_text), title_style_spine)])
                    content.append([Spacer(1, 0.5 * mm)])

                # ===== ۵. نویسنده =====
                if options.get('show_author') and book.author:
                    author_text = book.author
                    if len(author_text) > 35:
                        author_text = author_text[:32] + '...'
                    content.append([Paragraph(reshape_persian(author_text), author_style_spine)])
                    content.append([Spacer(1, 0.5 * mm)])

                # ===== ۶. سال انتشار =====
                if book.publish_year:
                    content.append([Paragraph(reshape_persian(str(book.publish_year)), year_style_spine)])
                    content.append([Spacer(1, 0.5 * mm)])

                # ===== ۷. شماره جلد =====
                if options.get('show_volume'):
                    volume_text = 'ج.۱'
                    content.append([Paragraph(reshape_persian(volume_text), volume_style_spine)])

                # ساخت جدول عطف
                spine_table = Table(
                    content,
                    colWidths=[spine_width * mm],
                )
                spine_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 0.5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),
                    ('LEFTPADDING', (0, 0), (-1, -1), 1),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 1),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
                ]))

                row_cells.append(spine_table)

            while len(row_cells) < spines_per_row:
                row_cells.append('')

            row_table = Table(
                [row_cells],
                colWidths=[(spine_width + 2) * mm] * spines_per_row,
                rowHeights=[spine_height * mm],
            )
            row_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))

            story.append(row_table)
            story.append(Spacer(1, 2 * mm))

        if page_num < len(book_groups) - 1:
            story.append(PageBreak())

    doc.build(story)
    output.seek(0)

    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response