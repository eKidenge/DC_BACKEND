from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from accounts.models import ProfessionalProfile, ClientProfile
from categories.models import ConsultationRequest
from .models import AdminLog, PlatformAnalytics
from django.utils import timezone

User = get_user_model()

@receiver(post_save, sender=User)
def log_user_creation(sender, instance, created, **kwargs):
    """Log user creation/updates"""
    if created:
        action = 'user_created'
        description = f'New user created: {instance.get_full_name()} ({instance.email})'
    else:
        action = 'user_updated'
        description = f'User updated: {instance.get_full_name()}'
    
    # Check if request object is available (for admin actions)
    import inspect
    for frame_info in inspect.stack():
        if 'request' in frame_info.frame.f_locals:
            request = frame_info.frame.f_locals['request']
            if request.user.is_authenticated and request.user.is_staff:
                AdminLog.objects.create(
                    admin=request.user,
                    action=action,
                    description=description,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            break

@receiver(post_save, sender=ProfessionalProfile)
def log_professional_verification(sender, instance, created, **kwargs):
    """Log professional verification"""
    if not created and 'is_verified' in instance.get_dirty_fields():
        if instance.is_verified:
            import inspect
            for frame_info in inspect.stack():
                if 'request' in frame_info.frame.f_locals:
                    request = frame_info.frame.f_locals['request']
                    if request.user.is_authenticated and request.user.is_staff:
                        AdminLog.objects.create(
                            admin=request.user,
                            action='professional_verified',
                            description=f'Verified professional: {instance.user.get_full_name()}',
                            ip_address=get_client_ip(request),
                            user_agent=request.META.get('HTTP_USER_AGENT', '')
                        )
                    break

def get_client_ip(request):
    """Extract client IP from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip