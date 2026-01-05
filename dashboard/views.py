from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta, datetime
import json

# ============================================
# IMPORTS
# ============================================
from accounts.models import User, ProfessionalProfile as AccountsProfessionalProfile
from .models import (
    ProfessionalAvailability, ProfessionalStat,
    IncomingCall, ProfessionalNotification, ProfessionalCalendar, 
    CallHistory, CallRequest
)
from .serializers import (
    AccountsProfessionalProfileSerializer, ProfessionalAvailabilitySerializer,
    ProfessionalStatSerializer, IncomingCallSerializer,
    ProfessionalNotificationSerializer, ProfessionalCalendarSerializer,
    CallHistorySerializer, CallRequestSerializer
)

from django.db.models import Sum, Count, Avg, Q
from django.core.cache import cache

# ============================================
# VIEWSETS FOR YOUR ROUTER
# ============================================

class ProfessionalProfileViewSet(viewsets.ModelViewSet):
    serializer_class = AccountsProfessionalProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return AccountsProfessionalProfile.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def toggle_online(self, request):
        """Toggle professional's online status"""
        try:
            profile = AccountsProfessionalProfile.objects.get(user=request.user)
            profile.is_online = not profile.is_online
            profile.save()
            
            # Update availability if exists
            try:
                availability = ProfessionalAvailability.objects.get(professional=profile)
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
        profile = AccountsProfessionalProfile.objects.get(user=self.request.user)
        return ProfessionalAvailability.objects.filter(professional=profile)
    
    @action(detail=False, methods=['post'])
    def update_settings(self, request):
        """Update availability settings"""
        try:
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
        profile = AccountsProfessionalProfile.objects.get(user=self.request.user)
        return ProfessionalStat.objects.filter(professional=profile)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get professional stats summary"""
        try:
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
            profile = AccountsProfessionalProfile.objects.get(user=request.user)
            now = timezone.now()
            
            # Get events for next 7 days
            upcoming_events = ProfessionalCalendar.objects.filter(
                professional=profile,
                start_time__gte=now,
                end_time__lte=now + timedelta(days=7),
                is_cancelled=False
            ).order_by('start_time')[:10]
            
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
        profile = AccountsProfessionalProfile.objects.get(user=self.request.user)
        
        # Filter by date if provided
        date_filter = self.request.query_params.get('date', None)
        queryset = CallHistory.objects.filter(professional=profile)
        
        if date_filter:
            date = datetime.fromisoformat(date_filter).date()
            queryset = queryset.filter(start_time__date=date)
        
        return queryset.order_by('-start_time')

# ============================================
# API VIEWS FOR YOUR URL PATTERNS
# ============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """Get dashboard summary data"""
    try:
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
# CALL REQUEST VIEWS FOR YOUR URL PATTERNS
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
        
        # Check if professional is online
        if not professional.is_online:
            return Response(
                {'error': 'Professional is currently offline'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create call request using serializer
        serializer = CallRequestSerializer(data=data)
        if serializer.is_valid():
            call_request = serializer.save(professional=professional)
            
            # Create notification for professional
            ProfessionalNotification.objects.create(
                user=professional.user,
                notification_type='incoming_call',
                title=f'Incoming Call Request',
                message=f'{call_request.client_name} is requesting a {call_request.duration}-minute {call_request.get_call_type_display()} consultation.',
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
            
            return Response(
                CallRequestSerializer(call_request).data,
                status=status.HTTP_201_CREATED
            )
        else:
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
            
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
        
        # Check if user has permission to view this call
        user = request.user
        is_professional = hasattr(user, 'accountsprofessionalprofile') and call_request.professional.user == user
        is_client = call_request.client_id == user.id
        
        if not (is_professional or is_client):
            return Response(
                {'error': 'Unauthorized to view this call'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = CallRequestSerializer(call_request)
        return Response(serializer.data)
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
        
        # Check if user is authorized to update this call
        user = request.user
        is_professional = hasattr(user, 'accountsprofessionalprofile') and call_request.professional.user == user
        is_client = call_request.client_id == user.id
        
        if not (is_professional or is_client):
            return Response(
                {'error': 'Unauthorized to update this call'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Update status
        old_status = call_request.status
        call_request.status = new_status
        
        # Set timestamps
        now = timezone.now()
        if new_status == 'accepted' and old_status != 'accepted':
            call_request.accepted_at = now
        elif new_status == 'rejected' and old_status != 'rejected':
            call_request.rejected_at = now
            call_request.rejection_reason = request.data.get('reason', 'No reason provided')
        elif new_status == 'connected' and old_status != 'connected':
            call_request.connected_at = now
        elif new_status == 'completed' and old_status != 'completed':
            call_request.ended_at = now
        
        call_request.save()
        
        # Create notification for the other party
        if new_status in ['accepted', 'rejected'] and is_professional:
            # Professional accepted/rejected, notify client
            notification_user = User.objects.filter(id=call_request.client_id).first()
            if notification_user:
                ProfessionalNotification.objects.create(
                    user=notification_user,
                    notification_type='call_status_update',
                    title=f'Call Request {new_status.capitalize()}',
                    message=f'Your call request has been {new_status} by {call_request.professional.user.get_full_name()}',
                    data={
                        'call_request_id': call_request.id,
                        'status': new_status,
                        'room_id': call_request.room_id
                    },
                    priority=2
                )
        
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
        
        # Check if user is authorized to cancel this call
        user = request.user
        is_professional = hasattr(user, 'accountsprofessionalprofile') and call_request.professional.user == user
        is_client = call_request.client_id == user.id
        
        if not (is_professional or is_client):
            return Response(
                {'error': 'Unauthorized to cancel this call'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if call can be cancelled
        if call_request.status not in ['pending', 'ringing']:
            return Response(
                {'error': f'Cannot cancel a call that is {call_request.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cancel the call
        call_request.status = 'cancelled'
        call_request.cancelled_at = timezone.now()
        call_request.save()
        
        # Create notification for the other party
        if is_client:
            # Client cancelled, notify professional
            notification_user = call_request.professional.user
            title = 'Call Cancelled'
            message = f'{call_request.client_name} has cancelled the call request'
        else:
            # Professional cancelled, notify client
            notification_user = User.objects.filter(id=call_request.client_id).first()
            title = 'Call Cancelled'
            message = f'{call_request.professional.user.get_full_name()} has cancelled the call request'
        
        if notification_user:
            ProfessionalNotification.objects.create(
                user=notification_user,
                notification_type='call_cancelled',
                title=title,
                message=message,
                data={
                    'call_request_id': call_request.id,
                    'cancelled_by': user.get_full_name()
                },
                priority=2
            )
        
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
        
        serializer = CallRequestSerializer(pending_calls, many=True)
        
        return Response({
            'pending_calls': serializer.data,
            'count': len(serializer.data)
        })
    except AccountsProfessionalProfile.DoesNotExist:
        return Response(
            {'error': 'Professional profile not found'},
            status=status.HTTP_404_NOT_FOUND
        )