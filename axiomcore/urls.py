from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from auth_app.views import CustomTokenObtainPairView, ValidateTokenView, AppInfoView

urlpatterns = [
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('verify-auth/', ValidateTokenView.as_view(), name='validate-token'),
    path('auth/', include('auth_app.urls')),
    path('admin/', admin.site.urls),
    path('api/', include('encryptor.urls')),
    path('api/app-info/', AppInfoView.as_view(), name='app-info'),

]