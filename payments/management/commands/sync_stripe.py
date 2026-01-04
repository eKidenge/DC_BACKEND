from django.core.management.base import BaseCommand
from django.conf import settings
import stripe
from payments.models import Payment, Payout

stripe.api_key = settings.STRIPE_SECRET_KEY

class Command(BaseCommand):
    help = 'Sync payment statuses with Stripe'
    
    def handle(self, *args, **options):
        self.stdout.write('Syncing payments with Stripe...')
        
        # Sync pending payments
        pending_payments = Payment.objects.filter(status__in=['pending', 'processing'])
        
        for payment in pending_payments:
            if payment.stripe_payment_intent_id:
                try:
                    intent = stripe.PaymentIntent.retrieve(
                        payment.stripe_payment_intent_id
                    )
                    
                    if intent.status == 'succeeded' and payment.status != 'completed':
                        payment.status = 'completed'
                        payment.paid_at = datetime.now()
                        payment.save()
                        self.stdout.write(f"Updated payment {payment.id} to completed")
                    
                    elif intent.status == 'canceled' and payment.status != 'cancelled':
                        payment.status = 'cancelled'
                        payment.save()
                        self.stdout.write(f"Updated payment {payment.id} to cancelled")
                        
                except stripe.error.StripeError as e:
                    self.stderr.write(f"Error syncing payment {payment.id}: {str(e)}")
        
        # Sync payouts
        processing_payouts = Payout.objects.filter(status='processing')
        
        for payout in processing_payouts:
            if payout.stripe_transfer_id:
                try:
                    transfer = stripe.Transfer.retrieve(
                        payout.stripe_transfer_id
                    )
                    
                    if transfer.status == 'paid' and payout.status != 'paid':
                        payout.status = 'paid'
                        payout.paid_at = datetime.now()
                        payout.save()
                        self.stdout.write(f"Updated payout {payout.id} to paid")
                    
                except stripe.error.StripeError as e:
                    self.stderr.write(f"Error syncing payout {payout.id}: {str(e)}")
        
        self.stdout.write('Sync completed!')