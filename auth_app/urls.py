from rest_framework.routers import DefaultRouter
from .views import UserAccountViewSet

router = DefaultRouter()
router.register(r'accounts', UserAccountViewSet, basename='account')

urlpatterns = router.urls