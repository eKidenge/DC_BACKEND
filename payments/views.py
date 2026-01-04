from rest_framework import generics, viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from django.db import transaction
from django.utils import timezone
from django.conf import settings
import stripe

from .models import Payment, Transaction, Payout, ProfessionalEarning, Coupon
from .serializers import (
    PaymentSerializer, CreatePaymentSerializer, PaymentIntentSerializer,
    ConfirmPaymentSerializer, PayoutSerializer, CreatePayoutSerializer,
    CouponSerializer, ValidateCouponSerializer
)
from categories.models import ConsultationRequest
from accounts.models import ProfessionalProfile

stripe.api_key = settings.STRIPE_SECRET_KEY

class PaymentViewSet(viewsets.ModelViewSet):
    """Payment management"""
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def create_payment_intent(self, request):
        """Create Stripe payment intent"""
        serializer = PaymentIntentSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                result = serializer.save()
                return Response(result, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def confirm_payment(self, request):
        """Confirm payment and update consultation status"""
        serializer = ConfirmPaymentSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            with transaction.atomic():
                payment = serializer.validated_data['payment']
                payment_intent = serializer.validated_data['payment_intent']
                
                # Update payment status
                payment.status = 'completed'
                payment.paid_at = timezone.now()
                payment.save()
                
                # Update consultation status
                consultation = payment.consultation
                consultation.status = 'accepted'
                consultation.save()
                
                # Create professional earning
                professional = consultation.professional
                
                # Calculate fees from Stripe metadata
                metadata = payment_intent.metadata
                platform_fee = float(metadata.get('platform_fee', 0))
                professional_earning = float(metadata.get('professional_earning', 0))
                
                ProfessionalEarning.objects.create(
                    professional=professional,
                    payment=payment,
                    gross_amount=payment.amount,
                    platform_fee=platform_fee,
                    processing_fee=payment.amount * 0.029,  # 2.9%
                    net_amount=professional_earning,
                    is_paid_out=False
                )
                
                # Create transaction record
                Transaction.objects.create(
                    payment=payment,
                    user=payment.user,
                    amount=payment.amount,
                    transaction_type='payment',
                    description=f"Consultation payment for {consultation.get_category_display()}",
                    stripe_transaction_id=payment_intent.id
                )
                
                return Response({
                    'success': True,
                    'payment_id': str(payment.id),
                    'call_id': str(consultation.id),
                    'message': 'Payment successful! Redirecting to call...'
                })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def refund(self, request, pk=None):
        """Refund a payment"""
        payment = self.get_object()
        
        if not payment.is_refundable:
            return Response(
                {'error': 'Payment cannot be refunded'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Create Stripe refund
            refund = stripe.Refund.create(
                payment_intent=payment.stripe_payment_intent_id
            )
            
            # Update payment status
            payment.status = 'refunded'
            payment.save()
            
            # Create refund transaction
            Transaction.objects.create(
                payment=payment,
                user=payment.user,
                amount=payment.amount,
                transaction_type='refund',
                description='Payment refund',
                stripe_transaction_id=refund.id
            )
            
            return Response({
                'success': True,
                'refund_id': refund.id,
                'amount': payment.amount
            })
            
        except stripe.error.StripeError as e:
            return Response(
                {'error': f'Stripe error: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

class PayoutViewSet(viewsets.ModelViewSet):
    """Payout management for professionals"""
    serializer_class = PayoutSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        try:
            professional = self.request.user.professional_profile
            return Payout.objects.filter(professional=professional)
        except ProfessionalProfile.DoesNotExist:
            return Payout.objects.none()
    
    def create(self, request):
        """Request a payout"""
        serializer = CreatePayoutSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            professional = serializer.validated_data['professional']
            amount = serializer.validated_data['amount']
            
            try:
                # Check if professional has Stripe Connect account
                if not professional.stripe_account_id:
                    # Create Stripe Connect account if doesn't exist
                    account = stripe.Account.create(
                        type='express',
                        country='US',
                        email=professional.user.email,
                        capabilities={
                            'card_payments': {'requested': True},
                            'transfers': {'requested': True},
                        }
                    )
                    professional.stripe_account_id = account.id
                    professional.save()
                
                # Create transfer to professional's Stripe account
                transfer = stripe.Transfer.create(
                    amount=int(amount * 100),  # Convert to cents
                    currency=serializer.validated_data['currency'].lower(),
                    destination=professional.stripe_account_id,
                    description=f"Payout for {professional.user.get_full_name()}"
                )
                
                # Create payout record
                payout = Payout.objects.create(
                    professional=professional,
                    amount=amount,
                    currency=serializer.validated_data['currency'],
                    status='processing',
                    stripe_transfer_id=transfer.id
                )
                
                # Mark earnings as paid out
                earnings = ProfessionalEarning.objects.filter(
                    professional=professional,
                    is_paid_out=False
                )[:5]  # Mark top 5 unpaid earnings
                
                for earning in earnings:
                    earning.is_paid_out = True
                    earning.payout = payout
                    earning.paid_out_at = timezone.now()
                    earning.save()
                
                return Response(
                    PayoutSerializer(payout).data,
                    status=status.HTTP_201_CREATED
                )
                
            except stripe.error.StripeError as e:
                return Response(
                    {'error': f'Stripe error: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def balance(self, request):
        """Get professional's available balance"""
        try:
            professional = request.user.professional_profile
            
            # Calculate total earnings
            total_earnings = ProfessionalEarning.objects.filter(
                professional=professional
            ).aggregate(
                total_gross=models.Sum('gross_amount'),
                total_net=models.Sum('net_amount'),
                pending_payout=models.Sum('net_amount', filter=models.Q(is_paid_out=False))
            )
            
            return Response({
                'available_balance': total_earnings['pending_payout'] or 0,
                'total_earned': total_earnings['total_net'] or 0,
                'total_gross': total_earnings['total_gross'] or 0,
                'currency': 'USD'
            })
            
        except ProfessionalProfile.DoesNotExist:
            return Response(
                {'error': 'User is not a professional'},
                status=status.HTTP_400_BAD_REQUEST
            )

class CouponViewSet(viewsets.ReadOnlyModelViewSet):
    """Coupon management"""
    queryset = Coupon.objects.filter(is_active=True)
    serializer_class = CouponSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def validate(self, request):
        """Validate a coupon code"""
        serializer = ValidateCouponSerializer(data=request.data)
        
        if serializer.is_valid():
            coupon = serializer.validated_data['coupon']
            amount = serializer.validated_data['amount']
            
            discounted_amount = coupon.apply_discount(amount)
            
            return Response({
                'valid': True,
                'coupon': CouponSerializer(coupon).data,
                'original_amount': amount,
                'discounted_amount': discounted_amount,
                'discount': amount - discounted_amount,
                'discount_type': coupon.discount_type,
                'discount_value': coupon.discount_value
            })
        
        return Response({
            'valid': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class PaymentWebhookView(APIView):
    """Handle Stripe webhooks"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            return Response({'error': 'Invalid payload'}, status=400)
        except stripe.error.SignatureVerificationError as e:
            return Response({'error': 'Invalid signature'}, status=400)
        
        # Handle the event
        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            self.handle_payment_succeeded(payment_intent)
        elif event['type'] == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            self.handle_payment_failed(payment_intent)
        elif event['type'] == 'transfer.created':
            transfer = event['data']['object']
            self.handle_transfer_created(transfer)
        
        return Response({'received': True})
    
    def handle_payment_succeeded(self, payment_intent):
        """Handle successful payment"""
        try:
            payment = Payment.objects.get(
                stripe_payment_intent_id=payment_intent['id']
            )
            
            # Update payment status if not already updated
            if payment.status != 'completed':
                payment.status = 'completed'
                payment.paid_at = timezone.now()
                payment.save()
                
                # Update consultation status
                consultation = payment.consultation
                consultation.status = 'accepted'
                consultation.save()
        
        except Payment.DoesNotExist:
            pass
    
    def handle_payment_failed(self, payment_intent):
        """Handle failed payment"""
        try:
            payment = Payment.objects.get(
                stripe_payment_intent_id=payment_intent['id']
            )
            payment.status = 'failed'
            payment.save()
        
        except Payment.DoesNotExist:
            pass
    
    def handle_transfer_created(self, transfer):
        """Handle transfer to professional"""
        try:
            payout = Payout.objects.get(stripe_transfer_id=transfer['id'])
            payout.status = 'paid'
            payout.paid_at = timezone.now()
            payout.save()
        
        except Payout.DoesNotExist:
            pass

class PaymentMethodsView(APIView):
    """Manage user's saved payment methods"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get user's saved payment methods"""
        user = request.user
        
        if not user.stripe_customer_id:
            return Response({'payment_methods': []})
        
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=user.stripe_customer_id,
                type='card'
            )
            
            methods = []
            for pm in payment_methods.data:
                methods.append({
                    'id': pm.id,
                    'brand': pm.card.brand,
                    'last4': pm.card.last4,
                    'exp_month': pm.card.exp_month,
                    'exp_year': pm.card.exp_year,
                    'is_default': False  # You can implement default logic
                })
            
            return Response({'payment_methods': methods})
            
        except stripe.error.StripeError as e:
            return Response(
                {'error': f'Stripe error: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def post(self, request):
        """Attach a payment method to user"""
        user = request.user
        
        # Create Stripe customer if doesn't exist
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.get_full_name()
            )
            user.stripe_customer_id = customer.id
            user.save()
        
        payment_method_id = request.data.get('payment_method_id')
        
        if not payment_method_id:
            return Response(
                {'error': 'Payment method ID required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=user.stripe_customer_id
            )
            
            return Response({'success': True})
            
        except stripe.error.StripeError as e:
            return Response(
                {'error': f'Stripe error: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )