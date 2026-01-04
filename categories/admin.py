from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    ServiceCategory, ConsultationRequest, 
    ConsultationAttachment, ConsultationMessage
)

class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'active', 'order', 'base_price', 
                   'commission_rate', 'get_professionals_count', 'created_at')
    list_filter = ('active', 'available_24_7', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('active', 'order')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'icon', 'active', 'order')
        }),
        ('Pricing', {
            'fields': ('base_price', 'commission_rate')
        }),
        ('Settings', {
            'fields': ('min_duration', 'max_duration', 'available_24_7')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_professionals_count(self, obj):
        """Display count of available professionals"""
        count = obj.get_available_professionals_count()
        url = reverse('admin:accounts_professionalprofile_changelist')
        return format_html(
            '<a href="{}?specialty__exact={}">{}</a>',
            url,
            obj.name,
            count
        )
    get_professionals_count.short_description = 'Professionals'
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('consultations')

class ConsultationAttachmentInline(admin.TabularInline):
    model = ConsultationAttachment
    extra = 0
    readonly_fields = ('file_name', 'file_type', 'file_size', 'uploaded_by', 'uploaded_at')
    fields = ('file', 'file_name', 'file_type', 'file_size', 'description', 'uploaded_by', 'uploaded_at')
    
    def has_add_permission(self, request, obj=None):
        return request.user.is_staff
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_staff

class ConsultationMessageInline(admin.TabularInline):
    model = ConsultationMessage
    extra = 0
    readonly_fields = ('sender', 'created_at')
    fields = ('sender', 'message', 'attachment', 'is_read', 'created_at')
    ordering = ('-created_at',)
    
    def has_add_permission(self, request, obj=None):
        return request.user.is_staff

@admin.register(ConsultationRequest)
class ConsultationRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'client_name', 'category_display', 'professional_display',
        'status_badge', 'priority_display', 'duration_minutes',
        'total_amount', 'created_at_display'
    )
    list_filter = (
        'status', 'priority', 'category', 'created_at',
        'is_urgent', 'professional__is_verified'
    )
    search_fields = (
        'id', 'client__first_name', 'client__last_name', 
        'client__email', 'title', 'description',
        'professional__user__first_name', 'professional__user__last_name'
    )
    readonly_fields = (
        'created_at', 'matched_at', 'accepted_at', 'started_at',
        'completed_at', 'cancelled_at', 'updated_at', 'match_attempts'
    )
    list_select_related = ('client', 'professional__user', 'category')
    inlines = [ConsultationAttachmentInline, ConsultationMessageInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'client', 'professional', 'category', 'title', 'description',
                'status', 'priority', 'is_urgent'
            )
        }),
        ('Scheduling', {
            'fields': (
                'preferred_date', 'preferred_time', 'duration_minutes',
                'scheduled_start', 'scheduled_end'
            )
        }),
        ('Pricing', {
            'fields': (
                'hourly_rate', 'total_amount', 'platform_fee', 
                'professional_earnings'
            )
        }),
        ('Communication', {
            'fields': (
                'client_notes', 'professional_notes', 'admin_notes'
            ),
            'classes': ('collapse',)
        }),
        ('Call Details', {
            'fields': (
                'call_id', 'call_start_time', 'call_end_time', 'call_duration'
            ),
            'classes': ('collapse',)
        }),
        ('Ratings & Feedback', {
            'fields': (
                'client_rating', 'client_review',
                'professional_rating', 'professional_feedback'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at', 'matched_at', 'accepted_at', 'started_at',
                'completed_at', 'cancelled_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
        ('Tracking', {
            'fields': ('match_attempts', 'source'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_cancelled', 'assign_professional']
    
    def client_name(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.client.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.client.get_full_name()
        )
    client_name.short_description = 'Client'
    
    def professional_display(self, obj):
        if obj.professional:
            url = reverse('admin:accounts_professionalprofile_change', args=[obj.professional.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.professional.user.get_full_name()
            )
        return "Not assigned"
    professional_display.short_description = 'Professional'
    
    def category_display(self, obj):
        url = reverse('admin:categories_servicecategory_change', args=[obj.category.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.category.name
        )
    category_display.short_description = 'Category'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'matched': 'blue',
            'accepted': 'green',
            'scheduled': 'teal',
            'in_progress': 'purple',
            'completed': 'green',
            'cancelled': 'red',
            'rejected': 'gray',
            'expired': 'gray',
        }
        return format_html(
            '<span style="padding: 2px 8px; border-radius: 12px; '
            'background-color: {}; color: white; font-size: 12px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def priority_display(self, obj):
        icons = {
            'low': '🔵',
            'medium': '🟡',
            'high': '🟠',
            'emergency': '🔴',
        }
        return format_html(
            '{} {}',
            icons.get(obj.priority, '⚪'),
            obj.get_priority_display()
        )
    priority_display.short_description = 'Priority'
    
    def created_at_display(self, obj):
        now = timezone.now()
        if obj.created_at.date() == now.date():
            return f"Today, {obj.created_at.strftime('%H:%M')}"
        elif obj.created_at.date() == (now - timezone.timedelta(days=1)).date():
            return f"Yesterday, {obj.created_at.strftime('%H:%M')}"
        return obj.created_at.strftime('%b %d, %Y')
    created_at_display.short_description = 'Created'
    
    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f"{updated} consultations marked as completed.")
    mark_as_completed.short_description = "Mark selected as completed"
    
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled', cancelled_at=timezone.now())
        self.message_user(request, f"{updated} consultations marked as cancelled.")
    mark_as_cancelled.short_description = "Mark selected as cancelled"
    
    def assign_professional(self, request, queryset):
        from accounts.models import ProfessionalProfile
        
        for consultation in queryset.filter(professional__isnull=True):
            # Find available professional
            available_pros = ProfessionalProfile.objects.filter(
                specialty=consultation.category.name,
                is_online=True,
                is_verified=True
            ).order_by('-rating')
            
            if available_pros.exists():
                consultation.professional = available_pros.first()
                consultation.status = 'matched'
                consultation.matched_at = timezone.now()
                consultation.save()
        
        self.message_user(request, "Professionals assigned to selected consultations.")
    assign_professional.short_description = "Assign professionals to selected"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.select_related('client', 'professional__user', 'category')
        return qs.filter(client=request.user)

@admin.register(ConsultationAttachment)
class ConsultationAttachmentAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'consultation_link', 'file_type', 
                   'file_size_mb', 'uploaded_by', 'uploaded_at')
    list_filter = ('file_type', 'uploaded_at')
    search_fields = ('file_name', 'consultation__title', 'uploaded_by__email')
    readonly_fields = ('file_size', 'uploaded_at')
    
    def consultation_link(self, obj):
        url = reverse('admin:categories_consultationrequest_change', args=[obj.consultation.id])
        return format_html(
            '<a href="{}">Consultation #{}</a>',
            url,
            obj.consultation.id
        )
    consultation_link.short_description = 'Consultation'
    
    def file_size_mb(self, obj):
        return f"{obj.file_size / (1024*1024):.2f} MB"
    file_size_mb.short_description = 'File Size'

@admin.register(ConsultationMessage)
class ConsultationMessageAdmin(admin.ModelAdmin):
    list_display = ('consultation_id', 'sender_name', 'message_preview', 
                   'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('message', 'sender__email', 'consultation__title')
    readonly_fields = ('created_at',)
    
    def consultation_id(self, obj):
        url = reverse('admin:categories_consultationrequest_change', args=[obj.consultation.id])
        return format_html(
            '<a href="{}">#{}</a>',
            url,
            obj.consultation.id
        )
    consultation_id.short_description = 'Consultation'
    
    def sender_name(self, obj):
        return obj.sender.get_full_name()
    sender_name.short_description = 'Sender'
    
    def message_preview(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'

# Register the ServiceCategory model
admin.site.register(ServiceCategory, ServiceCategoryAdmin)