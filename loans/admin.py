from django.contrib import admin
from .models import LoanApplication


@admin.register(LoanApplication)
class LoanApplicationAdmin(admin.ModelAdmin):
    list_display = ('application_id', 'user', 'loan_type', 'loan_amount', 'status', 'dti_ratio', 'applied_at')
    search_fields = ('application_id', 'user__username')
    list_filter = ('status', 'loan_type')
