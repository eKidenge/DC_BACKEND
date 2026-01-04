from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, ProfessionalProfile, ClientProfile

class ProfessionalProfileInline(admin.StackedInline):
    model = ProfessionalProfile
    can_delete = False
    verbose_name_plural = 'Professional Profile'
    filter_horizontal = ('service_categories',)  # ADD THIS LINE
    fieldsets = (
        ('Professional Details', {
            'fields': (
                'service_categories', 'specialty', 'license_number', 'hourly_rate',  # ADD 'service_categories'
                'rating', 'experience_years', 'bio', 'languages',
                'is_verified', 'is_online'
            )
        }),
    )

class ClientProfileInline(admin.StackedInline):
    model = ClientProfile
    can_delete = False
    verbose_name_plural = 'Client Profile'
    fieldsets = (
        ('Client Details', {
            'fields': ('date_of_birth', 'emergency_contact', 'preferences')
        }),
    )

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active', 'is_superuser', 'email_verified')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal Info'), {'fields': ('first_name', 'last_name', 'email', 'phone', 'profile_image')}),
        (_('Role & Permissions'), {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Verification'), {'fields': ('email_verified',)}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role'),
        }),
    )
    
    def get_inlines(self, request, obj=None):
        if obj and obj.role == 'professional':
            return [ProfessionalProfileInline]
        elif obj and obj.role == 'client':
            return [ClientProfileInline]
        return []

@admin.register(ProfessionalProfile)
class ProfessionalProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'display_categories', 'hourly_rate', 'rating', 'experience_years', 'is_verified', 'is_online')  # CHANGE 'specialty' to 'display_categories'
    list_filter = ('service_categories', 'is_verified', 'is_online', 'experience_years')  # CHANGE 'specialty' to 'service_categories'
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name', 'license_number')
    list_select_related = ('user',)
    list_per_page = 50
    filter_horizontal = ('service_categories',)  # ADD THIS LINE
    
    fieldsets = (
        ('Professional Information', {
            'fields': ('user', 'service_categories', 'specialty', 'license_number', 'hourly_rate', 'experience_years', 'bio')  # ADD 'service_categories'
        }),
        ('Status & Ratings', {
            'fields': ('rating', 'is_verified', 'is_online', 'languages')
        }),
    )
    
    readonly_fields = ('user',)
    
    def has_add_permission(self, request):
        return False
    
    def display_categories(self, obj):  # ADD THIS METHOD
        """Display categories as a comma-separated string in list view"""
        return ", ".join([cat.name for cat in obj.service_categories.all()])
    display_categories.short_description = 'Service Categories'

@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'date_of_birth', 'emergency_contact')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    list_select_related = ('user',)
    list_per_page = 50
    
    fieldsets = (
        ('Client Information', {
            'fields': ('user', 'date_of_birth', 'emergency_contact', 'preferences')
        }),
    )
    
    readonly_fields = ('user',)
    
    def has_add_permission(self, request):
        return False