# TradeGenius AI — Security

Last updated: 2026-09-18

Scope: the live bot/dashboard system (`bot/`, `dashboard/`, GitHub Actions, HuggingFace Spaces) —
the thing that actually holds broker credentials and executes trades today. This is deliberately
narrower than `docs/platform/SENTINEL_ENGINE_SECURITY_AND_PRIVACY_ARCHITECTURE.md`, which describes
a future multi-tenant, multi-product security model for the not-yet-launched Sentinel/AARA platform
layer. That document is aspirational; this one describes what is actually deployed and credentialed.

## 1. Trust Boundaries

```
GitHub Actions (cron, secrets: ALPACA_*, FRED_API_KEY, NEWSAPI_KEY, REDDIT_*,
FINNHUB_API_KEY, TELEGRAM_*, HF_TOKEN)
        │
        ▼
   bot/main.py  ──────► Alpaca (orders, account read)
        │        ──────► yfinance / FRED / NewsAPI / Reddit / Finnhub (read-only market data)
        │        ──────► Telegram Bot API (outbound alerts only)
        └──────► sync_db.py ──► HuggingFace Dataset repo (trades.db push)

HuggingFace Spaces (secrets: HF_TOKEN — read scope only for the dashboard's own pull)
        │
        ▼
   dashboard/app.py ──► HuggingFace Dataset (trades.db pull, read-only)
        │
        ▼
   Public browser (no auth) — read-only rendered charts/tables
```

Two separate credential scopes exist and do not overlap: the **bot** process (GitHub Actions) is the
only thing that can place an order or write to the dataset repo. The **dashboard** process
(HuggingFace Spaces) can only pull and render — it has no path back to Alpaca and no write
credential. A dashboard compromise cannot place a trade.

## 2. Why the Dashboard Has No Auth

The dashboard is a public, unauthenticated read view. This is a deliberate scope decision, not an
oversight: it renders no PII (single-user portfolio, ksri77's own account), no account numbers, and
no credentials (R-012 in `RISK_REGISTER.md` — model weights and config stay server-side). Adding auth
would protect nothing that isn't already safe to show. This decision should be revisited if the
dashboard ever surfaces a second user's data or any credential-adjacent value.

## 3. Credential Inventory and Blast Radius

Full config-key list and outage handling: `EXTERNAL_SERVICES.md`. Blast radius if each leaks:

| Credential | Capability it grants | Blast radius if leaked today |
|---|---|---|
| `ALPACA_KEY` / `ALPACA_SECRET` | Place/cancel orders, read positions/account, on the **paper** endpoint | Attacker can place bogus paper trades or read simulated portfolio data. No real money at risk — paper accounts hold no actual capital. Alpaca trading-API keys are order/read scoped only; they cannot initiate ACH transfers or withdrawals, so even a live-trading key of this kind cannot move cash out of the account. |
| `HF_TOKEN` | Push to the `trades.db` dataset repo; dashboard pulls from the same repo | Attacker could push corrupted or fabricated trade history, which the dashboard would then render as if real. Data-integrity risk, not a funds risk. |
| `TELEGRAM_TOKEN` / `TELEGRAM_CHAT_ID` | Send messages to the operator's Telegram chat | Attacker could spoof BUY/SELL/halt alerts to mislead the operator. Low impact — the operator should treat any surprising Telegram alert as unverified and check the dashboard/logs directly. |
| `FRED_API_KEY`, `NEWSAPI_KEY`, `REDDIT_*`, `FINNHUB_API_KEY` | Read-only market/news data, free tiers | Quota exhaustion at worst (bot degrades gracefully per `EXTERNAL_SERVICES.md` — the affected signal weight drops to 0, no halt). No data-sensitivity or funds risk. |

## 4. Secrets Handling

- Never committed to source: `.env` is git-ignored; production secrets live only in GitHub Actions
  repository secrets and HuggingFace Space secrets.
- No secret is logged. `bot/monitor/error_logger.py` and the Telegram alert path do not include raw
  credential values in any message.
- **No rotation policy exists today.** This is an accepted gap, not an oversight: rotate any key
  manually and immediately if compromise is suspected (revoke in the provider's dashboard, generate a
  new key, update the GitHub Actions / HF Space secret). There is no scheduled/automatic rotation.

## 5. What "Going Live" (Real Money) Requires

The project's stated end goal is Alpaca paper trading now, graduating to **Robinhood real-money**
trading once the win-rate target is met — not Alpaca live (Alpaca stays paper-only in this plan).
Robinhood has no paper-trading mode: its only programmatic path is the beta Trading MCP, against a
real-money-only funded sub-account, authenticated via OAuth/agent-client credentials with no
documented rate limits or SLA. Before that switch:

- [ ] Confirm the funded sub-account is isolated (its own balance cap) so a bug's maximum loss is
      bounded by account funding, not discovered after the fact.
- [ ] Re-verify `RISK_REGISTER.md`'s financial risk-appetite limits (5% daily / 10% weekly / 12%
      drawdown) are enforced in code (`bot/risk/risk_manager.py`) against the real-money account, not
      just the paper account — the gate exists today but has only ever been exercised against
      simulated capital.
- [ ] Decide and document an incident contact/escalation path — today there is one operator
      (ksri77) reachable only via the same Telegram bot the system alerts through; a compromised or
      down Telegram is a single point of failure at the exact moment it would matter most.
- [ ] Revisit §4's "no rotation policy" gap — a real-money credential leak is a materially worse
      outcome than a paper-account leak and justifies the rotation discipline paper trading didn't.
- [ ] Confirm `HALT_TRADING` (see `RUNBOOK.md`) has been tested against the real-money execution path,
      not only the paper path.

## 6. Non-Goals

This document does not cover: the aspirational multi-tenant/multi-product security model
(`docs/platform/SENTINEL_ENGINE_SECURITY_AND_PRIVACY_ARCHITECTURE.md`), compliance certifications, or
infrastructure the project doesn't run (there is no user database, no auth service, no PII store
beyond the single operator's own portfolio).
