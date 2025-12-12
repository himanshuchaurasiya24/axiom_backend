from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from auth_app.views import *
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('verify-auth/', ValidateTokenView.as_view(), name='validate-token'),
    path('auth/', include('auth_app.urls')),
    path('axiom-admin/', admin.site.urls),
    path('api/', include('encryptor.urls')),
    path('', health_check),
    path('api/app-info/', AppInfoView.as_view(), name='app-info'),
    path('plans/', SubscriptionInfoView.as_view(), name='subscription-plans'),
]

# This block is essential for local development and is skipped in production (DEBUG=False)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)