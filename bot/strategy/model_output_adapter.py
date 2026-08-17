"""Phase 1A Sprint 3 -- adapts the existing bare-float predictor outputs
(XGBPredictor.predict_proba, LSTMPredictor.predict_proba, sentiment score)
into the standardized {signal, confidence, metadata} shape
phase1a_requirements.md Section 5 requires for decision_events.model_outputs.

Per-model `signal` here is a documented, explicitly-labeled *informational*
threshold (0.5 for XGB/LSTM probabilities, 0.0 for sentiment's [-1,+1]
scale) -- it is NOT the ensemble's actual trading decision, which uses
different thresholds (STRONG_BUY_THRESHOLD/BUY_THRESHOLD/etc. in
bot.strategy.ensemble) applied to the *combined* weighted score, not any
one model's output in isolation. Conflating the two would misrepresent
what actually drove a BUY/SELL/HOLD action in the audit trail.
"""
from __future__ import annotations


def _prob_signal(prob: float) -> str:
    """XGB/LSTM probabilities are in [0, 1] -- 0.5 is the natural midpoint."""
    if prob > 0.5:
        return "BUY"
    if prob < 0.5:
        return "SELL"
    return "HOLD"


def _sentiment_signal(score: float) -> str:
    """Sentiment is in [-1, +1] -- 0.0 is the natural midpoint."""
    if score > 0.0:
        return "BUY"
    if score < 0.0:
        return "SELL"
    return "HOLD"


def build_model_outputs(
    xgb_prob: float,
    lstm_prob: float,
    sentiment_score: float,
    xgb_drivers: list | None = None,
    lstm_is_degraded: bool = False,
    lstm_val_loss: float | None = None,
    sentiment_headlines: list[str] | None = None,
) -> dict:
    """xgb_drivers: XGBPredictor.explain()'s [(feature_name, shap_value), ...]
    output, if available for this decision -- cast to JSON-safe types here
    since shap values are numpy floats, not native Python floats."""
    shap_drivers = [
        {"feature": str(name), "shap_value": float(value)}
        for name, value in (xgb_drivers or [])
    ]
    return {
        "xgboost": {
            "signal": _prob_signal(xgb_prob),
            "confidence": float(xgb_prob),
            "metadata": {"shap_drivers": shap_drivers},
        },
        "lstm": {
            "signal": _prob_signal(lstm_prob),
            "confidence": float(lstm_prob),
            "metadata": {
                "is_degraded": bool(lstm_is_degraded),
                "val_loss": lstm_val_loss,
            },
        },
        "finbert": {
            "signal": _sentiment_signal(sentiment_score),
            "confidence": float((sentiment_score + 1.0) / 2.0),
            "metadata": {
                "raw_score": float(sentiment_score),
                "headlines": list(sentiment_headlines or []),
            },
        },
    }
