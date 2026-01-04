from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from accounts.models import User, ProfessionalProfile

class Consultation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
        ('rescheduled', 'Rescheduled'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('partially_paid', 'Partially Paid'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed'),
    ]
    
    professional = models.ForeignKey(ProfessionalProfile, on_delete=models.CASCADE, related_name='calls_consultations')
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='client_consultations')
    category = models.CharField(max_length=100)
    title = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(default=30)
    scheduled_time = models.DateTimeField()
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    actual_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    meeting_link = models.URLField(blank=True, null=True)
    meeting_id = models.CharField(max_length=100, blank=True, null=True)
    recording_url = models.URLField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    client_notes = models.TextField(blank=True, null=True)
    professional_notes = models.TextField(blank=True, null=True)
    rating = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    feedback = models.TextField(blank=True, null=True)
    client_feedback = models.TextField(blank=True, null=True)
    cancellation_reason = models.TextField(blank=True, null=True)
    cancelled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cancelled_consultations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Consultation #{self.id}: {self.client.get_full_name()} with {self.professional.user.get_full_name()}"
    
    class Meta:
        ordering = ['-scheduled_time']

class CallSession(models.Model):
    STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('ringing', 'Ringing'),
        ('answered', 'Answered'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('rejected', 'Rejected'),
        ('missed', 'Missed'),
    ]
    
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='call_sessions')
    session_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated')
    initiated_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    caller_sid = models.CharField(max_length=100, blank=True, null=True)  # For Twilio or similar
    recording_url = models.URLField(blank=True, null=True)
    call_quality_score = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    network_issues = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Call Session {self.session_id} for Consultation #{self.consultation.id}"
    
    class Meta:
        ordering = ['-initiated_at']