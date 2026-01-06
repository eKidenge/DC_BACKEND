from rest_framework import serializers
from accounts.models import User, ProfessionalProfile, ClientProfile
from categories.models import ServiceCategory, ConsultationRequest  # ✅ Use ConsultationRequest
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
                  'date_joined', 'last_login', 'phone', 'profile_image']
    
    def get_full_name(self, obj):
        return obj.get_full_name()

class ProfessionalProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    categories = serializers.SerializerMethodField()
    total_earnings = serializers.SerializerMethodField()
    total_consultations = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    
    class Meta:
        model = ProfessionalProfile
        fields = ['id', 'user', 'hourly_rate', 'rating', 'experience_years', 'bio',
                  'languages', 'is_verified', 'is_online', 'last_seen', 'categories',
                  'total_earnings', 'total_consultations', 'average_rating', 'license_number']
    
    def get_categories(self, obj):
        categories = obj.service_categories.all()
        return [{'id': cat.id, 'name': cat.name} for cat in categories]
    
    def get_total_earnings(self, obj):
        # Calculate total earnings from completed consultations
        total = ConsultationRequest.objects.filter(
            professional=obj,  # ✅ This is ProfessionalProfile, not User
            status='completed'
        ).aggregate(total=Sum('professional_earnings'))['total']
        return total or 0
    
    def get_total_consultations(self, obj):
        return ConsultationRequest.objects.filter(professional=obj).count()
    
    def get_average_rating(self, obj):
        return obj.rating

class ClientProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer()
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

class ConsultationSerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField()
    professional_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ConsultationRequest  # ✅ This is the correct model
        fields = ['id', 'title', 'description', 'status', 'duration_minutes',
                  'total_amount', 'created_at', 'scheduled_start', 'scheduled_end',
                  'completed_at', 'client_name', 'professional_name', 'category_name',
                  'hourly_rate', 'professional_earnings', 'platform_fee']
    
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
        fields = ['id', 'admin_name', 'action', 'description', 'ip_address', 'created_at']
    
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
        fields = ['id', 'name', 'report_type', 'period_start', 'period_end',
                  'file_path', 'status', 'generated_by_name', 'generated_at', 'created_at']
    
    def get_generated_by_name(self, obj):
        return obj.generated_by.get_full_name() if obj.generated_by else None

class ProfessionalVerificationSerializer(serializers.Serializer):
    professional_id = serializers.IntegerField()
    verified = serializers.BooleanField()
    notes = serializers.CharField(required=False, allow_blank=True)

class UserStatusSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    is_active = serializers.BooleanField()