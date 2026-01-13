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
from django.conf import settings  # Add this import

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


# MORE TARGETED DEBUG
# Add this new view to accounts/views.py
import time
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.apps import apps
import json

# Persistent storage that survives between requests
_important_models = ['User', 'ConsultationRequest', 'MpesaTransaction', 'MpesaPaymentRequest']
_refresh_history = []

@csrf_exempt
def detect_refresh(request):
    """Specifically track if database is being reset"""
    action = request.GET.get('action', '')
    
    if action == 'clear':
        _refresh_history.clear()
        return JsonResponse({'status': 'history cleared'})
    
    # Track key models
    current_counts = {}
    for model_name in _important_models:
        try:
            model = apps.get_model(model_name.split('.')[-1]) if '.' in model_name else apps.get_model('*', model_name)
            current_counts[model_name] = model.objects.count()
        except:
            current_counts[model_name] = None
    
    # Check if this looks like a refresh (counts dropped significantly)
    is_refresh = False
    refresh_details = {}
    
    if _refresh_history:
        last_counts = _refresh_history[-1]['counts']
        for model_name, current_count in current_counts.items():
            if model_name in last_counts and last_counts[model_name] is not None:
                last_count = last_counts[model_name]
                if current_count < last_count * 0.5:  # Lost more than 50%
                    is_refresh = True
                    refresh_details[model_name] = {
                        'from': last_count,
                        'to': current_count,
                        'lost': last_count - current_count
                    }
    
    # Record this check
    check_record = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'unix_time': time.time(),
        'counts': current_counts,
        'is_refresh': is_refresh,
        'refresh_details': refresh_details,
        'source_ip': request.META.get('REMOTE_ADDR', 'unknown')
    }
    
    _refresh_history.append(check_record)
    
    # Keep only last 100 records
    if len(_refresh_history) > 100:
        _refresh_history.pop(0)
    
    # Calculate stats
    if len(_refresh_history) > 1:
        first = _refresh_history[0]
        last = _refresh_history[-1]
        time_span = last['unix_time'] - first['unix_time']
        checks_per_hour = len(_refresh_history) / (time_span / 3600) if time_span > 0 else 0
    else:
        checks_per_hour = 0
    
    # Check for any resets in history
    total_refreshes = sum(1 for r in _refresh_history if r['is_refresh'])
    
    return JsonResponse({
        'current': check_record,
        'summary': {
            'total_checks': len(_refresh_history),
            'total_refreshes_detected': total_refreshes,
            'checks_per_hour': f"{checks_per_hour:.1f}",
            'monitoring_since': _refresh_history[0]['timestamp'] if _refresh_history else 'just started'
        },
        'recent_history': _refresh_history[-5:],  # Last 5 checks
        'all_refreshes': [r for r in _refresh_history if r['is_refresh']]
    })

@csrf_exempt  
def check_data_health(request):
    """Check if data looks consistent (not being truncated)"""
    models_to_check = [
        'accounts.User',
        'categories.ConsultationRequest', 
        'payments.MpesaTransaction',
        'payments.MpesaPaymentRequest'
    ]
    
    results = []
    
    for model_path in models_to_check:
        try:
            app_label, model_name = model_path.split('.')
            model = apps.get_model(app_label, model_name)
            
            total = model.objects.count()
            
            # Check date range
            if hasattr(model, 'created_at'):
                dates = model.objects.aggregate(
                    oldest=models.Min('created_at'),
                    newest=models.Max('created_at')
                )
                date_info = dates
            else:
                date_info = {'oldest': 'N/A', 'newest': 'N/A'}
            
            # Check IDs are sequential (not reset)
            if total > 0:
                ids = list(model.objects.order_by('id').values_list('id', flat=True)[:100])
                min_id = min(ids)
                max_id = max(ids)
                gap_ratio = (max_id - min_id + 1) / total if total > 0 else 1
                has_gaps = gap_ratio > 1.2  # More than 20% gaps suggests deletions
            else:
                has_gaps = False
                min_id = max_id = 0
            
            results.append({
                'model': model_name,
                'count': total,
                'date_range': date_info,
                'id_range': f"{min_id}-{max_id}",
                'has_id_gaps': has_gaps,
                'health': 'GOOD' if total > 0 and not has_gaps else 'SUSPICIOUS'
            })
            
        except Exception as e:
            results.append({
                'model': model_path,
                'error': str(e),
                'health': 'ERROR'
            })
    
    return JsonResponse({
        'data_health_check': results,
        'check_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'note': 'Check for: 1) Count drops, 2) Date resets, 3) ID gaps'
    })
# =========================================================================
# system_info - ADD THIS FUNCTION (it's missing!)
# =========================================================================

@csrf_exempt
def system_info(request):
    """Check system and database info - THIS WILL REVEAL THE PROBLEM"""
    import os
    import django
    from django.db import connection
    from django.conf import settings
    
    # Get database info - convert Path to string
    db_settings = connection.settings_dict
    db_name = str(db_settings['NAME'])  # Convert PosixPath to string
    
    db_info = {
        'engine': db_settings['ENGINE'],
        'name': db_name,  # Use string version
        'raw_name': str(db_settings['NAME']),  # Also show as string
        'is_sqlite': 'sqlite' in db_settings['ENGINE'].lower()
    }
    
    # Critical check: If using SQLite on Render
    if db_info['is_sqlite']:
        db_info['warning'] = '⚠️ SQLITE DETECTED - On Render free tier, SQLite resets on every deploy!'
        
        # Check if file exists
        file_exists = os.path.exists(db_name)
        db_info['file_exists'] = file_exists
        
        if file_exists:
            size_bytes = os.path.getsize(db_name)
            db_info['file_size'] = f"{size_bytes:,} bytes ({size_bytes/1024/1024:.2f} MB)"
            
            # Check file modification time
            mod_time = os.path.getmtime(db_name)
            db_info['last_modified'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mod_time))
            db_info['seconds_since_mod'] = int(time.time() - mod_time)
        else:
            db_info['file_size'] = 'File not found - database is ephemeral'
            db_info['note'] = 'SQLite file gets recreated on each deploy on Render free tier'
    
    # Check environment
    is_render = 'RENDER' in os.environ
    
    return JsonResponse({
        'database': db_info,
        'environment': {
            'is_render': is_render,
            'debug_mode': settings.DEBUG,
            'service_type': os.environ.get('RENDER_SERVICE_TYPE', 'unknown'),
            'deploy_id': os.environ.get('RENDER_GIT_COMMIT', 'unknown')[:8] if 'RENDER_GIT_COMMIT' in os.environ else 'unknown'
        },
        'django_version': django.get_version(),
        'current_time': time.strftime('%Y-%m-%d %H:%M:%S UTC'),
        'timezone': settings.TIME_ZONE,
        'diagnosis': 'If "is_sqlite" is true AND "seconds_since_mod" is low, database is resetting on deploys',
        'solution': '1) Use PostgreSQL add-on OR 2) Switch to a different hosting with persistent storage'
    })
