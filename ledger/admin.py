from django.contrib import admin
from .models import Wallet, Transaction, LedgerEntry


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['account_holder', 'iban', 'balance', 'currency', 'country_code', 'status']
    list_filter = ['status', 'country_code']
    search_fields = ['account_holder', 'iban', 'email']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['tx_reference', 'sender', 'receiver', 'amount', 'fraud_risk_score', 'status', 'created_at']
    list_filter = ['status', 'location_country']
    search_fields = ['tx_reference', 'idempotency_key']


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ['transaction', 'wallet', 'entry_type', 'amount', 'balance_after', 'created_at']
    list_filter = ['entry_type']