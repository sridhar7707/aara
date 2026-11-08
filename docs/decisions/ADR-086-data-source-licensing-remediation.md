# ADR-086: Data-Source Licensing Remediation (yfinance, NewsAPI)

**Status:** Accepted by ksri77 on 2026-11-07 (chat instruction). Implementation not yet started. Interim rule: the bot keeps running on the current sources until the switch is complete. Note: NewsAPI on the free Developer plan is not permitted in production; the owner accepted that interim exposure knowingly.
**Decision Type:** Narrow ADR-002 exception, prospective. Governs which external data sources the trading pipeline may use. It does not change any governed trading value.
**Related:** ADR-002 (protected paths), ADR-052 (backtest quality gate on retrain), ADR-076 (XGB calibration observation), ADR-073 (labels, not yet implemented).

## 1. Context

Primary terms read on 2026-11-07:

- **Yahoo (yfinance).** The Yahoo terms prohibit "access or collect data... using any automated means" and any such access "for any purpose without our express, prior permission". Commercial reuse is prohibited. The bot's price pipeline relies on yfinance.
- **NewsAPI.** The Developer plan (free, 100 requests per day) "cannot be used in a staging or production environment (including internally)". Production use requires the Business plan at $449 per month, which allows "production and published commercial projects". The bot's sentiment signal uses NewsAPI.
- **GDELT.** Free for academic, commercial, and governmental use. Redistribution is permitted. Attribution to the GDELT Project and a link are required.
- **SEC EDGAR.** Government filing content is free to access and reuse. No copyright notice applies to filings.
- **Finnhub.** Personal use only. Business use requires written approval. Not usable.
- **Alpaca.** Paper accounts are entitled to IEX data only. IEX covers a small share of trading volume, so it is a weak price source. Whether Alpaca's data may be used for internal trading signals is not confirmed in its terms.
- **Tiingo and Massive (Polygon).** Terms not yet read (Tiingo redirected, Massive's page links to separate business and individual terms).

Current exposure: the production pipeline uses sources whose terms prohibit that use. The commercial exposure is larger, because external customers would be served the same data.

## 2. Decision (proposed)

1. **Retire yfinance from every automated path**, including research. Manual personal lookups only. Yahoo's terms prohibit the automated access, so no automated replacement is permitted.
2. **Replace NewsAPI.** Do not buy the $449 Business plan. The bot's sentiment input moves to GDELT tone data and SEC EDGAR filing events. Both are free, and both permit the intended use with attribution.
3. **Price data.** Move from yfinance to Alpaca's market-data API, the same account the bot already trades through. Before this step is accepted, the owner must obtain Alpaca's written confirmation that its data may be used for internal trading signals, and choose the feed (IEX or SIP). SIP is the better source, and its cost must be confirmed.
4. **Until the replacements are verified, no customer-facing output uses any of these sources.**
5. **Governed values are unchanged.** `stop_loss`, `daily_loss_limit`, `max_position`, and the XGB threshold are not touched by this ADR.

## 3. Consequences

- The sentiment input changes, so model outputs change. The retrain and backtest gate (ADR-052) applies before any new model is used.
- Expected costs: GDELT and EDGAR are $0. The Alpaca feed cost is unconfirmed; SIP pricing must be checked. NewsAPI Business ($449 per month, about $5,388 per year) is avoided.
- A transition period in which sentiment defaults to neutral may reduce signal volume. This must be measured, not assumed.

## 4. Verification before acceptance

- [x] Owner confirms the NewsAPI plan the account is on: free Developer plan (2026-11-07).
- [ ] Alpaca confirms in writing that its data may be used for internal trading signals, and the chosen feed and its cost. Draft inquiry prepared; the owner sends it.
- [x] Alpaca documentation read (2026-10-06 docs; 2025 support page): free plan is IEX-only real-time equities; SIP is on Algo Trader Plus at $99/month; no data-use terms appear in the docs.
- [ ] Tiingo and Massive terms are read in full, if either is considered.
- [ ] Counsel reviews this ADR before any external release.

## 4a. Owner decisions, 2026-11-08 (financial expert, on delegation)

- **NewsAPI: turned off.** The free Developer plan is not permitted in production, even internally. The $449/month Business plan is not justified by the trade record. Sentiment falls back to SEC headlines (already in the pipeline), and to neutral where nothing matches. Turning it off means removing the `NEWSAPI_KEY` repository secret (used by `trade.yml`). The owner runs that step, because deleting a secret cannot be undone.
- **GDELT shadow universe: seven names** (MSFT, DIS, AXP, BLK, GOOGL, SBUX, BA), with aliases observed in the data. The other screened names have no matches and cannot be scored by this source. The 80% coverage kill rule therefore cannot be met across the full universe, and it is measured per covered name instead. Review at 90 trading days.
- **Price feed:** unchanged. yfinance stays on the automated path until the Alpaca written answer arrives. This is the interim exposure the owner accepted.

## 5. Acceptance

Owner: ksri77 Date: 2026-11-07 (accepted in chat; the interim rule in the Status line applies)
