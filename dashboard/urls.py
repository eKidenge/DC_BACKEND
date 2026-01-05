from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'profile', views.ProfessionalProfileViewSet, basename='professional-profile')
router.register(r'availability', views.ProfessionalAvailabilityViewSet, basename='professional-availability')
router.register(r'stats', views.ProfessionalStatViewSet, basename='professional-stats')
router.register(r'incoming-calls', views.IncomingCallViewSet, basename='incoming-calls')
router.register(r'notifications', views.ProfessionalNotificationViewSet, basename='professional-notifications')
router.register(r'calendar', views.ProfessionalCalendarViewSet, basename='professional-calendar')
router.register(r'call-history', views.CallHistoryViewSet, basename='call-history')

urlpatterns = [
    path('', include(router.urls)),
    
    # Dashboard summary
    path('dashboard-summary/', views.dashboard_summary, name='dashboard-summary'),
    
    # Specific endpoints for React frontend
    path('toggle-online/', views.ProfessionalProfileViewSet.as_view({'post': 'toggle_online'}), name='toggle-online'),
    
    # Incoming calls specific endpoints
    path('incoming-calls/pending/', views.IncomingCallViewSet.as_view({'get': 'list'}), name='pending-calls'),
    path('incoming-calls/<int:pk>/accept/', views.IncomingCallViewSet.as_view({'post': 'accept'}), name='accept-call'),
    path('incoming-calls/<int:pk>/reject/', views.IncomingCallViewSet.as_view({'post': 'reject'}), name='reject-call'),
    path('incoming-calls/<int:pk>/update-status/', views.IncomingCallViewSet.as_view({'post': 'update_status'}), name='update-call-status'),
    
    # Notifications specific endpoints
    path('notifications/<int:pk>/mark-read/', views.ProfessionalNotificationViewSet.as_view({'post': 'mark_read'}), name='mark-notification-read'),
    path('notifications/mark-all-read/', views.ProfessionalNotificationViewSet.as_view({'post': 'mark_all_read'}), name='mark-all-notifications-read'),
    
    # Calendar specific endpoints
    path('calendar/upcoming/', views.ProfessionalCalendarViewSet.as_view({'get': 'upcoming'}), name='upcoming-events'),
    
    # Stats specific endpoints
    path('stats/summary/', views.ProfessionalStatViewSet.as_view({'get': 'summary'}), name='stats-summary'),
    
    # Availability specific endpoints
    path('availability/update/', views.ProfessionalAvailabilityViewSet.as_view({'post': 'update_settings'}), name='update-availability-settings'),

    # Call Request URLs
    path('call-requests/create/', views.create_call_request, name='create_call_request'),
    path('call-requests/<int:pk>/', views.get_call_request, name='get_call_request'),
    path('call-requests/<int:pk>/update-status/', views.update_call_status, name='update_call_status'),
    path('call-requests/<int:pk>/cancel/', views.cancel_call_request, name='cancel_call_request'),
    path('call-requests/pending/', views.professional_pending_calls, name='professional_pending_calls'),
    ]
