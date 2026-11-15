# 🛡️ PayGuard — ACID Double-Entry Fintech Ledger & AI Fraud Engine

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django 6.1](https://img.shields.io/badge/Django_6.1_&_DRF-092E20?style=for-the-badge&logo=django&logoColor=white)
![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)
![ACID Ledger](https://img.shields.io/badge/Double--Entry_ACID-10B981?style=for-the-badge&logo=postgresql&logoColor=white)
![Idempotency](https://img.shields.io/badge/Idempotency_Guard-3B82F6?style=for-the-badge&logo=redis&logoColor=white)

**PayGuard** is a production-architected core banking & payment processing engine built with **Python, Django 6.1, Django REST Framework, and Scikit-learn**.

Engineered to solve the three hardest problems in financial software—**balance corruption under concurrency**, **duplicate network charges**, and **account-drain fraud**—PayGuard combines deadlock-safe row-level locking (`select_for_update`), UUID idempotency replay protection, an immutable zero-sum double-entry general ledger, and `<10ms` machine learning fraud interception.

![PayGuard Fintech Command Center](templates/payguard_preview.png)

---

## 🎯 Core Financial Engineering Pillars

| Banking Challenge | Engineering Solution in PayGuard | Implementation Detail |
| :--- | :--- | :--- |
| **Balance Corruption & Race Conditions** | **ACID Row-Level Locking & Double-Entry Bookkeeping** | Locks sender/receiver wallets in deterministic primary-key order (`select_for_update()`) inside `transaction.atomic()` and writes paired `DEBIT` (`-`) and `CREDIT` (`+`) rows that always sum to `€0.00`. |
| **Double-Charging on Network Retries** | **UUID Idempotency Replay Guard** | Tracks unique `Idempotency-Key` headers per payment request; duplicate submissions return the original cached transaction receipt without mutating balances. |
| **Account Takeover & Drain Attacks** | **Real-Time Scikit-learn Fraud Ensemble** | Evaluates every transfer via a `RandomForestClassifier` + `IsolationForest` pipeline across 5 risk features, automatically blocking high-risk transfers (`score >= 72%`) and freezing compromised wallets (`FROZEN`). |

---

## 🏗️ System Architecture

```mermaid
flowchart LR
    subgraph Client ["Fintech Command Center UI"]
        TransferUI[SEPA Instant Transfer Console]
        SimTriggers[Stress-Test & Attack Simulators]
    end

    subgraph Engine ["PayGuard Core (Django 6.1 + DRF)"]
        IdemGuard[Idempotency-Key Deduplicator]
        RowLock["Ordered Row Lock (select_for_update)"]
        MLFraud["Scikit-learn Fraud Engine (RF + IsolationForest)"]
    end

    subgraph Storage ["ACID Relational Storage"]
        Wallets[(SEPA Wallets Table)]
        TxTable[(Transactions Audit Log)]
        Ledger[(Immutable Double-Entry Ledger)]
    end

    TransferUI -->|POST + Idempotency-Key| IdemGuard
    SimTriggers -->|Replay / Fraud Attack| IdemGuard
    IdemGuard -->|New UUID| RowLock
    RowLock -->|Extract Velocity & Geo Features| MLFraud
    MLFraud -->|Risk >= 72%: Freeze Wallet| Wallets
    MLFraud -->|Risk < 72%: Atomic Settlement| Wallets
    RowLock -->|Write Paired DEBIT & CREDIT| Ledger
    RowLock -->|Record Verdict| TxTable