from rest_framework import serializers
from django.utils import timezone
from .models import ServiceCategory, ConsultationRequest
from accounts.models import User, ProfessionalProfile
from accounts.serializers import UserSerializer, ProfessionalProfileSerializer

class ServiceCategorySerializer(serializers.ModelSerializer):
    """Serializer for service categories"""
    
    total_professionals = serializers.SerializerMethodField()
    
    class Meta:
        model = ServiceCategory
        fields = [
            'id', 'name', 'description', 'icon', 'active', 'order', 
            'base_price', 'commission_rate', 'min_duration', 'max_duration',
            'available_24_7', 'total_professionals', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'total_professionals', 'created_at', 'updated_at']
    
    def get_total_professionals(self, obj):
        return ProfessionalProfile.objects.filter(
            specialty=obj.name,
            is_verified=True
        ).count()

class ConsultationRequestSerializer(serializers.ModelSerializer):
    """Base serializer for consultation requests"""
    
    client = UserSerializer(read_only=True)
    professional = ProfessionalProfileSerializer(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = ConsultationRequest
        fields = [
            'id', 'client', 'category', 'category_name', 'professional',
            'status', 'priority', 'title', 'description', 'duration_minutes',
            'created_at', 'matched_at', 'accepted_at', 'completed_at',
            'hourly_rate', 'total_amount', 'time_ago'
        ]
        read_only_fields = [
            'id', 'client', 'created_at', 'matched_at', 'accepted_at', 
            'completed_at', 'time_ago'
        ]
    
    def get_time_ago(self, obj):
        """Get human-readable time difference"""
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff.days > 365:
            years = diff.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"

class CreateConsultationRequestSerializer(serializers.ModelSerializer):
    """Serializer for creating consultation requests"""
    
    class Meta:
        model = ConsultationRequest
        fields = [
            'category', 'title', 'description', 'priority', 
            'duration_minutes', 'hourly_rate'
        ]
        extra_kwargs = {
            'title': {'required': True},
            'description': {'required': False, 'allow_blank': True},
            'priority': {'default': 'medium'},
            'duration_minutes': {'default': 30},
            'hourly_rate': {'required': False}
        }
    
    def validate_category(self, value):
        """Validate category exists and is active"""
        if not value.active:
            raise serializers.ValidationError("Category is not active")
        return value
    
    def validate_duration_minutes(self, value):
        """Validate duration"""
        if value < 15:
            raise serializers.ValidationError("Minimum consultation duration is 15 minutes")
        if value > 240:
            raise serializers.ValidationError("Maximum consultation duration is 4 hours")
        return value
    
    def create(self, validated_data):
        """Create consultation request"""
        # Set client from request context
        validated_data['client'] = self.context['request'].user
        
        # Set hourly rate from category if not provided
        if 'hourly_rate' not in validated_data or not validated_data['hourly_rate']:
            category = validated_data['category']
            validated_data['hourly_rate'] = category.base_price
        
        # Calculate total amount
        duration_hours = validated_data['duration_minutes'] / 60
        validated_data['total_amount'] = float(validated_data['hourly_rate']) * duration_hours
        
        return ConsultationRequest.objects.create(**validated_data)

class ConsultationDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for consultation requests"""
    
    client = UserSerializer(read_only=True)
    professional = ProfessionalProfileSerializer(read_only=True)
    category_detail = ServiceCategorySerializer(source='category', read_only=True)
    estimated_cost = serializers.SerializerMethodField()
    can_be_cancelled = serializers.SerializerMethodField()
    can_be_accepted = serializers.SerializerMethodField()
    can_be_completed = serializers.SerializerMethodField()
    
    class Meta:
        model = ConsultationRequest
        fields = [
            'id', 'client', 'category', 'category_detail', 'professional',
            'status', 'priority', 'title', 'description', 'duration_minutes',
            'hourly_rate', 'total_amount', 'platform_fee', 'professional_earnings',
            'created_at', 'matched_at', 'accepted_at', 'completed_at', 'cancelled_at',
            'estimated_cost', 'can_be_cancelled', 'can_be_accepted', 'can_be_completed'
        ]
        read_only_fields = fields
    
    def get_estimated_cost(self, obj):
        """Calculate estimated cost based on professional's rate"""
        if obj.hourly_rate and obj.duration_minutes:
            hourly_rate = float(obj.hourly_rate)
            duration_hours = obj.duration_minutes / 60
            return float(hourly_rate * duration_hours)
        return 0
    
    def get_can_be_cancelled(self, obj):
        """Check if consultation can be cancelled"""
        user = self.context['request'].user
        
        if user.role == 'client' and obj.client == user:
            return obj.status in ['pending', 'matched', 'accepted', 'scheduled']
        elif user.role == 'professional' and obj.professional and obj.professional.user == user:
            return obj.status in ['matched', 'accepted', 'scheduled']
        elif user.is_staff:
            return True
        return False
    
    def get_can_be_accepted(self, obj):
        """Check if consultation can be accepted by professional"""
        user = self.context['request'].user
        
        if user.role == 'professional' and obj.professional and obj.professional.user == user:
            return obj.status in ['matched', 'scheduled']
        return False
    
    def get_can_be_completed(self, obj):
        """Check if consultation can be marked as completed"""
        user = self.context['request'].user
        
        if user.role == 'professional' and obj.professional and obj.professional.user == user:
            return obj.status in ['accepted', 'in_progress', 'scheduled']
        return False

class ConsultationListSerializer(serializers.ModelSerializer):
    """Serializer for consultation list views"""
    
    client_name = serializers.CharField(source='client.get_full_name', read_only=True)
    professional_name = serializers.CharField(source='professional.user.get_full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = ConsultationRequest
        fields = [
            'id', 'client_name', 'professional_name', 'category_name',
            'status', 'status_display', 'priority', 'title', 'duration_minutes',
            'hourly_rate', 'total_amount', 'created_at', 'time_ago'
        ]
        read_only_fields = fields
    
    def get_time_ago(self, obj):
        """Get human-readable time difference"""
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}h ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}m ago"
        else:
            return "Just now"

