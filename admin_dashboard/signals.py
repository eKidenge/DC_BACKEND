from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from accounts.models import ProfessionalProfile, ClientProfile
from categories.models import ConsultationRequest
from .models import AdminLog, PlatformAnalytics
from django.utils import timezone
import threading

User = get_user_model()

# Use thread-local storage for cache
_local = threading.local()

def get_verification_cache():
    """Get thread-local cache"""
    if not hasattr(_local, 'verification_cache'):
        _local.verification_cache = {}
    return _local.verification_cache

@receiver(pre_save, sender=ProfessionalProfile)
def cache_professional_verification_status(sender, instance, **kwargs):
    """Cache the current verification status before saving"""
    cache = get_verification_cache()
    
    if instance.pk:
        try:
            old_instance = ProfessionalProfile.objects.get(pk=instance.pk)
            cache[instance.pk] = {
                'is_verified': old_instance.is_verified,
                'timestamp': timezone.now()
            }
        except ProfessionalProfile.DoesNotExist:
            cache[instance.pk] = {'is_verified': None, 'timestamp': timezone.now()}
    else:
        # New instance - nothing to cache
        pass

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
    cache = get_verification_cache()
    
    if not created and instance.pk:
        # Get old verification status from cache
        cached_data = cache.get(instance.pk)
        
        if cached_data:
            old_is_verified = cached_data.get('is_verified')
            
            # Check if verification status changed
            if old_is_verified is not None and old_is_verified != instance.is_verified:
                # Find the admin user who made the change
                import inspect
                admin_user = None
                request_obj = None
                
                for frame_info in inspect.stack():
                    frame_locals = frame_info.frame.f_locals
                    if 'request' in frame_locals:
                        request_obj = frame_locals['request']
                        if request_obj.user.is_authenticated and request_obj.user.is_staff:
                            admin_user = request_obj.user
                            break
                
                # If no admin found in stack, try to get from threadlocal or use a default
                if not admin_user:
                    # You might want to track admin differently here
                    # For now, create log without admin
                    AdminLog.objects.create(
                        admin=None,
                        action='professional_verified' if instance.is_verified else 'professional_unverified',
                        description=f'Professional {instance.user.get_full_name()} {"verified" if instance.is_verified else "unverified"} (admin unknown)',
                        ip_address='',
                        user_agent=''
                    )
                else:
                    # Log the verification change with admin info
                    action = 'professional_verified' if instance.is_verified else 'professional_unverified'
                    status_change = "verified" if instance.is_verified else "unverified"
                    
                    AdminLog.objects.create(
                        admin=admin_user,
                        action=action,
                        description=f'{status_change.capitalize()} professional: {instance.user.get_full_name()}',
                        ip_address=get_client_ip(request_obj) if request_obj else '',
                        user_agent=request_obj.META.get('HTTP_USER_AGENT', '') if request_obj else ''
                    )
        
        # Clean up cache entry
        if instance.pk in cache:
            del cache[instance.pk]

def get_client_ip(request):
    """Extract client IP from request"""
    if not request:
        return ''
    
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip