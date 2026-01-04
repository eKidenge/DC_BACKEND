from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'categories', views.ServiceCategoryViewSet, basename='category')
router.register(r'consultations', views.ConsultationRequestViewSet, basename='consultation')

urlpatterns = [
    # Router URLs
    path('', include(router.urls)),
    
    # Category endpoints
    path('categories/', views.category_list, name='category-list'),
    path('categories/<str:category_name>/professionals/', 
         views.AvailableProfessionalsView.as_view(), 
         name='category-professionals'),
    
    # NEW: Quick consultation endpoint
    path('consultations/quick-create/', 
         views.QuickConsultationView.as_view(), 
         name='quick-consultation'),
    
    # Consultation endpoints
    path('consultations/create/', 
         views.CreateConsultationView.as_view(), 
         name='create-consultation'),
    path('consultations/user/', 
         views.user_consultations, 
         name='user-consultations'),
    path('consultations/stats/', 
         views.ConsultationStatisticsView.as_view(), 
         name='consultation-stats'),
    
    # Consultation actions
    path('consultations/<int:pk>/match/', 
         views.ConsultationRequestViewSet.as_view({'post': 'match'}), 
         name='match-consultation'),
    path('consultations/<int:pk>/accept/', 
         views.ConsultationRequestViewSet.as_view({'post': 'accept'}), 
         name='accept-consultation'),
    path('consultations/<int:pk>/cancel/', 
         views.ConsultationRequestViewSet.as_view({'post': 'cancel'}), 
         name='cancel-consultation'),
    path('consultations/<int:pk>/complete/', 
         views.ConsultationRequestViewSet.as_view({'post': 'complete'}), 
         name='complete-consultation'),
]

# API URL patterns for inclusion in main urls.py
api_patterns = [
    path('categories/', include(urlpatterns)),
]