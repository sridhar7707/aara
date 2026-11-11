"""Dispatch tests for the bot CLI (bot/_main_cli.py).

The CLI dispatches through the bot.main module object, so these tests patch bot.main and check
which function each flag reaches, with what arguments, and that a crash exits 1.
"""
import pytest

import bot._main_cli as cli
import bot.main as main_mod


@pytest.fixture
def calls(monkeypatch):
    seen = []

    def record(name):
        def _fn(*args, **kwargs):
            seen.append((name, args, kwargs))
        return _fn

    for name in ("run", "run_loop", "end_of_day_summary", "_do_clean_db", "_do_reset_daily_start"):
        monkeypatch.setattr(main_mod, name, record(name))
    return seen


def test_defaults_are_paper_mode_with_no_flags():
    args = cli.build_parser().parse_args([])
    assert args.mode == "paper"
    assert not (args.summary or args.loop or args.reset_daily_start or args.clean_db)


def test_live_is_an_allowed_mode_and_other_values_are_rejected():
    assert cli.build_parser().parse_args(["--mode", "live"]).mode == "live"
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--mode", "sim"])


def test_no_flags_runs_one_paper_cycle(calls):
    cli.main([])
    assert calls == [("run", (), {"mode": "paper"})]


def test_loop_flag_runs_the_long_running_loop_with_the_mode(calls):
    cli.main(["--loop", "--mode", "live"])
    assert calls == [("run_loop", (), {"mode": "live"})]


def test_summary_flag_sends_the_end_of_day_summary_and_does_not_trade(calls):
    cli.main(["--summary"])
    assert calls == [("end_of_day_summary", (), {})]


def test_reset_daily_start_flag_resets_only(calls):
    cli.main(["--reset-daily-start"])
    assert calls == [("_do_reset_daily_start", (), {})]


def test_clean_db_takes_precedence_over_every_other_flag(calls):
    # --clean-db is destructive and must never fall through to a trading cycle.
    cli.main(["--clean-db", "--loop", "--summary", "--reset-daily-start"])
    assert calls == [("_do_clean_db", (), {})]


def test_a_crash_is_logged_annotated_and_exits_1(monkeypatch, capsys):
    def boom(**_kwargs):
        raise RuntimeError("alpaca unreachable")

    monkeypatch.setattr(main_mod, "run", boom)
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "::error title=Trading Bot Crash::RuntimeError: alpaca unreachable" in out