class MatchProfessionalSerializer(serializers.Serializer):
    """Serializer for matching professionals"""
    
    consultation_id = serializers.IntegerField()
    professional_id = serializers.IntegerField(required=False)
    
    def validate(self, data):
        consultation_id = data['consultation_id']
        
        try:
            consultation = ConsultationRequest.objects.get(id=consultation_id)
        except ConsultationRequest.DoesNotExist:
            raise serializers.ValidationError("Consultation not found")
        
        if consultation.professional:
            raise serializers.ValidationError("Consultation already has a professional")
        
        data['consultation'] = consultation
        
        # If professional_id is provided, validate it
        if 'professional_id' in data:
            try:
                professional = ProfessionalProfile.objects.get(id=data['professional_id'])
                
                # Check if professional is available
                if not professional.is_online or not professional.is_verified:
                    raise serializers.ValidationError("Professional is not available")
                
                if professional.specialty != consultation.category.name:
                    raise serializers.ValidationError(
                        f"Professional does not specialize in {consultation.category.name}"
                    )
                
                data['professional'] = professional
            except ProfessionalProfile.DoesNotExist:
                raise serializers.ValidationError("Professional not found")
        
        return data

class QuickConsultationSerializer(serializers.ModelSerializer):
    """Serializer for quick consultation creation"""
    
    class Meta:
        model = ConsultationRequest
        fields = ['category', 'title', 'description', 'priority', 'duration_minutes']
        extra_kwargs = {
            'title': {'default': 'Quick Consultation'},
            'description': {'default': 'Quick consultation request'},
            'priority': {'default': 'medium'},
            'duration_minutes': {'default': 30}
        }
    
    def create(self, validated_data):
        """Create quick consultation"""
        # Set client from request context
        validated_data['client'] = self.context['request'].user
        
        # Set hourly rate from category
        category = validated_data['category']
        validated_data['hourly_rate'] = category.base_price
        
        # Calculate total amount
        duration_hours = validated_data['duration_minutes'] / 60
        validated_data['total_amount'] = category.base_price * duration_hours
        
        consultation = ConsultationRequest.objects.create(**validated_data)
        
        # Try to match immediately
        if hasattr(self.context.get('request'), 'user'):
            # This would trigger the matching logic
            pass
        
        return consultation