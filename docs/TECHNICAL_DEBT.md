# TradeGenius AI — Technical Debt

Last updated: 2026-09-18

Items are rated by effort (S/M/L/XL) and urgency (High/Medium/Low).
High-urgency items should be resolved before any real-money deployment.

## Active Debt

| ID | Item | Effort | Urgency | Notes |
|----|------|--------|---------|-------|
| TD-003 | `bot/monitor/` has 7 legacy private modules (`_dashboard_*.py`) | M | Low | Pre-refactor modules kept for backward compatibility. Should be deleted once confirmed not imported anywhere. (Count corrected 2026-09-18: was recorded as 8, actual is 7 — verified via `find bot/monitor -name "_dashboard_*.py"`) |
| TD-004 | DuckDB analytics not yet surfaced in dashboard | M | Low | `AnalyticsService.get_sharpe_ratio()` and `get_max_drawdown()` compute from DuckDB but the scorecard panel reads directly from SQLite. Should switch to analytics service for consistency |
| TD-005 | `bot/strategy/rl_agent.py` PPO model rarely invoked | M | Low | RL agent used for position sizing but Kelly criterion is primary sizer. Unclear if RL adds value — needs ablation study |
| TD-006 | No database migration tooling | M | Medium | Schema changes require manual SQL. If trades.db schema evolves, existing data needs migration script. Consider Alembic or manual versioned migrations |
| TD-007 | `backtest/engine.py` not connected to live parameter changes | M | Medium | Backtest uses hardcoded params; should read from `config.py` so a param change triggers a backtest validation |
| TD-016 | 4 files now over the documented 500-line limit (`DESIGN_PRINCIPLES.md` §5), not previously tracked | S–M | Low | Found via a full repo scan 2026-09-18, not flagged before: `bot/_main_positions.py` (534), `bot/_main_runner.py` (504), `dashboard/layout.py` (529), `scripts/phase1a_verification.py` (560). None are egregious (all under 15% over), but the limit exists for a reason — extract when next touched |
| TD-017 | `test_filter_css_rules_present_in_the_composed_stylesheet` (`applications/trading_intelligence/ui/tests/test_performance_learning_decision_ledger_filter_view.py`) is flaky | S | Low | Found 2026-09-18 while validating `tools/verify_docs.py --check-debt`: failed 1 of 5 back-to-back runs of the same file, passed reliably alone and on every other full-file run. Not root-caused — looks like order/timing-dependent state, not investigated further since it's a low reproduction rate and tangential to what was being tested at the time |

## Resolved Debt

| ID | Item | Resolved | How |
|----|------|----------|-----|
| TD-008 | `tests/measure_performance.py` needs periodic re-run | 2026-09-18 | Wasn't just staleness: the script only ever measured `pytest tests/`, never `sentinel_engine/` or `applications/` — those two now hold ~2/3 of the real suite. `NFR.md` said "535 passed" while the repo-wide count is 4,538. Fixed the script's test invocation |
| TD-015 | `measure_performance.py --update` intermittently reported "13 errors" instead of the real "4 failed / 4485 passed / 49 skipped" | 2026-09-18 | Two compounding causes, both fixed: (1) the script measured dashboard render latency — which opens a single-writer DuckDB connection (`analytics.duckdb`) in-process — *before* spawning the pytest subprocess, so the subprocess's own attempt to open the same file collided with itself; reordered to run the test suite first. (2) an orphaned python.exe from an earlier diagnostic session (PID 11396) was still holding that same file open; killed it. `NFR.md` now regenerates clean and matches a direct interactive `pytest -q` run exactly |
| TD-001 | `bot/main.py` was 556 lines (over 500-line limit) | 2026-09-18 (found already resolved) | Now 479 lines. Not a deliberate fix for this item specifically — logic was progressively extracted into `_main_candidates.py`, `_main_prep.py`, `_main_reconcile.py`, and `_main_trust_decisions.py` (none of which existed when this item was opened), which brought it back under the limit as a side effect |
| TD-009 | `dashboard/app.py` was 3979 lines (god file) | 2026-06-14 | SPEC 52: split into 15 component modules; app.py was 322 lines immediately after. (Note 2026-09-18: now 431 lines as new features accumulated since — still comfortably under the 500-line limit, not a regression of this fix) |
| TD-010 | `dashboard/components/history.py` was 694 lines | 2026-06-27 | Split: news → `news.py`, recommendation history → `recommendation_history.py` |
| TD-011 | Silent exceptions (`except: pass`) in 5 bot files | 2026-06-14 | SPEC 51: all upgraded to `log_exception()` or `logger.debug()` |
| TD-012 | `log_exception()` called with wrong signature in 5 places | 2026-06-14 | SPEC 55: corrected to 3-arg form; test coverage added |
| TD-013 | All render functions lacked error handling | 2026-06-14 | `@safe_render` decorator wraps all render_* functions |
| TD-002 | Missing unit test files for 8 bot modules | 2026-07-29 | Verified via `scripts/arch_review.py`'s rewritten (AST-based, facade-aware) `MISSING_TESTS` check + manual grep confirmation that each import is a real integration test, not incidental: `_main_signals.py` and `api_guard.py` got new direct test files this session (`tests/test__main_signals.py`, `tests/test_api_guard.py`); `_main_market.py` (`tests/test__main_market.py`) and `signal_gate.py` (`tests/test_signal_gate.py`) already had dedicated files predating this session; `_main_cycle.py`, `_main_db.py`, `_main_positions.py`, `_main_runner.py` are exercised directly by `tests/phase1a/*` integration tests. This item was stale — most of the underlying gap had already closed since 2026-06-27, the doc just wasn't updated to reflect it. |
| TD-014 | 4 failing tests in `applications/trading_intelligence/ui/tests/test_performance_learning_*.py` | 2026-09-18 | Root cause was 4 tests asserting the wrong scope (whole `PerformanceLearningUI.build()` source instead of the ADR-064 §2.12 ledger-inspection exclusion specifically) after the P0-2 shared-Refresh correction landed. Rewrote the assertions to check the real invariant behaviorally. **Process failure, not just a code fix:** this item sat in "Active Debt" for hours after the fix landed and the suite went green, because fixing the tests and updating this entry were treated as two separate tasks. Caught only when a reviewer cited this exact table row back at us. See `tools/verify_docs.py --check-debt` (added same day) so this can't happen silently again. |

## Debt Acceptance Policy

Debt is accepted when:
- Risk is explicitly documented here
- An owner and target resolution date are agreed
- The item does not affect financial safety (risk limits, PDT, stop-loss)
