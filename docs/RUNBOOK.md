# TradeGenius AI — Runbook

Last updated: 2026-09-18

What's monitored, what each alert means, and what to do when one fires. This is a single-operator
system (ksri77) — "escalation" below means "notify the operator via the same Telegram bot the system
already alerts through," not a paging rotation. That's a real scope limit, stated here rather than
implied.

## 1. What's Watched

The bot has no separate monitoring stack — Telegram alerts (`TELEGRAM_TOKEN`/`TELEGRAM_CHAT_ID`, see
`EXTERNAL_SERVICES.md`) are the alerting layer, and the dashboard (HuggingFace Spaces) is the
always-on visibility layer, refreshed every 60s via `gr.Timer`.

| Alert | Fires when | What to do |
|---|---|---|
| BUY signal | Ensemble + all 10 signal-gate checks pass | Informational — no action needed. Verify on the dashboard's Recent Orders table if the fill looks unexpected. |
| SELL signal (with reason) | Exit condition met (stop, target, sell-score) | Informational. The reason string names which exit rule fired — check `bot/strategy/` for that rule if the reason looks wrong. |
| Stop-loss triggered | ATR stop or 4% flat stop hit | Informational unless it fires repeatedly on the same symbol in one day — that's a signal the entry logic mis-sized or mis-timed that position. |
| Daily loss warning | Cumulative daily loss approaching the 5% risk-appetite limit (`RISK_REGISTER.md`) | Check the dashboard's portfolio panel. If the limit is about to be breached, confirm `risk_manager.py`'s daily-loss gate is about to halt new buys on its own before intervening manually. |
| VIX halt | VIX ≥ 28 | Informational — new buys are paused, existing positions still exit normally each cycle. No action needed unless the halt is stale (VIX has since dropped) and buys still aren't resuming — check the macro cache TTL (4h, `EXTERNAL_SERVICES.md`). |
| Daily summary (4:05 PM CT) / weekly report | Scheduled | Read for portfolio health; not an incident signal. |
| **No alert arrives during market hours** | — | This is itself a signal. Check §3 (cron miss) and §4 (Telegram outage) below — silence is not the same as "nothing happened." |

## 2. Manual Kill Switch

`bot/main.py` checks for `data/HALT_TRADING` at the start of every cycle — this is a **file**, not an
environment variable, so no redeploy or secret change is needed:

```bash
# Pause immediately (next cycle onward)
touch data/HALT_TRADING
git add data/HALT_TRADING && git commit -m "ops: emergency halt" && git push

# Confirm it took effect
# — Telegram will show: "⛔ EMERGENCY HALT ACTIVE — bot paused. Delete data/HALT_TRADING to resume."

# Resume
rm data/HALT_TRADING
git add -u && git commit -m "ops: resume trading" && git push
```

The check runs inside the GitHub Actions cron job, so the file must exist in the repo the workflow
checks out — a local-only file does nothing.

## 3. Incident: GitHub Actions Cron Miss (R-003)

**Symptom:** no BUY/SELL/summary alerts during market hours, dashboard timestamps stale.

1. Check the Actions tab for the workflow's run history — look for a failed or skipped run.
2. If the schedule was simply missed (GitHub Actions scheduling delay, not a bot bug), trigger it
   manually via `workflow_dispatch`.
3. The 5-minute loop is self-healing for a single missed tick — the next cycle catches up. Only
   intervene if multiple consecutive ticks are missing.

## 4. Incident: Alpaca Outage (R-002)

**Symptom:** Telegram/logs show repeated Alpaca call failures; no new orders placed.

1. Check Alpaca's status page.
2. Bot behavior is already defensive: orders queue, cycle logs a WARNING and skips rather than
   crashing (`EXTERNAL_SERVICES.md` outage table).
3. No manual action is required unless the outage persists past a full trading day — in that case,
   consider `HALT_TRADING` (§2) to stop generating a backlog of stale signals.

## 5. Incident: Runaway Loss / Gap-Down Open (R-011)

**Symptom:** daily loss warning fires and continues to climb.

1. The gap-down floor exit and ATR/4% flat stop are designed to fire automatically each cycle —
   confirm via the dashboard that open positions are actually being evaluated for exit, not stuck.
2. If losses continue past the risk-appetite hard limit (5% daily) without the automatic halt
   engaging, that is a `risk_manager.py` bug, not an operations issue — trigger `HALT_TRADING` (§2)
   immediately, then debug.

## 6. Incident: SQLite Corruption (R-007)

**Symptom:** `test_sqlite_threading.py`-style errors in production logs, or dashboard queries failing.

1. Restore from the most recent snapshot per `BACKUP_RECOVERY.md` (`backups/trades_*.db`, or the
   HuggingFace-pushed copy if local backups are also affected).
2. WAL mode makes this rare in practice — treat a recurrence as worth a root-cause pass on concurrent
   write paths, not just a restore-and-move-on.

## 7. Health Checks (run at session start, per root `CLAUDE.md`)

```bash
python tests/ui_tester.py                       # design system — must show 0 FAIL 0 WARN
python tests/requirements_tracker.py --status   # feature coverage baseline
python tests/requirements_tracker.py --docs-check  # verify all managed docs/*.md exist
```

## 8. Escalation

One operator, one channel: Telegram. If Telegram itself is down (see the credential note in
`SECURITY.md` §5 — this is flagged there as a single point of failure once real money is involved),
fall back to checking the dashboard directly and the GitHub Actions run log — both work independently
of Telegram.
