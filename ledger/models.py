from django.db import models
from decimal import Decimal


class Wallet(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('FROZEN', 'Frozen (Fraud Hold)'),
    ]

    account_holder = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    iban = models.CharField(max_length=34, unique=True)
    currency = models.CharField(max_length=3, default='EUR')
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    country_code = models.CharField(max_length=2, default='DE')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account_holder} ({self.iban}) - €{self.balance}"


class Transaction(models.Model):
    STATUS_CHOICES = [
        ('SETTLED', 'Settled (ACID Verified)'),
        ('BLOCKED_FRAUD', 'Blocked by ML Fraud Engine'),
        ('REJECTED_FUNDS', 'Insufficient Funds'),
    ]

    tx_reference = models.CharField(max_length=32, unique=True)
    idempotency_key = models.CharField(max_length=64, unique=True, db_index=True)
    sender = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name='sent_transactions')
    receiver = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name='received_transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='EUR')
    location_country = models.CharField(max_length=2, default='DE')
    device_fingerprint = models.CharField(max_length=64, default='web-berlin-chrome')
    fraud_risk_score = models.FloatField(default=0.0)
    fraud_reason = models.CharField(max_length=255, default='Clean Velocity & Geo Match')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SETTLED')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tx_reference} | €{self.amount} | {self.status}"


class LedgerEntry(models.Model):
    """
    Immutable Double-Entry Accounting Book:
    Every settled Transaction generates 1 DEBIT row and 1 CREDIT row that sum to 0.00.
    """
    ENTRY_TYPES = [
        ('DEBIT', 'Debit (-)'),
        ('CREDIT', 'Credit (+)'),
    ]

    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='entries')
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name='ledger_entries')
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # Negative for DEBIT, Positive for CREDIT
    balance_after = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.entry_type} €{self.amount} on {self.wallet.iban}"