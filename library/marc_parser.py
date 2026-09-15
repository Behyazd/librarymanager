# library/marc_parser.py
"""
پارسر فایل MARC ایران (IRMARC)
"""
import io
import re
from pymarc import MARCReader, Record


def clean_text(text):
    """پاکسازی متن از کاراکترهای کنترلی Unicode"""
    if not text:
        return ''
    text = re.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069\u061c]', '', text)
    text = ' '.join(text.split())
    return text.strip()


def get_field_value(record, tag, subfield_code):
    """دریافت مقدار یک زیرفیلد خاص از یک فیلد"""
    fields = record.get_fields(tag)
    if fields:
        values = fields[0].get_subfields(subfield_code)
        if values:
            return clean_text(values[0])
    return ''


def parse_marc_file(file_bytes):
    """دریافت فایل MARC و برگرداندن لیست رکوردها"""
    records = []
    file_stream = io.BytesIO(file_bytes)

    try:
        reader = MARCReader(file_stream, to_unicode=True, force_utf8=True)

        for record in reader:
            if record is None:
                continue
            parsed = parse_marc_record(record)
            records.append(parsed)

    except Exception as e:
        print(f"خطا در پارس MARC: {e}")
        import traceback
        traceback.print_exc()
        return []

    return records


def parse_marc_record(record: Record):
    """استخراج فیلدها از یک رکورد MARC ایران"""
    data = {
        'isbn': '',
        'national_biblio_number': '',
        'fapa': '',
        'title': '',
        'subtitle': '',
        'statement_of_responsibility': '',
        'author': '',
        'author_dates': '',
        'publisher': '',
        'publish_place': '',
        'publish_year': '',
        'pages': '',
        'dimensions': '',
        'dewey_class': '',
        'lcc_class': '',
        'subject': '',
        'notes': '',
        'marc_record': str(record),
    }

    # ==================== 010: شابک ====================
    data['isbn'] = get_field_value(record, '010', 'a')

    # ==================== 020 $b: شماره کتابشناسی ملی ====================
    nbn = get_field_value(record, '020', 'b')
    if nbn:
        data['national_biblio_number'] = nbn

    # ==================== 200: عنوان و نام پدیدآور ====================
    field_200 = record.get_fields('200')
    if field_200:
        f = field_200[0]

        title = f.get_subfields('a')
        if title:
            data['title'] = clean_text(title[0]).rstrip(' /:.')

        sub_e = f.get_subfields('e')
        if sub_e:
            e_text = clean_text(sub_e[0]).lstrip(': ').rstrip(' /:.')
            if e_text:
                data['subtitle'] = e_text

        sub_f = f.get_subfields('f')
        if sub_f:
            data['statement_of_responsibility'] = clean_text(sub_f[0])

    # ==================== 210: مشخصات نشر ====================
    field_210 = record.get_fields('210')
    if field_210:
        f = field_210[0]

        place = f.get_subfields('a')
        if place:
            data['publish_place'] = clean_text(place[0]).rstrip(' :,')

        publisher = f.get_subfields('c')
        if publisher:
            pub = clean_text(publisher[0]).lstrip(': ').rstrip(' :,')
            data['publisher'] = pub

        year = f.get_subfields('d')
        if year:
            data['publish_year'] = clean_text(year[0]).lstrip('، ').rstrip(' .,')

    # ==================== 215: مشخصات ظاهری ====================
    field_215 = record.get_fields('215')
    if field_215:
        f = field_215[0]

        pages = f.get_subfields('a')
        if pages:
            data['pages'] = clean_text(pages[0])

        dims = f.get_subfields('d')
        if dims:
            data['dimensions'] = clean_text(dims[0]).lstrip('؛ ')

    # ==================== 320: یادداشت ====================
    data['notes'] = get_field_value(record, '320', 'a')

    # ==================== 606: موضوعات ====================
    subjects = []
    for f in record.get_fields('606'):
        subj_a = f.get_subfields('a')
        subj_y = f.get_subfields('y')

        if subj_a:
            subj_text = clean_text(subj_a[0])
            if subj_y:
                subj_text += ' ' + clean_text(subj_y[0])
            subjects.append(subj_text)

    data['subject'] = '\n'.join(subjects)

    # ==================== 676: رده دیویی ====================
    data['dewey_class'] = get_field_value(record, '676', 'a')

    # ==================== 680: رده کنگره ====================
    data['lcc_class'] = get_field_value(record, '680', 'a')

    # ==================== 700: سرشناسه (نویسنده) ====================
    # فقط از فیلد 700 می‌خوانیم (نه 100)
    field_700 = record.get_fields('700')
    if field_700:
        f = field_700[0]

        author_a = f.get_subfields('a')
        author_b = f.get_subfields('b')
        author_f = f.get_subfields('f')

        author_parts = []
        if author_a:
            author_parts.append(clean_text(author_a[0]))
        if author_b:
            b_text = clean_text(author_b[0]).lstrip('، ').strip()
            if b_text:
                author_parts.append(b_text)

        data['author'] = '، '.join(author_parts)

        if author_f:
            data['author_dates'] = clean_text(author_f[0]).lstrip('، ').rstrip('،')

    # ==================== 915: فاپا ====================
    data['fapa'] = get_field_value(record, '915', 'a')

    return data