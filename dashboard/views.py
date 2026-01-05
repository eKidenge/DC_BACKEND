from django.shortcuts import render
from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta, datetime
import json

# ============================================
# FIXED IMPORTS - No duplicates
# ============================================
from accounts.models import User, ProfessionalProfile as AccountsProfessionalProfile
from .models import (
    ProfessionalAvailability, ProfessionalStat,
    IncomingCall, ProfessionalNotification, ProfessionalCalendar, 
    CallHistory, CallRequest  # <-- CallRequest is already here
)

# FIXED: Remove duplicate import of the models above

# ============================================
# FIXED SERIALIZER IMPORTS - Add CallRequestSerializer
# ============================================
from .serializers import (
    AccountsProfessionalProfileSerializer, ProfessionalAvailabilitySerializer,
    ProfessionalStatSerializer, IncomingCallSerializer,
    ProfessionalNotificationSerializer, ProfessionalCalendarSerializer,
    CallHistorySerializer,
    CallRequestSerializer  # <-- ADD THIS LINE
)

from django.db.models import Sum, Count, Avg, Q
from django.core.cache import cache

# ============================================
# UPDATED VIEWSETS
# ============================================

class ProfessionalProfileViewSet(viewsets.ModelViewSet):
    # CHANGED: Use AccountsProfessionalProfileSerializer
    serializer_class = AccountsProfessionalProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # CHANGED: Use AccountsProfessionalProfile
        return AccountsProfessionalProfile.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def toggle_online(self, request):
        """Toggle professional's online status"""
        try:
            # CHANGED: Use AccountsProfessionalProfile
            profile = AccountsProfessionalProfile.objects.get(user=request.user)
            profile.is_online = not profile.is_online
            profile.save()
            
            # Update availability if exists
            try:
                # CHANGED: Use dashboard_availability
                availability = profile.dashboard_availability
                availability.is_available = profile.is_online
                availability.save()
            except ProfessionalAvailability.DoesNotExist:
                pass
            
            return Response({
                'status': 'success',
                'is_online': profile.is_online,
                'message': f'You are now {"online" if profile.is_online else "offline"}'
            })
        except AccountsProfessionalProfile.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Professional profile not found'
            }, status=status.HTTP_404_NOT_FOUND)

class ProfessionalAvailabilityViewSet(viewsets.ModelViewSet):
    serializer_class = ProfessionalAvailabilitySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # CHANGED: Get profile from accounts
        profile = AccountsProfessionalProfile.objects.get(user=self.request.user)
        return ProfessionalAvailability.objects.filter(professional=profile)
    
    @action(detail=False, methods=['post'])
    def update_settings(self, request):
        """Update availability settings"""
        try:
            # CHANGED: Get profile from accounts
            profile = AccountsProfessionalProfile.objects.get(user=request.user)
            availability, created = ProfessionalAvailability.objects.get_or_create(
                professional=profile
            )
            
            data = request.data
            if 'auto_accept_calls' in data:
                availability.auto_accept_calls = data['auto_accept_calls']
            if 'max_daily_sessions' in data:
                availability.max_daily_sessions = data['max_daily_sessions']
            if 'working_hours_start' in data:
                availability.working_hours_start = data['working_hours_start']
            if 'working_hours_end' in data:
                availability.working_hours_end = data['working_hours_end']
            if 'break_duration_minutes' in data:
                availability.break_duration_minutes = data['break_duration_minutes']
            if 'break_start_time' in data:
                availability.break_start_time = data['break_start_time']
            if 'buffer_minutes' in data:
                availability.buffer_minutes = data['buffer_minutes']
            if 'available_days' in data:
                availability.available_days = data['available_days']
            if 'timezone' in data:
                availability.timezone = data['timezone']
            
            availability.save()
            serializer = self.get_serializer(availability)
            return Response(serializer.data)
        except AccountsProfessionalProfile.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Professional profile not found'
            }, status=status.HTTP_404_NOT_FOUND)

class ProfessionalStatViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProfessionalStatSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # CHANGED: Get profile from accounts
        profile = AccountsProfessionalProfile.objects.get(user=self.request.user)
        return ProfessionalStat.objects.filter(professional=profile)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get professional stats summary"""
        try:
            # CHANGED: Get profile from accounts
            profile = AccountsProfessionalProfile.objects.get(user=request.user)
            stats, created = ProfessionalStat.objects.get_or_create(professional=profile)
            
            # Calculate real-time stats if needed
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Update today's stats from call history
            today_calls = CallHistory.objects.filter(
                professional=profile,
                start_time__gte=today_start
            )
            
            stats.today_earnings = today_calls.aggregate(total=Sum('earnings'))['total'] or 0
            stats.today_consultations = today_calls.count()
            stats.today_hours = (today_calls.aggregate(total=Sum('duration_seconds'))['total'] or 0) / 3600
            
            # Update weekly stats
            week_start = today_start - timedelta(days=today_start.weekday())
            week_calls = CallHistory.objects.filter(
                professional=profile,
                start_time__gte=week_start
            )
            stats.week_earnings = week_calls.aggregate(total=Sum('earnings'))['total'] or 0
            stats.week_consultations = week_calls.count()
            stats.week_hours = (week_calls.aggregate(total=Sum('duration_seconds'))['total'] or 0) / 3600
            
            stats.save()
            serializer = self.get_serializer(stats)
            return Response(serializer.data)
        except AccountsProfessionalProfile.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Professional profile not found'
            }, status=status.HTTP_404_NOT_FOUND)

class IncomingCallViewSet(viewsets.ModelViewSet):
    serializer_class = IncomingCallSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # CHANGED: Get profile from accounts
        profile = AccountsProfessionalProfile.objects.get(user=self.request.user)
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status', None)
        queryset = IncomingCall.objects.filter(professional=profile)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Accept an incoming call"""
        try:
            # CHANGED: Get profile from accounts
            profile = AccountsProfessionalProfile.objects.get(user=request.user)
            incoming_call = self.get_object()
            
            # Check if call is still pending/ringing
            if incoming_call.status not in ['pending', 'ringing']:
                return Response({
                    'status': 'error',
                    'message': 'Call is no longer available'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if call has expired
            if timezone.now() > incoming_call.expires_at:
                incoming_call.status = 'expired'
                incoming_call.save()
                return Response({
                    'status': 'error',
                    'message': 'Call has expired'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Accept the call
            incoming_call.status = 'accepted'
            incoming_call.accepted_at = timezone.now()
            incoming_call.responded_at = timezone.now()
            incoming_call.save()
            
            # Create call history entry
            CallHistory.objects.create(
                professional=profile,
                client_name=incoming_call.client_name,
                earnings=incoming_call.estimated_earnings,
                start_time=timezone.now(),
                end_time=timezone.now() + timedelta(minutes=incoming_call.duration)
            )
            
            return Response({
                'status': 'success',
                'message': 'Call accepted successfully',
                'call_id': incoming_call.id,
                'consultation_id': incoming_call.consultation.id if incoming_call.consultation else None
            })
        except IncomingCall.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Call not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject an incoming call"""
        try:
            incoming_call = self.get_object()
            
            # Check if call is still pending/ringing
            if incoming_call.status not in ['pending', 'ringing']:
                return Response({
                    'status': 'error',
                    'message': 'Call is no longer available'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Reject the call
            incoming_call.status = 'rejected'
            incoming_call.rejected_at = timezone.now()
            incoming_call.responded_at = timezone.now()
            incoming_call.rejection_reason = request.data.get('reason', 'No reason provided')
            incoming_call.save()
            
            return Response({
                'status': 'success',
                'message': 'Call rejected'
            })
        except IncomingCall.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Call not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update call status"""
        try:
            incoming_call = self.get_object()
            new_status = request.data.get('status')
            
            if new_status in dict(IncomingCall.STATUS_CHOICES):
                incoming_call.status = new_status
                
                if new_status == 'ringing':
                    incoming_call.expires_at = timezone.now() + timedelta(seconds=60)
                
                incoming_call.save()
                
                return Response({
                    'status': 'success',
                    'message': f'Call status updated to {new_status}'
                })
            else:
                return Response({
                    'status': 'error',
                    'message': 'Invalid status'
                }, status=status.HTTP_400_BAD_REQUEST)
        except IncomingCall.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Call not found'
            }, status=status.HTTP_404_NOT_FOUND)

class ProfessionalNotificationViewSet(viewsets.ModelViewSet):
    serializer_class = ProfessionalNotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Get unread notifications by default
        is_read = self.request.query_params.get('is_read', 'false').lower() == 'true'
        return ProfessionalNotification.objects.filter(
            user=self.request.user,
            is_read=is_read
        ).order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a notification as read"""
        try:
            notification = self.get_object()
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
            
            return Response({
                'status': 'success',
                'message': 'Notification marked as read'
            })
        except ProfessionalNotification.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Notification not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        notifications = ProfessionalNotification.objects.filter(
            user=request.user,
            is_read=False
        )
        updated = notifications.update(is_read=True, read_at=timezone.now())
        
        return Response({
            'status': 'success',
            'message': f'{updated} notifications marked as read'
        })

class ProfessionalCalendarViewSet(viewsets.ModelViewSet):
    serializer_class = ProfessionalCalendarSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # CHANGED: Get profile from accounts
        profile = AccountsProfessionalProfile.objects.get(user=self.request.user)
        
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        queryset = ProfessionalCalendar.objects.filter(professional=profile)
        
        if start_date:
            start_date = datetime.fromisoformat(start_date)
            queryset = queryset.filter(start_time__gte=start_date)
        
        if end_date:
            end_date = datetime.fromisoformat(end_date)
            queryset = queryset.filter(end_time__lte=end_date)
        
        return queryset.order_by('start_time')
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming events"""
        try:
            # CHANGED: Get profile from accounts
            profile = AccountsProfessionalProfile.objects.get(user=request.user)
            now = timezone.now()
            
            # Get events for next 7 days
            upcoming_events = ProfessionalCalendar.objects.filter(
                professional=profile,
                start_time__gte=now,
                end_time__lte=now + timedelta(days=7),
                is_cancelled=False
            ).order_by('start_time')[:10]  # Limit to 10 events
            
            serializer = self.get_serializer(upcoming_events, many=True)
            return Response(serializer.data)
        except AccountsProfessionalProfile.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Professional profile not found'
            }, status=status.HTTP_404_NOT_FOUND)

class CallHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CallHistorySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # CHANGED: Get profile from accounts
        profile = AccountsProfessionalProfile.objects.get(user=self.request.user)
        
        # Filter by date if provided
        date_filter = self.request.query_params.get('date', None)
        queryset = CallHistory.objects.filter(professional=profile)
        
        if date_filter:
            date = datetime.fromisoformat(date_filter).date()
            queryset = queryset.filter(start_time__date=date)
        
        return queryset.order_by('-start_time')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """Get dashboard summary data"""
    try:
        # CHANGED: Get profile from accounts
        profile = AccountsProfessionalProfile.objects.get(user=request.user)
        
        # Get stats
        stats, _ = ProfessionalStat.objects.get_or_create(professional=profile)
        
        # Get pending calls
        pending_calls = IncomingCall.objects.filter(
            professional=profile,
            status__in=['pending', 'ringing']
        ).count()
        
        # Get unread notifications
        unread_notifications = ProfessionalNotification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        
        # Get today's earnings
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_earnings = CallHistory.objects.filter(
            professional=profile,
            start_time__gte=today_start
        ).aggregate(total=Sum('earnings'))['total'] or 0
        
        return Response({
            'profile': AccountsProfessionalProfileSerializer(profile).data,
            'stats': ProfessionalStatSerializer(stats).data,
            'pending_calls': pending_calls,
            'unread_notifications': unread_notifications,
            'today_earnings': float(today_earnings),
            'is_online': profile.is_online,
            'timestamp': timezone.now().isoformat()
        })
    except AccountsProfessionalProfile.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Professional profile not found'
        }, status=status.HTTP_404_NOT_FOUND)

# ============================================
# ADDITIONAL UTILITY VIEWS
# ============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_professional_status(request):
    """Check if user has a professional profile"""
    try:
        profile = AccountsProfessionalProfile.objects.get(user=request.user)
        return Response({
            'is_professional': True,
            'profile_id': profile.id,
            'is_online': profile.is_online,
            'is_verified': profile.is_verified
        })
    except AccountsProfessionalProfile.DoesNotExist:
        return Response({
            'is_professional': False,
            'message': 'User does not have a professional profile'
        })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_professional_profile(request):
    """Update professional profile (partial update)"""
    try:
        profile = AccountsProfessionalProfile.objects.get(user=request.user)
        
        # Allowed fields to update
        allowed_fields = ['hourly_rate', 'bio', 'experience_years', 'languages']
        
        for field in allowed_fields:
            if field in request.data:
                setattr(profile, field, request.data[field])
        
        profile.save()
        
        return Response({
            'status': 'success',
            'message': 'Profile updated successfully',
            'profile': AccountsProfessionalProfileSerializer(profile).data
        })
    except AccountsProfessionalProfile.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Professional profile not found'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def professional_analytics(request):
    """Get professional analytics data"""
    try:
        profile = AccountsProfessionalProfile.objects.get(user=request.user)
        
        # Get stats
        stats, _ = ProfessionalStat.objects.get_or_create(professional=profile)
        
        # Calculate monthly earnings trend (last 6 months)
        six_months_ago = timezone.now() - timedelta(days=180)
        monthly_calls = CallHistory.objects.filter(
            professional=profile,
            start_time__gte=six_months_ago
        ).extra({
            'month': "strftime('%%Y-%%m', start_time)"
        }).values('month').annotate(
            total_earnings=Sum('earnings'),
            call_count=Count('id')
        ).order_by('month')
        
        # Get top categories
        from categories.models import ServiceCategory
        categories = profile.service_categories.all()
        
        return Response({
            'stats': ProfessionalStatSerializer(stats).data,
            'monthly_earnings': list(monthly_calls),
            'categories': [
                {
                    'id': cat.id,
                    'name': cat.name,
                    'description': cat.description
                } for cat in categories
            ],
            'total_earnings': float(stats.today_earnings + stats.week_earnings + stats.month_earnings),
            'average_rating': float(profile.rating)
        })
    except AccountsProfessionalProfile.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Professional profile not found'
        }, status=status.HTTP_404_NOT_FOUND)


