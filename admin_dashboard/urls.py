from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'professionals', views.ProfessionalViewSet, basename='admin-professionals')
router.register(r'clients', views.ClientViewSet, basename='admin-clients')
router.register(r'consultations', views.ConsultationViewSet, basename='admin-consultations')
router.register(r'reports', views.ReportViewSet, basename='admin-reports')
router.register(r'users', views.UserViewSet, basename='admin-users')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/stats/', views.AdminDashboardViewSet.as_view({'get': 'list'}), name='admin-dashboard-stats'),
    path('dashboard/activity/', views.AdminDashboardViewSet.as_view({'get': 'activity'}), name='admin-dashboard-activity'),
]