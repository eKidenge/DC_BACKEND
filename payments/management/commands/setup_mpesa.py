from django.core.management.base import BaseCommand
from django.conf import settings
from payments.models import MpesaConfiguration

class Command(BaseCommand):
    help = 'Setup M-Pesa configuration for sandbox or production'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--environment',
            type=str,
            choices=['sandbox', 'production'],
            default='sandbox',
            help='Environment to setup (sandbox or production)'
        )
    
    def handle(self, *args, **options):
        environment = options['environment']
        
        if environment == 'sandbox':
            config = {
                'name': 'Sandbox Configuration',
                'config_type': 'sandbox',
                'consumer_key': '',  # Get from Safaricom Developer Portal
                'consumer_secret': '',  # Get from Safaricom Developer Portal
                'passkey': '',  # Get from Safaricom Developer Portal
                'business_short_code': '174379',  # Sandbox shortcode
                'party_b': '174379',
                'callback_url': f'{settings.BASE_URL}/api/payments/mpesa/callback/',
                'result_url': f'{settings.BASE_URL}/api/payments/mpesa/callback/',
            }
        else:  # production
            config = {
                'name': 'Production Configuration',
                'config_type': 'production',
                'consumer_key': '',  # Your production consumer key
                'consumer_secret': '',  # Your production consumer secret
                'passkey': '',  # Your production passkey
                'business_short_code': '',  # Your business shortcode
                'party_b': '',  # Your party B
                'callback_url': f'{settings.BASE_URL}/api/payments/mpesa/callback/',
                'result_url': f'{settings.BASE_URL}/api/payments/mpesa/callback/',
            }
        
        # Create or update configuration
        mpesa_config, created = MpesaConfiguration.objects.update_or_create(
            config_type=environment,
            defaults=config
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(
                f'{environment.capitalize()} M-Pesa configuration created successfully!'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'{environment.capitalize()} M-Pesa configuration updated successfully!'
            ))