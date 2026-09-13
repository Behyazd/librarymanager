# library/scrapers.py
import requests
from bs4 import BeautifulSoup
import logging
import re

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}


def search_book(query):
    """
    جستجوی کتاب با استفاده از iranketab.ir
    """
    if not query:
        return []

    results = search_iranketab(query)
    if results:
        return results

    # اگر نتیجه‌ای نبود، OpenLibrary را امتحان کن
    return search_openlibrary(query)


def search_iranketab(query):
    """
    جستجو در iranketab.ir
    """
    try:
        url = f"https://iranketab.ir/search/{query}"

        logger.info(f"جستجو در iranketab.ir: {url}")
        response = requests.get(url, headers=HEADERS, timeout=15)

        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        results = []

        # پیدا کردن نتایج جستجو
        book_items = soup.select('div.book, div.result-item, div[class*="book"]')

        for item in book_items[:15]:
            title_elem = item.find('h3') or item.find('h4') or item.find('a', class_=lambda c: c and 'title' in c)
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            if not title or len(title) < 2:
                continue

            # استخراج نویسنده
            author = 'نامشخص'
            author_elem = item.find(class_=lambda c: c and ('author' in c or 'writer' in c))
            if author_elem:
                author = author_elem.get_text(strip=True)

            results.append({
                'title': title,
                'author': author,
                'publisher': '',
                'year': '',
                'isbn': '',
                'source': 'iranketab.ir'
            })

        return results

    except Exception as e:
        logger.error(f"خطا در iranketab.ir: {e}")
        return []


def search_openlibrary(query):
    """
    جستجو در OpenLibrary API (پشتیبان)
    """
    try:
        url = "https://openlibrary.org/search.json"
        params = {
            'q': query,
            'limit': 15,
            'fields': 'title,author_name,publisher,first_publish_year,isbn'
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            return []

        data = response.json()
        results = []

        for doc in data.get('docs', []):
            title = doc.get('title', 'بدون عنوان')
            authors = doc.get('author_name', ['نامشخص'])
            author = authors[0] if authors else 'نامشخص'
            publishers = doc.get('publisher', [''])
            publisher = publishers[0] if publishers else ''

            year = doc.get('first_publish_year', '')
            if not year:
                years = doc.get('publish_year', [])
                year = years[0] if years else ''

            isbns = doc.get('isbn', [])
            isbn = isbns[0] if isbns else ''

            results.append({
                'title': title,
                'author': author,
                'publisher': publisher,
                'year': str(year) if year else '',
                'isbn': isbn,
                'source': 'OpenLibrary'
            })

        return results

    except Exception as e:
        logger.error(f"خطا در OpenLibrary: {e}")
        return []