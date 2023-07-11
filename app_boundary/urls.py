from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProvinceViewSet, DistrictViewSet, CommuneViewSet,CountryViewSet

router = DefaultRouter()
router.register(r'Country', CountryViewSet, basename='country')
router.register(r'Province', ProvinceViewSet, basename='province')
router.register(r'Commune', CommuneViewSet, basename='commune')
router.register(r'District', DistrictViewSet, basename='district')

urlpatterns = [
    path('', include(router.urls)),
]
