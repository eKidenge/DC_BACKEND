from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from rest_framework import status
from .models import User as CustomUser, ProfessionalProfile, ClientProfile
from .serializers import UserSerializer, RegisterSerializer

# ADD THIS IMPORT
from categories.models import ServiceCategory

class RoleSelectionView(APIView):
    """Role selection page - for reference only (React handles this)"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        # This would return HTML, but React handles it
        # You can remove this view if React handles role selection
        return Response({
            'message': 'Role selection handled by React frontend',
            'frontend_url': 'http://localhost:3000/role-selection'
        })

class LoginView(APIView):
    """Login user and return token - MODIFIED to auto-detect role"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        # REMOVED: role parameter - we'll auto-detect it
        
        if not username or not password:
            return Response(
                {'error': 'Username and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Authenticate user
        user = authenticate(username=username, password=password)
        
        if user:
            # Get the user's role from the database (auto-detect)
            user_role = user.role  # This comes from your User model
            
            # Create or get token
            token, created = Token.objects.get_or_create(user=user)
            
            # Prepare user data
            user_data = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user_role,
                'full_name': f"{user.first_name} {user.last_name}".strip() or user.username
            }
            
            # Add profile-specific data
            try:
                if user_role == 'professional':
                    profile = user.professional_profile
                    user_data['profile'] = {
                        'specialty': profile.specialty,
                        'hourly_rate': str(profile.hourly_rate),
                        'rating': profile.rating,
                        'experience_years': profile.experience_years,
                        'is_verified': profile.is_verified,
                        'is_online': profile.is_online,
                        'professional_id': profile.id
                    }
                elif user_role == 'client':
                    profile = user.client_profile
                    user_data['profile'] = {
                        'date_of_birth': str(profile.date_of_birth) if profile.date_of_birth else None,
                        'emergency_contact': profile.emergency_contact,
                        'client_id': profile.id
                    }
            except (ProfessionalProfile.DoesNotExist, ClientProfile.DoesNotExist):
                # Profile doesn't exist yet, which is fine
                pass
            
            return Response({
                'token': token.key,
                'user': user_data,
                'message': 'Login successful'
            })
        
        return Response(
            {'error': 'Invalid username or password'},
            status=status.HTTP_400_BAD_REQUEST
        )

class LogoutView(APIView):
    """Logout user"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # Delete the token
        Token.objects.filter(user=request.user).delete()
        logout(request)
        
        return Response({'message': 'Successfully logged out'})

class RegisterView(APIView):
    """Register new user"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            
            # Create profile based on role
            if user.role == 'professional':
                ProfessionalProfile.objects.create(
                    user=user,
                    specialty=request.data.get('specialty', 'legal'),
                    hourly_rate=request.data.get('hourly_rate', 50.00)
                )
            elif user.role == 'client':
                ClientProfile.objects.create(user=user)
            
            # Generate token for auto-login
            token = Token.objects.create(user=user)
            
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data,
                'message': 'Registration successful'
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CurrentUserView(APIView):
    """Get current authenticated user info"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        data = UserSerializer(user).data
        
        # Add profile data based on role
        if user.role == 'professional':
            try:
                profile = user.professional_profile
                data['profile'] = {
                    'specialty': profile.specialty,
                    'hourly_rate': str(profile.hourly_rate),
                    'rating': profile.rating,
                    'experience_years': profile.experience_years,
                    'is_verified': profile.is_verified,
                    'is_online': profile.is_online
                }
            except ProfessionalProfile.DoesNotExist:
                pass
        elif user.role == 'client':
            try:
                profile = user.client_profile
                data['profile'] = {
                    'date_of_birth': str(profile.date_of_birth) if profile.date_of_birth else None,
                    'emergency_contact': profile.emergency_contact
                }
            except ClientProfile.DoesNotExist:
                pass
        
        return Response(data)

# ADD THIS VIEW FOR SERVICE CATEGORIES
class ServiceCategoriesView(APIView):
    """Get all active service categories"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        try:
            # Get only active categories, ordered by 'order' field
            categories = ServiceCategory.objects.filter(active=True).order_by('order')
            
            categories_data = []
            for category in categories:
                categories_data.append({
                    'id': category.id,
                    'name': category.name,
                    'description': category.description,
                    'icon': category.icon,
                    'order': category.order,
                    'base_price': str(category.base_price),
                    'commission_rate': str(category.commission_rate),
                    'available_24_7': category.available_24_7,
                    'created_at': category.created_at.isoformat() if category.created_at else None
                })
            
            return Response({
                'count': len(categories_data),
                'categories': categories_data
            })
            
        except Exception as e:
            return Response(
                {'error': f'Error fetching categories: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
