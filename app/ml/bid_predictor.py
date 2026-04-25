"""
ML Bid Predictor — trains a RandomForest on historical keyword performance
to predict the optimal CPC bid for each keyword.

Falls back to CPA-rule-based logic if fewer than MIN_SAMPLES records exist.
"""
import logging
import os
import pickle
from datetime import date, timedelta

import numpy as np

logger = logging.getLogger(__name__)

MODEL_PATH = "models/bid_predictor.pkl"
MIN_SAMPLES = 50
MICROS = 1_000_000


# ── Feature encoding ──────────────────────────────────────────
MATCH_TYPE_MAP = {"BROAD": 0, "PHRASE": 1, "EXACT": 2, "BROAD_MATCH_MODIFIER": 0}
DEVICE_MAP = {"DESKTOP": 0, "MOBILE": 1, "TABLET": 2, "CONNECTED_TV": 3}
DAY_MAP = {
    "MONDAY": 0, "TUESDAY": 1, "WEDNESDAY": 2, "THURSDAY": 3,
    "FRIDAY": 4, "SATURDAY": 5, "SUNDAY": 6,
}


def _build_features(row: dict) -> list[float]:
    """Convert a keyword performance row into a feature vector."""
    clicks = max(row.get("clicks", 0), 1)
    impressions = max(row.get("impressions", 0), 1)
    conversions = row.get("conversions", 0)

    return [
        row.get("hour", 12),
        DAY_MAP.get(str(row.get("day_of_week", "MONDAY")).upper(), 0),
        DEVICE_MAP.get(str(row.get("device", "DESKTOP")).upper(), 0),
        MATCH_TYPE_MAP.get(str(row.get("match_type", "BROAD")).upper(), 0),
        clicks / impressions,                           # ctr
        conversions / clicks,                           # conv_rate
        row.get("cost_micros", 0) / MICROS / clicks,   # actual cpc usd
        row.get("impressions", 0),
        row.get("clicks", 0),
        row.get("conversions", 0),
    ]


def train_model(db) -> bool:
    """
    Train a RandomForest on historical keyword data from the DB.
    Returns True if training succeeded, False if not enough data.
    """
    try:
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline
        from app.db.models import QualityScoreHistory, PerformanceSnapshot
    except ImportError:
        logger.error("scikit-learn not installed — cannot train ML model")
        return False

    # Pull historical keyword snapshots enriched with QS data
    qs_rows = db.query(QualityScoreHistory).filter(
        QualityScoreHistory.clicks > 0
    ).all()

    if len(qs_rows) < MIN_SAMPLES:
        logger.info(
            "ML training skipped — only %d samples (need %d)",
            len(qs_rows), MIN_SAMPLES
        )
        return False

    X, y = [], []
    for row in qs_rows:
        clicks = max(row.clicks, 1)
        impressions = max(row.clicks * 10, 1)  # estimate impressions
        conversions = row.cost_micros / MICROS / max(row.cost_micros / MICROS / max(row.clicks, 1) * 20, 1)

        features = [
            12,  # hour (unknown from daily snapshot)
            0,   # day
            0,   # device
            MATCH_TYPE_MAP.get(str(row.match_type or "BROAD").upper(), 0),
            row.clicks / impressions,
            0,   # conv rate estimate
            row.cost_micros / MICROS / clicks,
            row.clicks,
            row.clicks,
            0,
        ]
        # Target: actual CPC in micros
        target = row.cost_micros / max(row.clicks, 1)
        X.append(features)
        y.append(target)

    X = np.array(X, dtype=float)
    y = np.array(y, dtype=float)

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("regressor", GradientBoostingRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            random_state=42,
        )),
    ])

    model.fit(X, y)

    os.makedirs("models", exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    logger.info("ML model trained on %d samples, saved to %s", len(X), MODEL_PATH)
    return True


def load_model():
    if not os.path.exists(MODEL_PATH):
        return None
    try:
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        logger.error("Failed to load ML model: %s", e)
        return None


def predict_optimal_bid(row: dict, target_cpa_usd: float = 15.0) -> dict:
    """
    Predict the optimal CPC bid for a keyword row.
    Returns dict with predicted_bid_micros, confidence, method.
    """
    model = load_model()

    if model is not None:
        try:
            features = np.array([_build_features(row)], dtype=float)
            predicted_cpc_micros = float(model.predict(features)[0])
            predicted_cpc_micros = max(10_000, min(predicted_cpc_micros, 50_000_000))

            conv_rate = row.get("conversions", 0) / max(row.get("clicks", 1), 1)
            predicted_cpa = (predicted_cpc_micros / MICROS) / max(conv_rate, 0.001)

            return {
                "predicted_bid_micros": int(predicted_cpc_micros),
                "predicted_cpa": round(predicted_cpa, 2),
                "confidence": 0.80,
                "method": "ml_gradient_boost",
            }
        except Exception as e:
            logger.warning("ML prediction failed, falling back to rules: %s", e)

    # ── Fallback: CPA-based rule logic ──────────────────────
    cost = row.get("cost_micros", 0) / MICROS
    conversions = row.get("conversions", 0)
    current_bid = row.get("cpc_bid_micros", 500_000)

    if conversions > 0:
        actual_cpa = cost / conversions
        ratio = target_cpa_usd / actual_cpa
        predicted_bid = int(current_bid * ratio)
    else:
        predicted_bid = int(current_bid * 0.85)

    predicted_bid = max(50_000, min(predicted_bid, 20_000_000))

    return {
        "predicted_bid_micros": predicted_bid,
        "predicted_cpa": target_cpa_usd,
        "confidence": 0.50,
        "method": "cpa_rule_fallback",
    }
