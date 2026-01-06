from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

class AdminLog(models.Model):
    ACTION_CHOICES = (
        ('user_created', 'User Created'),
        ('user_updated', 'User Updated'),
        ('user_deleted', 'User Deleted'),
        ('professional_verified', 'Professional Verified'),
        ('consultation_created', 'Consultation Created'),
        ('consultation_updated', 'Consultation Updated'),
        ('payment_processed', 'Payment Processed'),
        ('system_settings_changed', 'System Settings Changed'),
        ('login', 'Admin Login'),
        ('logout', 'Admin Logout'),
        ('report_generated', 'Report Generated'),
        ('settings_updated', 'Settings Updated'),
    )
    
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='admin_logs'
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField()
    details = models.JSONField(default=dict, blank=True)  # Store additional data
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Admin Log'
        verbose_name_plural = 'Admin Logs'
        indexes = [
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['admin', 'created_at']),
        ]
    
    def __str__(self):
        admin_name = self.admin.get_full_name() if self.admin else 'System'
        return f"{admin_name} - {self.get_action_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class PlatformSettings(models.Model):
    CATEGORY_CHOICES = (
        ('general', 'General'),
        ('payments', 'Payments'),
        ('notifications', 'Notifications'),
        ('consultations', 'Consultations'),
        ('security', 'Security'),
        ('appearance', 'Appearance'),
    )
    
    SETTING_TYPE_CHOICES = (
        ('string', 'String'),
        ('integer', 'Integer'),
        ('float', 'Float'),
        ('boolean', 'Boolean'),
        ('json', 'JSON'),
        ('text', 'Text'),
    )
    
    key = models.CharField(max_length=100, unique=True, help_text="Setting key (e.g., 'site_name', 'commission_rate')")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    value = models.JSONField(help_text="Setting value (can be string, number, boolean, or JSON)")
    setting_type = models.CharField(max_length=20, choices=SETTING_TYPE_CHOICES, default='string')
    description = models.TextField(blank=True, help_text="Description of what this setting controls")
    is_public = models.BooleanField(default=False, help_text="Whether this setting can be accessed via API")
    is_required = models.BooleanField(default=False, help_text="Whether this setting must have a value")
    min_value = models.CharField(max_length=50, blank=True, help_text="Minimum value (for numeric settings)")
    max_value = models.CharField(max_length=50, blank=True, help_text="Maximum value (for numeric settings)")
    options = models.JSONField(default=list, blank=True, help_text="Allowed options (for select fields)")
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='updated_settings'
    )
    
    class Meta:
        ordering = ['category', 'key']
        verbose_name = 'Platform Setting'
        verbose_name_plural = 'Platform Settings'
        indexes = [
            models.Index(fields=['category', 'key']),
            models.Index(fields=['is_public']),
        ]
    
    def __str__(self):
        return f"{self.key} ({self.get_category_display()})"
    
    def clean(self):
        """Validate setting value based on type"""
        from django.core.exceptions import ValidationError
        
        if self.setting_type == 'integer':
            try:
                int(self.value)
            except (ValueError, TypeError):
                raise ValidationError({'value': 'Value must be an integer for integer type'})
        
        elif self.setting_type == 'float':
            try:
                float(self.value)
            except (ValueError, TypeError):
                raise ValidationError({'value': 'Value must be a float for float type'})
        
        elif self.setting_type == 'boolean':
            if not isinstance(self.value, bool):
                raise ValidationError({'value': 'Value must be a boolean for boolean type'})
        
        elif self.setting_type == 'json':
            if not isinstance(self.value, (dict, list)):
                try:
                    import json
                    json.loads(self.value)
                except (ValueError, TypeError):
                    raise ValidationError({'value': 'Value must be valid JSON for JSON type'})
        
        # Validate min/max for numeric types
        if self.setting_type in ['integer', 'float'] and self.min_value:
            try:
                min_val = float(self.min_value)
                val = float(self.value)
                if val < min_val:
                    raise ValidationError({'value': f'Value must be at least {self.min_value}'})
            except ValueError:
                pass
        
        if self.setting_type in ['integer', 'float'] and self.max_value:
            try:
                max_val = float(self.max_value)
                val = float(self.value)
                if val > max_val:
                    raise ValidationError({'value': f'Value must be at most {self.max_value}'})
            except ValueError:
                pass
        
        # Validate options
        if self.options and self.value not in self.options:
            raise ValidationError({'value': f'Value must be one of: {", ".join(map(str, self.options))}'})

