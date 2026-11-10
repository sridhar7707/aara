# ADR-090: Third-Party Prices Stay Private; Public Branch Carries Only Derived Scores

**Status:** Accepted by ksri77 on 2026-11-10 ("i give you permission to do all"). Records an incident and a publication rule. The workflow change that implements the rule is NOT yet made, so the forward-log job stays disabled until it is.
**Decision Type:** Data-handling rule and incident record. Amends ADR-084 (forward-log workflow) and ADR-087 (public-repo rules).

## Incident
- The scheduled forward-log job committed `forward_log/prices.csv` (raw daily closes obtained from yfinance / Yahoo Finance) to the public `forward-log-data` branch on 2026-11-09 and 2026-11-10 (commit `fd5a12c`).
- The job was disabled (`forward_log.yml`, state `disabled_manually`). The current branch tip removes `prices.csv` (commit `baa4243`).
- **The earlier copies remain in the branch history and cannot be removed.** The branch ruleset blocks force-push and deletion, which protects the audit record and also means the published prices cannot be withdrawn from history.
- Yahoo's terms restrict automated collection and publication of its data. Publishing those prices was not permitted.

## Rule
1. **Third-party prices never go to a public branch, a public artifact, or any published result.** This includes raw closes, adjusted closes, and any series from which prices can be reconstructed.
2. **Prices may be stored locally** (git-ignored `data/`) for private research, on the owner's own machine. Yahoo's terms restrict automated collection, and the owner accepts that risk for local research only.
3. **Derived statistics may be published** only with citation, and only if they cannot be used to recover prices (per the ADR-087 rules). Momentum scores are derived from prices, so they are not covered by this rule yet; see open question 1.
4. **EDGAR fundamentals** (SEC public information) may be published with the citation SEC requests. The SEC name and logo are not used as branding.
5. **Wikipedia-derived membership** may be published under CC BY-SA 4.0 with attribution; the underlying S&P facts are unverified.

## Required before the forward-log job is re-enabled
- Change `forward_log.yml` so it no longer commits `prices.csv`. Scores only, and only if open question 1 is resolved in favour of publishing.
- The change needs its own review and the owner's acceptance, as it changes a scheduled, write-scoped workflow.

## Open questions (owner)
1. **Are momentum scores publishable?** They are derived from Yahoo prices. If they cannot be reconstructed into prices, publishing ranks may be acceptable. Counsel should decide.
2. **Counsel review.** Any public release of results built on yfinance data needs a lawyer's view before publication.
3. **Keep or remove the public branch.** Its history already holds the incident data.

## Consequences
- The fundamentals reject test (ADR-089) results remain valid as a local result. Publishing its numbers is a derived statistic and still needs open question 2.
- No real money, no trading change, no limit change.
