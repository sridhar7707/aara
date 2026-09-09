"""ADR-069 (B2) -- the deterministic three-model unanimity recommendation
rule in sentinel_engine.adapters.recommendation_adapter.recommend_entry_action.

Contract (SS5.3, the sole authorized rule):

    xgboost == "BUY" AND lstm == "BUY" AND finbert == "BUY"
        -> ("BUY",  "SENTINEL")
    every other case (any "SELL", any "HOLD", missing / empty / unrecognised)
        -> ("WAIT", "SENTINEL")

No Candidate B (majority) and no Candidate C (partial support). No threshold,
weight, score, count, or configuration. No Evidence, no Decision, no
persistence, no confidence math. Reads only model_outputs[model]["signal"].
"""
import ast
import inspect
import itertools

import pytest

from sentinel_engine.adapters import recommendation_adapter
from sentinel_engine.adapters.recommendation_adapter import recommend_entry_action
from sentinel_engine.domain.action_source import ActionSource
from sentinel_engine.domain.decision_action import DecisionAction

_SIGNALS = ("BUY", "SELL", "HOLD")


def _model_outputs(xgb="BUY", lstm="BUY", finbert="BUY", *, is_degraded=False,
                   xgb_conf=0.7, lstm_conf=0.51, finbert_conf=0.6):
    return {
        "xgboost": {"signal": xgb, "confidence": xgb_conf,
                    "metadata": {"shap_drivers": [{"feature": "rsi", "shap_value": 0.1}]}},
        "lstm": {"signal": lstm, "confidence": lstm_conf,
                 "metadata": {"is_degraded": is_degraded, "val_loss": 0.02}},
        "finbert": {"signal": finbert, "confidence": finbert_conf,
                    "metadata": {"raw_score": 0.2, "headlines": ["h1"]}},
    }


# -- 5: the complete 3^3 truth table --------------------------------------

@pytest.mark.parametrize("xgb,lstm,finbert", list(itertools.product(_SIGNALS, _SIGNALS, _SIGNALS)))
def test_full_truth_table_only_unanimous_buy_concurs(xgb, lstm, finbert):
    action, source = recommend_entry_action(_model_outputs(xgb, lstm, finbert))

    if xgb == lstm == finbert == "BUY":
        assert (action, source) == (DecisionAction.BUY.value, ActionSource.SENTINEL.value)
    else:
        assert (action, source) == (DecisionAction.WAIT.value, ActionSource.SENTINEL.value)


def test_truth_table_has_exactly_one_buy_row_and_twenty_six_wait_rows():
    results = [
        recommend_entry_action(_model_outputs(x, l, f))[0]
        for x, l, f in itertools.product(_SIGNALS, _SIGNALS, _SIGNALS)
    ]
    assert results.count("BUY") == 1
    assert results.count("WAIT") == 26


def test_unanimous_buy_concurs():
    assert recommend_entry_action(_model_outputs("BUY", "BUY", "BUY")) == ("BUY", "SENTINEL")


def test_action_source_is_always_sentinel():
    for x, l, f in itertools.product(_SIGNALS, _SIGNALS, _SIGNALS):
        assert recommend_entry_action(_model_outputs(x, l, f))[1] == "SENTINEL"


# -- 9: no Candidate B (majority) ---------------------------------------

@pytest.mark.parametrize("combo", [("BUY", "BUY", "SELL"), ("BUY", "BUY", "HOLD"),
                                   ("BUY", "SELL", "BUY"), ("HOLD", "BUY", "BUY")])
def test_two_of_three_buy_does_not_concur_no_majority_rule(combo):
    assert recommend_entry_action(_model_outputs(*combo)) == ("WAIT", "SENTINEL")


# -- 10: no Candidate C (>=1 SUPPORTING, 0 CONTRADICTING) --------------

@pytest.mark.parametrize("combo", [("BUY", "HOLD", "HOLD"), ("HOLD", "BUY", "HOLD"),
                                   ("HOLD", "HOLD", "BUY"), ("BUY", "BUY", "HOLD")])
def test_supporting_without_contradiction_does_not_concur_no_partial_support_rule(combo):
    # Candidate C would return BUY for these; Candidate A must return WAIT.
    assert recommend_entry_action(_model_outputs(*combo)) == ("WAIT", "SENTINEL")


# -- 6: defensive cases -> WAIT, never a Sentinel BUY, never raises -----

@pytest.mark.parametrize("bad_signal", [None, "", "   ", "buy", "STRONG_BUY", "REJECT", "WATCH", 123])
def test_unexpected_or_missing_signal_yields_wait_not_buy(bad_signal):
    outputs = _model_outputs("BUY", "BUY", "BUY")
    outputs["finbert"]["signal"] = bad_signal
    assert recommend_entry_action(outputs) == ("WAIT", "SENTINEL")


def test_missing_model_key_yields_wait_and_does_not_raise():
    outputs = _model_outputs("BUY", "BUY", "BUY")
    del outputs["lstm"]
    assert recommend_entry_action(outputs) == ("WAIT", "SENTINEL")


