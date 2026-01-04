from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _

class ServiceCategory(models.Model):
    """Categories for different types of services"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True)  # Icon class name
    active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Pricing settings
    base_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Base price for this category"
    )
    commission_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=20.00,
        help_text="Platform commission percentage"
    )
    
    # Requirements
    min_duration = models.IntegerField(
        default=15,
        help_text="Minimum consultation duration in minutes"
    )
    max_duration = models.IntegerField(
        default=120,
        help_text="Maximum consultation duration in minutes"
    )
    
    # Availability
    available_24_7 = models.BooleanField(
        default=False,
        help_text="Whether this service is available 24/7"
    )
    
    class Meta:
        verbose_name = "Service Category"
        verbose_name_plural = "Service Categories"
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name
    
    def get_available_professionals_count(self):
        """Count available professionals in this category"""
        from accounts.models import ProfessionalProfile
        return ProfessionalProfile.objects.filter(
            service_categories=self,
            is_online=True,
            is_verified=True
        ).count()

class ConsultationRequest(models.Model):
    """Consultation request model"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('matched', 'Matched'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('emergency', 'Emergency'),
    ]
    
    # Basic info
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='consultation_requests',
        verbose_name="Client"
    )
    professional = models.ForeignKey(
        'accounts.ProfessionalProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='consultations',
        verbose_name="Professional"
    )
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.PROTECT,
        related_name='consultations',
        verbose_name="Service Category"
    )
    
    # Request details
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium'
    )
    
    # Scheduling
    preferred_date = models.DateField(null=True, blank=True)
    preferred_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(
        default=30,
        validators=[MinValueValidator(15), MaxValueValidator(240)]
    )
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    
    # Pricing
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    platform_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    professional_earnings = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    
    # Communication
    client_notes = models.TextField(blank=True, null=True)
    professional_notes = models.TextField(blank=True, null=True)
    admin_notes = models.TextField(blank=True, null=True)
    
    # Call details
    call_id = models.CharField(max_length=100, blank=True, null=True)
    call_start_time = models.DateTimeField(null=True, blank=True)
    call_end_time = models.DateTimeField(null=True, blank=True)
    call_duration = models.IntegerField(default=0, help_text="Actual call duration in minutes")
    
    # Ratings
    client_rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    client_review = models.TextField(blank=True, null=True)
    professional_rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    professional_feedback = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    matched_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Tracking
    match_attempts = models.IntegerField(default=0)
    is_urgent = models.BooleanField(default=False)
    source = models.CharField(max_length=50, default='web', blank=True)
    
    class Meta:
        verbose_name = "Consultation Request"
        verbose_name_plural = "Consultation Requests"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['professional', 'status']),
            models.Index(fields=['category', 'status']),
        ]
    
    def __str__(self):
        return f"Consultation #{self.id} - {self.client.get_full_name()}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate pricing if not set
        if self.duration_minutes and self.hourly_rate:
            hours = self.duration_minutes / 60
            self.total_amount = hours * float(self.hourly_rate)
            
            # Calculate platform fee and earnings based on category commission rate
            if self.category:
                commission_percentage = float(self.category.commission_rate) / 100
                self.platform_fee = self.total_amount * commission_percentage
                self.professional_earnings = self.total_amount - self.platform_fee
        
        # Update timestamps based on status changes
        if self.pk:
            old_instance = ConsultationRequest.objects.get(pk=self.pk)
            if old_instance.status != self.status:
                now = timezone.now()
                if self.status == 'matched':
                    self.matched_at = now
                elif self.status == 'accepted':
                    self.accepted_at = now
                elif self.status == 'in_progress':
                    self.started_at = now
                elif self.status == 'completed':
                    self.completed_at = now
                elif self.status == 'cancelled':
                    self.cancelled_at = now
        
        super().save(*args, **kwargs)
    
    def get_category_display(self):
        """Get category display name"""
        return self.category.name if self.category else "Unknown"
    
    def get_status_display_class(self):
        """Get CSS class for status display"""
        status_classes = {
            'pending': 'warning',
            'matched': 'info',
            'accepted': 'primary',
            'scheduled': 'info',
            'in_progress': 'success',
            'completed': 'success',
            'cancelled': 'danger',
            'rejected': 'danger',
            'expired': 'secondary',
        }
        return status_classes.get(self.status, 'secondary')
    
    def get_actual_duration(self):
        """Calculate actual duration if call has ended"""
        if self.call_start_time and self.call_end_time:
            duration = self.call_end_time - self.call_start_time
            return duration.total_seconds() / 60
        return self.call_duration or 0
    
    def can_be_accepted_by(self, user):
        """Check if user can accept this consultation"""
        try:
            professional = user.professional_profile
            return (
                self.professional == professional and
                self.status in ['matched', 'scheduled']
            )
        except:
            return False
    
    def can_be_cancelled_by(self, user):
        """Check if user can cancel this consultation"""
        if user == self.client:
            return self.status in ['pending', 'matched', 'accepted', 'scheduled']
        elif hasattr(user, 'professional_profile') and self.professional == user.professional_profile:
            return self.status in ['matched', 'accepted', 'scheduled']
        elif user.is_staff:
            return True
        return False
    
    def calculate_price(self):
        """Calculate and update pricing"""
        if not self.hourly_rate or not self.duration_minutes:
            return
        
        hours = self.duration_minutes / 60
        self.total_amount = hours * float(self.hourly_rate)
        
        if self.category:
            commission_percentage = float(self.category.commission_rate) / 100
            self.platform_fee = self.total_amount * commission_percentage
            self.professional_earnings = self.total_amount - self.platform_fee

class ConsultationAttachment(models.Model):
    """Attachments for consultation requests"""
    consultation = models.ForeignKey(
        ConsultationRequest,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to='consultation_attachments/%Y/%m/%d/')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)
    file_size = models.IntegerField(help_text="File size in bytes")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = "Consultation Attachment"
        verbose_name_plural = "Consultation Attachments"
    
    def __str__(self):
        return f"{self.file_name} - Consultation #{self.consultation.id}"

class ConsultationMessage(models.Model):
    """Messages between client and professional"""
    consultation = models.ForeignKey(
        ConsultationRequest,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='consultation_messages'
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # For file attachments in messages
    attachment = models.FileField(
        upload_to='consultation_messages/%Y/%m/%d/',
        blank=True,
        null=True
    )
    attachment_type = models.CharField(max_length=50, blank=True, null=True)
    
    class Meta:
        verbose_name = "Consultation Message"
        verbose_name_plural = "Consultation Messages"
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message from {self.sender} - {self.created_at}"
