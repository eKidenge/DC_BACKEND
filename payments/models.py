from django.db import models
from django.conf import settings
from accounts.models import User, ProfessionalProfile
from categories.models import ConsultationRequest
import uuid

class Payment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('manual', 'Manual'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    consultation = models.ForeignKey(ConsultationRequest, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='stripe')
    
    # Stripe specific fields
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_client_secret = models.TextField(blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['stripe_payment_intent_id']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"Payment {self.id} - {self.amount} {self.currency}"
    
    @property
    def is_successful(self):
        return self.status == 'completed'
    
    @property
    def is_refundable(self):
        return self.status == 'completed'

class Transaction(models.Model):
    TYPE_CHOICES = (
        ('payment', 'Payment'),
        ('refund', 'Refund'),
        ('payout', 'Payout'),
        ('fee', 'Fee'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='transactions', null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    
    # Transaction details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # Stripe references
    stripe_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_balance_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    effective_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.amount}"

class Payout(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    professional = models.ForeignKey(ProfessionalProfile, on_delete=models.CASCADE, related_name='payouts')
    
    # Payout details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    currency = models.CharField(max_length=3, default='USD')
    
    # Stripe Connect details
    stripe_payout_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_transfer_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Bank/Card details
    destination_type = models.CharField(max_length=50, blank=True)  # bank_account, card
    destination_last4 = models.CharField(max_length=4, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    estimated_arrival_date = models.DateField(null=True, blank=True)
    
    # Metadata
    description = models.TextField(blank=True)
    failure_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Payout {self.id} - {self.amount} to {self.professional.user.email}"

class ProfessionalEarning(models.Model):
    """Track professional earnings and commissions"""
    professional = models.ForeignKey(ProfessionalProfile, on_delete=models.CASCADE, related_name='earnings')
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='professional_earnings')
    
    # Earning breakdown
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2)
    processing_fee = models.DecimalField(max_digits=10, decimal_places=2)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Commission rates
    platform_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)  # 20%
    processing_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=2.90)  # 2.9%
    
    # Status
    is_paid_out = models.BooleanField(default=False)
    payout = models.ForeignKey(Payout, on_delete=models.SET_NULL, null=True, blank=True, related_name='earnings')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    paid_out_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['professional', 'is_paid_out']),
        ]
    
    def __str__(self):
        return f"Earning {self.net_amount} for {self.professional.user.email}"

class Coupon(models.Model):
    """Discount coupons"""
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=10, choices=[('percentage', 'Percentage'), ('fixed', 'Fixed Amount')])
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_uses = models.IntegerField(default=1)
    uses_count = models.IntegerField(default=0)
    
    # Validity
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    # Restrictions
    min_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    categories = models.ManyToManyField('categories.ServiceCategory', blank=True)
    professionals = models.ManyToManyField(ProfessionalProfile, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['code', 'is_active']),
        ]
    
    def __str__(self):
        return self.code
    
    @property
    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        return (
            self.is_active and
            self.valid_from <= now <= self.valid_until and
            (self.max_uses == 0 or self.uses_count < self.max_uses)
        )
    
    def apply_discount(self, amount):
        if self.discount_type == 'percentage':
            discount = amount * (self.discount_value / 100)
        else:
            discount = min(self.discount_value, amount)
        return max(amount - discount, 0)

class PaymentConfig(models.Model):
    """Platform payment configuration"""
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Payment Configuration"
        verbose_name_plural = "Payment Configurations"
    
    def __str__(self):
        return self.key
    
# At the end of payments/models.py
from .mpesa_models import *