from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from library.api_views import (
    BookViewSet, MemberViewSet, LoanViewSet,
    NotificationViewSet, AuthViewSet, simple_login,
    parse_marc, import_marc
)

router = DefaultRouter()
router.register('books', BookViewSet)
router.register('members', MemberViewSet)
router.register('loans', LoanViewSet)
router.register('notifications', NotificationViewSet)
router.register('auth', AuthViewSet, basename='auth')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),

    # API - MARC
    path('api/books/parse-marc/', parse_marc, name='parse_marc'),
    path('api/books/import-marc/', import_marc, name='import_marc'),

    # API - REST
    path('api/', include(router.urls)),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/simple-login/', simple_login, name='simple_login'),

    # PWA
    path('', include('pwa.urls')),

    # Library URLs
    path('', include('library.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)