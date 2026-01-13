from rest_framework import viewsets, status
from rest_framework.decorators import action, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
from datetime import datetime, timedelta
import json
import csv
from django.http import HttpResponse
from django.contrib.auth.hashers import make_password

from accounts.models import User, ProfessionalProfile, ClientProfile
from categories.models import ServiceCategory, ConsultationRequest
from .models import AdminLog, PlatformSettings, Report
from .serializers import (
    UserSerializer, ProfessionalProfileSerializer, ClientProfileSerializer,ClientCreateSerializer,  # Add this
    ConsultationSerializer, AdminLogSerializer, PlatformStatsSerializer,
    ReportSerializer, ProfessionalVerificationSerializer, UserStatusSerializer
)

# Add this at the top with other classes
class AdminMixin:
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class AdminDashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAdminUser]
    
    def list(self, request):
        """Get platform statistics"""
        today = timezone.now().date()
        
        # Calculate stats
        total_users = User.objects.count()
        total_professionals = User.objects.filter(role='professional').count()
        total_clients = User.objects.filter(role='client').count()
        
        total_consultations = ConsultationRequest.objects.count()
        
        # Total revenue from completed consultations
        total_revenue = ConsultationRequest.objects.filter(
            status='completed'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Active consultations
        active_consultations = ConsultationRequest.objects.filter(
            status__in=['pending', 'matched', 'accepted', 'in_progress']
        ).count()
        
        # Today's stats
        today_revenue = ConsultationRequest.objects.filter(
            created_at__date=today,
            status='completed'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        today_consultations = ConsultationRequest.objects.filter(
            created_at__date=today
        ).count()
        
        # Pending verifications
        pending_verifications = ProfessionalProfile.objects.filter(
            is_verified=False
        ).count()
        
        # Offline professionals
        offline_professionals = ProfessionalProfile.objects.filter(
            is_online=False
        ).count()
        
        stats = {
            'total_users': total_users,
            'total_professionals': total_professionals,
            'total_clients': total_clients,
            'total_consultations': total_consultations,
            'total_revenue': total_revenue,
            'active_consultations': active_consultations,
            'today_revenue': today_revenue,
            'today_consultations': today_consultations,
            'pending_verifications': pending_verifications,
            'offline_professionals': offline_professionals
        }
        
        serializer = PlatformStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def activity(self, request):
        """Get recent admin activity"""
        logs = AdminLog.objects.all()[:20]
        serializer = AdminLogSerializer(logs, many=True)
        return Response(serializer.data)

class ProfessionalViewSet(viewsets.ModelViewSet, AdminMixin):
    """Manage professionals (admin only)"""
    permission_classes = [IsAdminUser]
    queryset = ProfessionalProfile.objects.all().select_related('user')
    serializer_class = ProfessionalProfileSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        verification = self.request.query_params.get('verification', None)
        if verification == 'pending':
            queryset = queryset.filter(is_verified=False)
        elif verification == 'verified':
            queryset = queryset.filter(is_verified=True)
        
        online = self.request.query_params.get('online', None)
        if online == 'true':
            queryset = queryset.filter(is_online=True)
        elif online == 'false':
            queryset = queryset.filter(is_online=False)
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search)
            )
        
        return queryset
    
    def create(self, request):
        """Create a new professional"""
        try:
            user_data = request.data.get('user', {})
            professional_data = request.data.get('professional', {})
            
            if 'password' in user_data:
                user_data['password'] = make_password(user_data['password'])
            
            user_data['role'] = 'professional'
            user_data['is_active'] = True
            
            user_serializer = UserSerializer(data=user_data)
            if not user_serializer.is_valid():
                return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            user = user_serializer.save()
            
            professional_data['user'] = user  # Send user instance, not ID
            professional_serializer = self.get_serializer(data=professional_data)
            
            if professional_serializer.is_valid():
                professional_serializer.save()
                
                AdminLog.objects.create(
                    admin=request.user,
                    action='user_created',
                    description=f'Created professional: {user.get_full_name()}',
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                return Response(professional_serializer.data, status=status.HTTP_201_CREATED)
            else:
                user.delete()
                return Response(professional_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify a professional"""
        professional = self.get_object()
        
        if professional.is_verified:
            return Response(
                {'error': 'Professional is already verified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        professional.is_verified = True
        professional.save()
        
        AdminLog.objects.create(
            admin=request.user,
            action='professional_verified',
            description=f'Verified professional: {professional.user.get_full_name()}',
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({'status': 'verified'})
    
    @action(detail=True, methods=['patch'])
    def toggle_active(self, request, pk=None):
        """Toggle professional's active status"""
        professional = self.get_object()
        user = professional.user
        
        serializer = UserStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        is_active = serializer.validated_data['is_active']
        user.is_active = is_active
        user.save()
        
        action = 'activated' if is_active else 'deactivated'
        AdminLog.objects.create(
            admin=request.user,
            action='user_updated',
            description=f'{action} professional: {user.get_full_name()}',
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({'status': action})

class ClientViewSet(viewsets.ModelViewSet, AdminMixin):
    """Manage clients (admin only)"""
    permission_classes = [IsAdminUser]
    queryset = ClientProfile.objects.all().select_related('user')
    #serializer_class = ClientProfileSerializer
    serializer_class = ClientCreateSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search)
            )
        
        active = self.request.query_params.get('active', None)
        if active == 'true':
            queryset = queryset.filter(user__is_active=True)
        elif active == 'false':
            queryset = queryset.filter(user__is_active=False)
        
        return queryset
    
    def create(self, request):
        """Create a new client"""
        try:
            user_data = request.data.get('user', {})
            client_data = request.data.get('client', {})
            
            if 'password' in user_data:
                user_data['password'] = make_password(user_data['password'])
            
            user_data['role'] = 'client'
            user_data['is_active'] = True
            
            user_serializer = UserSerializer(data=user_data)
            if not user_serializer.is_valid():
                return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            user = user_serializer.save()
            
            client_data['user'] = user  # ← Send user instance, not ID
            client_serializer = self.get_serializer(data=client_data)
            
            if client_serializer.is_valid():
                client_serializer.save()
                
                AdminLog.objects.create(
                    admin=request.user,
                    action='user_created',
                    description=f'Created client: {user.get_full_name()}',
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                return Response(client_serializer.data, status=status.HTTP_201_CREATED)
            else:
                user.delete()
                return Response(client_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['patch'])
    def toggle_active(self, request, pk=None):
        """Toggle client's active status"""
        client = self.get_object()
        user = client.user
        
        serializer = UserStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        is_active = serializer.validated_data['is_active']
        user.is_active = is_active
        user.save()
        
        action = 'activated' if is_active else 'deactivated'
        AdminLog.objects.create(
            admin=request.user,
            action='user_updated',
            description=f'{action} client: {user.get_full_name()}',
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({'status': action})

class ConsultationViewSet(viewsets.ModelViewSet, AdminMixin):
    """Manage consultations (admin only)"""
    permission_classes = [IsAdminUser]
    queryset = ConsultationRequest.objects.all().select_related('client', 'professional__user', 'category')
    serializer_class = ConsultationSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__gte=start_date)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__lte=end_date)
            except ValueError:
                pass
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(client__username__icontains=search) |
                Q(client__first_name__icontains=search) |
                Q(client__last_name__icontains=search)
            )
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent consultations"""
        consultations = self.get_queryset().order_by('-created_at')[:50]
        serializer = self.get_serializer(consultations, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get consultation statistics"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=6)
        
        daily_stats = []
        for i in range(7):
            date = start_date + timedelta(days=i)
            count = ConsultationRequest.objects.filter(
                created_at__date=date
            ).count()
            daily_stats.append({
                'date': date.strftime('%Y-%m-%d'),
                'consultations': count
            })
        
        revenue_by_category = []
        categories = ServiceCategory.objects.all()
        for category in categories:
            revenue = ConsultationRequest.objects.filter(
                category=category,
                status='completed'
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            if revenue > 0:
                revenue_by_category.append({
                    'name': category.name,
                    'revenue': revenue
                })
        
        status_distribution = ConsultationRequest.objects.values('status').annotate(
            count=Count('id')
        )
        
        return Response({
            'daily_stats': daily_stats,
            'revenue_by_category': revenue_by_category,
            'status_distribution': status_distribution
        })
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a consultation"""
        consultation = self.get_object()
        
        if consultation.status in ['completed', 'cancelled']:
            return Response(
                {'error': f'Consultation is already {consultation.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        consultation.status = 'cancelled'
        consultation.save()
        
        AdminLog.objects.create(
            admin=request.user,
            action='consultation_updated',
            description=f'Cancelled consultation #{consultation.id}',
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({'status': 'cancelled'})

class ReportViewSet(viewsets.ModelViewSet, AdminMixin):
    """Manage reports (admin only)"""
    permission_classes = [IsAdminUser]
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Generate a new report"""
        report_type = request.data.get('report_type')
        period_start = request.data.get('period_start')
        period_end = request.data.get('period_end')
        name = request.data.get('name', f'{report_type} Report')
        format_type = request.data.get('format', 'json')
        
        try:
            period_start = datetime.strptime(period_start, '%Y-%m-%d').date()
            period_end = datetime.strptime(period_end, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        report = Report.objects.create(
            name=name,
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            format=format_type,
            status='pending',
            generated_by=request.user
        )
        
        try:
            if report_type == 'revenue':
                data = self._generate_revenue_report(period_start, period_end)
            elif report_type == 'users':
                data = self._generate_user_report(period_start, period_end)
            elif report_type == 'consultations':
                data = self._generate_consultation_report(period_start, period_end)
            elif report_type == 'professionals':
                data = self._generate_professional_report(period_start, period_end)
            elif report_type == 'clients':
                data = self._generate_client_report(period_start, period_end)
            else:
                raise ValueError(f'Unknown report type: {report_type}')
            
            report.data = data
            report.status = 'generated'
            report.generated_at = timezone.now()
            report.save()
            
            AdminLog.objects.create(
                admin=request.user,
                action='report_generated',
                description=f'Generated report: {name}',
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return Response(ReportSerializer(report).data)
            
        except Exception as e:
            report.status = 'failed'
            report.error_message = str(e)
            report.save()
            return Response(
                {'error': f'Failed to generate report: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download report in CSV format"""
        report = self.get_object()
        
        if report.status != 'generated':
            return Response(
                {'error': 'Report not ready for download'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{report.name}.csv"'
        
        writer = csv.writer(response)
        
        if report.report_type == 'revenue':
            writer.writerow(['Date', 'Revenue'])
            for item in report.data.get('daily_revenue', []):
                writer.writerow([item['date'], item['revenue']])
        
        elif report.report_type == 'users':
            writer.writerow(['Date', 'New Users'])
            for item in report.data.get('daily_users', []):
                writer.writerow([item['date'], item['new_users']])
        
        elif report.report_type == 'consultations':
            writer.writerow(['Date', 'Consultations'])
            for item in report.data.get('daily_consultations', []):
                writer.writerow([item['date'], item['consultations']])
        
        return response
    
    def _generate_revenue_report(self, start_date, end_date):
        daily_revenue = []
        current_date = start_date
        
        while current_date <= end_date:
            revenue = ConsultationRequest.objects.filter(
                created_at__date=current_date,
                status='completed'
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            daily_revenue.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'revenue': revenue
            })
            current_date += timedelta(days=1)
        
        revenue_by_category = ConsultationRequest.objects.filter(
            created_at__date__range=[start_date, end_date],
            status='completed'
        ).values('category__name').annotate(
            revenue=Sum('total_amount'),
            count=Count('id')
        )
        
        return {
            'period': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d')
            },
            'daily_revenue': daily_revenue,
            'revenue_by_category': list(revenue_by_category),
            'total_revenue': sum(item['revenue'] for item in daily_revenue)
        }
    
    def _generate_user_report(self, start_date, end_date):
        daily_users = []
        current_date = start_date
        
        while current_date <= end_date:
            count = User.objects.filter(
                date_joined__date=current_date
            ).count()
            
            daily_users.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'new_users': count
            })
            current_date += timedelta(days=1)
        
        user_distribution = User.objects.filter(
            date_joined__date__range=[start_date, end_date]
        ).values('role').annotate(count=Count('id'))
        
        return {
            'period': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d')
            },
            'daily_users': daily_users,
            'user_distribution': list(user_distribution),
            'total_new_users': sum(item['new_users'] for item in daily_users)
        }
    
    def _generate_consultation_report(self, start_date, end_date):
        daily_consultations = []
        current_date = start_date
        
        while current_date <= end_date:
            count = ConsultationRequest.objects.filter(
                created_at__date=current_date
            ).count()
            
            daily_consultations.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'consultations': count
            })
            current_date += timedelta(days=1)
        
        status_distribution = ConsultationRequest.objects.filter(
            created_at__date__range=[start_date, end_date]
        ).values('status').annotate(count=Count('id'))
        
        avg_duration = ConsultationRequest.objects.filter(
            created_at__date__range=[start_date, end_date],
            duration_minutes__isnull=False
        ).aggregate(avg=Avg('duration_minutes'))['avg'] or 0
        
        return {
            'period': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d')
            },
            'daily_consultations': daily_consultations,
            'status_distribution': list(status_distribution),
            'total_consultations': sum(item['consultations'] for item in daily_consultations),
            'average_duration': avg_duration
        }
    
    def _generate_professional_report(self, start_date, end_date):
        professionals = ProfessionalProfile.objects.filter(
            user__date_joined__date__range=[start_date, end_date]
        ).select_related('user')
        
        performance_data = []
        for pro in professionals:
            consultations = ConsultationRequest.objects.filter(
                professional=pro,
                created_at__date__range=[start_date, end_date]
            )
            
            completed = consultations.filter(status='completed').count()
            revenue = consultations.filter(
                status='completed'
            ).aggregate(total=Sum('professional_earnings'))['total'] or 0
            
            performance_data.append({
                'id': pro.id,
                'name': pro.user.get_full_name(),
                'email': pro.user.email,
                'hourly_rate': pro.hourly_rate,
                'rating': pro.rating,
                'total_consultations': consultations.count(),
                'completed_consultations': completed,
                'total_revenue': revenue,
                'is_verified': pro.is_verified,
                'is_online': pro.is_online
            })
        
        return {
            'period': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d')
            },
            'professionals': performance_data,
            'total_professionals': len(performance_data)
        }
    
    def _generate_client_report(self, start_date, end_date):
        clients = ClientProfile.objects.filter(
            user__date_joined__date__range=[start_date, end_date]
        ).select_related('user')
        
        client_data = []
        for client in clients:
            consultations = ConsultationRequest.objects.filter(
                client=client.user,
                created_at__date__range=[start_date, end_date]
            )
            
            spent = consultations.filter(
                status='completed'
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            client_data.append({
                'id': client.id,
                'name': client.user.get_full_name(),
                'email': client.user.email,
                'total_consultations': consultations.count(),
                'total_spent': spent,
                'last_consultation': consultations.order_by('-created_at').first().created_at if consultations.exists() else None
            })
        
        active_clients = User.objects.filter(
            role='client',
            last_login__date__range=[start_date, end_date]
        ).count()
        
        total_clients = User.objects.filter(role='client').count()
        retention_rate = (active_clients / total_clients * 100) if total_clients > 0 else 0
        
        return {
            'period': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d')
            },
            'clients': client_data,
            'active_clients': active_clients,
            'total_clients': total_clients,
            'retention_rate': retention_rate
        }

class UserViewSet(viewsets.ModelViewSet, AdminMixin):
    """Manage all users (admin only)"""
    permission_classes = [IsAdminUser]
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        role = self.request.query_params.get('role', None)
        if role:
            queryset = queryset.filter(role=role)
        
        active = self.request.query_params.get('active', None)
        if active == 'true':
            queryset = queryset.filter(is_active=True)
        elif active == 'false':
            queryset = queryset.filter(is_active=False)
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )
        
        return queryset
    
    @action(detail=True, methods=['patch'])
    def toggle_active(self, request, pk=None):
        """Toggle user active status"""
        user = self.get_object()
        
        serializer = UserStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        is_active = serializer.validated_data['is_active']
        user.is_active = is_active
        user.save()
        
        action = 'activated' if is_active else 'deactivated'
        AdminLog.objects.create(
            admin=request.user,
            action='user_updated',
            description=f'{action} user: {user.get_full_name()}',
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({'status': action})
        #admin dashboard/views.py
