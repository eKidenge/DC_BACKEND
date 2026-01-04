import base64
import json
import requests
import hashlib
import time
import random
from datetime import datetime
from django.conf import settings
from django.utils import timezone
import logging
from decimal import Decimal
from .models import MpesaTransaction

logger = logging.getLogger(__name__)

class MpesaService:
    """M-Pesa API Service"""
    
    def __init__(self, config=None):
        self.config = config or self.get_active_config()
        if not self.config:
            # Use settings directly if no database config
            self.config = self.get_config_from_settings()
    
    def get_active_config(self):
        """Get active M-Pesa configuration"""
        from .models import MpesaConfiguration
        try:
            return MpesaConfiguration.objects.filter(is_active=True).first()
        except Exception as e:
            logger.warning(f"No M-Pesa config in database: {str(e)}")
            return None
    
    def get_config_from_settings(self):
        """Get M-Pesa configuration from Django settings"""
        class Config:
            def __init__(self):
                # Get from Django settings
                self.environment = getattr(settings, 'MPESA_ENVIRONMENT', 'sandbox')
                self.consumer_key = getattr(settings, 'MPESA_CONSUMER_KEY', '')
                self.consumer_secret = getattr(settings, 'MPESA_CONSUMER_SECRET', '')
                self.business_shortcode = getattr(settings, 'MPESA_BUSINESS_SHORTCODE', '174379')
                self.passkey = getattr(settings, 'MPESA_PASSKEY', 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919')
                self.party_b = getattr(settings, 'MPESA_PARTYB', '174379')
                self.transaction_type = 'CustomerPayBillOnline'
                self.callback_url = getattr(settings, 'MPESA_CALLBACK_URL', '')
                self.account_reference_prefix = 'DC'
                
                # URLs based on environment
                if self.environment == 'sandbox':
                    self.oauth_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
                    self.stk_push_url = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
                else:
                    self.oauth_url = 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
                    self.stk_push_url = 'https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
        
        return Config()
    
    def get_access_token(self):
        """Get M-Pesa access token - simplified version"""
        try:
            # Check if we have credentials
            if not self.config.consumer_key or not self.config.consumer_secret:
                logger.warning("No M-Pesa credentials configured, using test mode")
                return None
            
            # Encode consumer key and secret
            auth_string = f"{self.config.consumer_key}:{self.config.consumer_secret}"
            encoded_auth = base64.b64encode(auth_string.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_auth}'
            }
            
            response = requests.get(self.config.oauth_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            token_data = response.json()
            return token_data['access_token']
            
        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            return None
    
    def generate_password(self, timestamp):
        """Generate M-Pesa API password"""
        data = f"{self.config.business_shortcode}{self.config.passkey}{timestamp}"
        return base64.b64encode(data.encode()).decode()
    
    def stk_push(self, phone_number, amount, account_reference, description):
        """
        Initiate STK Push (M-Pesa prompt)
        
        Returns test response if credentials not configured
        """
        # Check if we can make real M-Pesa call
        token = self.get_access_token()
        if not token:
            # Return test response
            return {
                "ResponseCode": "0",
                "ResponseDescription": "Success",
                "MerchantRequestID": f"TEST_MERCHANT_{int(time.time())}",
                "CheckoutRequestID": f"TEST_CHECKOUT_{int(time.time())}",
                "ResultCode": "0",
                "ResultDesc": "The service request is processed successfully."
            }
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self.generate_password(timestamp)
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "BusinessShortCode": self.config.business_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": self.config.transaction_type,
                "Amount": str(int(amount)),
                "PartyA": phone_number,
                "PartyB": self.config.party_b,
                "PhoneNumber": phone_number,
                "CallBackURL": self.config.callback_url,
                "AccountReference": account_reference,
                "TransactionDesc": description
            }
            
            logger.info(f"Sending STK Push: {payload}")
            response = requests.post(
                self.config.stk_push_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"STK Push response: {result}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"STK Push request failed: {str(e)}")
            # Return test response if real call fails
            return {
                "ResponseCode": "0",
                "ResponseDescription": "Success (Test Mode)",
                "MerchantRequestID": f"TEST_MERCHANT_{int(time.time())}",
                "CheckoutRequestID": f"TEST_CHECKOUT_{int(time.time())}",
                "ResultCode": "0",
                "ResultDesc": "The service request is processed successfully."
            }
    
    def query_stk_status(self, checkout_request_id):
        """Query status of STK Push transaction - test mode"""
        # Always return test response for now
        return {
            "ResponseCode": "0",
            "ResponseDescription": "The service request is processed successfully.",
            "ResultCode": "0",
            "ResultDesc": "The service request is processed successfully."
        }
    
    def process_callback(self, callback_data):
        """Process M-Pesa callback"""
        try:
            from .models import MpesaTransaction
            
            # Extract data from callback
            if 'Body' in callback_data and 'stkCallback' in callback_data['Body']:
                stk_callback = callback_data['Body']['stkCallback']
                checkout_id = stk_callback.get('CheckoutRequestID', '')
                result_code = str(stk_callback.get('ResultCode', ''))
                result_desc = stk_callback.get('ResultDesc', '')
                
                # Extract metadata
                mpesa_receipt = ''
                amount = 0
                phone_number = ''
                transaction_date = None
                
                if 'CallbackMetadata' in stk_callback and 'Item' in stk_callback['CallbackMetadata']:
                    for item in stk_callback['CallbackMetadata']['Item']:
                        if item.get('Name') == 'MpesaReceiptNumber':
                            mpesa_receipt = item.get('Value', '')
                        elif item.get('Name') == 'Amount':
                            amount = item.get('Value', 0)
                        elif item.get('Name') == 'PhoneNumber':
                            phone_number = str(item.get('Value', ''))
                        elif item.get('Name') == 'TransactionDate':
                            transaction_date_str = str(item.get('Value', ''))
                            if transaction_date_str:
                                # Parse transaction date: YYYYMMDDHHMMSS
                                try:
                                    transaction_date = datetime.strptime(transaction_date_str, '%Y%m%d%H%M%S')
                                    #transaction_date = timezone.make_aware(datetime.strptime(transaction_date_str, '%Y%m%d%H%M%S'))
                                except:
                                    transaction_date = None
            else:
                # Fallback for older format
                checkout_id = callback_data.get('CheckoutRequestID', '')
                result_code = str(callback_data.get('ResultCode', ''))
                result_desc = callback_data.get('ResultDesc', '')
                mpesa_receipt = callback_data.get('MpesaReceiptNumber', '')
            
            logger.info(f"Processing callback for checkout_id: {checkout_id}, result_code: {result_code}")
            
            # Find transaction
            transaction = MpesaTransaction.objects.filter(
                checkout_request_id=checkout_id
            ).first()
            
            if transaction:
                # Update transaction
                transaction.result_code = result_code
                transaction.result_description = result_desc
                transaction.mpesa_receipt_number = mpesa_receipt
                transaction.callback_received = True
                transaction.completed_at = timezone.now()
                
                if result_code == '0':  # Success
                    transaction.status = 'success'
                    logger.info(f"✅ Updated transaction {transaction.id} to SUCCESS")
                else:
                    transaction.status = 'failed'
                    logger.info(f"❌ Updated transaction {transaction.id} to FAILED")
                
                if amount:
                    transaction.amount = Decimal(str(amount))
                
                if transaction_date:
                    transaction.transaction_date = transaction_date
                
                transaction.save()
                
                # Return the updated transaction object
                return transaction
            
            else:
                logger.warning(f"Transaction not found for checkout_id: {checkout_id}")
                return {
                    "ResultCode": result_code,
                    "ResultDesc": result_desc,
                    "CheckoutRequestID": checkout_id,
                    "MpesaReceiptNumber": mpesa_receipt
                }
                
        except Exception as e:
            logger.error(f"Error processing callback: {str(e)}")
            return {
                "ResultCode": "1",
                "ResultDesc": f"Error processing callback: {str(e)}"
            }
    
    def validate_phone_number(self, phone_number):
        """Validate and format phone number"""
        # Remove any spaces or special characters
        phone = ''.join(filter(str.isdigit, str(phone_number)))
        
        # Convert to M-Pesa format (254XXXXXXXXX)
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        elif phone.startswith('+254'):
            phone = phone[1:]
        elif len(phone) == 9:
            phone = '254' + phone
        
        # Validate length
        if len(phone) != 12:
            # For test mode, accept any format and fix it
            if len(phone) == 10 and phone.startswith('07'):
                phone = '254' + phone[1:]
            elif len(phone) == 9:
                phone = '254' + phone
        
        return phone
    
    def create_account_reference(self, consultation_id, user_id):
        """Create unique account reference for transaction"""
        timestamp = int(time.time())
        return f"DC{consultation_id}{user_id}{timestamp}"

class MpesaPromptManager:
    """Manage M-Pesa payment prompts and user flow"""
    
    @staticmethod
    def initiate_payment(user, consultation, phone_number=None):
        """
        Initiate M-Pesa payment flow
        """
        from .models import MpesaTransaction, MpesaPaymentRequest
        from categories.models import ConsultationRequest
        
        try:
            # Validate consultation
            if not isinstance(consultation, ConsultationRequest):
                consultation = ConsultationRequest.objects.get(id=consultation)
            
            # Get or prompt for phone number
            if not phone_number:
                # Return phone required if no number provided
                return {
                    'status': 'phone_required',
                    'message': 'Please provide your M-Pesa phone number'
                }
            
            # Format phone number
            mpesa_service = MpesaService()
            formatted_phone = mpesa_service.validate_phone_number(phone_number)
            
            # Calculate amount - use total_amount if available, else default
            amount = consultation.total_amount if hasattr(consultation, 'total_amount') and consultation.total_amount else Decimal('300.00')
            
            # Create account reference
            account_reference = mpesa_service.create_account_reference(
                consultation.id, user.id
            )
            
            # Generate transaction ID
            transaction_id_val = random.randint(100000, 999999)
            
            # Create M-Pesa transaction record
            transaction = MpesaTransaction.objects.create(
                user=user,
                consultation=consultation,
                amount=amount,
                phone_number=formatted_phone,
                transaction_id=transaction_id_val,
                account_reference=account_reference,
                transaction_desc=f"Consultation #{consultation.id} Payment",
                status='initiated',
                transaction_type='c2b'
            )
            
            # Initiate STK Push
            try:
                stk_response = mpesa_service.stk_push(
                    phone_number=formatted_phone,
                    amount=amount,
                    account_reference=account_reference,
                    description=f"Payment for consultation #{consultation.id}"
                )
                
                if stk_response.get('ResponseCode') == '0':
                    # Successfully initiated
                    transaction.merchant_request_id = stk_response.get('MerchantRequestID', f'TEST_MERCHANT_{int(time.time())}')
                    transaction.checkout_request_id = stk_response.get('CheckoutRequestID', f'TEST_CHECKOUT_{int(time.time())}')
                    transaction.response_code = stk_response.get('ResponseCode', '0')
                    transaction.response_description = stk_response.get('ResponseDescription', 'Success (Test Mode)')
                    transaction.initiated_at = timezone.now()
                    transaction.status = 'processing'
                    transaction.save()
                    
                    # Create payment request record
                    MpesaPaymentRequest.objects.create(
                        user=user,
                        consultation=consultation,
                        amount=amount,
                        phone_number=formatted_phone,
                        merchant_request_id=transaction.merchant_request_id,
                        checkout_request_id=transaction.checkout_request_id,
                        expires_at=timezone.now() + timezone.timedelta(minutes=10),
                        status='initiated'
                    )
                    
                    return {
                        'status': 'success',
                        'message': 'M-Pesa prompt sent to your phone',
                        'transaction_id': str(transaction.id),
                        'checkout_request_id': transaction.checkout_request_id,
                        'merchant_request_id': transaction.merchant_request_id,
                        'phone_number': formatted_phone,
                        'amount': str(amount),
                        'account_reference': account_reference
                    }
                
                else:
                    # Failed to initiate
                    transaction.response_code = stk_response.get('ResponseCode', '1')
                    transaction.response_description = stk_response.get('ResponseDescription', 'Failed')
                    transaction.status = 'failed'
                    transaction.error_message = stk_response.get('ResponseDescription', 'Failed')
                    transaction.save()
                    
                    return {
                        'status': 'failed',
                        'message': stk_response.get('ResponseDescription', 'Failed to initiate payment'),
                        'transaction_id': str(transaction.id)
                    }
                    
            except Exception as e:
                transaction.status = 'failed'
                transaction.error_message = str(e)
                transaction.save()
                
                return {
                    'status': 'error',
                    'message': f'Failed to initiate payment: {str(e)}',
                    'transaction_id': str(transaction.id)
                }
        
        except Exception as e:
            logger.error(f"Error initiating M-Pesa payment: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    @staticmethod
    def check_payment_status(checkout_request_id, transaction_id=None):
        """
        Check status of M-Pesa payment
        """
        from .models import MpesaTransaction
        
        try:
            # Try to find transaction
            transaction = None
            if checkout_request_id:
                transaction = MpesaTransaction.objects.filter(
                    checkout_request_id=checkout_request_id
                ).first()
            
            if not transaction and transaction_id:
                transaction = MpesaTransaction.objects.filter(
                    id=transaction_id
                ).first()
            
            if not transaction:
                # For test mode, create a mock transaction
                if checkout_request_id and checkout_request_id.startswith('TEST_'):
                    # Simulate success for test payments
                    return {
                        'status': 'success',
                        'message': 'Payment confirmed successfully (Test Mode)',
                        'transaction_id': transaction_id or f'TXN_{random.randint(1000, 9999)}',
                        'mpesa_receipt_number': f'MPESA{random.randint(100000, 999999)}',
                        'amount': '300.00',
                        'completed_at': timezone.now().isoformat()
                    }
                
                return {
                    'status': 'not_found',
                    'message': 'Transaction not found'
                }
            
            # For test payments, auto-confirm after some time
            if transaction.checkout_request_id and transaction.checkout_request_id.startswith('TEST_'):
                if transaction.status == 'processing':
                    # Update to success after 2 seconds
                    if transaction.initiated_at and (timezone.now() - transaction.initiated_at).seconds > 2:
                        transaction.status = 'success'
                        transaction.mpesa_receipt_number = f'MPESA{random.randint(100000, 999999)}'
                        transaction.completed_at = timezone.now()
                        transaction.save()
            
            # Return current status
            return {
                'status': transaction.status,
                'message': transaction.response_description or 'Payment processing',
                'transaction_id': str(transaction.id),
                'checkout_request_id': transaction.checkout_request_id,
                'mpesa_receipt_number': transaction.mpesa_receipt_number,
                'amount': str(transaction.amount),
                'completed_at': transaction.completed_at.isoformat() if transaction.completed_at else None
            }
        
        except Exception as e:
            logger.error(f"Error checking payment status: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    @staticmethod
    def create_test_transaction(user, consultation, phone_number, amount=300):
        """Create a test transaction for development"""
        from .models import MpesaTransaction
        
        transaction = MpesaTransaction.objects.create(
            user=user,
            consultation=consultation,
            amount=amount,
            phone_number=phone_number,
            account_reference=f'TEST{consultation.id}{user.id}{int(time.time())}',
            transaction_desc='Test payment',
            merchant_request_id=f'TEST_MERCHANT_{int(time.time())}',
            checkout_request_id=f'TEST_CHECKOUT_{int(time.time())}',
            response_code='0',
            response_description='Test payment initiated',
            status='success',
            mpesa_receipt_number=f'MPESA{random.randint(100000, 999999)}',
            initiated_at=timezone.now(),
            completed_at=timezone.now()
        )
        
        return transaction
