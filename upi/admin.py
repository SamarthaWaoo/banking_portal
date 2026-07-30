from django.contrib import admin
from .models import BankAccount, Transaction


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('account_number', 'user', 'upi_id', 'account_type', 'balance', 'is_active', 'created_at')
    search_fields = ('account_number', 'upi_id', 'user__username')
    list_filter = ('account_type', 'is_active')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('reference_id', 'sender_account', 'receiver_account', 'amount', 'status', 'timestamp')
    search_fields = ('reference_id',)
    list_filter = ('status', 'transaction_type', 'timestamp')
