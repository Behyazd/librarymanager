"""
Django settings for library_project project.
"""

import os
from pathlib import Path
import dj_database_url
from datetime import timedelta

# ==================== BASE ====================
BASE_DIR = Path(__file__).resolve().parent.parent

# ==================== SECURITY ====================
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-temporary-key-change-in-production'
)

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '0.0.0.0',
    '.onrender.com',
    'librarymanager-fvth.onrender.com',
    'behyazd.pythonanywhere.com',
    '172.19.8.216',
    '.median.co',
    '.gonative.io',
    '.median.co.',
]

CSRF_TRUSTED_ORIGINS = [
    'https://librarymanager-fvth.onrender.com',
    'https://*.onrender.com',
    'https://behyazd.pythonanywhere.com',
    'https://*.median.co',
    'https://*.median.co.',
    'https://*.gonative.io',
    'https://*.gonative.io.',
    'https://*.trycloudflare.com',
    'https://*.lhr.life',
    'https://*.localhost.run',
]

# ==================== APPLICATION DEFINITION ====================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_jalali',
    'library',
    'pwa',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'library_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'library_project.wsgi.application'

# ==================== DATABASE ====================
# در محیط تولید (Render) از PostgreSQL استفاده می‌کند
# در محیط محلی از SQLite استفاده می‌کند
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# ==================== PASSWORD VALIDATION ====================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==================== INTERNATIONALIZATION ====================
LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True

# ==================== STATIC FILES ====================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []

# WhiteNoise برای سرو فایل‌های استاتیک در تولید
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# ==================== MEDIA FILES ====================
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ==================== AUTHENTICATION ====================
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# ==================== REST FRAMEWORK ====================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': (
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
}

# ==================== JWT ====================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ==================== CORS ====================
CORS_ALLOW_ALL_ORIGINS = True

# برای تولید، این را جایگزین کنید:
# CORS_ALLOWED_ORIGINS = [
#     'https://behyazd.pythonanywhere.com',
#     'https://librarymanager.onrender.com',
#     'https://*.median.co',
# ]

# ==================== PWA ====================
PWA_APP_NAME = 'کتابخانه من'
PWA_APP_DESCRIPTION = "مدیریت کتابخانه شخصی"
PWA_APP_THEME_COLOR = '#0A76D6'
PWA_APP_BACKGROUND_COLOR = '#ffffff'
PWA_APP_DISPLAY = 'standalone'
PWA_APP_SCOPE = '/'
PWA_APP_ORIENTATION = 'portrait'
PWA_APP_START_URL = '/'
PWA_APP_STATUS_BAR_COLOR = 'default'
PWA_APP_ICONS = [
    {
        'src': '/static/icons/icon-192x192.png',
        'sizes': '192x192',
        'type': 'image/png'
    },
    {
        'src': '/static/icons/icon-512x512.png',
        'sizes': '512x512',
        'type': 'image/png'
    }
]
PWA_APP_DIR = 'rtl'
PWA_APP_LANG = 'fa'
PWA_APP_DEBUG_MODE = False

# ==================== DEFAULT AUTO FIELD ====================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==================== SECURITY (PRODUCTION) ====================
# این تنظیمات فقط در محیط تولید (DEBUG=False) اعمال می‌شوند
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000  # 1 سال
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True