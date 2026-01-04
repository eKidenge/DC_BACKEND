from django.contrib import admin
from accounts.models import ProfessionalProfile as AccountsProfessionalProfile
from .models import (
    ProfessionalAvailability, ProfessionalStat,
    IncomingCall, ProfessionalNotification, ProfessionalCalendar, CallHistory
)

# DO NOT REGISTER AccountsProfessionalProfile here - it's already in accounts.admin
# Just import it for the other admin classes to reference

@admin.register(ProfessionalAvailability)
class ProfessionalAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('professional', 'is_available', 'auto_accept_calls', 'max_daily_sessions', 'updated_at')
    list_filter = ('is_available', 'auto_accept_calls')
    search_fields = ('professional__user__username', 'professional__user__email')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ProfessionalStat)
class ProfessionalStatAdmin(admin.ModelAdmin):
    list_display = ('professional', 'total_consultations', 'today_earnings', 'average_rating', 'last_updated')
    list_filter = ('stats_date',)
    search_fields = ('professional__user__username', 'professional__user__email')
    readonly_fields = ('last_updated', 'stats_date')

@admin.register(IncomingCall)
class IncomingCallAdmin(admin.ModelAdmin):
    list_display = ('client_name', 'professional', 'category', 'status', 'estimated_earnings', 'created_at')
    list_filter = ('status', 'category', 'created_at')
    search_fields = ('client_name', 'professional__user__username', 'client_phone')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ProfessionalNotification)
class ProfessionalNotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'title', 'is_read', 'priority', 'created_at')
    list_filter = ('notification_type', 'is_read', 'priority', 'created_at')
    search_fields = ('user__username', 'title', 'message')
    readonly_fields = ('created_at',)

@admin.register(ProfessionalCalendar)
class ProfessionalCalendarAdmin(admin.ModelAdmin):
    list_display = ('title', 'professional', 'event_type', 'start_time', 'end_time', 'is_confirmed')
    list_filter = ('event_type', 'is_confirmed', 'is_cancelled', 'start_time')
    search_fields = ('title', 'professional__user__username', 'description')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(CallHistory)
class CallHistoryAdmin(admin.ModelAdmin):
    list_display = ('client_name', 'professional', 'duration_seconds', 'earnings', 'start_time')
    list_filter = ('start_time',)
    search_fields = ('client_name', 'professional__user__username')
    readonly_fields = ('created_at',)