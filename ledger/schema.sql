-- Phase 0 Decision Intelligence Foundation schema.
-- Implements docs/architecture/phase0_data_model.md v1.5, Section 5.
--
-- v1.5 (post-freeze exception, phase0_decisions.md #16): risk_evaluation_events
-- .position_sizing_applied split into recommended_position_size + actual_position_size --
-- one field couldn't hold both "what the governor would have done" and "what
-- actually happened," which differ by design throughout Observation Mode (FR-1.10a).
--
-- 16 tables total: 8 Immutable Trust Ledger (Group A, hash-chained,
-- append-only, zero exceptions as of v1.2) + 5 Versioned Reference Records
-- (Group B, append-only by trigger, no hash chain) + 3 Operational Tables
-- (Group C, mutable) -- plus the decision_state VIEW (Section 5.1a),
-- which replaces the v1.1 stored decision_events.outcome_state column.
--
-- CREATE TABLE statements are ordered in valid dependency topological order
-- (v1.2 data model doc changelog): reference tables with no FK dependencies
-- first, through tables that reference them, to operational tables last.
--
-- v1.3: deployment_manifest_events gets its own event_id; active_deployment_pointer
-- represents "no active deployment" as row absence, active_manifest_id stays NOT NULL.
--
-- v1.4: candidate provenance (FR-0.1a/FR-0.13) is now DB-enforced, not just a
-- code comment -- see trg_decision_events_requires_completed_evaluation below.
--
-- v1.5.1 (Phase 1A addition, phase1a_requirements.md Section 13a):
-- constitution_enforcement_events added as an 8th Group A table -- it did not
-- exist in the Phase 0 freeze, added per the same "genuine, documented
-- exception" process as v1.5's risk_evaluation_events split.

PRAGMA foreign_keys = ON;

-- ============================================================================
-- Group B: Versioned Reference Records (append-only by trigger, no hash
-- chain). Created first -- decision_events (Group A) has a real FK to
-- deployment_manifests.
-- ============================================================================

CREATE TABLE IF NOT EXISTS model_artifacts (
    artifact_id          TEXT PRIMARY KEY,
    model_family         TEXT NOT NULL,
    version_label        TEXT NOT NULL,
    architecture_notes   TEXT,
    feature_set_hash     TEXT NOT NULL,
    created_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_versions (
    strategy_version_id  TEXT PRIMARY KEY,
    rules                TEXT NOT NULL,   -- JSON
    created_at           TEXT NOT NULL,
    notes                TEXT
);

CREATE TABLE IF NOT EXISTS risk_rulesets (
    risk_ruleset_id  TEXT PRIMARY KEY,
    rules            TEXT NOT NULL,   -- JSON, includes Risk Governor threshold config
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_training_runs (
    training_run_id       TEXT PRIMARY KEY,
    artifact_id           TEXT NOT NULL REFERENCES model_artifacts(artifact_id),
    training_data_start   TEXT NOT NULL,
    training_data_end     TEXT NOT NULL,
    validation_metrics    TEXT NOT NULL,   -- JSON
    trained_at            TEXT NOT NULL,
    artifact_storage_ref  TEXT NOT NULL,
    artifact_checksum     TEXT NOT NULL,
    artifact_size_bytes   INTEGER NOT NULL,   -- v1.2: cheap second signal alongside checksum
    artifact_created_at   TEXT NOT NULL       -- v1.2: filesystem timestamp, distinct from trained_at
);

CREATE TABLE IF NOT EXISTS deployment_manifests (
    manifest_id              TEXT PRIMARY KEY,
    component_training_runs  TEXT NOT NULL,   -- JSON {xgboost: training_run_id, ...}
    risk_ruleset_id          TEXT NOT NULL REFERENCES risk_rulesets(risk_ruleset_id),
    strategy_version_id      TEXT NOT NULL REFERENCES strategy_versions(strategy_version_id),
    feature_pipeline_version TEXT NOT NULL,   -- v1.2: promoted out of runtime_environment JSON
    runtime_environment      TEXT NOT NULL,   -- JSON {python, xgboost_lib_version, random_seed}
    created_at               TEXT NOT NULL
);

-- ============================================================================
-- Group A: Immutable Trust Ledger (hash-chained, append-only, zero
-- exceptions as of v1.2 -- decision_events.outcome_state removed; lifecycle
-- state is now the decision_state VIEW below, Section 5.1a)
-- ============================================================================

CREATE TABLE IF NOT EXISTS candidate_evaluation_events (
    sequence_number             INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_event_id          TEXT NOT NULL UNIQUE,
    timestamp                   TEXT NOT NULL,
    asset                       TEXT NOT NULL,
    screening_version           TEXT NOT NULL,
    screening_results           TEXT NOT NULL,   -- JSON
    data_available              INTEGER NOT NULL,   -- bool
    required_models_available   INTEGER NOT NULL,   -- bool
    evaluation_requested        INTEGER NOT NULL,   -- bool
    evaluation_completed        INTEGER NOT NULL,   -- bool, v1.2 (FR-0.13): distinct from
                                                     -- evaluation_requested -- a crashed/partial
                                                     -- evaluation must never look like a genuine
                                                     -- qualified rejection (FR-0.1a)
    record_hash                 TEXT NOT NULL,
    previous_record_hash        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cost_models (
    sequence_number      INTEGER PRIMARY KEY AUTOINCREMENT,
    cost_model_id        TEXT NOT NULL UNIQUE,
    spread_assumption    REAL NOT NULL,
    slippage_assumption  REAL NOT NULL,
    commission_rules     TEXT NOT NULL,   -- JSON
    tax_assumptions      TEXT NOT NULL,   -- JSON
    created_at           TEXT NOT NULL,
    record_hash          TEXT NOT NULL,
    previous_record_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approval_events (
    sequence_number      INTEGER PRIMARY KEY AUTOINCREMENT,
    approval_id          TEXT NOT NULL UNIQUE,
    timestamp            TEXT NOT NULL,
    subject_type         TEXT NOT NULL,   -- WEIGHT_CHANGE / MANIFEST_PROMOTION / EXPERIMENT_PROMOTION / RISK_RULE_CHANGE / CAPITAL_INCREASE
    subject_id           TEXT NOT NULL,
    decision             TEXT NOT NULL,   -- APPROVE / REJECT / DEFER
    reason_checklist     TEXT NOT NULL,   -- JSON
    reason_comment       TEXT NOT NULL,
    reviewer             TEXT NOT NULL,
    record_hash          TEXT NOT NULL,
    previous_record_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_events (
    sequence_number         INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id             TEXT NOT NULL UNIQUE,
    candidate_event_id      TEXT NOT NULL REFERENCES candidate_evaluation_events(candidate_event_id),
    timestamp               TEXT NOT NULL,
    asset                   TEXT NOT NULL,
    action                  TEXT NOT NULL,       -- BUY / SELL / HOLD / REJECT
    event_type              TEXT NOT NULL,       -- EXECUTED / QUALIFIED_REJECTION
    portfolio_snapshot      TEXT NOT NULL,       -- JSON
    market_context          TEXT NOT NULL,       -- JSON
    model_outputs           TEXT NOT NULL,       -- JSON
    risk_checks             TEXT NOT NULL,       -- JSON
    final_confidence        REAL NOT NULL CHECK (final_confidence >= 0.0 AND final_confidence <= 1.0),  -- v1.2
    deployment_manifest_id  TEXT NOT NULL REFERENCES deployment_manifests(manifest_id),
    intent                  TEXT NOT NULL,       -- JSON {primary_intent, contributing_modules[]}
    data_completeness       TEXT NOT NULL,       -- JSON {status, missing_inputs[], stale_inputs[]}
    record_hash             TEXT NOT NULL,
    previous_record_hash    TEXT NOT NULL
    -- No outcome_state column (v1.2) -- decision_events is immutable with
    -- zero exceptions. Lifecycle state is derived by decision_state below.
);

CREATE TABLE IF NOT EXISTS decision_outcome_events (
    sequence_number      INTEGER PRIMARY KEY AUTOINCREMENT,
    outcome_id           TEXT NOT NULL UNIQUE,
    decision_id          TEXT NOT NULL REFERENCES decision_events(decision_id),
    exit_timestamp       TEXT NOT NULL,
    gross_return         REAL NOT NULL,
    net_return           REAL NOT NULL,
    holding_period_days  INTEGER NOT NULL,
    cost_breakdown       TEXT NOT NULL,        -- JSON
    cost_model_id        TEXT NOT NULL REFERENCES cost_models(cost_model_id),
    record_hash          TEXT NOT NULL,
    previous_record_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_evaluation_events (
    sequence_number          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id                 TEXT NOT NULL UNIQUE,
    timestamp                TEXT NOT NULL,
    from_state               TEXT NOT NULL,    -- OBSERVATION / NORMAL / WARNING / DEFENSIVE
    to_state                 TEXT NOT NULL,
    trigger_reason           TEXT NOT NULL,
    validation_mode          TEXT NOT NULL,    -- NATURAL / REPLAY_FORCED
    replay_scenario_id       TEXT,             -- nullable
    recommended_position_size REAL,            -- nullable, v1.5: what the Risk Governor
                                                -- computed it *would* apply -- populated even
                                                -- in OBSERVATION/NORMAL, since Observation
                                                -- Mode exists to compare this against
                                                -- actual_position_size after the fact
    actual_position_size     REAL,             -- nullable, v1.5: what actually happened to
                                                -- the account -- typically equals pre-governor
                                                -- sizing during Observation Mode (FR-1.10a)
    record_hash              TEXT NOT NULL,
    previous_record_hash     TEXT NOT NULL
);

-- v1.5.1 (Phase 1A requirement, phase1a_requirements.md Section 13a): tracks
-- every TRADING_CONSTITUTION.md rule check against every decision_events row.
-- Part of the immutable ledger (append-only, hash-chained) though it did not
-- exist in Phase 0. Phase 1A has no per-trade human approval workflow
-- (phase0_decisions.md #17), so ESCALATED/FAIL results here are advisory --
-- logged for Phase 1B compliance analysis, never blocking execution. See
-- bot/trust_ledger/constitution.py for the six rule checks that write here.
CREATE TABLE IF NOT EXISTS constitution_enforcement_events (
    sequence_number       INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id              TEXT NOT NULL UNIQUE,
    decision_id           TEXT NOT NULL REFERENCES decision_events(decision_id),
    rule_id               TEXT NOT NULL,
    rule_name             TEXT NOT NULL,
    check_timestamp       TEXT NOT NULL,
    check_result          TEXT NOT NULL,   -- PASS / FAIL / ESCALATED
    action_taken          TEXT NOT NULL,   -- execution_proceeded / advisory_only
    reason                TEXT,
    record_hash           TEXT NOT NULL,
    previous_record_hash  TEXT NOT NULL,
    CHECK (check_result IN ('PASS', 'FAIL', 'ESCALATED'))
);

CREATE TABLE IF NOT EXISTS deployment_manifest_events (
    sequence_number      INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id             TEXT NOT NULL UNIQUE,   -- v1.3, e.g. MFE-20260728-001 -- the one ledger
                                                  -- table that previously had no semantic identifier
                                                  -- besides sequence_number
    manifest_id          TEXT NOT NULL REFERENCES deployment_manifests(manifest_id),
    event_type           TEXT NOT NULL,   -- CREATED / TESTING_STARTED / REVIEW_REQUESTED / APPROVED / PROMOTED / RETIRED
    approval_event_id    TEXT REFERENCES approval_events(approval_id),  -- nullable, set for APPROVED
    timestamp            TEXT NOT NULL,
    record_hash           TEXT NOT NULL,
    previous_record_hash TEXT NOT NULL,
    -- v1.2 (FR-0.12): a PROMOTED row must carry a non-null approval_event_id,
    -- enforced at the DB level -- independent of whatever inserted it, not
    -- just the application's MANIFEST_TRANSITIONS state machine.
    CHECK (event_type != 'PROMOTED' OR approval_event_id IS NOT NULL)
);

-- ============================================================================
-- Group C: Operational Tables (mutable, not sources of historical truth)
-- ============================================================================

CREATE TABLE IF NOT EXISTS active_deployment_pointer (
    id                 INTEGER PRIMARY KEY CHECK (id = 1),  -- single row, enforced by construction
    -- v1.3: "no active deployment" is row ABSENCE, not a NULL value here.
    -- active_manifest_id stays NOT NULL -- clearing the active manifest is
    -- DELETE FROM active_deployment_pointer WHERE id=1, never an UPDATE to
    -- NULL (which would violate this constraint anyway).
    active_manifest_id TEXT NOT NULL UNIQUE REFERENCES deployment_manifests(manifest_id),
    updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS data_quality_events (
    event_id   TEXT PRIMARY KEY,
    timestamp  TEXT NOT NULL,
    source     TEXT NOT NULL,
    status     TEXT NOT NULL,   -- HEALTHY / DEGRADED / DOWN
    detail     TEXT
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version      INTEGER PRIMARY KEY,
    applied_at   TEXT NOT NULL,
    description  TEXT NOT NULL,
    checksum     TEXT   -- v1.2: hash of the migration file's own contents, for audit
);

-- ============================================================================
-- 5.1a Lifecycle state (derived, not stored) -- replaces v1.1's stored,
-- hash-excluded decision_events.outcome_state column, which was a subtle
-- immutability violation (a row could return different content depending on
-- when it was read, even with an unchanged hash). ANALYZED is deliberately
-- not modeled here -- that's Phase 1 calibration-batch design.
-- ============================================================================

CREATE VIEW IF NOT EXISTS decision_state AS
SELECT d.decision_id,
       CASE WHEN o.decision_id IS NULL THEN 'OPEN' ELSE 'CLOSED' END AS outcome_state
FROM decision_events d
LEFT JOIN (SELECT DISTINCT decision_id FROM decision_outcome_events) o
  ON o.decision_id = d.decision_id;

-- ============================================================================
-- Indexes
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_decision_events_asset       ON decision_events(asset);
CREATE INDEX IF NOT EXISTS idx_decision_events_manifest     ON decision_events(deployment_manifest_id);
CREATE INDEX IF NOT EXISTS idx_decision_events_candidate_event ON decision_events(candidate_event_id);  -- v1.3
CREATE INDEX IF NOT EXISTS idx_decision_outcome_decision_id ON decision_outcome_events(decision_id);
CREATE INDEX IF NOT EXISTS idx_candidate_events_asset       ON candidate_evaluation_events(asset);
CREATE INDEX IF NOT EXISTS idx_manifest_events_manifest_id  ON deployment_manifest_events(manifest_id);
CREATE INDEX IF NOT EXISTS idx_training_runs_artifact       ON model_training_runs(artifact_id);
CREATE INDEX IF NOT EXISTS idx_constitution_enforcement_decision_id ON constitution_enforcement_events(decision_id);

-- ============================================================================
-- Append-only enforcement triggers (Section 3): blanket no-update/no-delete
-- for every Group A and Group B table. As of v1.2 there are NO exceptions --
-- decision_events is fully immutable like everything else; the previous
-- outcome_state carve-out trigger has been removed along with the column.
-- ============================================================================

CREATE TRIGGER IF NOT EXISTS trg_model_artifacts_no_update
BEFORE UPDATE ON model_artifacts
BEGIN SELECT RAISE(ABORT, 'model_artifacts is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_model_artifacts_no_delete
BEFORE DELETE ON model_artifacts
BEGIN SELECT RAISE(ABORT, 'model_artifacts is append-only'); END;

CREATE TRIGGER IF NOT EXISTS trg_strategy_versions_no_update
BEFORE UPDATE ON strategy_versions
BEGIN SELECT RAISE(ABORT, 'strategy_versions is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_strategy_versions_no_delete
BEFORE DELETE ON strategy_versions
BEGIN SELECT RAISE(ABORT, 'strategy_versions is append-only'); END;

CREATE TRIGGER IF NOT EXISTS trg_risk_rulesets_no_update
BEFORE UPDATE ON risk_rulesets
BEGIN SELECT RAISE(ABORT, 'risk_rulesets is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_risk_rulesets_no_delete
BEFORE DELETE ON risk_rulesets
BEGIN SELECT RAISE(ABORT, 'risk_rulesets is append-only'); END;

CREATE TRIGGER IF NOT EXISTS trg_model_training_runs_no_update
BEFORE UPDATE ON model_training_runs
BEGIN SELECT RAISE(ABORT, 'model_training_runs is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_model_training_runs_no_delete
BEFORE DELETE ON model_training_runs
BEGIN SELECT RAISE(ABORT, 'model_training_runs is append-only'); END;

CREATE TRIGGER IF NOT EXISTS trg_deployment_manifests_no_update
BEFORE UPDATE ON deployment_manifests
BEGIN SELECT RAISE(ABORT, 'deployment_manifests is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_deployment_manifests_no_delete
BEFORE DELETE ON deployment_manifests
BEGIN SELECT RAISE(ABORT, 'deployment_manifests is append-only'); END;

CREATE TRIGGER IF NOT EXISTS trg_candidate_evaluation_events_no_update
BEFORE UPDATE ON candidate_evaluation_events
BEGIN SELECT RAISE(ABORT, 'candidate_evaluation_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_candidate_evaluation_events_no_delete
BEFORE DELETE ON candidate_evaluation_events
BEGIN SELECT RAISE(ABORT, 'candidate_evaluation_events is append-only'); END;

CREATE TRIGGER IF NOT EXISTS trg_cost_models_no_update
BEFORE UPDATE ON cost_models
BEGIN SELECT RAISE(ABORT, 'cost_models is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_cost_models_no_delete
BEFORE DELETE ON cost_models
BEGIN SELECT RAISE(ABORT, 'cost_models is append-only'); END;

CREATE TRIGGER IF NOT EXISTS trg_approval_events_no_update
BEFORE UPDATE ON approval_events
BEGIN SELECT RAISE(ABORT, 'approval_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_approval_events_no_delete
BEFORE DELETE ON approval_events
BEGIN SELECT RAISE(ABORT, 'approval_events is append-only'); END;

CREATE TRIGGER IF NOT EXISTS trg_decision_events_no_update
BEFORE UPDATE ON decision_events
BEGIN SELECT RAISE(ABORT, 'decision_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_decision_events_no_delete
BEFORE DELETE ON decision_events
BEGIN SELECT RAISE(ABORT, 'decision_events is append-only'); END;

CREATE TRIGGER IF NOT EXISTS trg_decision_outcome_events_no_update
BEFORE UPDATE ON decision_outcome_events
BEGIN SELECT RAISE(ABORT, 'decision_outcome_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_decision_outcome_events_no_delete
BEFORE DELETE ON decision_outcome_events
BEGIN SELECT RAISE(ABORT, 'decision_outcome_events is append-only'); END;

CREATE TRIGGER IF NOT EXISTS trg_risk_evaluation_events_no_update
BEFORE UPDATE ON risk_evaluation_events
BEGIN SELECT RAISE(ABORT, 'risk_evaluation_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_risk_evaluation_events_no_delete
BEFORE DELETE ON risk_evaluation_events
BEGIN SELECT RAISE(ABORT, 'risk_evaluation_events is append-only'); END;

CREATE TRIGGER IF NOT EXISTS trg_deployment_manifest_events_no_update
BEFORE UPDATE ON deployment_manifest_events
BEGIN SELECT RAISE(ABORT, 'deployment_manifest_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_deployment_manifest_events_no_delete
BEFORE DELETE ON deployment_manifest_events
BEGIN SELECT RAISE(ABORT, 'deployment_manifest_events is append-only'); END;

CREATE TRIGGER IF NOT EXISTS trg_constitution_enforcement_events_no_update
BEFORE UPDATE ON constitution_enforcement_events
BEGIN SELECT RAISE(ABORT, 'constitution_enforcement_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_constitution_enforcement_events_no_delete
BEFORE DELETE ON constitution_enforcement_events
BEGIN SELECT RAISE(ABORT, 'constitution_enforcement_events is append-only'); END;

-- ============================================================================
-- Chain-integrity triggers (new in v1.2, Section 3 item 3): a BEFORE INSERT
-- trigger on every Group A table rejects any row whose previous_record_hash
-- doesn't match that table's actual current chain head. Catches a wrong or
-- stale hash pointer at insert time, regardless of what inserted the row --
-- a stronger guarantee than "the application always computes it correctly."
-- Does NOT replace verify_chain()/the nightly job: this only checks the
-- chain *pointer* at write time, not that a stored record_hash was computed
-- correctly for rows already at rest (e.g. a direct file edit years later).
-- ============================================================================

CREATE TRIGGER IF NOT EXISTS trg_candidate_evaluation_events_chain_integrity
BEFORE INSERT ON candidate_evaluation_events
WHEN NEW.previous_record_hash != COALESCE(
    (SELECT record_hash FROM candidate_evaluation_events ORDER BY sequence_number DESC LIMIT 1),
    '0000000000000000000000000000000000000000000000000000000000000000'
)
BEGIN SELECT RAISE(ABORT, 'candidate_evaluation_events: previous_record_hash does not match current chain head'); END;

CREATE TRIGGER IF NOT EXISTS trg_cost_models_chain_integrity
BEFORE INSERT ON cost_models
WHEN NEW.previous_record_hash != COALESCE(
    (SELECT record_hash FROM cost_models ORDER BY sequence_number DESC LIMIT 1),
    '0000000000000000000000000000000000000000000000000000000000000000'
)
BEGIN SELECT RAISE(ABORT, 'cost_models: previous_record_hash does not match current chain head'); END;

CREATE TRIGGER IF NOT EXISTS trg_approval_events_chain_integrity
BEFORE INSERT ON approval_events
WHEN NEW.previous_record_hash != COALESCE(
    (SELECT record_hash FROM approval_events ORDER BY sequence_number DESC LIMIT 1),
    '0000000000000000000000000000000000000000000000000000000000000000'
)
BEGIN SELECT RAISE(ABORT, 'approval_events: previous_record_hash does not match current chain head'); END;

CREATE TRIGGER IF NOT EXISTS trg_decision_events_chain_integrity
BEFORE INSERT ON decision_events
WHEN NEW.previous_record_hash != COALESCE(
    (SELECT record_hash FROM decision_events ORDER BY sequence_number DESC LIMIT 1),
    '0000000000000000000000000000000000000000000000000000000000000000'
)
BEGIN SELECT RAISE(ABORT, 'decision_events: previous_record_hash does not match current chain head'); END;

CREATE TRIGGER IF NOT EXISTS trg_decision_outcome_events_chain_integrity
BEFORE INSERT ON decision_outcome_events
WHEN NEW.previous_record_hash != COALESCE(
    (SELECT record_hash FROM decision_outcome_events ORDER BY sequence_number DESC LIMIT 1),
    '0000000000000000000000000000000000000000000000000000000000000000'
)
BEGIN SELECT RAISE(ABORT, 'decision_outcome_events: previous_record_hash does not match current chain head'); END;

CREATE TRIGGER IF NOT EXISTS trg_risk_evaluation_events_chain_integrity
BEFORE INSERT ON risk_evaluation_events
WHEN NEW.previous_record_hash != COALESCE(
    (SELECT record_hash FROM risk_evaluation_events ORDER BY sequence_number DESC LIMIT 1),
    '0000000000000000000000000000000000000000000000000000000000000000'
)
BEGIN SELECT RAISE(ABORT, 'risk_evaluation_events: previous_record_hash does not match current chain head'); END;

CREATE TRIGGER IF NOT EXISTS trg_deployment_manifest_events_chain_integrity
BEFORE INSERT ON deployment_manifest_events
WHEN NEW.previous_record_hash != COALESCE(
    (SELECT record_hash FROM deployment_manifest_events ORDER BY sequence_number DESC LIMIT 1),
    '0000000000000000000000000000000000000000000000000000000000000000'
)
BEGIN SELECT RAISE(ABORT, 'deployment_manifest_events: previous_record_hash does not match current chain head'); END;

CREATE TRIGGER IF NOT EXISTS trg_constitution_enforcement_events_chain_integrity
BEFORE INSERT ON constitution_enforcement_events
WHEN NEW.previous_record_hash != COALESCE(
    (SELECT record_hash FROM constitution_enforcement_events ORDER BY sequence_number DESC LIMIT 1),
    '0000000000000000000000000000000000000000000000000000000000000000'
)
BEGIN SELECT RAISE(ABORT, 'constitution_enforcement_events: previous_record_hash does not match current chain head'); END;

-- ============================================================================
-- Candidate provenance enforcement (new in v1.4): a decision_events row must
-- reference a candidate whose evaluation actually completed. Previously this
-- was only a code comment (FR-0.1a/FR-0.13) -- nothing stopped a decision
-- from citing a crashed/partial evaluation as though it were a genuine
-- qualified rejection. This closes that gap at the DB level, independent of
-- what inserted the row.
-- ============================================================================

CREATE TRIGGER IF NOT EXISTS trg_decision_events_requires_completed_evaluation
BEFORE INSERT ON decision_events
WHEN (
    SELECT evaluation_completed FROM candidate_evaluation_events
    WHERE candidate_event_id = NEW.candidate_event_id
) != 1
BEGIN SELECT RAISE(ABORT, 'decision_events: candidate_event_id has not completed evaluation'); END;
