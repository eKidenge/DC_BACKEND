from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import json

# IMPORT from accounts app instead of django.contrib.auth
from accounts.models import User, ProfessionalProfile as AccountsProfessionalProfile

# ============================================
# DELETE the duplicate ProfessionalProfile class
# We'll use the one from accounts
# ============================================

class ProfessionalAvailability(models.Model):
    # CHANGE: Reference the ProfessionalProfile from accounts app
    professional = models.OneToOneField(
        AccountsProfessionalProfile,  # Changed from ProfessionalProfile
        on_delete=models.CASCADE, 
        related_name='dashboard_availability'  # Changed from 'availability' to avoid conflict
    )
    
    is_available = models.BooleanField(default=True)
    auto_accept_calls = models.BooleanField(default=False)
    max_daily_sessions = models.PositiveIntegerField(default=8)
    working_hours_start = models.TimeField(default='09:00:00')
    working_hours_end = models.TimeField(default='17:00:00')
    break_duration_minutes = models.PositiveIntegerField(default=60)
    break_start_time = models.TimeField(default='13:00:00')
    buffer_minutes = models.PositiveIntegerField(default=15)
    available_days = models.JSONField(default=dict, help_text="JSON of available days")
    timezone = models.CharField(max_length=50, default='UTC')
    next_available_time = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Availability for {self.professional.user.get_full_name()}"
    
    def save(self, *args, **kwargs):
        if not self.available_days:
            self.available_days = {
                "monday": True,
                "tuesday": True,
                "wednesday": True,
                "thursday": True,
                "friday": True,
                "saturday": False,
                "sunday": False
            }
        super().save(*args, **kwargs)

class ProfessionalStat(models.Model):
    # CHANGE: Reference the ProfessionalProfile from accounts app
    professional = models.OneToOneField(
        AccountsProfessionalProfile,  # Changed from ProfessionalProfile
        on_delete=models.CASCADE, 
        related_name='dashboard_stats'  # Changed from 'stats' to avoid conflict
    )
    
    # Lifetime stats
    total_consultations = models.PositiveIntegerField(default=0)
    completed_consultations = models.PositiveIntegerField(default=0)
    pending_consultations = models.PositiveIntegerField(default=0)
    cancelled_consultations = models.PositiveIntegerField(default=0)
    
    # Today's stats
    today_consultations = models.PositiveIntegerField(default=0)
    today_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    today_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    # Weekly stats
    week_consultations = models.PositiveIntegerField(default=0)
    week_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    week_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    # Monthly stats
    month_consultations = models.PositiveIntegerField(default=0)
    month_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    month_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    # Performance metrics
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, validators=[MinValueValidator(0), MaxValueValidator(5)])
    response_time_minutes = models.PositiveIntegerField(default=0)
    acceptance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    cancellation_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    # Advanced analytics
    top_categories = models.JSONField(default=list, help_text="JSON list of top categories")
    busiest_days = models.JSONField(default=list, help_text="JSON list of busiest days")
    busiest_hours = models.JSONField(default=list, help_text="JSON list of busiest hours")
    earnings_by_category = models.JSONField(default=dict, help_text="JSON of earnings by category")
    earnings_by_month = models.JSONField(default=dict, help_text="JSON of earnings by month")
    repeat_clients = models.PositiveIntegerField(default=0)
    client_satisfaction_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    last_updated = models.DateTimeField(auto_now=True)
    stats_date = models.DateField(auto_now_add=True)
    
    def __str__(self):
        return f"Stats for {self.professional.user.get_full_name()}"

class IncomingCall(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('ringing', 'Ringing'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('missed', 'Missed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    # CHANGE: Reference the ProfessionalProfile from accounts app
    professional = models.ForeignKey(
        AccountsProfessionalProfile,  # Changed from ProfessionalProfile
        on_delete=models.CASCADE, 
        related_name='dashboard_incoming_calls'  # Changed from 'incoming_calls'
    )
    
    consultation = models.ForeignKey('calls.Consultation', on_delete=models.CASCADE, null=True, blank=True)
    client_name = models.CharField(max_length=255)
    client_phone = models.CharField(max_length=20, blank=True, null=True)
    category = models.CharField(max_length=100)
    duration = models.PositiveIntegerField(help_text="Duration in minutes")
    estimated_earnings = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    call_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Incoming call from {self.client_name} to {self.professional.user.get_full_name()}"
    
    class Meta:
        ordering = ['-created_at']

class ProfessionalNotification(models.Model):
    NOTIFICATION_TYPES = [
        ('system', 'System'),
        ('incoming_call', 'Incoming Call'),
        ('consultation_update', 'Consultation Update'),
        ('payment', 'Payment'),
        ('rating', 'Rating'),
        ('promotion', 'Promotion'),
        ('announcement', 'Announcement'),
        ('reminder', 'Reminder'),
    ]
    
    PRIORITY_CHOICES = [
        (0, 'Low'),
        (1, 'Medium'),
        (2, 'High'),
        (3, 'Urgent'),
    ]
    
    # CHANGE: Use the User from accounts app
    user = models.ForeignKey(
        User,  # From accounts.models
        on_delete=models.CASCADE, 
        related_name='dashboard_notifications'  # Changed from 'professional_notifications'
    )
    
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    action_url = models.CharField(max_length=500, blank=True, null=True)
    action_text = models.CharField(max_length=100, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.notification_type}: {self.title}"
    
    class Meta:
        ordering = ['-created_at']

class ProfessionalCalendar(models.Model):
    EVENT_TYPES = [
        ('consultation', 'Consultation'),
        ('break', 'Break'),
        ('busy', 'Busy'),
        ('holiday', 'Holiday'),
        ('training', 'Training'),
        ('other', 'Other'),
    ]
    
    # CHANGE: Reference the ProfessionalProfile from accounts app
    professional = models.ForeignKey(
        AccountsProfessionalProfile,  # Changed from ProfessionalProfile
        on_delete=models.CASCADE, 
        related_name='dashboard_calendar_events'  # Changed from 'calendar_events'
    )
    
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    consultation = models.ForeignKey('calls.Consultation', on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    all_day = models.BooleanField(default=False)
    is_confirmed = models.BooleanField(default=True)
    is_cancelled = models.BooleanField(default=False)
    cancellation_reason = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=500, blank=True, null=True)
    is_virtual = models.BooleanField(default=True)
    meeting_link = models.URLField(blank=True, null=True)
    meeting_id = models.CharField(max_length=100, blank=True, null=True)
    remind_minutes_before = models.PositiveIntegerField(default=15)
    reminder_sent = models.BooleanField(default=False)
    color = models.CharField(max_length=7, default='#3B82F6')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.event_type}: {self.title}"
    
    class Meta:
        ordering = ['start_time']

class CallHistory(models.Model):
    # CHANGE: Reference the ProfessionalProfile from accounts app
    professional = models.ForeignKey(
        AccountsProfessionalProfile,  # Changed from ProfessionalProfile
        on_delete=models.CASCADE, 
        related_name='dashboard_call_history'  # Changed from 'call_history'
    )
    
    consultation = models.ForeignKey('calls.Consultation', on_delete=models.SET_NULL, null=True, blank=True)
    client_name = models.CharField(max_length=255)
    duration_seconds = models.PositiveIntegerField(default=0)
    earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    call_quality = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    recording_url = models.URLField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Call with {self.client_name} at {self.start_time}"
    
    class Meta:
        verbose_name_plural = "Call Histories"
        ordering = ['-start_time']
