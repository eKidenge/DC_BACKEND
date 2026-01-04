from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import mpesa_views

router = DefaultRouter()
router.register(r'transactions', mpesa_views.MpesaTransactionViewSet, basename='mpesa-transaction')
router.register(r'payment-requests', mpesa_views.MpesaPaymentRequestViewSet, basename='mpesa-request')

urlpatterns = [
    path('', include(router.urls)),
    
    # M-Pesa payment endpoints
    path('initiate/', mpesa_views.MpesaPaymentView.as_view(), name='mpesa-initiate'),
    path('callback/', mpesa_views.MpesaCallbackView.as_view(), name='mpesa-callback'),
    path('status/', mpesa_views.MpesaPaymentView.as_view(), name='mpesa-status'),
    
    # Utility endpoints
    path('balance/', mpesa_views.get_mpesa_balance, name='mpesa-balance'),
    path('active-requests/', mpesa_views.MpesaPaymentRequestViewSet.as_view({'get': 'active'}), name='active-mpesa-requests'),
]