from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, ProfessionalProfile, ClientProfile
from django.contrib.auth.hashers import check_password

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'phone']
        read_only_fields = ['id', 'role']

class LoginSerializer(serializers.Serializer):
    """Serializer for user login - NO ROLE FIELD REQUIRED"""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            raise serializers.ValidationError("Username and password are required")
        
        # Try to authenticate
        user = authenticate(username=username, password=password)
        
        if not user:
            # If authenticate fails, try manual check (useful for custom user models)
            try:
                user = User.objects.get(username=username)
                if not check_password(password, user.password):
                    raise serializers.ValidationError("Invalid username or password")
            except User.DoesNotExist:
                raise serializers.ValidationError("Invalid username or password")
        
        data['user'] = user
        return data

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)
    
    # Professional specific fields (optional)
    specialty = serializers.CharField(write_only=True, required=False)
    hourly_rate = serializers.DecimalField(write_only=True, max_digits=10, decimal_places=2, required=False)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'phone', 'role',
            'specialty', 'hourly_rate'
        ]
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'email': {'required': True}
        }
    
    def validate(self, data):
        # Check passwords match
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Passwords do not match")
        
        # Validate role-specific fields
        if data['role'] == 'professional':
            if not data.get('specialty'):
                raise serializers.ValidationError("Specialty is required for professionals")
            if not data.get('hourly_rate'):
                raise serializers.ValidationError("Hourly rate is required for professionals")
        
        return data
    
    def create(self, validated_data):
        # Remove extra fields
        password = validated_data.pop('password')
        validated_data.pop('password_confirm')
        specialty = validated_data.pop('specialty', None)
        hourly_rate = validated_data.pop('hourly_rate', None)
        
        # Create user
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        
        return user

class ProfessionalProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = ProfessionalProfile
        fields = ['id', 'user', 'specialty', 'hourly_rate', 'rating', 
                  'experience_years', 'languages', 'is_verified', 'is_online']
