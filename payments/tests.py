from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from decimal import Decimal
from .models import Payment, ProfessionalProfile, ConsultationRequest

User = get_user_model()

class PaymentTests(APITestCase):
    def setUp(self):
        # Create users
        self.client_user = User.objects.create_user(
            username='client',
            email='client@test.com',
            password='password',
            role='client'
        )
        
        self.professional_user = User.objects.create_user(
            username='professional',
            email='professional@test.com',
            password='password',
            role='professional'
        )
        
        # Create professional profile
        self.professional = ProfessionalProfile.objects.create(
            user=self.professional_user,
            specialty='legal',
            hourly_rate=Decimal('100.00')
        )
        
        # Create consultation
        self.consultation = ConsultationRequest.objects.create(
            client=self.client_user,
            professional=self.professional,
            category='legal',
            duration_minutes=30
        )
        
        # Authenticate
        self.client.force_authenticate(user=self.client_user)
    
    def test_create_payment_intent(self):
        url = '/api/payments/create-payment-intent/'
        data = {
            'amount': '100.00',
            'consultation_id': self.consultation.id,
            'currency': 'usd'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('client_secret', response.data)
        self.assertIn('payment_id', response.data)
    
    def test_confirm_payment(self):
        # First create payment intent
        intent_response = self.client.post(
            '/api/payments/create-payment-intent/',
            {'amount': '100.00', 'consultation_id': self.consultation.id},
            format='json'
        )
        
        payment_id = intent_response.data['payment_id']
        
        # Then confirm payment (mocked)
        url = '/api/payments/confirm-payment/'
        data = {
            'payment_id': payment_id,
            'payment_intent_id': 'pi_test_123'
        }
        
        response = self.client.post(url, data, format='json')
        
        # Should fail because it's a fake payment intent
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)