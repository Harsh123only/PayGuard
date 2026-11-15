import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payguard_core.settings')
django.setup()

from ledger.models import Wallet
from ml_fraud.fraud_engine import get_models

# Pre-train the Scikit-learn RandomForest + IsolationForest model on first seed
get_models()

wallets = [
    {
        "account_holder": "Harsh Treasury Vault (Berlin HQ)",
        "email": "treasury@payguard.de",
        "iban": "DE89 3704 0044 0532 0130 00",
        "balance": Decimal("25000.00"),
        "country_code": "DE",
    },
    {
        "account_holder": "N26 Merchant Settlement Pool",
        "email": "settlement@n26-partner.de",
        "iban": "DE44 1001 1001 2620 4910 88",
        "balance": Decimal("14200.00"),
        "country_code": "DE",
    },
    {
        "account_holder": "Solaris Corporate Expense Card",
        "email": "ops@solaris-corp.de",
        "iban": "DE91 1102 2233 0088 7766 55",
        "balance": Decimal("6850.00"),
        "country_code": "DE",
    },
    {
        "account_holder": "Nordic SaaS Vendor Escrow",
        "email": "billing@nordicsaas.se",
        "iban": "DE19 5001 0517 5408 3321 09",
        "balance": Decimal("9400.00"),
        "country_code": "DE",
    },
]

for w in wallets:
    Wallet.objects.get_or_create(iban=w["iban"], defaults=w)

print("PayGuard Seeded: 4 European SEPA Wallets & Scikit-learn Fraud Model Ready!")