def test_missing_signal_key_yields_wait_and_does_not_raise():
    outputs = _model_outputs("BUY", "BUY", "BUY")
    del outputs["xgboost"]["signal"]
    assert recommend_entry_action(outputs) == ("WAIT", "SENTINEL")


@pytest.mark.parametrize("garbage", [None, {}, [], "nonsense", 0])
def test_structurally_broken_model_outputs_yields_wait_and_does_not_raise(garbage):
    assert recommend_entry_action(garbage) == ("WAIT", "SENTINEL")


def test_recommend_never_raises_across_the_whole_truth_table_plus_noise():
    for x, l, f in itertools.product(_SIGNALS + ("", None, "junk"), repeat=3):
        recommend_entry_action(_model_outputs(x, l, f))  # must not raise


# -- 12-15: is_degraded / LSTM band / model confidence / metadata have no effect

def test_is_degraded_has_no_effect_on_the_recommendation():
    assert recommend_entry_action(_model_outputs("BUY", "BUY", "BUY", is_degraded=True)) == ("BUY", "SENTINEL")
    assert recommend_entry_action(_model_outputs("BUY", "SELL", "BUY", is_degraded=True)) == ("WAIT", "SENTINEL")


@pytest.mark.parametrize("lstm_conf", [0.45, 0.46, 0.50, 0.51, 0.55])
def test_lstm_indeterminate_band_confidence_has_no_effect(lstm_conf):
    assert recommend_entry_action(_model_outputs("BUY", "BUY", "BUY", lstm_conf=lstm_conf)) == ("BUY", "SENTINEL")
    assert recommend_entry_action(_model_outputs("BUY", "HOLD", "BUY", lstm_conf=lstm_conf)) == ("WAIT", "SENTINEL")


@pytest.mark.parametrize("conf", [0.0, 0.01, 0.5, 0.99, 1.0])
def test_model_confidence_value_has_no_effect(conf):
    assert recommend_entry_action(
        _model_outputs("BUY", "BUY", "BUY", xgb_conf=conf, lstm_conf=conf, finbert_conf=conf)
    ) == ("BUY", "SENTINEL")


def test_metadata_contents_have_no_effect():
    outputs = _model_outputs("BUY", "BUY", "BUY")
    outputs["xgboost"]["metadata"] = {"anything": "at all", "score": 999}
    assert recommend_entry_action(outputs) == ("BUY", "SENTINEL")


# -- 11 & 16-17: no threshold/score/weight/count; model_outputs untouched

def test_model_outputs_dict_is_not_mutated():
    outputs = _model_outputs("BUY", "SELL", "HOLD")
    import copy
    snapshot = copy.deepcopy(outputs)
    recommend_entry_action(outputs)
    assert outputs == snapshot


def test_return_value_is_a_two_string_tuple_no_scores_or_counts():
    result = recommend_entry_action(_model_outputs("BUY", "SELL", "BUY"))
    assert isinstance(result, tuple) and len(result) == 2
    assert all(isinstance(x, str) for x in result)


def test_module_exposes_no_threshold_or_configuration_knob():
    src = inspect.getsource(recommendation_adapter)
    tree = ast.parse(src)
    # the only public entry point takes exactly one positional arg: model_outputs
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert set(funcs) == {"_signal_of", "recommend_entry_action"}
    rec = funcs["recommend_entry_action"]
    arg_names = [a.arg for a in rec.args.args]
    assert arg_names == ["model_outputs"]
    assert rec.args.defaults == [] and rec.args.kwonlyargs == []
    # no numeric literal other than in _signal_of's exception tuple / model index
    numbers = [n.value for n in ast.walk(rec) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))]
    assert numbers == [], f"unexpected numeric literal(s) in the rule: {numbers}"


# -- 8 & 29: not a general action generator; no execution-capable imports

def test_recommendation_adapter_never_returns_sell_buy_more_or_hold():
    produced = {
        recommend_entry_action(_model_outputs(x, l, f))[0]
        for x, l, f in itertools.product(_SIGNALS, _SIGNALS, _SIGNALS)
    }
    assert produced <= {"BUY", "WAIT"}
    assert "SELL" not in produced and "BUY_MORE" not in produced and "HOLD" not in produced


def test_recommendation_adapter_module_has_no_bot_or_execution_imports():
    source = inspect.getsource(recommendation_adapter)
    tree = ast.parse(source)
    forbidden = ("bot", "alpaca", "sentinel_engine.services", "sentinel_engine.composition",
                 "sentinel_engine.governance", "sentinel_engine.repositories",
                 "sentinel_engine.ledger", "sentinel_engine.evidence")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden), alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith(forbidden), module


def test_recommendation_adapter_constructs_no_evidence_or_decision():
    src = inspect.getsource(recommendation_adapter)
    assert "Evidence(" not in src
    assert "Decision(" not in src
    assert "create_decision" not in src
