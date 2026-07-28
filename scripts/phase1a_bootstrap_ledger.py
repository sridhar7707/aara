"""Phase 1A Sprint 1 -- one-time bootstrap of the Trust Ledger's reference
chain (model_artifacts -> model_training_runs -> strategy_versions ->
risk_rulesets -> deployment_manifests -> PROMOTED), so decision_events has
a deployment_manifest_id to reference (its FK is NOT NULL).

Idempotent: does nothing if active_deployment_pointer already has a row.

KNOWN GAP, deliberately not silently worked around: models/validation_report.json
(and models/hf_fresh/validation_report.json) both predate the currently-deployed
model files -- their feature_cols/AUC describe an older model version, not the
2026-07-23 retrain actually on disk (verified independently: the live
xgb_predictor.pkl's feature_names_in_ exactly matches bot.strategy.features
.FEATURE_COLS_V4, which neither validation_report.json's feature list matches).
Per user decision (2026-07-28): bootstrap now with the mismatched metrics
explicitly labeled stale, rather than block on a full retrain (scripts/train_model.py
would replace the live model weights, a much bigger action than "update a report").
Checksum/size/mtime are computed fresh from the real files and are accurate;
only the AUC/val_loss/feature_cols historical numbers are flagged as stale.
Re-run scripts/train_model.py and this bootstrap's follow-up (not yet built --
Phase 1A doesn't yet support re-bootstrapping after a retrain) when accurate
metrics are needed.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xgboost  # noqa: E402
from loguru import logger  # noqa: E402

import ledger.ledger as ledger_svc  # noqa: E402
from bot.strategy.ensemble import (  # noqa: E402
    WEIGHTS, STRONG_BUY_THRESHOLD, BUY_THRESHOLD, SELL_THRESHOLD,
    STRONG_SELL_THRESHOLD, STRONG_BUY_FRACTION, BUY_FRACTION,
)
from bot.strategy.features import FEATURE_COLS_V4  # noqa: E402
from bot.strategy.xgb_predictor import FORWARD_PERIODS as XGB_FORWARD_PERIODS  # noqa: E402
from bot.trust_ledger.connection import get_ledger_conn  # noqa: E402
from bot.trust_ledger.ids import new_approval_id, new_cost_model_id  # noqa: E402
from config import (  # noqa: E402
    MAX_POSITION_PCT, DAILY_LOSS_LIMIT_PCT, WEEKLY_LOSS_LIMIT_PCT,
    PORTFOLIO_DRAWDOWN_LIMIT_PCT, MAX_POSITIONS, MAX_SECTOR_POSITIONS,
    MAX_SECTOR_EXPOSURE_PCT,
)

MANIFEST_ID = "production_v1_manifest"
STRATEGY_VERSION_ID = "ensemble_v4_2026_07_23"
RISK_RULESET_ID = "risk_v1_2026_07_28"
FEATURE_PIPELINE_VERSION = "features_v4"

_STALE_METRICS_NOTE = (
    "STALE: models/validation_report.json predates the currently-deployed "
    "model file (mtime-verified). Its feature_cols do not match the live "
    "model's feature_names_in_ (independently checked). These numbers "
    "describe an older model version, kept here for historical reference "
    "only -- do not treat as this training run's actual accuracy. "
    "Regenerate via scripts/train_model.py for accurate metrics."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_checksum_and_size(path: str) -> tuple[str, int]:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest(), os.path.getsize(path)


def _file_mtime_iso(path: str) -> str:
    return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).isoformat()


def _load_stale_validation_report() -> dict:
    path = "models/validation_report.json"
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def already_bootstrapped(conn) -> bool:
    row = conn.execute("SELECT 1 FROM active_deployment_pointer LIMIT 1").fetchone()
    return row is not None


def bootstrap(db_path: str | None = None, close: bool = True):
    """Runs the bootstrap. db_path/close are test seams (default path,
    closes its own connection, when called as a script)."""
    from bot.trust_ledger.connection import DEFAULT_LEDGER_DB_PATH
    conn = get_ledger_conn(db_path or DEFAULT_LEDGER_DB_PATH)
    if already_bootstrapped(conn):
        logger.info("Trust Ledger already bootstrapped (active_deployment_pointer has a row) -- skipping.")
        if close:
            conn.close()
            return None
        return conn

    now = _utc_now()
    stale_report = _load_stale_validation_report()

    # ── Group B: model_artifacts ────────────────────────────────────────────
    feature_set_hash = hashlib.sha256(",".join(FEATURE_COLS_V4).encode("utf-8")).hexdigest()

    xgb_artifact_id = "xgboost_v4"
    lstm_artifact_id = "lstm_v4"
    conn.execute(
        "INSERT INTO model_artifacts (artifact_id, model_family, version_label, "
        "architecture_notes, feature_set_hash, created_at) VALUES (?,?,?,?,?,?)",
        (xgb_artifact_id, "xgboost", "v4", "XGBClassifier, FORWARD_PERIODS=21 (medium-term)",
         feature_set_hash, now),
    )
    conn.execute(
        "INSERT INTO model_artifacts (artifact_id, model_family, version_label, "
        "architecture_notes, feature_set_hash, created_at) VALUES (?,?,?,?,?,?)",
        (lstm_artifact_id, "lstm", "v4", "Sequence model, SEQ_LEN=20", feature_set_hash, now),
    )

    # ── Group B: model_training_runs ────────────────────────────────────────
    xgb_path = "models/saved/xgb_predictor.pkl"
    lstm_path = "models/saved/lstm_predictor.pt"
    xgb_checksum, xgb_size = _file_checksum_and_size(xgb_path)
    lstm_checksum, lstm_size = _file_checksum_and_size(lstm_path)
    xgb_created_at = _file_mtime_iso(xgb_path)
    lstm_created_at = _file_mtime_iso(lstm_path)

    xgb_run_id = f"train_{xgb_created_at[:10].replace('-', '')}_xgb"
    lstm_run_id = f"train_{lstm_created_at[:10].replace('-', '')}_lstm"

    # training_data_start/end are NOT NULL columns with no "unknown" sentinel
    # defined by the schema -- stale_report's date_range is the only source
    # available, so it's used, but every field derived from stale_report is
    # also duplicated inside validation_metrics.status so a reader hitting
    # this row directly (not just the metrics JSON) still sees the caveat.
    training_data_start = stale_report.get("date_range", {}).get("from", "UNKNOWN")
    training_data_end = stale_report.get("date_range", {}).get("to", "UNKNOWN")

    xgb_metrics = {
        "status": _STALE_METRICS_NOTE,
        "reported_xgb_val_auc": stale_report.get("xgb_val_auc"),
        "reported_feature_cols": stale_report.get("feature_cols"),
        "reported_training_data_range": [training_data_start, training_data_end],
        "forward_periods": XGB_FORWARD_PERIODS,
        "trained_at_caveat": "trained_at/artifact_created_at below are both the artifact "
                              "file's filesystem mtime, not a genuine training-completion "
                              "timestamp -- no trustworthy trained_at source exists (see status).",
    }
    lstm_metrics = {
        "status": _STALE_METRICS_NOTE,
        "reported_lstm_val_loss": stale_report.get("lstm_val_loss"),
        "reported_feature_cols": stale_report.get("feature_cols"),
        "reported_training_data_range": [training_data_start, training_data_end],
        "trained_at_caveat": "trained_at/artifact_created_at below are both the artifact "
                              "file's filesystem mtime, not a genuine training-completion "
                              "timestamp -- no trustworthy trained_at source exists (see status).",
    }

    conn.execute(
        "INSERT INTO model_training_runs (training_run_id, artifact_id, training_data_start, "
        "training_data_end, validation_metrics, trained_at, artifact_storage_ref, "
        "artifact_checksum, artifact_size_bytes, artifact_created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (xgb_run_id, xgb_artifact_id, training_data_start, training_data_end, json.dumps(xgb_metrics),
         xgb_created_at, xgb_path, xgb_checksum, xgb_size, xgb_created_at),
    )
    conn.execute(
        "INSERT INTO model_training_runs (training_run_id, artifact_id, training_data_start, "
        "training_data_end, validation_metrics, trained_at, artifact_storage_ref, "
        "artifact_checksum, artifact_size_bytes, artifact_created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (lstm_run_id, lstm_artifact_id, training_data_start, training_data_end, json.dumps(lstm_metrics),
         lstm_created_at, lstm_path, lstm_checksum, lstm_size, lstm_created_at),
    )

    # ── Group B: strategy_versions ──────────────────────────────────────────
    strategy_rules = {
        "weights": WEIGHTS,
        "strong_buy_threshold": STRONG_BUY_THRESHOLD,
        "buy_threshold": BUY_THRESHOLD,
        "sell_threshold": SELL_THRESHOLD,
        "strong_sell_threshold": STRONG_SELL_THRESHOLD,
        "strong_buy_fraction": STRONG_BUY_FRACTION,
        "buy_fraction": BUY_FRACTION,
    }
    conn.execute(
        "INSERT INTO strategy_versions (strategy_version_id, rules, created_at, notes) VALUES (?,?,?,?)",
        (STRATEGY_VERSION_ID, json.dumps(strategy_rules), now,
         "Snapshot of bot.strategy.ensemble constants at Phase 1A bootstrap time."),
    )

    # ── Group B: risk_rulesets ───────────────────────────────────────────────
    risk_rules = {
        "max_position_pct": MAX_POSITION_PCT,
        "daily_loss_limit_pct": DAILY_LOSS_LIMIT_PCT,
        "weekly_loss_limit_pct": WEEKLY_LOSS_LIMIT_PCT,
        "portfolio_drawdown_limit_pct": PORTFOLIO_DRAWDOWN_LIMIT_PCT,
        "max_positions": MAX_POSITIONS,
        "max_sector_positions": MAX_SECTOR_POSITIONS,
        "max_sector_exposure_pct": MAX_SECTOR_EXPOSURE_PCT,
    }
    conn.execute(
        "INSERT INTO risk_rulesets (risk_ruleset_id, rules, created_at) VALUES (?,?,?)",
        (RISK_RULESET_ID, json.dumps(risk_rules), now),
    )

    # ── Group A: cost_models (hash-chained) ─────────────────────────────────
    cost_model_id = new_cost_model_id("v1")
    ledger_svc.append_ledger_row(conn, "cost_models", {
        "cost_model_id": cost_model_id,
        "spread_assumption": 0.001,
        "slippage_assumption": 0.001,
        "commission_rules": {"model": "zero_commission_retail_broker"},
        "tax_assumptions": {"status": "placeholder pending tax-professional review"},
        "created_at": now,
    })

    # ── Group B: deployment_manifests ───────────────────────────────────────
    runtime_environment = {
        "python": platform.python_version(),
        "xgboost_lib_version": xgboost.__version__,
        "random_seed": 42,
    }
    conn.execute(
        "INSERT INTO deployment_manifests (manifest_id, component_training_runs, risk_ruleset_id, "
        "strategy_version_id, feature_pipeline_version, runtime_environment, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (MANIFEST_ID, json.dumps({"xgboost": xgb_run_id, "lstm": lstm_run_id}),
         RISK_RULESET_ID, STRATEGY_VERSION_ID, FEATURE_PIPELINE_VERSION,
         json.dumps(runtime_environment), now),
    )
    conn.commit()

    # ── Manifest lifecycle: CREATED -> ... -> PROMOTED ──────────────────────
    ledger_svc.transition_manifest(conn, MANIFEST_ID, "CREATED", now)
    ledger_svc.transition_manifest(conn, MANIFEST_ID, "TESTING_STARTED", now)
    ledger_svc.transition_manifest(conn, MANIFEST_ID, "REVIEW_REQUESTED", now)

    approval_id = new_approval_id()
    ledger_svc.append_ledger_row(conn, "approval_events", {
        "approval_id": approval_id,
        "timestamp": now,
        "subject_type": "MANIFEST_PROMOTION",
        "subject_id": MANIFEST_ID,
        "decision": "APPROVE",
        "reason_checklist": {
            "known_metrics_gap": "validation_report.json is stale -- see model_training_runs.validation_metrics",
        },
        "reason_comment": "Phase 1A bootstrap: promoting the already-deployed model for ledger integration, not a new model.",
        "reviewer": "phase1a_bootstrap_script",
    })
    ledger_svc.transition_manifest(conn, MANIFEST_ID, "APPROVED", now, approval_event_id=approval_id)
    ledger_svc.transition_manifest(conn, MANIFEST_ID, "PROMOTED", now)

    logger.info(f"Trust Ledger bootstrapped: manifest={MANIFEST_ID} PROMOTED, active_deployment_pointer set.")
    if close:
        conn.close()
        return None
    return conn


if __name__ == "__main__":
    bootstrap()
