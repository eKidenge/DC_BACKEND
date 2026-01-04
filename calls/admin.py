from django.contrib import admin
from .models import Consultation, CallSession

@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ('id', 'professional', 'client', 'category', 'status', 'scheduled_time', 'amount', 'payment_status')
    list_filter = ('status', 'payment_status', 'category', 'scheduled_time')
    search_fields = ('professional__user__username', 'client__username', 'title', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('professional', 'client', 'category', 'title', 'description')
        }),
        ('Timing', {
            'fields': ('duration_minutes', 'scheduled_time', 'start_time', 'end_time', 'actual_duration_minutes')
        }),
        ('Status', {
            'fields': ('status', 'cancellation_reason', 'cancelled_by')
        }),
        ('Payment', {
            'fields': ('amount', 'amount_paid', 'payment_status', 'payment_method', 'payment_reference')
        }),
        ('Meeting', {
            'fields': ('meeting_link', 'meeting_id', 'recording_url')
        }),
        ('Feedback', {
            'fields': ('rating', 'feedback', 'client_feedback')
        }),
        ('Notes', {
            'fields': ('notes', 'client_notes', 'professional_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

@admin.register(CallSession)
class CallSessionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'consultation', 'status', 'initiated_at', 'duration_seconds')
    list_filter = ('status', 'initiated_at')
    search_fields = ('session_id', 'consultation__id', 'caller_sid')
    readonly_fields = ('initiated_at', 'created_at')
    fieldsets = (
        ('Session Info', {
            'fields': ('consultation', 'session_id', 'status')
        }),
        ('Timing', {
            'fields': ('initiated_at', 'answered_at', 'ended_at', 'duration_seconds')
        }),
        ('Technical Details', {
            'fields': ('caller_sid', 'recording_url', 'call_quality_score', 'network_issues')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )