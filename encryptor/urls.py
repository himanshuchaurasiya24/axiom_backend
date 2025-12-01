from rest_framework.routers import DefaultRouter
from .views import FileViewSet, CategoryViewSet

router = DefaultRouter()
router.register(r'files', FileViewSet, basename='file')
router.register(r"categories", CategoryViewSet, basename='category')

urlpatterns = router.urls