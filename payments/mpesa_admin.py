from django.contrib import admin
from .models import (
    MpesaTransaction, MpesaPaymentRequest, 
    MpesaCallback, MpesaConfiguration, 
    MpesaAccessToken, MpesaBusinessTill
)

@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'amount', 'phone_number', 
        'status', 'created_at', 'mpesa_receipt_number'
    ]
    list_filter = ['status', 'transaction_type', 'created_at']
    search_fields = [
        'user__email', 'user__username', 
        'phone_number', 'mpesa_receipt_number',
        'merchant_request_id', 'checkout_request_id'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'initiated_at', 
        'completed_at', 'transaction_date'
    ]
    list_per_page = 50
    
    actions = ['mark_as_success', 'mark_as_failed']
    
    def mark_as_success(self, request, queryset):
        queryset.update(status='success')
        self.message_user(request, f"{queryset.count()} transactions marked as successful")
    mark_as_success.short_description = "Mark selected as successful"
    
    def mark_as_failed(self, request, queryset):
        queryset.update(status='failed')
        self.message_user(request, f"{queryset.count()} transactions marked as failed")
    mark_as_failed.short_description = "Mark selected as failed"

@admin.register(MpesaPaymentRequest)
class MpesaPaymentRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'amount', 'phone_number', 
        'status', 'created_at', 'expires_at', 'is_active'
    ]
    list_filter = ['status', 'is_active', 'created_at']
    search_fields = ['user__email', 'phone_number', 'checkout_request_id']
    readonly_fields = ['created_at', 'updated_at', 'expires_at']
    list_per_page = 50

@admin.register(MpesaCallback)
class MpesaCallbackAdmin(admin.ModelAdmin):
    list_display = ['id', 'callback_type', 'received_at', 'processed']
    list_filter = ['callback_type', 'processed', 'received_at']
    search_fields = ['callback_type']
    readonly_fields = ['received_at', 'processed_at']
    list_per_page = 50

@admin.register(MpesaConfiguration)
class MpesaConfigurationAdmin(admin.ModelAdmin):
    list_display = ['name', 'config_type', 'is_active', 'business_short_code']
    list_filter = ['config_type', 'is_active']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return ['created_at', 'updated_at', 'consumer_key', 'consumer_secret', 'passkey']
        return ['created_at', 'updated_at']

@admin.register(MpesaAccessToken)
class MpesaAccessTokenAdmin(admin.ModelAdmin):
    list_display = ['id', 'expires_in', 'generated_at', 'is_valid']
    readonly_fields = ['generated_at']
    list_per_page = 10
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(MpesaBusinessTill)
class MpesaBusinessTillAdmin(admin.ModelAdmin):
    list_display = ['till_number', 'business_name', 'category', 'is_active']
    list_filter = ['is_active', 'category']
    search_fields = ['till_number', 'business_name']

# Register in main admin.py
from .admin import admin_site

admin_site.register(MpesaTransaction, MpesaTransactionAdmin)
admin_site.register(MpesaPaymentRequest, MpesaPaymentRequestAdmin)
admin_site.register(MpesaCallback, MpesaCallbackAdmin)
admin_site.register(MpesaConfiguration, MpesaConfigurationAdmin)
admin_site.register(MpesaAccessToken, MpesaAccessTokenAdmin)
admin_site.register(MpesaBusinessTill, MpesaBusinessTillAdmin)