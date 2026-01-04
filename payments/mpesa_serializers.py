from rest_framework import serializers
from .models import (
    MpesaTransaction, MpesaPaymentRequest, 
    MpesaCallback, MpesaConfiguration
)
from django.utils import timezone
from decimal import Decimal

class MpesaPaymentInitiateSerializer(serializers.Serializer):
    """Serializer for initiating M-Pesa payment"""
    
    consultation_id = serializers.IntegerField(required=True)
    phone_number = serializers.CharField(required=True)
    
    def validate_phone_number(self, value):
        """Validate M-Pesa phone number"""
        # Basic validation - you can add more robust validation
        digits = ''.join(filter(str.isdigit, value))
        
        if len(digits) < 9 or len(digits) > 12:
            raise serializers.ValidationError("Invalid phone number format")
        
        return value
    
    def validate(self, data):
        from categories.models import ConsultationRequest
        
        user = self.context['request'].user
        
        # Validate consultation
        try:
            consultation = ConsultationRequest.objects.get(
                id=data['consultation_id'],
                client=user
            )
        except ConsultationRequest.DoesNotExist:
            raise serializers.ValidationError("Consultation not found")
        
        # Check if consultation already has successful payment
        if consultation.payments.filter(status='completed').exists():
            raise serializers.ValidationError("Payment already completed for this consultation")
        
        # Check if professional is assigned
        if not consultation.professional:
            raise serializers.ValidationError("No professional assigned")
        
        data['consultation'] = consultation
        return data

class MpesaPaymentStatusSerializer(serializers.Serializer):
    """Serializer for checking payment status"""
    
    checkout_request_id = serializers.CharField(required=False)
    transaction_id = serializers.UUIDField(required=False)
    
    def validate(self, data):
        if not data.get('checkout_request_id') and not data.get('transaction_id'):
            raise serializers.ValidationError(
                "Either checkout_request_id or transaction_id is required"
            )
        return data

class MpesaTransactionSerializer(serializers.ModelSerializer):
    """Serializer for M-Pesa transactions"""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    consultation_details = serializers.SerializerMethodField()
    formatted_phone = serializers.SerializerMethodField()
    
    class Meta:
        model = MpesaTransaction
        fields = [
            'id', 'amount', 'phone_number', 'formatted_phone', 'status',
            'account_reference', 'transaction_desc', 'mpesa_receipt_number',
            'transaction_date', 'created_at', 'completed_at',
            'user_email', 'user_name', 'consultation_details'
        ]
        read_only_fields = [
            'id', 'created_at', 'completed_at', 'mpesa_receipt_number',
            'transaction_date'
        ]
    
    def get_consultation_details(self, obj):
        if obj.consultation:
            return {
                'id': obj.consultation.id,
                'category': obj.consultation.get_category_display(),
                'professional': obj.consultation.professional.user.get_full_name(),
                'duration': obj.consultation.duration_minutes
            }
        return None
    
    def get_formatted_phone(self, obj):
        return obj.formatted_phone

class MpesaPaymentRequestSerializer(serializers.ModelSerializer):
    """Serializer for payment requests"""
    
    consultation_details = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = MpesaPaymentRequest
        fields = [
            'id', 'amount', 'phone_number', 'status',
            'checkout_request_id', 'created_at', 'expires_at',
            'time_remaining', 'consultation_details', 'is_active'
        ]
        read_only_fields = ['id', 'created_at', 'expires_at']
    
    def get_consultation_details(self, obj):
        return {
            'id': obj.consultation.id,
            'category': obj.consultation.get_category_display(),
            'professional': obj.consultation.professional.user.get_full_name()
        }
    
    def get_time_remaining(self, obj):
        if obj.is_expired:
            return "Expired"
        
        remaining = obj.expires_at - timezone.now()
        minutes = int(remaining.total_seconds() / 60)
        seconds = int(remaining.total_seconds() % 60)
        
        return f"{minutes}m {seconds}s"

class MpesaCallbackSerializer(serializers.ModelSerializer):
    """Serializer for M-Pesa callbacks"""
    
    class Meta:
        model = MpesaCallback
        fields = ['id', 'callback_type', 'received_at', 'processed']
        read_only_fields = ['id', 'received_at']

class MpesaConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for M-Pesa configuration"""
    
    is_sandbox = serializers.BooleanField(read_only=True)
    is_production = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = MpesaConfiguration
        fields = [
            'id', 'name', 'config_type', 'is_active', 'is_sandbox', 'is_production',
            'business_short_code', 'transaction_type', 'party_b',
            'account_reference_prefix', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']