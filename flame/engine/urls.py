from .views import UtilizationViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(prefix='utilization', viewset=UtilizationViewSet)
urlpatterns = router.urls
print(urlpatterns)
