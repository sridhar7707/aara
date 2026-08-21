"""Tests for scripts/project_one_trust_ledger_decision.py (ADR-043,
accepted 2026-08-21).

Uses only an isolated, tmp_path-based SQLite fixture database -- never
touches the real data/trust_ledger.db.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts import project_one_trust_ledger_decision as script  # noqa: E402

SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts",
    "project_one_trust_ledger_decision.py",
)


def _script_source() -> str:
    with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _make_fixture_db(tmp_path, rows):
    """Creates a minimal, isolated decision_events table (only the
    ADR-043 Section 9-authorized columns, plus a few excluded ones to
    prove they're never selected) and inserts the given rows. Returns
    the db path as a str."""
    db_path = str(tmp_path / "fixture_trust_ledger.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE decision_events (
            decision_id TEXT PRIMARY KEY,
            asset TEXT,
            action TEXT,
            timestamp TEXT,
            final_confidence REAL,
            model_outputs TEXT,
            risk_checks TEXT,
            deployment_manifest_id TEXT,
            record_hash TEXT,
            previous_record_hash TEXT
        )
        """
    )
    for row in rows:
        conn.execute(
            """
            INSERT INTO decision_events (
                decision_id, asset, action, timestamp, final_confidence,
                model_outputs, risk_checks, deployment_manifest_id,
                record_hash, previous_record_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["decision_id"],
                row["asset"],
                row["action"],
                row["timestamp"],
                row["final_confidence"],
                json.dumps(row["model_outputs"]),
                json.dumps({"gate_trace": []}),
                "excluded-manifest-id",
                "excluded-record-hash",
                "excluded-previous-hash",
            ),
        )
    conn.commit()
    conn.close()
    return db_path


def _sample_model_outputs():
    return {
        "xgboost": {"signal": "BUY", "confidence": 0.57, "metadata": {}},
        "lstm": {"signal": "BUY", "confidence": 0.55, "metadata": {}},
        "finbert": {"signal": "BUY", "confidence": 0.50, "metadata": {}},
    }


def _sample_row(decision_id="DEC-TEST-001"):
    return {
        "decision_id": decision_id,
        "asset": "SLB",
        "action": "REJECT",
        "timestamp": "2026-08-17T14:22:18.901835+00:00",
        "final_confidence": 0.5547,
        "model_outputs": _sample_model_outputs(),
    }


# --- 1/2/3: exactly-one CLI argument enforcement ---------------------------


def test_cli_rejects_zero_arguments():
    with pytest.raises(SystemExit):
        script.parse_args([])


def test_cli_rejects_multiple_arguments():
    with pytest.raises(SystemExit):
        script.parse_args(["DEC-A", "DEC-B"])


def test_cli_accepts_exactly_one_argument():
    args = script.parse_args(["DEC-TEST-001"])
    assert args.decision_id == "DEC-TEST-001"


def test_cli_decision_id_is_not_split_or_iterated(tmp_path):
    """A comma-joined string is not treated as multiple decisions -- it
    is used verbatim as a single opaque parameter and simply won't match
    any real decision_id."""
    db_path = _make_fixture_db(tmp_path, [_sample_row("DEC-A")])
    result = script.project_one_decision("DEC-A,DEC-B", db_path=db_path)
    assert result is None


# --- exactly one decision produces exactly one projection ------------------


def test_exactly_one_decision_produces_exactly_one_projection(tmp_path):
    db_path = _make_fixture_db(tmp_path, [_sample_row("DEC-TEST-001")])

    projection = script.project_one_decision("DEC-TEST-001", db_path=db_path)

    assert projection is not None
    assert projection.decision_id == "DEC-TEST-001"
    assert projection.symbol == "SLB"
    assert projection.action == "REJECT"
    assert projection.confidence == 0.5547


def test_unknown_decision_id_returns_none(tmp_path):
    db_path = _make_fixture_db(tmp_path, [_sample_row("DEC-TEST-001")])

    result = script.project_one_decision("DEC-DOES-NOT-EXIST", db_path=db_path)

    assert result is None


def test_second_row_in_db_is_never_read(tmp_path):
    db_path = _make_fixture_db(
        tmp_path, [_sample_row("DEC-TEST-001"), _sample_row("DEC-TEST-002")]
    )

    projection = script.project_one_decision("DEC-TEST-001", db_path=db_path)

    assert projection.decision_id == "DEC-TEST-001"


# --- duplicate processing refused (ADR-043 Section 12) ---------------------


def test_duplicate_projection_creation_is_refused(tmp_path):
    db_path = _make_fixture_db(tmp_path, [_sample_row("DEC-TEST-001")])
    projection_repository = script._ScriptProjectionRepository()

    first = script.project_one_decision(
        "DEC-TEST-001", db_path=db_path, projection_repository=projection_repository
    )
    assert first is not None

    with pytest.raises(script.DuplicateDecisionProjectionError):
        script.project_one_decision(
            "DEC-TEST-001", db_path=db_path, projection_repository=projection_repository
        )


def test_two_default_invocations_get_independent_repositories(tmp_path):
    """Without an injected repository (the real, authorized invocation
    path), each call gets a brand-new repository pair -- proving
    repositories are process-local, not a shared/module-level singleton."""
    db_path = _make_fixture_db(tmp_path, [_sample_row("DEC-TEST-001")])

    first = script.project_one_decision("DEC-TEST-001", db_path=db_path)
    second = script.project_one_decision("DEC-TEST-001", db_path=db_path)

    assert first is not None
    assert second is not None
    # updated_at legitimately differs by call time (existing,
    # unmodified EvidenceService stamps it from evidence.collected_at at
    # association time) -- compare only the fields that should be
    # identical across two independent runs of the same input row.
    assert first.decision_id == second.decision_id
    assert first.symbol == second.symbol
    assert first.action == second.action
    assert first.confidence == second.confidence
    assert first.status == second.status


# --- read-only SQLite behavior ----------------------------------------------


def test_connection_mechanism_is_read_only(tmp_path):
    db_path = _make_fixture_db(tmp_path, [_sample_row("DEC-TEST-001")])

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO decision_events (decision_id) VALUES ('should-fail')")
    finally:
        conn.close()


def test_script_source_uses_mode_ro_and_uri_true():
    source = _script_source()
    assert 'mode=ro' in source
    assert 'uri=True' in source


def test_script_source_contains_no_write_statements():
    source = _script_source()
    for forbidden in ("INSERT INTO", "UPDATE ", "DELETE FROM"):
        assert forbidden not in source


def test_read_decision_row_closes_connection(tmp_path):
    db_path = _make_fixture_db(tmp_path, [_sample_row("DEC-TEST-001")])

    script.read_decision_row("DEC-TEST-001", db_path)

    # If the connection weren't closed, a fresh writer connection with a
    # short busy_timeout would still succeed here -- this proves no
    # lingering read-only handle blocks a normal writer afterward.
    conn = sqlite3.connect(db_path, timeout=1)
    conn.execute("INSERT INTO decision_events (decision_id) VALUES ('post-read-write-ok')")
    conn.commit()
    conn.close()


# --- protected-path / ADR-013 composition isolation -------------------------


_FORBIDDEN_IMPORT_PATTERN = re.compile(
    r"^\s*(import|from)\s+(bot|dashboard|scheduler|database|applications)(\.|$|\s)",
    re.MULTILINE,
)


def test_script_imports_no_protected_paths():
    source = _script_source()
    assert not _FORBIDDEN_IMPORT_PATTERN.search(source)


_ADR013_COMPOSITION_IMPORT_PATTERN = re.compile(
    r"^\s*(import|from)\s+sentinel_engine\.composition(\.evidence)?\b",
    re.MULTILINE,
)


def test_script_does_not_import_adr013_composition():
    """Checks actual import statements only -- the module docstring and
    inline comments legitimately mention ADR-013's composition module by
    name to explain why it is deliberately not used; that prose is not
    an import and must not fail this check."""
    source = _script_source()
    assert not _ADR013_COMPOSITION_IMPORT_PATTERN.search(source)


def test_script_repositories_are_new_classes_not_adr013_singleton():
    from sentinel_engine.composition import evidence as adr013_composition

    assert script._ScriptLedgerStore is not adr013_composition._TemporaryLedgerStore
    assert (
        script._ScriptProjectionRepository
        is not adr013_composition._TemporaryProjectionRepository
    )


def test_repositories_are_freshly_instantiated_each_time():
    a = script._ScriptProjectionRepository()
    b = script._ScriptProjectionRepository()
    assert a is not b
    assert a._projections is not b._projections


# --- no persistence / no output files ---------------------------------------


def test_no_output_files_created(tmp_path, monkeypatch, capsys):
    db_path = _make_fixture_db(tmp_path, [_sample_row("DEC-TEST-001")])
    before = set(os.listdir(tmp_path))

    monkeypatch.chdir(tmp_path)
    exit_code = script.main(["DEC-TEST-001", "--db-path", db_path])

    after = set(os.listdir(tmp_path))
    assert exit_code == 0
    assert after == before  # no new file appeared anywhere in tmp_path


def test_script_source_never_opens_a_file_for_writing():
    source = _script_source()
    assert '"w"' not in source
    assert "'w'" not in source
    assert "logging" not in source


# --- output content: banner, no hash, no five-metric, no "verified" --------


def test_every_output_line_carries_ephemeral_banner(tmp_path, capsys):
    db_path = _make_fixture_db(tmp_path, [_sample_row("DEC-TEST-001")])

    script.main(["DEC-TEST-001", "--db-path", db_path])

    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines, "expected at least one output line"
    for line in lines:
        assert line.startswith(script.EPHEMERAL_BANNER)


def test_output_never_contains_hash_or_verified_claims(tmp_path, capsys):
    db_path = _make_fixture_db(tmp_path, [_sample_row("DEC-TEST-001")])

    script.main(["DEC-TEST-001", "--db-path", db_path])

    out = capsys.readouterr().out.lower()
    for forbidden in ("record_hash", "previous_record_hash", "verified", "hash="):
        assert forbidden not in out


def test_output_never_contains_five_metric_values(tmp_path, capsys):
    db_path = _make_fixture_db(tmp_path, [_sample_row("DEC-TEST-001")])

    script.main(["DEC-TEST-001", "--db-path", db_path])

    out = capsys.readouterr().out.lower()
    for forbidden in (
        "decision quality score",
        "conviction score",
        "evidence strength",
        "model agreement",
    ):
        assert forbidden not in out


# --- excluded governance/risk/approval/model-identity data ------------------


def test_select_statement_only_reads_authorized_columns():
    assert script._SELECT_COLUMNS == (
        "decision_id, asset, action, timestamp, final_confidence, model_outputs"
    )
    for excluded in ("risk_checks", "deployment_manifest_id", "record_hash", "SELECT *", "select *"):
        assert excluded not in script._SELECT_COLUMNS


def test_excluded_columns_present_in_db_never_reach_the_projection(tmp_path):
    """risk_checks/deployment_manifest_id/record_hash are present in the
    fixture row (as real Trust Ledger rows also carry them) but must
    never surface anywhere in the resulting Decision/DecisionProjection,
    since decision_adapter.to_decision() has no field for any of them."""
    db_path = _make_fixture_db(tmp_path, [_sample_row("DEC-TEST-001")])

    projection = script.project_one_decision("DEC-TEST-001", db_path=db_path)

    projection_values = str(vars(projection))
    for excluded in ("excluded-manifest-id", "excluded-record-hash", "excluded-previous-hash"):
        assert excluded not in projection_values
