from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import mpesa_views
from . import mpesa_urls

router = DefaultRouter()
router.register(r'payments', views.PaymentViewSet, basename='payment')
router.register(r'payouts', views.PayoutViewSet, basename='payout')
router.register(r'coupons', views.CouponViewSet, basename='coupon')

urlpatterns = [
    # Stripe payments
    path('stripe/', include([
        path('', include(router.urls)),
        path('webhook/', views.PaymentWebhookView.as_view(), name='payment-webhook'),
        path('payment-methods/', views.PaymentMethodsView.as_view(), name='payment-methods'),
        path('create-payment-intent/', views.PaymentViewSet.as_view({'post': 'create_payment_intent'}), name='create-payment-intent'),
        path('confirm-payment/', views.PaymentViewSet.as_view({'post': 'confirm_payment'}), name='confirm-payment'),
    ])),
    
    # M-Pesa payments
    path('mpesa/', include(mpesa_urls)),
]