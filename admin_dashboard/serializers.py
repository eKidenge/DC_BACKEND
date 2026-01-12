from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from accounts.models import User, ProfessionalProfile, ClientProfile
from categories.models import ServiceCategory, ConsultationRequest
from .models import AdminLog, PlatformSettings, Report
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    user_type = serializers.CharField(source='role')
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'full_name', 'user_type', 'is_active', 
                  'date_joined', 'last_login', 'phone', 'profile_image', 'first_name', 
                  'last_name', 'role']
        read_only_fields = ['date_joined', 'last_login']
    
    def get_full_name(self, obj):
        return obj.get_full_name()

class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating users"""
    password = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name', 'phone', 'role']
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        validated_data['password'] = make_password(password)
        return super().create(validated_data)

class ProfessionalProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    categories = serializers.SerializerMethodField()
    total_earnings = serializers.SerializerMethodField()
    total_consultations = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    
    class Meta:
        model = ProfessionalProfile
        fields = ['id', 'user', 'hourly_rate', 'rating', 'experience_years', 'bio',
                  'languages', 'is_verified', 'is_online', 'last_seen', 'categories',
                  'total_earnings', 'total_consultations', 'average_rating', 'license_number']
        read_only_fields = ['rating', 'is_online', 'last_seen']
    
    def get_categories(self, obj):
        categories = obj.service_categories.all()
        return [{'id': cat.id, 'name': cat.name} for cat in categories]
    
    def get_total_earnings(self, obj):
        total = ConsultationRequest.objects.filter(
            professional=obj,
            status='completed'
        ).aggregate(total=Sum('professional_earnings'))['total']
        return total or 0
    
    def get_total_consultations(self, obj):
        return ConsultationRequest.objects.filter(professional=obj).count()
    
    def get_average_rating(self, obj):
        return obj.rating

class ProfessionalCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating professional with user"""
    user = UserCreateSerializer()
    
    class Meta:
        model = ProfessionalProfile
        fields = ['id', 'user', 'hourly_rate', 'experience_years', 'bio',
                  'languages', 'license_number', 'service_categories']
    
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user_data['role'] = 'professional'
        
        user_serializer = UserCreateSerializer(data=user_data)
        if user_serializer.is_valid():
            user = user_serializer.save()
        else:
            raise serializers.ValidationError(user_serializer.errors)
        
        professional = ProfessionalProfile.objects.create(user=user, **validated_data)
        return professional

class ClientProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    total_spent = serializers.SerializerMethodField()
    total_consultations = serializers.SerializerMethodField()
    last_consultation = serializers.SerializerMethodField()
    
    class Meta:
        model = ClientProfile
        fields = ['id', 'user', 'total_spent', 'total_consultations', 
                  'last_consultation', 'date_of_birth', 'preferences']
    
    def get_total_spent(self, obj):
        total = ConsultationRequest.objects.filter(
            client=obj.user,
            status='completed'
        ).aggregate(total=Sum('total_amount'))['total']
        return total or 0
    
    def get_total_consultations(self, obj):
        return ConsultationRequest.objects.filter(client=obj.user).count()
    
    def get_last_consultation(self, obj):
        last = ConsultationRequest.objects.filter(
            client=obj.user
        ).order_by('-created_at').first()
        return last.created_at if last else None

class ClientCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating client with user"""
    user = UserCreateSerializer()
    
    class Meta:
        model = ClientProfile
        fields = ['id', 'user', 'date_of_birth', 'preferences']
    
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user_data['role'] = 'client'
        
        user_serializer = UserCreateSerializer(data=user_data)
        if user_serializer.is_valid():
            user = user_serializer.save()
        else:
            raise serializers.ValidationError(user_serializer.errors)
        
        client = ClientProfile.objects.create(user=user, **validated_data)
        return client

class ConsultationSerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField()
    professional_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ConsultationRequest
        fields = ['id', 'title', 'description', 'status', 'duration_minutes',
                  'total_amount', 'created_at', 'scheduled_start', 'scheduled_end',
                  'completed_at', 'client_name', 'professional_name', 'category_name',
                  'hourly_rate', 'professional_earnings', 'platform_fee', 'client', 
                  'professional', 'category']
        read_only_fields = ['created_at', 'completed_at']
    
    def get_client_name(self, obj):
        return obj.client.get_full_name() if obj.client else None
    
    def get_professional_name(self, obj):
        return obj.professional.user.get_full_name() if obj.professional else None
    
    def get_category_name(self, obj):
        return obj.category.name if obj.category else None

class AdminLogSerializer(serializers.ModelSerializer):
    admin_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AdminLog
        fields = ['id', 'admin_name', 'action', 'description', 'ip_address', 'created_at', 'details']
    
    def get_admin_name(self, obj):
        return obj.admin.get_full_name() if obj.admin else 'System'

class PlatformStatsSerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    total_professionals = serializers.IntegerField()
    total_clients = serializers.IntegerField()
    total_consultations = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    active_consultations = serializers.IntegerField()
    today_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    today_consultations = serializers.IntegerField()
    pending_verifications = serializers.IntegerField()
    offline_professionals = serializers.IntegerField()

class ReportSerializer(serializers.ModelSerializer):
    generated_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Report
        fields = ['id', 'name', 'report_type', 'format', 'period_start', 'period_end',
                  'file_path', 'file_url', 'file_size', 'data', 'summary', 'status',
                  'error_message', 'generated_by_name', 'generated_at', 'processing_time',
                  'filters', 'parameters', 'created_at', 'updated_at']
    
    def get_generated_by_name(self, obj):
        return obj.generated_by.get_full_name() if obj.generated_by else None

class ProfessionalVerificationSerializer(serializers.Serializer):
    professional_id = serializers.IntegerField()
    verified = serializers.BooleanField()
    notes = serializers.CharField(required=False, allow_blank=True)

class UserStatusSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()

class ReportGenerateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    report_type = serializers.CharField()
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    format = serializers.ChoiceField(choices=['json', 'csv', 'pdf', 'excel'], default='json')
    filters = serializers.JSONField(required=False, default=dict)
    parameters = serializers.JSONField(required=False, default=dict)

class PlatformSettingsSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = PlatformSettings
        fields = ['id', 'key', 'category', 'value', 'setting_type', 'description',
                  'is_public', 'is_required', 'min_value', 'max_value', 'options',
                  'created_at', 'updated_at', 'updated_by_name']
    
    def get_updated_by_name(self, obj):
        return obj.updated_by.get_full_name() if obj.updated_by else None

class ConsultationCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)
