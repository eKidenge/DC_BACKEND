from rest_framework import serializers
from django.utils import timezone
from .models import CallRequest  # Add CallRequest to imports

# IMPORT from accounts instead
from accounts.models import User, ProfessionalProfile as AccountsProfessionalProfile
from dashboard.models import (
    ProfessionalAvailability, ProfessionalStat, IncomingCall,
    ProfessionalNotification, ProfessionalCalendar, CallHistory
)

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User  # From accounts
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name', 'role', 'phone']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

# CHANGE: Serializer for accounts ProfessionalProfile
class AccountsProfessionalProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = AccountsProfessionalProfile  # From accounts
        fields = [
            'id', 'user', 'service_categories', 'specialty', 'license_number',
            'hourly_rate', 'rating', 'experience_years', 'bio', 'languages',
            'is_verified', 'is_online', 'last_seen'
        ]

class ProfessionalAvailabilitySerializer(serializers.ModelSerializer):
    professional = AccountsProfessionalProfileSerializer(read_only=True)
    
    class Meta:
        model = ProfessionalAvailability
        fields = '__all__'

class ProfessionalStatSerializer(serializers.ModelSerializer):
    professional = AccountsProfessionalProfileSerializer(read_only=True)
    
    class Meta:
        model = ProfessionalStat
        fields = '__all__'

class IncomingCallSerializer(serializers.ModelSerializer):
    professional = AccountsProfessionalProfileSerializer(read_only=True)
    time_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = IncomingCall
        fields = '__all__'
    
    def get_time_remaining(self, obj):
        if obj.expires_at and obj.status in ['pending', 'ringing']:
            remaining = obj.expires_at - timezone.now()
            return max(0, remaining.total_seconds())
        return 0

class ProfessionalNotificationSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = ProfessionalNotification
        fields = '__all__'
    
    def get_time_ago(self, obj):
        from django.utils.timesince import timesince
        return timesince(obj.created_at)

class ProfessionalCalendarSerializer(serializers.ModelSerializer):
    professional = AccountsProfessionalProfileSerializer(read_only=True)
    duration_minutes = serializers.SerializerMethodField()
    
    class Meta:
        model = ProfessionalCalendar
        fields = '__all__'
    
    def get_duration_minutes(self, obj):
        if obj.start_time and obj.end_time:
            duration = obj.end_time - obj.start_time
            return duration.total_seconds() / 60
        return 0

class CallHistorySerializer(serializers.ModelSerializer):
    professional = AccountsProfessionalProfileSerializer(read_only=True)
    duration_minutes = serializers.SerializerMethodField()
    formatted_date = serializers.SerializerMethodField()
    
    class Meta:
        model = CallHistory
        fields = '__all__'
    
    def get_duration_minutes(self, obj):
        return obj.duration_seconds / 60 if obj.duration_seconds else 0
    
    def get_formatted_date(self, obj):
        return obj.start_time.strftime('%b %d, %Y %I:%M %p')


# ============================================
# CALL REQUEST SERIALIZER (ADD THIS)
# ============================================

class CallRequestSerializer(serializers.ModelSerializer):
    professional_name = serializers.CharField(source='professional.user.get_full_name', read_only=True)
    time_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = CallRequest  # Make sure you import CallRequest at the top
        fields = [
            'id', 'professional', 'professional_name', 'client_id', 'client_name',
            'client_phone', 'call_type', 'duration', 'consultation_id', 'amount',
            'category', 'status', 'room_id', 'expires_at', 'responded_at',
            'accepted_at', 'rejected_at', 'connected_at', 'ended_at',
            'rejection_reason', 'time_remaining', 'created_at'
        ]
        read_only_fields = ['created_at', 'room_id', 'expires_at']
    
    def get_time_remaining(self, obj):
        """Calculate remaining time for pending calls"""
        if obj.status in ['pending', 'ringing'] and obj.expires_at:
            remaining = obj.expires_at - timezone.now()
            seconds = remaining.total_seconds()
            return max(0, int(seconds))
        return 0
    
    def create(self, validated_data):
        """Automatically set room_id and expires_at on creation"""
        call_request = CallRequest.objects.create(**validated_data)
        return call_request
