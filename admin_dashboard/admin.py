from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from django.db.models import Count, Sum, Avg
from .models import AdminLog, PlatformSettings, Report, PlatformAnalytics, NotificationTemplate
import json

class AdminLogAdmin(admin.ModelAdmin):
    list_display = ['admin_name', 'action_display', 'description_short', 'ip_address', 'created_at_formatted']
    list_filter = ['action', 'created_at', 'admin']
    search_fields = ['admin__username', 'admin__email', 'description', 'ip_address']
    readonly_fields = ['created_at', 'details_formatted']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Log Information', {
            'fields': ('admin', 'action', 'description', 'details_formatted')
        }),
        ('Technical Details', {
            'fields': ('ip_address', 'user_agent', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def admin_name(self, obj):
        if obj.admin:
            url = reverse("admin:accounts_user_change", args=[obj.admin.id])
            return format_html('<a href="{}">{}</a>', url, obj.admin.get_full_name())
        return 'System'
    admin_name.short_description = 'Admin'
    
    def action_display(self, obj):
        colors = {
            'user_created': 'green',
            'user_updated': 'blue',
            'user_deleted': 'red',
            'professional_verified': 'orange',
            'payment_processed': 'purple',
        }
        color = colors.get(obj.action, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_action_display()
        )
    action_display.short_description = 'Action'
    
    def description_short(self, obj):
        if len(obj.description) > 50:
            return f"{obj.description[:50]}..."
        return obj.description
    description_short.short_description = 'Description'
    
    def created_at_formatted(self, obj):
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    created_at_formatted.short_description = 'Timestamp'
    
    def details_formatted(self, obj):
        if obj.details:
            return format_html('<pre>{}</pre>', json.dumps(obj.details, indent=2))
        return 'No details'
    details_formatted.short_description = 'Details (JSON)'
    
    def has_add_permission(self, request):
        return False  # Cannot add logs manually
    
    def has_change_permission(self, request, obj=None):
        return False  # Cannot change logs

class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'category_display', 'value_short', 'setting_type', 'is_public', 'updated_at']
    list_filter = ['category', 'setting_type', 'is_public', 'is_required']
    search_fields = ['key', 'description', 'value']
    readonly_fields = ['created_at', 'updated_at', 'updated_by']
    list_editable = ['is_public']
    ordering = ['category', 'key']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('key', 'category', 'description')
        }),
        ('Setting Value', {
            'fields': ('setting_type', 'value', 'options', 'min_value', 'max_value')
        }),
        ('Access Control', {
            'fields': ('is_public', 'is_required')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def category_display(self, obj):
        colors = {
            'general': 'blue',
            'payments': 'green',
            'notifications': 'orange',
            'consultations': 'purple',
            'security': 'red',
            'appearance': 'pink',
        }
        color = colors.get(obj.category, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_category_display()
        )
    category_display.short_description = 'Category'
    
    def value_short(self, obj):
        value_str = str(obj.value)
        if len(value_str) > 30:
            return f"{value_str[:30]}..."
        return value_str
    value_short.short_description = 'Value'
    
    def save_model(self, request, obj, form, change):
        if change:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_required:
            return self.readonly_fields + ['key', 'setting_type']
        return self.readonly_fields

class ReportAdmin(admin.ModelAdmin):
    list_display = ['name', 'report_type_display', 'period_range', 'status_display', 'format', 'generated_by_name', 'generated_at_formatted']
    list_filter = ['report_type', 'status', 'format', 'generated_at']
    search_fields = ['name', 'summary', 'error_message']
    readonly_fields = ['created_at', 'updated_at', 'processing_time', 'data_formatted', 'filters_formatted']
    actions = ['regenerate_report', 'mark_as_generated']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Report Information', {
            'fields': ('name', 'report_type', 'format', 'period_start', 'period_end')
        }),
        ('Status & Generation', {
            'fields': ('status', 'error_message', 'generated_by', 'generated_at', 'processing_time')
        }),
        ('Files & Output', {
            'fields': ('file_path', 'file_url', 'file_size', 'summary')
        }),
        ('Data & Filters', {
            'fields': ('data_formatted', 'filters_formatted', 'parameters_formatted'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def report_type_display(self, obj):
        icons = {
            'revenue': '💰',
            'users': '👥',
            'consultations': '💬',
            'professionals': '👨‍⚕️',
            'clients': '👤',
            'platform_health': '📊',
            'financial': '📈',
        }
        icon = icons.get(obj.report_type, '📄')
        return format_html('{} {}', icon, obj.get_report_type_display())
    report_type_display.short_description = 'Type'
    
    def period_range(self, obj):
        days = obj.duration_days
        return format_html(
            '{} to {}<br><small style="color: gray;">({} days)</small>',
            obj.period_start,
            obj.period_end,
            days
        )
    period_range.short_description = 'Period'
    
    def status_display(self, obj):
        colors = {
            'pending': 'gray',
            'processing': 'orange',
            'generated': 'green',
            'failed': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def generated_by_name(self, obj):
        if obj.generated_by:
            url = reverse("admin:accounts_user_change", args=[obj.generated_by.id])
            return format_html('<a href="{}">{}</a>', url, obj.generated_by.get_full_name())
        return 'System'
    generated_by_name.short_description = 'Generated By'
    
    def generated_at_formatted(self, obj):
        if obj.generated_at:
            return obj.generated_at.strftime('%Y-%m-%d %H:%M')
        return 'Not generated'
    generated_at_formatted.short_description = 'Generated At'
    
    def data_formatted(self, obj):
        if obj.data:
            return format_html('<pre>{}</pre>', json.dumps(obj.data, indent=2))
        return 'No data'
    data_formatted.short_description = 'Data (JSON)'
    
    def filters_formatted(self, obj):
        if obj.filters:
            return format_html('<pre>{}</pre>', json.dumps(obj.filters, indent=2))
        return 'No filters'
    filters_formatted.short_description = 'Filters (JSON)'
    
    def parameters_formatted(self, obj):
        if obj.parameters:
            return format_html('<pre>{}</pre>', json.dumps(obj.parameters, indent=2))
        return 'No parameters'
    parameters_formatted.short_description = 'Parameters (JSON)'
    
    @admin.action(description="Regenerate selected reports")
    def regenerate_report(self, request, queryset):
        for report in queryset:
            report.status = 'pending'
            report.error_message = ''
            report.generated_at = None
            report.file_path = ''
            report.file_url = ''
            report.save()
        self.message_user(request, f"{queryset.count()} reports marked for regeneration.")
    
    @admin.action(description="Mark as generated (for testing)")
    def mark_as_generated(self, request, queryset):
        for report in queryset:
            report.status = 'generated'
            report.generated_at = timezone.now()
            report.save()
        self.message_user(request, f"{queryset.count()} reports marked as generated.")

class PlatformAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_users', 'new_users', 'total_consultations', 'daily_revenue', 'client_satisfaction_score']
    list_filter = ['date']
    search_fields = ['date']
    readonly_fields = ['calculated_at', 'category_breakdown_formatted', 'hourly_breakdown_formatted']
    date_hierarchy = 'date'
    ordering = ['-date']
    
    fieldsets = (
        ('Date', {
            'fields': ('date', 'calculated_at')
        }),
        ('User Metrics', {
            'fields': ('total_users', 'new_users', 'active_users'),
            'classes': ('collapse',)
        }),
        ('Professional Metrics', {
            'fields': ('total_professionals', 'new_professionals', 'online_professionals', 'verified_professionals'),
            'classes': ('collapse',)
        }),
        ('Client Metrics', {
            'fields': ('total_clients', 'new_clients', 'active_clients'),
            'classes': ('collapse',)
        }),
        ('Consultation Metrics', {
            'fields': ('total_consultations', 'new_consultations', 'completed_consultations', 'cancelled_consultations', 'active_consultations'),
            'classes': ('collapse',)
        }),
        ('Financial Metrics', {
            'fields': ('total_revenue', 'daily_revenue', 'platform_earnings', 'professional_earnings'),
            'classes': ('collapse',)
        }),
        ('Performance Metrics', {
            'fields': ('average_consultation_duration', 'average_response_time', 'client_satisfaction_score', 'professional_satisfaction_score'),
            'classes': ('collapse',)
        }),
        ('Conversion Metrics', {
            'fields': ('consultation_conversion_rate', 'professional_verification_rate', 'client_retention_rate'),
            'classes': ('collapse',)
        }),
        ('Breakdowns', {
            'fields': ('category_breakdown_formatted', 'hourly_breakdown_formatted', 'device_breakdown_formatted'),
            'classes': ('collapse',)
        }),
    )
    
    def category_breakdown_formatted(self, obj):
        if obj.category_breakdown:
            return format_html('<pre>{}</pre>', json.dumps(obj.category_breakdown, indent=2))
        return 'No data'
    category_breakdown_formatted.short_description = 'Category Breakdown'
    
    def hourly_breakdown_formatted(self, obj):
        if obj.hourly_breakdown:
            return format_html('<pre>{}</pre>', json.dumps(obj.hourly_breakdown, indent=2))
        return 'No data'
    hourly_breakdown_formatted.short_description = 'Hourly Breakdown'
    
    def device_breakdown_formatted(self, obj):
        if obj.device_breakdown:
            return format_html('<pre>{}</pre>', json.dumps(obj.device_breakdown, indent=2))
        return 'No data'
    device_breakdown_formatted.short_description = 'Device Breakdown'
    
    def has_add_permission(self, request):
        return False  # Analytics should be auto-generated
    
    def has_change_permission(self, request, obj=None):
        return False  # Analytics should be auto-generated

class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'template_type_display', 'subject_short', 'is_active', 'is_system', 'updated_at']
    list_filter = ['template_type', 'is_active', 'is_system']
    search_fields = ['name', 'subject', 'content', 'variables']
    readonly_fields = ['created_at', 'updated_at', 'variables_formatted']
    list_editable = ['is_active']
    
    fieldsets = (
        ('Template Information', {
            'fields': ('name', 'template_type', 'subject', 'content')
        }),
        ('Variables & Status', {
            'fields': ('variables_formatted', 'is_active', 'is_system')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def template_type_display(self, obj):
        icons = {
            'email': '📧',
            'sms': '📱',
            'push': '📲',
            'in_app': '🔔',
        }
        icon = icons.get(obj.template_type, '📄')
        return format_html('{} {}', icon, obj.get_template_type_display())
    template_type_display.short_description = 'Type'
    
    def subject_short(self, obj):
        if obj.subject and len(obj.subject) > 30:
            return f"{obj.subject[:30]}..."
        return obj.subject or '-'
    subject_short.short_description = 'Subject'
    
    def variables_formatted(self, obj):
        if obj.variables:
            return format_html('<pre>{}</pre>', json.dumps(obj.variables, indent=2))
        return 'No variables'
    variables_formatted.short_description = 'Variables (JSON)'
    
    def save_model(self, request, obj, form, change):
        # Auto-populate variables from content
        import re
        variables = re.findall(r'\{\{\s*(\w+)\s*\}\}', obj.content)
        obj.variables = list(set(variables))
        super().save_model(request, obj, form, change)

# Register models
admin.site.register(AdminLog, AdminLogAdmin)
admin.site.register(PlatformSettings, PlatformSettingsAdmin)
admin.site.register(Report, ReportAdmin)
admin.site.register(PlatformAnalytics, PlatformAnalyticsAdmin)
admin.site.register(NotificationTemplate, NotificationTemplateAdmin)