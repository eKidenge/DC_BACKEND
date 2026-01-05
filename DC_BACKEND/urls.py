from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),
    path('api/categories/', include('categories.urls')),
    path('api/payments/', include('payments.urls')),
    #path('api/calls/', include('calls.urls')),
    path('api/dashboard/', include('dashboard.urls')),
    path('api/call-requests/', include('dashboard.urls')),  # <-- add this line
    
    # API info at root
    path('', lambda request: JsonResponse({
        'app': 'Expert Consultation Platform',
        'api': 'http://localhost:8000/api/',
        'frontend': 'http://localhost:3000',
        'admin': 'http://localhost:8000/admin/'
    })),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)