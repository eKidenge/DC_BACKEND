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


# ADDED TO MONITOR DB JAN 13TH
# Replace your existing debug_db_status function with this enhanced version
import time
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.apps import apps
from django.db import connection

# Global storage with persistent tracking across deploys
_db_history = []
_MAX_HISTORY = 50
_last_check_time = None

@csrf_exempt
def debug_db_status(request):
    """Enhanced debug endpoint to monitor database state"""
    global _last_check_time
    
    # Get action from query params
    action = request.GET.get('action', '')
    
    if action == 'reset':
        _db_history.clear()
        return JsonResponse({'status': 'history cleared'})
    
    if action == 'full':
        # Return detailed info about each model
        return get_full_diagnostic()
    
    # Get current counts for all models
    models = apps.get_models()
    current_state = {}
    current_time = time.time()
    
    # Track time since last check
    time_since_last = None
    if _last_check_time:
        time_since_last = current_time - _last_check_time
    _last_check_time = current_time
    
    # Get detailed counts
    for model in models:
        try:
            count = model.objects.count()
            current_state[model.__name__] = count
            
            # For models that have data, check the latest record
            if count > 0:
                try:
                    latest = model.objects.order_by('-id').first()
                    if latest and hasattr(latest, 'created_at'):
                        current_state[f"{model.__name__}_latest"] = str(latest.created_at)
                except:
                    pass
                    
        except Exception as e:
            current_state[model.__name__] = f'ERROR: {str(e)}'
    
    # Check SQL queries executed
    queries = []
    if len(connection.queries) > 0:
        queries = [q['sql'][:100] for q in connection.queries[-10:]]
    
    # Store in history
    snapshot = {
        'timestamp': time.strftime('%H:%M:%S'),
        'unix_time': current_time,
        'state': current_state,
        'queries': queries[:3]  # Store last 3 queries
    }
    
    _db_history.append(snapshot)
    if len(_db_history) > _MAX_HISTORY:
        _db_history.pop(0)
    
    # Find changes since ANY previous snapshot (not just last one)
    all_changes = []
    if len(_db_history) > 1:
        # Compare with all previous snapshots
        for i in range(len(_db_history) - 1):
            prev = _db_history[i]['state']
            for model_name, count in current_state.items():
                if not model_name.endswith('_latest') and model_name in prev:
                    prev_count = prev[model_name]
                    if isinstance(prev_count, int) and isinstance(count, int):
                        if prev_count != count:
                            change_found = {
                                'model': model_name,
                                'from': prev_count,
                                'to': count,
                                'when': _db_history[i]['timestamp'],
                                'ago': f"{len(_db_history) - 1 - i} checks ago"
                            }
                            # Only add if not already recorded
                            if not any(c['model'] == model_name and c['from'] == prev_count and c['to'] == count 
                                     for c in all_changes):
                                all_changes.append(change_found)
    
    return JsonResponse({
        'current_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'time_since_last_check': f"{time_since_last:.1f}s" if time_since_last else 'first check',
        'current_counts': {k: v for k, v in current_state.items() if not k.endswith('_latest')},
        'all_changes_detected': all_changes,
        'recent_queries': queries[:5],
        'history_size': len(_db_history),
        'check_count': len(_db_history)
    })

def get_full_diagnostic():
    """Return detailed diagnostic info"""
    models = apps.get_models()
    detailed_info = []
    
    for model in models:
        try:
            count = model.objects.count()
            info = {
                'model': model.__name__,
                'count': count,
                'app': model._meta.app_label,
                'table': model._meta.db_table,
            }
            
            if count > 0:
                # Get sample of recent records
                try:
                    recent = list(model.objects.order_by('-id')[:3].values('id', 'created_at'))
                    info['recent'] = recent
                except:
                    info['recent'] = 'N/A'
            
            detailed_info.append(info)
        except Exception as e:
            detailed_info.append({
                'model': model.__name__,
                'error': str(e)
            })
    
    return JsonResponse({
        'detailed_models': detailed_info,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    })
