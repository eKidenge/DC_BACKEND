from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from dashboard import views as dashboard_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),
    path('api/categories/', include('categories.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/dashboard/', include('dashboard.urls')),  # dashboard app URLs
    
    # ✅ ADD THIS LINE - Admin Dashboard API
    path('api/admin/', include('admin_dashboard.urls')),
    
    # Direct call-request endpoints at /api/call-requests/
    path('api/call-requests/create/', dashboard_views.create_call_request, name='create_call_request'),
    path('api/call-requests/<int:pk>/', dashboard_views.get_call_request, name='get_call_request'),
    path('api/call-requests/<int:pk>/update-status/', dashboard_views.update_call_status, name='update_call_status'),
    path('api/call-requests/<int:pk>/cancel/', dashboard_views.cancel_call_request, name='cancel_call_request'),
    path('api/call-requests/pending/', dashboard_views.professional_pending_calls, name='professional_pending_calls'),
    
    # API info at root
    path('', lambda request: JsonResponse({
        'app': 'Expert Consultation Platform',
        'api': 'http://localhost:8000/api/',
        'frontend': 'http://localhost:3000',
        'admin': 'http://localhost:8000/admin/',
        'admin_api': 'http://localhost:8000/api/admin/',  # ✅ Added admin API info
    })),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)