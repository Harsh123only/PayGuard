import os
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier, IsolationForest

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'fraud_model.joblib')


def train_and_save_model():
    np.random.seed(42)
    # Features: [amount, ratio_to_balance, tx_last_min_count, is_foreign_geo, is_untrusted_device]
    normal_X = np.column_stack([
        np.random.uniform(10, 800, 600),         # normal EUR amounts
        np.random.uniform(0.01, 0.35, 600),      # small fraction of wallet balance
        np.random.randint(0, 3, 600),            # 0-2 tx in last minute
        np.random.choice([0, 1], 600, p=[0.92, 0.08]),
        np.zeros(600)
    ])
    normal_y = np.zeros(600)

    fraud_X = np.column_stack([
        np.random.uniform(1800, 15000, 200),     # high-value drain attempts
        np.random.uniform(0.65, 1.0, 200),       # draining 65%-100% of balance
        np.random.randint(3, 12, 200),           # high velocity burst
        np.random.choice([0, 1], 200, p=[0.2, 0.8]),
        np.random.choice([0, 1], 200, p=[0.3, 0.7])
    ])
    fraud_y = np.ones(200)

    X = np.vstack([normal_X, fraud_X])
    y = np.concatenate([normal_y, fraud_y])

    clf = RandomForestClassifier(n_estimators=80, max_depth=6, random_state=42)
    clf.fit(X, y)

    iso = IsolationForest(contamination=0.15, random_state=42)
    iso.fit(normal_X)

    joblib.dump({'rf': clf, 'iso': iso}, MODEL_PATH)
    return {'rf': clf, 'iso': iso}


_MODELS = None


def get_models():
    global _MODELS
    if _MODELS is None:
        if os.path.exists(MODEL_PATH):
            _MODELS = joblib.load(MODEL_PATH)
        else:
            _MODELS = train_and_save_model()
    return _MODELS


def score_transaction(amount: float, sender_balance: float, recent_tx_count: int, is_foreign: int, untrusted_device: int):
    """
    Returns (risk_score_0_to_100, reason_string, is_blocked_bool)
    """
    models = get_models()
    ratio = min(amount / max(sender_balance, 1.0), 1.5)
    features = np.array([[amount, ratio, recent_tx_count, is_foreign, untrusted_device]])

    rf_prob = float(models['rf'].predict_proba(features)[0][1]) * 100.0
    iso_flag = int(models['iso'].predict(features)[0] == -1)

    score = min(round(rf_prob * 0.8 + (20.0 if iso_flag else 0.0), 1), 99.9)

    reasons = []
    if amount > 2500:
        reasons.append("High-Value Anomaly")
    if ratio > 0.70:
        reasons.append("Account Drain Pattern (>70% Balance)")
    if recent_tx_count >= 3:
        reasons.append(f"Velocity Spike ({recent_tx_count} tx/min)")
    if is_foreign:
        reasons.append("Cross-Border Geo Mismatch")
    if untrusted_device:
        reasons.append("Unrecognized Device Fingerprint")

    reason_str = " + ".join(reasons) if reasons else "Verified Normal Spend Profile"
    is_blocked = score >= 72.0
    return score, reason_str, is_blocked