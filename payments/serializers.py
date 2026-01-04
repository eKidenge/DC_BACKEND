from rest_framework import serializers
from .models import Payment, Transaction, Payout, ProfessionalEarning, Coupon
from accounts.models import ProfessionalProfile
from categories.models import ConsultationRequest
from decimal import Decimal
import stripe
from django.conf import settings

class PaymentSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    consultation_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            'id', 'amount', 'currency', 'status', 'payment_method',
            'created_at', 'paid_at', 'description', 'user_email',
            'consultation_details', 'stripe_payment_intent_id'
        ]
        read_only_fields = ['id', 'created_at', 'paid_at', 'stripe_payment_intent_id']
    
    def get_consultation_details(self, obj):
        if obj.consultation:
            return {
                'id': obj.consultation.id,
                'category': obj.consultation.get_category_display(),
                'duration': obj.consultation.duration_minutes,
            }
        return None

class CreatePaymentSerializer(serializers.Serializer):
    consultation_id = serializers.IntegerField(required=True)
    payment_method = serializers.ChoiceField(
        choices=['stripe', 'paypal'], 
        default='stripe'
    )
    save_payment_method = serializers.BooleanField(default=False)
    coupon_code = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        user = self.context['request'].user
        
        # Validate consultation exists and belongs to user
        try:
            consultation = ConsultationRequest.objects.get(
                id=data['consultation_id'],
                client=user
            )
        except ConsultationRequest.DoesNotExist:
            raise serializers.ValidationError("Consultation not found")
        
        # Check if consultation already has payment
        if consultation.payments.filter(status__in=['completed', 'processing']).exists():
            raise serializers.ValidationError("Payment already exists for this consultation")
        
        # Validate professional is assigned
        if not consultation.professional:
            raise serializers.ValidationError("No professional assigned to this consultation")
        
        data['consultation'] = consultation
        return data

class PaymentIntentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1)
    currency = serializers.CharField(default='usd')
    consultation_id = serializers.IntegerField()
    payment_method_types = serializers.ListField(
        child=serializers.CharField(),
        default=['card']
    )
    
    def create(self, validated_data):
        consultation_id = validated_data['consultation_id']
        amount = validated_data['amount']
        
        try:
            consultation = ConsultationRequest.objects.get(id=consultation_id)
            professional = consultation.professional
            
            # Calculate platform fees
            platform_fee_percent = Decimal('20.00')  # 20% platform fee
            processing_fee_percent = Decimal('2.90')  # 2.9% processing fee
            
            platform_fee = amount * (platform_fee_percent / 100)
            processing_fee = amount * (processing_fee_percent / 100)
            professional_earning = amount - platform_fee - processing_fee
            
            # Create Stripe Payment Intent
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            payment_intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=validated_data['currency'],
                payment_method_types=validated_data['payment_method_types'],
                metadata={
                    'consultation_id': str(consultation_id),
                    'professional_id': str(professional.id),
                    'user_id': str(consultation.client.id),
                    'platform_fee': str(platform_fee),
                    'professional_earning': str(professional_earning)
                }
            )
            
            # Create payment record
            payment = Payment.objects.create(
                user=consultation.client,
                consultation=consultation,
                amount=amount,
                currency=validated_data['currency'].upper(),
                status='pending',
                payment_method='stripe',
                stripe_payment_intent_id=payment_intent.id,
                stripe_client_secret=payment_intent.client_secret,
                description=f"Consultation with {professional.user.get_full_name()}"
            )
            
            return {
                'client_secret': payment_intent.client_secret,
                'payment_id': str(payment.id),
                'amount': amount,
                'professional': professional.user.get_full_name(),
                'professional_title': professional.title,
                'consultation_category': consultation.get_category_display()
            }
            
        except ConsultationRequest.DoesNotExist:
            raise serializers.ValidationError("Consultation not found")
        except stripe.error.StripeError as e:
            raise serializers.ValidationError(f"Stripe error: {str(e)}")

class ConfirmPaymentSerializer(serializers.Serializer):
    payment_id = serializers.UUIDField()
    payment_intent_id = serializers.CharField()
    
    def validate(self, data):
        try:
            payment = Payment.objects.get(
                id=data['payment_id'],
                user=self.context['request'].user
            )
            
            # Verify with Stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            payment_intent = stripe.PaymentIntent.retrieve(data['payment_intent_id'])
            
            if payment_intent.status != 'succeeded':
                raise serializers.ValidationError("Payment not completed")
            
            data['payment'] = payment
            data['payment_intent'] = payment_intent
            
        except Payment.DoesNotExist:
            raise serializers.ValidationError("Payment not found")
        except stripe.error.StripeError as e:
            raise serializers.ValidationError(f"Stripe error: {str(e)}")
        
        return data

class PayoutSerializer(serializers.ModelSerializer):
    professional_email = serializers.EmailField(source='professional.user.email', read_only=True)
    professional_name = serializers.CharField(source='professional.user.get_full_name', read_only=True)
    
    class Meta:
        model = Payout
        fields = [
            'id', 'amount', 'currency', 'status', 'created_at', 'paid_at',
            'estimated_arrival_date', 'professional_email', 'professional_name',
            'destination_last4', 'failure_message'
        ]
        read_only_fields = ['id', 'created_at', 'paid_at']

class CreatePayoutSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=10)  # Min $10
    currency = serializers.CharField(default='USD')
    
    def validate(self, data):
        user = self.context['request'].user
        
        try:
            professional = user.professional_profile
        except ProfessionalProfile.DoesNotExist:
            raise serializers.ValidationError("User is not a professional")
        
        # Check available balance
        available_balance = professional.get_available_balance()
        if data['amount'] > available_balance:
            raise serializers.ValidationError(
                f"Amount exceeds available balance. Available: ${available_balance}"
            )
        
        data['professional'] = professional
        return data

class CouponSerializer(serializers.ModelSerializer):
    is_valid = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Coupon
        fields = [
            'id', 'code', 'discount_type', 'discount_value',
            'valid_from', 'valid_until', 'is_active', 'is_valid',
            'min_amount', 'max_uses', 'uses_count'
        ]
        read_only_fields = ['id', 'uses_count']

class ValidateCouponSerializer(serializers.Serializer):
    code = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    consultation_id = serializers.IntegerField(required=False)
    
    def validate(self, data):
        try:
            coupon = Coupon.objects.get(code=data['code'])
            
            if not coupon.is_valid:
                raise serializers.ValidationError("Coupon is not valid")
            
            # Check minimum amount
            if coupon.min_amount and data['amount'] < coupon.min_amount:
                raise serializers.ValidationError(
                    f"Minimum amount required: ${coupon.min_amount}"
                )
            
            # Check consultation category if specified
            if 'consultation_id' in data:
                try:
                    consultation = ConsultationRequest.objects.get(id=data['consultation_id'])
                    if coupon.categories.exists() and consultation.category not in coupon.categories.all():
                        raise serializers.ValidationError("Coupon not valid for this category")
                except ConsultationRequest.DoesNotExist:
                    pass
            
            data['coupon'] = coupon
            return data
            
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("Invalid coupon code")