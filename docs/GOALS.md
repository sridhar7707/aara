# TradeGenius AI — Project Goals

Last updated: 2026-09-18

## Primary Goal

Build an AI-powered swing-trading copilot that consistently outperforms a buy-and-hold SPY
benchmark over a 12-month paper-trading period, while operating autonomously within hard
risk limits and providing full explainability for every decision.

## Specific Targets

| Goal | Target | Measurement |
|------|--------|-------------|
| Win rate | ≥ 60% of closed trades profitable | `trades` table: count(pnl>0)/count(*) |
| Outperform SPY | Beat SPY total return by ≥ 5 pp / year | `render_paper_trading_scorecard()` |
| Max drawdown | Never exceed 12% from portfolio high | `PORTFOLIO_DRAWDOWN_LIMIT_PCT = 0.12` |
| Daily loss limit | Stop trading if daily loss > 5% | `DAILY_LOSS_LIMIT_PCT = 0.05` |
| Explainability | Every BUY/SELL includes top 3 SHAP drivers | Telegram alerts + Dashboard Why panel |
| Automation | Fully autonomous during market hours | GitHub Actions cron, no human intervention |
| Transparency | Real-time dashboard accessible from any device | HuggingFace Spaces (public URL) |

## Non-Goals (Explicit)

- **Not** high-frequency trading — trades held 3–25 days (swing style)
- **Not** options, futures, or crypto — US equities and ETFs only
- **Not** real-money deployment until win rate ≥ 60% sustained over 60 days of paper trading
  (matches `scripts/confidence_check.py`'s enforced `min_days: 60` — corrected 2026-09-18, was
  recorded as 90 and contradicted `SUCCESS_METRICS.md`/the actual code)
- **Not** a signal service — all decisions stay in the bot; no public signal publishing
- **Not** fully autonomous real-money trading without human oversight

## Success Horizon

Paper-trading phase: minimum 60 calendar days before evaluating real-money deployment
(`scripts/confidence_check.py`'s `min_days: 60`; corrected 2026-09-18, see Non-Goals above).
Real-money gate: win rate ≥ 60%, no month with >5% loss, drawdown ≤ 8% (tighter than limit).

## Stakeholders

- Primary owner: ksri77@gmail.com
- Dashboard: public read-only (HuggingFace Spaces)
- Alerts: Telegram channel (private)
