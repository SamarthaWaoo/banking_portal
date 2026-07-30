from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'customer_id', 'email', 'phone_number', 'is_kyc_verified', 'created_at')
    search_fields = ('username', 'customer_id', 'email', 'pan_number', 'phone_number')
    fieldsets = UserAdmin.fieldsets + (
        ('KYC Details', {
            'fields': ('pan_number', 'aadhaar_number', 'phone_number', 'date_of_birth',
                       'customer_id', 'is_kyc_verified')
        }),
    )
    readonly_fields = ('customer_id',)


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.site_header = "SpendSmart Bank Admin"
admin.site.site_title = "SpendSmart Bank Admin Portal"
admin.site.index_title = "Bank Operations Dashboard"
