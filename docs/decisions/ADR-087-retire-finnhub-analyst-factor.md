# ADR-087: Retire the Finnhub Analyst Factor

**Status:** Proposed. Not accepted. Implementation waits for the owner's acceptance.
**Decision Type:** Narrow data-source licensing change. Removes one screener factor. Does not change any governed trading value.
**Related:** ADR-086 (data-source licensing remediation).

## 1. Context

- Finnhub's terms (read 2026-11-07) say: "All plan listed on Finnhub website is strictly for personal use unless explicitly stated otherwise", and "Personal plan can't be used by any business even internally without a written approval".
- The bot uses Finnhub for one factor: the analyst upgrade and downgrade signal, for the top 50 screener candidates (`scripts/screen_universe.py`, Stage 2b). The factor is optional: when `FINNHUB_API_KEY` is unset, it is skipped (`screen_universe.py` line 324).
- Finnhub is also referenced in `config.py`, `scripts/_screener_helpers.py`, `scripts/dashboard.py`, and in the `trade.yml` and `premarket.yml` workflow environments.

## 2. Decision (proposed)

1. Retire the analyst factor. Do not replace it now.
2. After acceptance, the owner removes the `FINNHUB_API_KEY` repository secret. The screener then skips the factor, as the code already allows.
3. Re-adding the key requires Finnhub's written approval for business use. It does not come back on the personal plan.

## 3. Consequences

- The screener's ranking changes. The analyst factor carried weight in the top-50 ranking, so the top names may change.
- Before acceptance, measure the effect: compare the top-20 screener output with and without the factor, using logged screener runs (`screener_log`). The owner decides whether the change is acceptable.
- Cost: $0 saved on a free plan; the licensing exposure is removed.

## 4. Acceptance

Owner: __________________ Date: __________