class Report(models.Model):
    REPORT_TYPE_CHOICES = (
        ('revenue', 'Revenue Report'),
        ('users', 'User Growth Report'),
        ('consultations', 'Consultation Report'),
        ('professionals', 'Professional Performance'),
        ('clients', 'Client Retention'),
        ('platform_health', 'Platform Health'),
        ('financial', 'Financial Summary'),
    )
    
    REPORT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('generated', 'Generated'),
        ('failed', 'Failed'),
    )
    
    REPORT_FORMAT_CHOICES = (
        ('json', 'JSON'),
        ('csv', 'CSV'),
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
    )
    
    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPE_CHOICES)
    format = models.CharField(max_length=10, choices=REPORT_FORMAT_CHOICES, default='json')
    
    # Date range
    period_start = models.DateField()
    period_end = models.DateField()
    
    # File storage
    file_path = models.CharField(max_length=500, blank=True, help_text="Path to generated report file")
    file_url = models.URLField(blank=True, help_text="URL to download the report")
    file_size = models.BigIntegerField(default=0, help_text="File size in bytes")
    
    # Report data
    data = models.JSONField(default=dict, blank=True, help_text="Report data in JSON format")
    summary = models.TextField(blank=True, help_text="Report summary/executive overview")
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=REPORT_STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, help_text="Error message if report generation failed")
    
    # Generation info
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='generated_reports'
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    processing_time = models.FloatField(default=0, help_text="Time taken to generate report in seconds")
    
    # Filters and parameters
    filters = models.JSONField(default=dict, blank=True, help_text="Filters applied to generate this report")
    parameters = models.JSONField(default=dict, blank=True, help_text="Additional parameters for report generation")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'
        indexes = [
            models.Index(fields=['report_type', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['generated_by', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()}) - {self.period_start} to {self.period_end}"
    
    @property
    def is_ready(self):
        return self.status == 'generated'
    
    @property
    def duration_days(self):
        """Calculate report duration in days"""
        return (self.period_end - self.period_start).days + 1
    
    def mark_as_processing(self):
        self.status = 'processing'
        self.save(update_fields=['status'])
    
    def mark_as_generated(self, data=None, file_path=None, file_url=None, processing_time=0):
        self.status = 'generated'
        self.generated_at = timezone.now()
        self.processing_time = processing_time
        
        if data:
            self.data = data
        
        if file_path:
            self.file_path = file_path
        
        if file_url:
            self.file_url = file_url
        
        self.save()
    
    def mark_as_failed(self, error_message):
        self.status = 'failed'
        self.error_message = error_message
        self.save(update_fields=['status', 'error_message'])

class PlatformAnalytics(models.Model):
    """Daily platform analytics snapshots"""
    date = models.DateField(unique=True)
    
    # User metrics
    total_users = models.IntegerField(default=0)
    new_users = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)
    
    # Professional metrics
    total_professionals = models.IntegerField(default=0)
    new_professionals = models.IntegerField(default=0)
    online_professionals = models.IntegerField(default=0)
    verified_professionals = models.IntegerField(default=0)
    
    # Client metrics
    total_clients = models.IntegerField(default=0)
    new_clients = models.IntegerField(default=0)
    active_clients = models.IntegerField(default=0)
    
    # Consultation metrics
    total_consultations = models.IntegerField(default=0)
    new_consultations = models.IntegerField(default=0)
    completed_consultations = models.IntegerField(default=0)
    cancelled_consultations = models.IntegerField(default=0)
    active_consultations = models.IntegerField(default=0)
    
    # Financial metrics
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    daily_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    professional_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Performance metrics
    average_consultation_duration = models.FloatField(default=0)  # in minutes
    average_response_time = models.FloatField(default=0)  # in minutes
    client_satisfaction_score = models.FloatField(default=0)  # 0-5 scale
    professional_satisfaction_score = models.FloatField(default=0)  # 0-5 scale
    
    # Conversion metrics
    consultation_conversion_rate = models.FloatField(default=0)  # percentage
    professional_verification_rate = models.FloatField(default=0)  # percentage
    client_retention_rate = models.FloatField(default=0)  # percentage
    
    # Additional data
    category_breakdown = models.JSONField(default=dict, blank=True)  # Consultations by category
    hourly_breakdown = models.JSONField(default=dict, blank=True)  # Activity by hour
    device_breakdown = models.JSONField(default=dict, blank=True)  # Web vs Mobile
    
    # Timestamps
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name = 'Platform Analytics'
        verbose_name_plural = 'Platform Analytics'
        indexes = [
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"Analytics for {self.date}"
    
    @classmethod
    def get_or_create_daily(cls, date=None):
        """Get or create analytics for a specific date"""
        if date is None:
            date = timezone.now().date()
        
        analytics, created = cls.objects.get_or_create(date=date)
        return analytics, created
    
    @property
    def revenue_per_consultation(self):
        if self.completed_consultations > 0:
            return self.daily_revenue / self.completed_consultations
        return 0
    
    @property
    def user_growth_rate(self):
        if self.total_users > 0 and self.new_users > 0:
            return (self.new_users / self.total_users) * 100
        return 0

class NotificationTemplate(models.Model):
    """Email/SMS notification templates for admin"""
    TEMPLATE_TYPE_CHOICES = (
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('in_app', 'In-App Notification'),
    )
    
    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)
    subject = models.CharField(max_length=200, blank=True)
    content = models.TextField(help_text="Template content with {{ variables }}")
    variables = models.JSONField(default=list, blank=True, help_text="Available template variables")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False, help_text="System templates cannot be deleted")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
        unique_together = ['name', 'template_type']
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"
    
    def render(self, context):
        """Render template with context variables"""
        content = self.content
        for key, value in context.items():
            placeholder = f"{{{{ {key} }}}}"
            content = content.replace(placeholder, str(value))
        return content