from django.contrib import admin
from .models import (
    Payment, Transaction, Payout, 
    ProfessionalEarning, Coupon, PaymentConfig
)

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'amount', 'currency', 'status', 'created_at']
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['user__email', 'user__username', 'stripe_payment_intent_id']
    readonly_fields = ['created_at', 'updated_at', 'paid_at']
    list_per_page = 20

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'amount', 'transaction_type', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['user__email', 'stripe_transaction_id']
    readonly_fields = ['created_at', 'effective_at']
    list_per_page = 20

@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ['id', 'professional', 'amount', 'status', 'created_at', 'paid_at']
    list_filter = ['status', 'created_at', 'paid_at']
    search_fields = ['professional__user__email', 'stripe_payout_id']
    readonly_fields = ['created_at', 'paid_at']
    list_per_page = 20

@admin.register(ProfessionalEarning)
class ProfessionalEarningAdmin(admin.ModelAdmin):
    list_display = ['id', 'professional', 'net_amount', 'is_paid_out', 'created_at']
    list_filter = ['is_paid_out', 'created_at']
    search_fields = ['professional__user__email']
    readonly_fields = ['created_at', 'paid_out_at']
    list_per_page = 20

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'discount_value', 'is_active', 'is_valid', 'uses_count']
    list_filter = ['is_active', 'discount_type']
    search_fields = ['code']
    filter_horizontal = ['categories', 'professionals']
    list_per_page = 20
    
    def is_valid(self, obj):
        return obj.is_valid
    is_valid.boolean = True

@admin.register(PaymentConfig)
class PaymentConfigAdmin(admin.ModelAdmin):
    list_display = ['key', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['key', 'description']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 20