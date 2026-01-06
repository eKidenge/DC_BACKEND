from django.apps import AppConfig

class AdminDashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admin_dashboard'
    verbose_name = 'Admin Dashboard'
    
    def ready(self):
        """Import signals when app is ready"""
        try:
            import admin_dashboard.signals  # noqa
        except ImportError:
            pass