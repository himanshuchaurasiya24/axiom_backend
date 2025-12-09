from rest_framework.routers import DefaultRouter
from .views import FileViewSet, CategoryViewSet,CategorySummaryViewSet

router = DefaultRouter()
router.register(r'files', FileViewSet, basename='file')
router.register(r"categories", CategoryViewSet, basename='category')
router.register(r'category-summary', CategorySummaryViewSet, basename='category-summary')

urlpatterns = router.urls