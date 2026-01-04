from rest_framework import viewsets, generics, status, permissions, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action, api_view, permission_classes
from django.db.models import Count, Avg, Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
import random
import logging

from .models import ServiceCategory, ConsultationRequest
from .serializers import (
    ServiceCategorySerializer, ConsultationRequestSerializer,
    CreateConsultationRequestSerializer, MatchProfessionalSerializer,
    ConsultationDetailSerializer, ConsultationListSerializer
)
from accounts.models import ProfessionalProfile, User
from payments.models import Payment

logger = logging.getLogger(__name__)

# AI Matching Helper Class
class SimpleAIMatcher:
    """Simple AI matching algorithm"""
    
    @staticmethod
    def find_best_professional(category, client):
        """Find the best available professional for a category"""
        
        print(f"🔍 [AI MATCHER] Starting search for category: {category.name} (ID: {category.id})")
        print(f"🔍 [AI MATCHER] Client: {client.get_full_name()} (ID: {client.id})")
        
        # Get all online professionals in this category
        professionals = ProfessionalProfile.objects.filter(
            service_categories=category,  # ← CHANGED TO USE RELATIONSHIP
            is_online=True,
            is_verified=True
        ).select_related('user')
        
        print(f"📊 [AI MATCHER] Found {professionals.count()} professionals after filters")
        print(f"📊 [AI MATCHER] Filters used: service_categories={category.id}, is_online=True, is_verified=True")
        print(f"🔄 [AI MATCHER] DEBUG: Using service_categories filter with category ID: {category.id}")
        
        if professionals.exists():
            print("👥 [AI MATCHER] Professionals found:")
            for idx, prof in enumerate(professionals, 1):
                print(f"   {idx}. {prof.user.get_full_name()}")
                print(f"      Specialty: '{prof.specialty}'")
                print(f"      Online: {prof.is_online}, Verified: {prof.is_verified}")
                print(f"      Rating: {prof.rating}, Experience: {prof.experience_years} years")
        else:
            print("⚠️ [AI MATCHER] NO professionals found with current filters")
            print("🔎 [AI MATCHER] Checking what's in the database...")
            
            # Check all professionals without filters
            all_pros = ProfessionalProfile.objects.all().select_related('user')
            print(f"🔎 [AI MATCHER] Total professionals in database: {all_pros.count()}")
            
            if all_pros.exists():
                print("🔎 [AI MATCHER] All professionals in system:")
                for prof in all_pros:
                    specialty_match = category.name.lower() in prof.specialty.lower() if prof.specialty else False
                    print(f"   • {prof.user.get_full_name()}")
                    print(f"     Specialty: '{prof.specialty}'")
                    print(f"     Contains '{category.name}'? {specialty_match}")
                    print(f"     Online: {prof.is_online}, Verified: {prof.is_verified}")
            else:
                print("❌ [AI MATCHER] NO professionals exist in the database at all!")
        
        if not professionals:
            print("❌ [AI MATCHER] Returning None - no professionals found")
            return None
        
        # Score each professional
        scored = []
        print("🧮 [AI MATCHER] Calculating AI scores...")
        for prof in professionals:
            score = SimpleAIMatcher._calculate_score(prof, client)
            scored.append((prof, score))
            print(f"   {prof.user.get_full_name()}: {score:.1f}/100")
        
        # Sort by highest score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Return best match
        best = scored[0][0] if scored else None
        best_score = scored[0][1] if scored else 0
        
        if best:
            print(f"✅ [AI MATCHER] BEST MATCH: {best.user.get_full_name()} with score {best_score:.1f}/100")
        else:
            print(f"❌ [AI MATCHER] No best match found (empty scored list)")
        
        return best
    
    @staticmethod
    def _calculate_score(professional, client):
        """Calculate simple AI score (0-100)"""
        score = 0
        
        print(f"   📈 Calculating score for {professional.user.get_full_name()}:")
        
        # 1. Rating (0-40 points)
        rating_points = professional.rating * 8
        score += rating_points
        print(f"     Rating: {professional.rating}/5.0 → {rating_points:.1f} points")
        
        # 2. Experience (0-30 points)
        exp_points = min(professional.experience_years * 3, 30)
        score += exp_points
        print(f"     Experience: {professional.experience_years} years → {exp_points:.1f} points")
        
        # 3. Current load penalty (negative scoring)
        current_calls = ConsultationRequest.objects.filter(
            professional=professional,
            status__in=['matched', 'accepted', 'in_progress']
            ).count()
        
        load_penalty = 0
        if current_calls >= 3:
            load_penalty = -30
        elif current_calls == 2:
            load_penalty = -15
        elif current_calls == 1:
            load_penalty = -5
        
        score += load_penalty
        print(f"     Current calls: {current_calls} → {load_penalty} points penalty")
        
        # 4. Response time (check previous consultations)
        response_bonus = 0
        try:
            from dashboard.models import ProfessionalStat
            stats = ProfessionalStat.objects.get(professional=professional)
            if stats and stats.response_time:
                if stats.response_time < 60:  # < 1 minute
                    response_bonus = 20
                elif stats.response_time < 180:  # < 3 minutes
                    response_bonus = 15
                elif stats.response_time < 300:  # < 5 minutes
                    response_bonus = 10
                print(f"     Response time: {stats.response_time}s → {response_bonus} points bonus")
        except:
            print(f"     Response time: No stats available → 0 points bonus")
        
        score += response_bonus
        
        # 5. Small random factor to avoid bias
        random_bonus = random.uniform(0, 10)
        score += random_bonus
        print(f"     Random factor: +{random_bonus:.1f} points")
        
        final_score = max(0, score)  # Ensure score doesn't go negative
        print(f"     FINAL SCORE: {final_score:.1f}/100")
        
        return final_score

class ServiceCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """View service categories"""
    queryset = ServiceCategory.objects.filter(active=True)
    serializer_class = ServiceCategorySerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']
    
    @action(detail=True, methods=['get'])
    def professionals(self, request, pk=None):
        """Get available professionals in this category"""
        category = self.get_object()
        
        # Get online professionals in this category
        professionals = ProfessionalProfile.objects.filter(
            specialty=category.name,
            is_online=True,
            is_verified=True
        ).select_related('user')
        
        professional_data = []
        for prof in professionals:
            # Calculate stats
            stats = prof.professionalstat if hasattr(prof, 'professionalstat') else None
            
            professional_data.append({
                'id': prof.id,
                'name': prof.user.get_full_name(),
                'title': prof.title,
                'specialty': prof.get_specialty_display(),
                'rating': prof.rating,
                'experience_years': prof.experience_years,
                'hourly_rate': float(prof.hourly_rate),
                'languages': prof.languages,
                'bio': prof.bio,
                'is_online': prof.is_online,
                'stats': {
                    'total_consultations': stats.total_consultations if stats else 0,
                    'average_rating': stats.average_rating if stats else 0,
                    'response_time': stats.response_time if stats else 0,
                } if stats else None
            })
        
        return Response({
            'category': ServiceCategorySerializer(category).data,
            'professionals': professional_data,
            'count': len(professional_data)
        })

