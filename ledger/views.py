import uuid
from decimal import Decimal
from datetime import timedelta
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import Wallet, Transaction, LedgerEntry
from ml_fraud.fraud_engine import score_transaction


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def dashboard_state(request):
    wallets = Wallet.objects.all().order_by('id')
    txs = Transaction.objects.select_related('sender', 'receiver').order_by('-created_at')[:25]
    entries = LedgerEntry.objects.select_related('transaction', 'wallet').order_by('-created_at')[:30]

    ledger_sum = LedgerEntry.objects.aggregate(net=Sum('amount'))['net'] or Decimal('0.00')
    total_volume = Transaction.objects.filter(status='SETTLED').aggregate(vol=Sum('amount'))['vol'] or Decimal('0.00')
    blocked_count = Transaction.objects.filter(status='BLOCKED_FRAUD').count()

    return Response({
        "metrics": {
            "total_settled_volume": float(total_volume),
            "blocked_fraud_count": blocked_count,
            "double_entry_net_sum": float(ledger_sum),
            "acid_integrity_verified": (ledger_sum == Decimal('0.00')),
        },
        "wallets": [
            {
                "id": w.id,
                "account_holder": w.account_holder,
                "email": w.email,
                "iban": w.iban,
                "balance": float(w.balance),
                "country_code": w.country_code,
                "status": w.status,
            }
            for w in wallets
        ],
        "transactions": [
            {
                "tx_reference": t.tx_reference,
                "idempotency_key": t.idempotency_key,
                "sender_name": t.sender.account_holder,
                "sender_iban": t.sender.iban,
                "receiver_name": t.receiver.account_holder,
                "receiver_iban": t.receiver.iban,
                "amount": float(t.amount),
                "location_country": t.location_country,
                "device_fingerprint": t.device_fingerprint,
                "fraud_risk_score": t.fraud_risk_score,
                "fraud_reason": t.fraud_reason,
                "status": t.status,
                "created_at": t.created_at.strftime("%H:%M:%S"),
            }
            for t in txs
        ],
        "ledger_entries": [
            {
                "tx_reference": e.transaction.tx_reference,
                "wallet_holder": e.wallet.account_holder,
                "iban": e.wallet.iban,
                "entry_type": e.entry_type,
                "amount": float(e.amount),
                "balance_after": float(e.balance_after),
                "created_at": e.created_at.strftime("%H:%M:%S"),
            }
            for e in entries
        ]
    })


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def execute_transfer(request):
    sender_id = int(request.data.get('sender_id'))
    receiver_id = int(request.data.get('receiver_id'))
    amount = Decimal(str(request.data.get('amount', '0')))
    idempotency_key = request.data.get('idempotency_key', '').strip() or str(uuid.uuid4())
    location_country = request.data.get('location_country', 'DE').upper()
    device_fingerprint = request.data.get('device_fingerprint', 'web-berlin-chrome')

    if sender_id == receiver_id:
        return Response({"error": "Sender and receiver wallets must be different."}, status=status.HTTP_400_BAD_REQUEST)
    if amount <= Decimal('0.00'):
        return Response({"error": "Transfer amount must be greater than €0.00."}, status=status.HTTP_400_BAD_REQUEST)

    existing_tx = Transaction.objects.filter(idempotency_key=idempotency_key).first()
    if existing_tx:
        return Response({
            "idempotent_replay": True,
            "message": f"Idempotency Guard Triggered! Returning cached receipt for {existing_tx.tx_reference} (Zero double-charge).",
            "tx_reference": existing_tx.tx_reference,
            "status": existing_tx.status,
            "fraud_risk_score": existing_tx.fraud_risk_score,
            "fraud_reason": existing_tx.fraud_reason,
        }, status=status.HTTP_200_OK)

    with transaction.atomic():
        first_id, second_id = sorted([sender_id, receiver_id])
        locked_wallets = {
            w.id: w for w in Wallet.objects.select_for_update().filter(id__in=[first_id, second_id])
        }
        sender = locked_wallets.get(sender_id)
        receiver = locked_wallets.get(receiver_id)

        if not sender or not receiver:
            return Response({"error": "Wallet not found."}, status=status.HTTP_404_NOT_FOUND)

        if sender.status == 'FROZEN':
            return Response({"error": f"Wallet {sender.iban} is FROZEN due to prior security alert. Click 'Unfreeze' first."}, status=status.HTTP_403_FORBIDDEN)

        one_min_ago = timezone.now() - timedelta(minutes=1)
        recent_tx_count = Transaction.objects.filter(sender=sender, created_at__gte=one_min_ago).count()
        is_foreign = 1 if location_country != sender.country_code else 0
        untrusted_device = 1 if 'unrecognized' in device_fingerprint.lower() or 'tor' in device_fingerprint.lower() else 0

        risk_score, reason_str, is_blocked = score_transaction(
            amount=float(amount),
            sender_balance=float(sender.balance),
            recent_tx_count=recent_tx_count,
            is_foreign=is_foreign,
            untrusted_device=untrusted_device,
        )

        tx_ref = f"PG-{uuid.uuid4().hex[:8].upper()}"

        if is_blocked:
            sender.status = 'FROZEN'
            sender.save(update_fields=['status'])
            tx = Transaction.objects.create(
                tx_reference=tx_ref,
                idempotency_key=idempotency_key,
                sender=sender,
                receiver=receiver,
                amount=amount,
                location_country=location_country,
                device_fingerprint=device_fingerprint,
                fraud_risk_score=risk_score,
                fraud_reason=reason_str,
                status='BLOCKED_FRAUD',
            )
            return Response({
                "idempotent_replay": False,
                "message": f"BLOCKED BY AI FRAUD ENGINE (Score: {risk_score}/100) — Wallet {sender.iban} automatically frozen!",
                "tx_reference": tx.tx_reference,
                "status": tx.status,
                "fraud_risk_score": risk_score,
                "fraud_reason": reason_str,
            }, status=status.HTTP_200_OK)

        if sender.balance < amount:
            tx = Transaction.objects.create(
                tx_reference=tx_ref,
                idempotency_key=idempotency_key,
                sender=sender,
                receiver=receiver,
                amount=amount,
                location_country=location_country,
                device_fingerprint=device_fingerprint,
                fraud_risk_score=risk_score,
                fraud_reason="Insufficient Wallet Balance",
                status='REJECTED_FUNDS',
            )
            return Response({"error": "Insufficient funds in sender wallet."}, status=status.HTTP_400_BAD_REQUEST)

        sender.balance -= amount
        receiver.balance += amount
        sender.save(update_fields=['balance'])
        receiver.save(update_fields=['balance'])

        tx = Transaction.objects.create(
            tx_reference=tx_ref,
            idempotency_key=idempotency_key,
            sender=sender,
            receiver=receiver,
            amount=amount,
            location_country=location_country,
            device_fingerprint=device_fingerprint,
            fraud_risk_score=risk_score,
            fraud_reason=reason_str,
            status='SETTLED',
        )

        LedgerEntry.objects.create(
            transaction=tx,
            wallet=sender,
            entry_type='DEBIT',
            amount=-amount,
            balance_after=sender.balance,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            wallet=receiver,
            entry_type='CREDIT',
            amount=amount,
            balance_after=receiver.balance,
        )

    return Response({
        "idempotent_replay": False,
        "message": f"ACID Transfer Settled! {tx.tx_reference} (€{amount})",
        "tx_reference": tx.tx_reference,
        "status": tx.status,
        "fraud_risk_score": risk_score,
        "fraud_reason": reason_str,
    }, status=status.HTTP_201_CREATED)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def toggle_wallet_status(request, wallet_id):
    wallet = Wallet.objects.filter(id=wallet_id).first()
    if not wallet:
        return Response({"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND)
    wallet.status = 'ACTIVE' if wallet.status == 'FROZEN' else 'FROZEN'
    wallet.save(update_fields=['status'])
    return Response({"message": f"Wallet {wallet.iban} is now {wallet.status}", "status": wallet.status})