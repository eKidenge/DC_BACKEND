from django.core.management.base import BaseCommand
from django.utils import timezone
from payments.models import MpesaPaymentRequest, MpesaAccessToken

class Command(BaseCommand):
    help = 'Clean up expired M-Pesa data'
    
    def handle(self, *args, **options):
        self.stdout.write('Cleaning up M-Pesa data...')
        
        # Clean expired payment requests
        expired_requests = MpesaPaymentRequest.objects.filter(
            expires_at__lt=timezone.now(),
            status__in=['pending', 'initiated']
        )
        
        count = expired_requests.count()
        expired_requests.update(status='expired', is_active=False)
        
        self.stdout.write(f'Marked {count} payment requests as expired')
        
        # Clean old access tokens (older than 2 hours)
        old_tokens = MpesaAccessToken.objects.filter(
            generated_at__lt=timezone.now() - timezone.timedelta(hours=2)
        )
        
        token_count = old_tokens.count()
        old_tokens.delete()
        
        self.stdout.write(f'Deleted {token_count} old access tokens')
        
        self.stdout.write(self.style.SUCCESS('Cleanup completed!'))