# JUST ADDED TO REQUEST CALL BY CLIENTS TO PROFESSIONALS
# ============================================
# CALL REQUEST VIEWS (ADD THESE TO YOUR EXISTING VIEWS.PY)
# ============================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_call_request(request):
    """Create a new call request from client to professional"""
    try:
        data = request.data
        
        # Get professional
        professional_id = data.get('professional')
        if not professional_id:
            return Response(
                {'error': 'Professional ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            professional = AccountsProfessionalProfile.objects.get(id=professional_id)
        except AccountsProfessionalProfile.DoesNotExist:
            return Response(
                {'error': 'Professional not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create call request
        call_request = CallRequest.objects.create(
            professional=professional,
            client_id=data.get('client_id'),
            client_name=data.get('client_name'),
            client_phone=data.get('client_phone', ''),
            call_type=data.get('call_type', 'video'),
            duration=data.get('duration', 30),
            consultation_id=data.get('consultation_id'),
            amount=data.get('amount', 0),
            category=data.get('category', 'Consultation'),
            status='pending'
        )
        
        # Create notification for professional
        ProfessionalNotification.objects.create(
            user=professional.user,
            notification_type='incoming_call',
            title=f'Incoming Call from {call_request.client_name}',
            message=f'{call_request.client_name} is requesting a {call_request.get_call_type_display()} consultation.',
            data={
                'call_request_id': call_request.id,
                'client_name': call_request.client_name,
                'call_type': call_request.call_type,
                'duration': call_request.duration,
                'amount': float(call_request.amount),
                'category': call_request.category,
                'room_id': call_request.room_id
            },
            priority=3
        )
        
        return Response({
            'id': call_request.id,
            'status': call_request.status,
            'room_id': call_request.room_id,
            'message': 'Call request created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_call_request(request, pk):
    """Get call request details"""
    try:
        call_request = CallRequest.objects.get(id=pk)
        return Response({
            'id': call_request.id,
            'status': call_request.status,
            'professional_id': call_request.professional.id,
            'client_name': call_request.client_name,
            'call_type': call_request.call_type,
            'room_id': call_request.room_id,
            'expires_at': call_request.expires_at
        })
    except CallRequest.DoesNotExist:
        return Response(
            {'error': 'Call request not found'},
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_call_status(request, pk):
    """Update call request status"""
    try:
        call_request = CallRequest.objects.get(id=pk)
        new_status = request.data.get('status')
        
        if not new_status:
            return Response(
                {'error': 'Status is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        call_request.status = new_status
        
        if new_status == 'accepted':
            call_request.accepted_at = timezone.now()
        elif new_status == 'rejected':
            call_request.rejected_at = timezone.now()
        
        call_request.save()
        
        return Response({
            'id': call_request.id,
            'status': call_request.status,
            'message': f'Call status updated to {new_status}'
        })
    except CallRequest.DoesNotExist:
        return Response(
            {'error': 'Call request not found'},
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_call_request(request, pk):
    """Cancel a call request"""
    try:
        call_request = CallRequest.objects.get(id=pk)
        call_request.status = 'cancelled'
        call_request.save()
        
        return Response({
            'id': call_request.id,
            'status': call_request.status,
            'message': 'Call request cancelled'
        })
    except CallRequest.DoesNotExist:
        return Response(
            {'error': 'Call request not found'},
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def professional_pending_calls(request):
    """Get pending calls for professional"""
    try:
        user = request.user
        professional = AccountsProfessionalProfile.objects.get(user=user)
        
        pending_calls = CallRequest.objects.filter(
            professional=professional,
            status__in=['pending', 'ringing']
        ).order_by('-created_at')
        
        calls_data = []
        for call in pending_calls:
            calls_data.append({
                'id': call.id,
                'client_name': call.client_name,
                'call_type': call.call_type,
                'duration': call.duration,
                'amount': float(call.amount),
                'created_at': call.created_at,
                'expires_at': call.expires_at
            })
        
        return Response({
            'pending_calls': calls_data,
            'count': len(calls_data)
        })
    except AccountsProfessionalProfile.DoesNotExist:
        return Response(
            {'error': 'Professional profile not found'},
            status=status.HTTP_404_NOT_FOUND
        )