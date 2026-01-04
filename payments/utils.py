from django.conf import settings
import stripe
from decimal import Decimal

stripe.api_key = settings.STRIPE_SECRET_KEY

def calculate_fees(amount, professional_rate=None):
    """Calculate platform and processing fees"""
    amount = Decimal(str(amount))
    
    # Platform fee percentage (20% default)
    platform_fee_percent = Decimal('20.00')
    
    # Stripe processing fee (2.9% + $0.30)
    stripe_percent = Decimal('2.90')
    stripe_fixed = Decimal('0.30')
    
    # Calculate fees
    platform_fee = amount * (platform_fee_percent / 100)
    stripe_fee = (amount * (stripe_percent / 100)) + stripe_fixed
    
    # Professional earning
    professional_earning = amount - platform_fee - stripe_fee
    
    return {
        'gross_amount': amount,
        'platform_fee': platform_fee,
        'processing_fee': stripe_fee,
        'professional_earning': professional_earning,
        'platform_fee_percent': platform_fee_percent,
        'processing_fee_percent': stripe_percent,
    }

def create_stripe_customer(user):
    """Create a Stripe customer for user"""
    try:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.get_full_name(),
            metadata={
                'user_id': str(user.id),
                'username': user.username
            }
        )
        return customer.id
    except stripe.error.StripeError as e:
        raise Exception(f"Failed to create Stripe customer: {str(e)}")

def create_connected_account(professional):
    """Create Stripe Connect account for professional"""
    try:
        account = stripe.Account.create(
            type='express',
            country='US',  # Update based on professional's country
            email=professional.user.email,
            business_type='individual',
            individual={
                'first_name': professional.user.first_name,
                'last_name': professional.user.last_name,
                'email': professional.user.email,
            },
            capabilities={
                'card_payments': {'requested': True},
                'transfers': {'requested': True},
            },
            business_profile={
                'url': 'https://yourplatform.com',
                'mcc': '7299',  # Miscellaneous personal services
            }
        )
        return account.id
    except stripe.error.StripeError as e:
        raise Exception(f"Failed to create Stripe account: {str(e)}")

def generate_onboarding_link(professional):
    """Generate Stripe onboarding link for professionals"""
    if not professional.stripe_account_id:
        raise Exception("Professional doesn't have Stripe account")
    
    try:
        account_link = stripe.AccountLink.create(
            account=professional.stripe_account_id,
            refresh_url='https://yourplatform.com/dashboard/payouts/setup',
            return_url='https://yourplatform.com/dashboard/payouts/success',
            type='account_onboarding',
        )
        return account_link.url
    except stripe.error.StripeError as e:
        raise Exception(f"Failed to create onboarding link: {str(e)}")

def verify_stripe_signature(payload, sig_header):
    """Verify Stripe webhook signature"""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        return event
    except ValueError:
        raise Exception("Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise Exception("Invalid signature")