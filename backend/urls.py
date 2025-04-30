# backend/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Simple JWT view'larını import ediyoruz
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView, # Opsiyonel: Token doğrulamak için
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')), # API uygulamamızın URL'leri
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')), # Browsable API login/logout

    # Simple JWT URL'leri
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'), # Token almak için (username/password gönderilir)
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'), # Access token yenilemek için (refresh token gönderilir)
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'), # Opsiyonel: Token'ın geçerli olup olmadığını kontrol etmek için
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)