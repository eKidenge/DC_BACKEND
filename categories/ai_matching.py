# categories/ai_matching.py
import random
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count, Avg
from .models import ConsultationRequest
from accounts.models import ProfessionalProfile
import logging

logger = logging.getLogger(__name__)

class SimpleAIMatcher:
    """Simple AI matching algorithm that works with your existing system"""
    
    @staticmethod
    def find_best_professional(category, client):
        """Find the best available professional for a category"""
        
        # Get all online professionals in this category
        professionals = ProfessionalProfile.objects.filter(
            specialty=category.name,  # Using your existing field
            is_online=True,
            is_verified=True
        ).select_related('user')
        
        if not professionals:
            return None
        
        # Score each professional
        scored = []
        for prof in professionals:
            score = SimpleAIMatcher._calculate_score(prof, client)
            scored.append((prof, score))
        
        # Sort by highest score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Return best match
        return scored[0][0] if scored else None
    
    @staticmethod
    def _calculate_score(professional, client):
        """Calculate simple AI score (0-100)"""
        score = 0
        
        # 1. Rating (0-40 points)
        score += professional.rating * 8  # 5 stars = 40 points
        
        # 2. Experience (0-30 points)
        score += min(professional.experience_years * 3, 30)
        
        # 3. Current load penalty (negative scoring)
        current_calls = professional.user.consultations.filter(
            status__in=['matched', 'accepted', 'in_progress']
        ).count()
        
        if current_calls >= 3:
            score -= 30
        elif current_calls == 2:
            score -= 15
        elif current_calls == 1:
            score -= 5
        
        # 4. Response time (check previous consultations)
        previous = ConsultationRequest.objects.filter(
            professional=professional,
            status='completed'
        ).aggregate(
            avg_response=Avg('accepted_at', filter=Q(accepted_at__isnull=False))
        )['avg_response']
        
        if previous:
            response_seconds = previous.total_seconds()
            if response_seconds < 60:  # < 1 minute
                score += 20
            elif response_seconds < 180:  # < 3 minutes
                score += 15
            elif response_seconds < 300:  # < 5 minutes
                score += 10
        
        # 5. Small random factor to avoid bias
        score += random.uniform(0, 10)
        
        return max(0, score)  # Ensure score doesn't go negative