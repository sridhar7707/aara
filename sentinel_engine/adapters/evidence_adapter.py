"""Translation boundary between bot model-output data and the Sentinel
Evidence contract (ADR-012).

Takes plain data (the shape bot/strategy/model_output_adapter.py's
build_model_outputs() already produces), never a bot type, so this module
has zero import dependency on bot/. All fields are validated here because
this is a system boundary. Per ADR-012, decision_id is never accepted or
required by this adapter; decision linkage is handled separately by
EvidenceService.associate_evidence(decision_id, evidence).
"""
import uuid
from datetime import datetime, timezone

from sentinel_engine.evidence.evidence import Evidence

_REQUIRED_MODELS = ("xgboost", "lstm", "finbert")


def to_evidence_records(model_outputs: dict) -> list[Evidence]:
    missing_models = [model for model in _REQUIRED_MODELS if model not in model_outputs]
    if missing_models:
        raise ValueError(
            f"model_outputs missing required model(s): {', '.join(missing_models)}"
        )

    for model in _REQUIRED_MODELS:
        entry = model_outputs[model]
        if not isinstance(entry, dict):
            raise ValueError(f"model_outputs[{model!r}] must be a dict")

        signal = entry.get("signal")
        if not isinstance(signal, str) or not signal:
            raise ValueError(f"model_outputs[{model!r}]['signal'] must be a non-empty str")

        confidence = entry.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            raise ValueError(f"model_outputs[{model!r}]['confidence'] must be numeric")

        metadata = entry.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError(f"model_outputs[{model!r}]['metadata'] must be a dict")

    return [
        Evidence(
            evidence_id=str(uuid.uuid4()),
            evidence_type="MODEL_OUTPUT",
            source=model,
            data=dict(model_outputs[model]),
            collected_at=datetime.now(timezone.utc),
        )
        for model in _REQUIRED_MODELS
    ]
