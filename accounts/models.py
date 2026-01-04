from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator

class User(AbstractUser):
    ROLE_CHOICES = (
        ('client', 'Client'),
        ('professional', 'Professional'),
        ('admin', 'Admin'),
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='client')
    phone = models.CharField(max_length=20, blank=True)
    #profile_image = models.ImageField(upload_to='profiles/', blank=True)
    profile_image = models.FileField(upload_to='profiles/', blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.username} ({self.role})"

class ProfessionalProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='professional_profile')
    
    # NEW: Link to ServiceCategory from categories app
    service_categories = models.ManyToManyField(
        'categories.ServiceCategory',
        related_name='professionals',
        blank=True
    )
    
    # Keep old specialty field for backward compatibility
    specialty = models.CharField(max_length=50, blank=True)
    
    license_number = models.CharField(max_length=100, blank=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)
    rating = models.FloatField(default=4.0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    experience_years = models.IntegerField(default=1)
    bio = models.TextField(blank=True)
    languages = models.JSONField(default=list)  # ['English', 'Spanish']
    is_verified = models.BooleanField(default=False)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        categories = self.service_categories.all()
        if categories.exists():
            category_names = ", ".join([cat.name for cat in categories[:2]])
            return f"{self.user.get_full_name()} - {category_names}"
        return f"{self.user.get_full_name()}"

class ClientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client_profile')
    date_of_birth = models.DateField(null=True, blank=True)
    emergency_contact = models.CharField(max_length=100, blank=True)
    preferences = models.JSONField(default=dict)  # {"language": "English", ...}
    
    def __str__(self):
        return f"{self.user.get_full_name()}" 
