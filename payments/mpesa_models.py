from django.db import models
import uuid
from django.conf import settings
from django.utils import timezone
from decimal import Decimal

class MpesaTransaction(models.Model):
    """Store M-Pesa transaction details"""
    
    TRANSACTION_TYPES = (
        ('c2b', 'Customer to Business'),
        ('b2c', 'Business to Customer'),
        ('reversal', 'Reversal'),
        ('balance', 'Account Balance'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('initiated', 'Initiated'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('reversed', 'Reversed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mpesa_transactions')
    consultation = models.ForeignKey('categories.ConsultationRequest', on_delete=models.SET_NULL, null=True, blank=True)
    
    # ===== ADD THIS FIELD =====
    transaction_id = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Transaction ID for frontend reference"
    )
    # ===========================
    
    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, default='c2b')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=15)  # Format: 2547XXXXXXXX
    account_reference = models.CharField(max_length=50)
    transaction_desc = models.TextField()
    
    # M-Pesa response fields
    merchant_request_id = models.CharField(max_length=100, blank=True)
    checkout_request_id = models.CharField(max_length=100, blank=True)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True)
    transaction_date = models.DateTimeField(null=True, blank=True)
    response_code = models.CharField(max_length=10, blank=True)
    response_description = models.TextField(blank=True)
    result_code = models.CharField(max_length=10, blank=True)
    result_description = models.TextField(blank=True)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    callback_received = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    initiated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Error handling
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['merchant_request_id']),
            models.Index(fields=['checkout_request_id']),
            models.Index(fields=['mpesa_receipt_number']),
            models.Index(fields=['phone_number', 'created_at']),
            models.Index(fields=['transaction_id']),  # Add index for transaction_id
        ]
    
    def __str__(self):
        return f"M-Pesa {self.transaction_type.upper()} - {self.amount} - {self.status}"
    
    @property
    def is_successful(self):
        return self.status == 'success'
    
    @property
    def formatted_phone(self):
        """Format phone number for display"""
        if self.phone_number.startswith('254'):
            return f"0{self.phone_number[3:]}"
        return self.phone_number

class MpesaPaymentRequest(models.Model):
    """Store payment requests waiting for M-Pesa prompt"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    consultation = models.ForeignKey('categories.ConsultationRequest', on_delete=models.CASCADE)
    
    # ===== ADD THIS FIELD =====
    transaction_id = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Transaction ID for frontend reference"
    )
    # ===========================
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=15, blank=True)
    
    # M-Pesa STK Push details
    merchant_request_id = models.CharField(max_length=100, blank=True)
    checkout_request_id = models.CharField(max_length=100, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('initiated', 'Initiated'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    ], default='pending')
    
    # Expiry
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"M-Pesa Request - {self.amount}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def mark_expired(self):
        if self.is_expired and self.status not in ['completed', 'failed']:
            self.status = 'expired'
            self.is_active = False
            self.save()

class MpesaCallback(models.Model):
    """Store all M-Pesa callbacks for audit"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(MpesaTransaction, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Callback data
    callback_type = models.CharField(max_length=50)  # stk_push, c2b, b2c, reversal
    raw_data = models.JSONField()
    processed = models.BooleanField(default=False)
    
    # Timestamps
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-received_at']
    
    def __str__(self):
        return f"{self.callback_type} - {self.received_at}"

class MpesaAccessToken(models.Model):
    """Store and manage M-Pesa API access tokens"""
    
    access_token = models.TextField()
    expires_in = models.IntegerField()  # Seconds until expiration
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-generated_at']
    
    def __str__(self):
        return f"Token expires in {self.expires_in}s"
    
    @property
    def is_valid(self):
        """Check if token is still valid (with 60 seconds buffer)"""
        elapsed = (timezone.now() - self.generated_at).total_seconds()
        return elapsed < (self.expires_in - 60)

class MpesaConfiguration(models.Model):
    """Store M-Pesa API configuration"""
    
    CONFIG_TYPES = (
        ('production', 'Production'),
        ('sandbox', 'Sandbox'),
    )
    
    name = models.CharField(max_length=100)
    config_type = models.CharField(max_length=20, choices=CONFIG_TYPES, default='sandbox')
    is_active = models.BooleanField(default=True)
    
    # API Credentials
    consumer_key = models.CharField(max_length=500)
    consumer_secret = models.CharField(max_length=500)
    passkey = models.CharField(max_length=500)
    business_short_code = models.CharField(max_length=10)
    initiator_name = models.CharField(max_length=100, blank=True)
    security_credential = models.TextField(blank=True)
    
    # API URLs
    stk_push_url = models.URLField(default='https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest')
    oauth_url = models.URLField(default='https://sandbox.safaricom.co.ke/oauth/v1/generate')
    callback_url = models.URLField()
    result_url = models.URLField()
    
    # Transaction defaults
    transaction_type = models.CharField(max_length=50, default='CustomerPayBillOnline')
    party_b = models.CharField(max_length=10)  # Usually same as business_short_code
    account_reference_prefix = models.CharField(max_length=10, default='DC')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "M-Pesa Configuration"
        verbose_name_plural = "M-Pesa Configurations"
    
    def __str__(self):
        return f"{self.name} ({self.config_type})"
    
    @property
    def is_sandbox(self):
        return self.config_type == 'sandbox'
    
    @property
    def is_production(self):
        return self.config_type == 'production'

class MpesaBusinessTill(models.Model):
    """For businesses using Buy Goods (Till Number)"""
    
    till_number = models.CharField(max_length=10, unique=True)
    business_name = models.CharField(max_length=200)
    category = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "M-Pesa Business Till"
        verbose_name_plural = "M-Pesa Business Tills"
    
    def __str__(self):
        return f"{self.business_name} - {self.till_number}"