class ConsultationRequestViewSet(viewsets.ModelViewSet):
    """Manage consultation requests"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'professional':
            try:
                professional = user.professional_profile
                return ConsultationRequest.objects.filter(
                    professional=professional
                ).order_by('-created_at')
            except ProfessionalProfile.DoesNotExist:
                return ConsultationRequest.objects.none()
        else:  # client or admin
            return ConsultationRequest.objects.filter(
                client=user
            ).order_by('-created_at')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateConsultationRequestSerializer
        elif self.action == 'list':
            return ConsultationListSerializer
        elif self.action in ['retrieve', 'update', 'partial_update']:
            return ConsultationDetailSerializer
        return ConsultationRequestSerializer
    
    def perform_create(self, serializer):
        """Create consultation request with client"""
        consultation = serializer.save(client=self.request.user)
        
        # Try to match with a professional immediately
        self.match_professional(consultation)
    
    @action(detail=True, methods=['post'])
    def match(self, request, pk=None):
        """Manually trigger professional matching"""
        consultation = self.get_object()
        
        if consultation.professional:
            return Response({
                'error': 'Consultation already has a professional assigned'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        matched = self.match_professional(consultation)
        
        if matched:
            return Response({
                'success': True,
                'message': 'Professional matched successfully',
                'professional': {
                    'id': consultation.professional.id,
                    'name': consultation.professional.user.get_full_name(),
                    'title': consultation.professional.title,
                    'hourly_rate': float(consultation.professional.hourly_rate)
                }
            })
        else:
            return Response({
                'success': False,
                'message': 'No available professionals found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Professional accepts a consultation request"""
        consultation = self.get_object()
        
        # Check if user is a professional
        try:
            professional = request.user.professional_profile
        except ProfessionalProfile.DoesNotExist:
            return Response(
                {'error': 'Only professionals can accept consultations'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if professional is assigned to this consultation
        if consultation.professional != professional:
            return Response(
                {'error': 'You are not assigned to this consultation'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Update consultation status
        consultation.status = 'accepted'
        consultation.accepted_at = timezone.now()
        consultation.save()
        
        # Create notification for client
        from dashboard.models import Notification
        Notification.objects.create(
            user=consultation.client,
            notification_type='system',
            title='Consultation Accepted',
            message=f'{professional.user.get_full_name()} has accepted your consultation request.',
            action_url=f'/consultation/{consultation.id}/',
            action_text='View Details'
        )
        
        return Response({
            'success': True,
            'message': 'Consultation accepted successfully',
            'next_step': 'payment'
        })
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a consultation request"""
        consultation = self.get_object()
        
        # Check permissions
        user = request.user
        if user.role == 'client' and consultation.client != user:
            return Response(
                {'error': 'You can only cancel your own consultations'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Update status
        consultation.status = 'cancelled'
        consultation.cancelled_at = timezone.now()
        consultation.save()
        
        # Refund payment if exists
        payments = consultation.payments.filter(status='completed')
        for payment in payments:
            # Add refund logic here
            pass
        
        return Response({
            'success': True,
            'message': 'Consultation cancelled successfully'
        })
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark consultation as completed"""
        consultation = self.get_object()
        
        # Check if user is professional assigned to this consultation
        try:
            professional = request.user.professional_profile
            if consultation.professional != professional:
                return Response(
                    {'error': 'Only assigned professional can mark as completed'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except ProfessionalProfile.DoesNotExist:
            return Response(
                {'error': 'Only professionals can complete consultations'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Update status
        consultation.status = 'completed'
        consultation.completed_at = timezone.now()
        consultation.save()
        
        # Update professional stats
        from dashboard.models import ProfessionalStat
        stats, _ = ProfessionalStat.objects.get_or_create(
            professional=professional
        )
        stats.update_stats(consultation)
        
        return Response({
            'success': True,
            'message': 'Consultation marked as completed'
        })
    
    def match_professional(self, consultation):
        """AI-powered professional matching"""
        # Use AI to find best professional
        best_professional = SimpleAIMatcher.find_best_professional(
            consultation.category, 
            consultation.client
        )
        
        if best_professional:
            consultation.professional = best_professional
            consultation.status = 'matched'
            consultation.matched_at = timezone.now()
            
            # ✅ FIX 1: Update with professional's actual hourly rate
            consultation.hourly_rate = best_professional.hourly_rate
            
            consultation.save()  # This will auto-calculate total_amount based on new hourly_rate
            
            print(f"💰 [AI MATCHER] Updated consultation hourly_rate to: {best_professional.hourly_rate}")
            print(f"💰 [AI MATCHER] New total_amount: {consultation.total_amount}")
            
            # Create incoming call in dashboard
            from dashboard.models import IncomingCall
            
            # Calculate estimated earnings BEFORE creating IncomingCall
            estimated_earnings = consultation.total_amount if consultation.total_amount else 0
            
            IncomingCall.objects.create(
                professional=best_professional,
                consultation_id=consultation.id,  # ← CHANGE TO consultation_id
                client_name=consultation.client.get_full_name(),
                client_phone=consultation.client.phone or '',
                category=consultation.get_category_display(),
                duration=consultation.duration_minutes,
                estimated_earnings=estimated_earnings,  # ADD THIS - Now defined
                expires_at=timezone.now() + timezone.timedelta(minutes=5),
                status='pending'
            )
            
            # Create notification for professional
            from dashboard.models import Notification
            Notification.objects.create(
                user=best_professional.user,
                notification_type='incoming_call',
                title='New Consultation Request',
                message=f'New {consultation.get_category_display()} consultation from {consultation.client.get_full_name()}',
                data={
                    'consultation_id': consultation.id,
                    'client_name': consultation.client.get_full_name(),
                    'category': consultation.get_category_display(),
                    'duration': consultation.duration_minutes,
                    'client_id': consultation.client.id
                },
                action_url=f'/dashboard/calls/{consultation.id}/',
                action_text='Accept Call'
            )
            
            logger.info(f"Consultation {consultation.id} matched with {best_professional.user.get_full_name()}")
            return True
        
        logger.warning(f"No professional found for consultation {consultation.id}")
        return False

class CreateConsultationView(APIView):
    """Create a new consultation request"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = CreateConsultationRequestSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            consultation = serializer.save(client=request.user)
            
            # Try to match immediately
            viewset = ConsultationRequestViewSet()
            viewset.request = request
            viewset.format_kwarg = None
            matched = viewset.match_professional(consultation)
            
            response_data = ConsultationDetailSerializer(consultation).data
            
            if matched:
                response_data['match_status'] = 'matched'
                response_data['message'] = 'Professional matched successfully'
            else:
                response_data['match_status'] = 'pending'
                response_data['message'] = 'Looking for available professionals...'
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# NEW: Quick Consultation View with AI Matching
class QuickConsultationView(APIView):
    """Create consultation and match with AI immediately"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            category_id = request.data.get('category_id')
            
            if not category_id:
                return Response(
                    {'error': 'category_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            category = get_object_or_404(ServiceCategory, id=category_id, active=True)
            
            # Create consultation
            consultation = ConsultationRequest.objects.create(
                client=request.user,
                category=category,
                title=f"{category.name} Consultation",
                description="Quick consultation request",
                status='pending',
                hourly_rate=0,  # ✅ FIX 2: Set to 0, will be updated by match_professional
                duration_minutes=category.min_duration,
                total_amount=0  # ✅ FIX 3: Will be calculated after matching
            )
            
            # Try to match using AI
            matched = ConsultationRequestViewSet().match_professional(consultation)
            
            response_data = {
                'success': True,
                'consultation_id': consultation.id,
                'category': category.name,
                'status': consultation.status,
                'matched': matched,
                'requires_payment': True if matched else False
            }
            
            if matched:
                response_data.update({
                    'professional': {
                        'id': consultation.professional.id,
                        'name': consultation.professional.user.get_full_name(),
                        'rate': float(consultation.professional.hourly_rate),
                        'rating': consultation.professional.rating
                    },
                    'payment_details': {
                        'amount': float(consultation.total_amount),
                        'currency': 'KES',
                        'description': f"{category.name} Consultation",
                        'consultation_id': consultation.id
                    }
                })
            else:
                response_data.update({
                    'message': 'No professionals available at the moment. Please try again in a few minutes.',
                    'queue_position': 1
                })
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Quick consultation error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class AvailableProfessionalsView(APIView):
    """Get available professionals for a category"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        category_name = request.query_params.get('category')
        
        if not category_name:
            return Response(
                {'error': 'Category parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            category = ServiceCategory.objects.get(name=category_name, active=True)
        except ServiceCategory.DoesNotExist:
            return Response(
                {'error': 'Category not found or inactive'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get available professionals
        professionals = ProfessionalProfile.objects.filter(
            specialty=category.name,
            is_online=True,
            is_verified=True
        ).select_related('user').order_by('-rating', '-experience_years')
        
        professional_data = []
        for prof in professionals:
            # Calculate availability
            from dashboard.models import ProfessionalAvailability
            availability = ProfessionalAvailability.objects.filter(
                professional=prof
            ).first()
            
            professional_data.append({
                'id': prof.id,
                'name': prof.user.get_full_name(),
                'title': prof.title,
                'rating': prof.rating,
                'experience_years': prof.experience_years,
                'hourly_rate': float(prof.hourly_rate),
                'languages': prof.languages,
                'bio': prof.bio,
                'is_available_now': availability.is_available_now() if availability else False,
                'next_available_slot': None,  # You can implement slot calculation
                'total_consultations': getattr(prof.professionalstat, 'total_consultations', 0) if hasattr(prof, 'professionalstat') else 0,
                'ai_score': SimpleAIMatcher._calculate_score(prof, request.user) if request.user.is_authenticated else 0
            })
        
        return Response({
            'category': ServiceCategorySerializer(category).data,
            'professionals': professional_data,
            'count': len(professional_data),
            'matching_algorithm': 'AI-powered (rating, experience, availability, response time)'
        })

class ConsultationStatisticsView(APIView):
    """Get consultation statistics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        if user.role == 'client':
            consultations = ConsultationRequest.objects.filter(client=user)
        elif user.role == 'professional':
            try:
                professional = user.professional_profile
                consultations = ConsultationRequest.objects.filter(professional=professional)
            except ProfessionalProfile.DoesNotExist:
                return Response(
                    {'error': 'User is not a professional'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:  # admin
            consultations = ConsultationRequest.objects.all()
        
        # Calculate statistics
        total = consultations.count()
        completed = consultations.filter(status='completed').count()
        pending = consultations.filter(status__in=['pending', 'matched']).count()
        cancelled = consultations.filter(status='cancelled').count()
        
        # Monthly statistics
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        
        month_ago = timezone.now() - timedelta(days=30)
        monthly_stats = consultations.filter(
            created_at__gte=month_ago
        ).values('created_at__date').annotate(
            count=Count('id')
        ).order_by('created_at__date')
        
        # Category distribution
        category_stats = consultations.values(
            'category__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        # AI matching success rate
        matched_count = consultations.filter(status='matched').count()
        matching_success_rate = (matched_count / total * 100) if total > 0 else 0
        
        return Response({
            'total': total,
            'completed': completed,
            'pending': pending,
            'cancelled': cancelled,
            'completion_rate': (completed / total * 100) if total > 0 else 0,
            'matching_success_rate': matching_success_rate,
            'monthly_stats': list(monthly_stats),
            'category_distribution': list(category_stats),
            'average_duration': consultations.aggregate(
                avg_duration=Avg('duration_minutes')
            )['avg_duration'] or 0
        })

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def category_list(request):
    """Public endpoint to get all active categories"""
    categories = ServiceCategory.objects.filter(active=True)
    serializer = ServiceCategorySerializer(categories, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_consultations(request):
    """Get all consultations for the current user"""
    user = request.user
    
    if user.role == 'client':
        consultations = ConsultationRequest.objects.filter(
            client=user
        ).select_related(
            'category', 'professional__user'
        ).order_by('-created_at')
    elif user.role == 'professional':
        try:
            professional = user.professional_profile
            consultations = ConsultationRequest.objects.filter(
                professional=professional
            ).select_related(
                'category', 'client'
            ).order_by('-created_at')
        except ProfessionalProfile.DoesNotExist:
            return Response(
                {'error': 'User is not a professional'},
                status=status.HTTP_400_BAD_REQUEST
            )
    else:
        consultations = ConsultationRequest.objects.none()
    
    serializer = ConsultationListSerializer(consultations, many=True)
    return Response(serializer.data)