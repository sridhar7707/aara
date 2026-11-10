# ADR-092: Enforce Constitution Rules 1, 4 and 5; Rule 2 Stays Advisory

**Status:** Accepted by the financial expert on the owner's delegation, 2026-11-09. Owner ratification pending. Implementation is not started.
**Decision Type:** Governance: moves named constitution rules from advisory to enforced.
**Related:** ADR-047 (Rule 1), ADR-048 (Rule 4), ADR-050 (Rule 5), ADR-051 (Rule 2), ADR-046 (derived views).

## Decision
1. **Enforce Rule 1 (risk-governor advisory boundary), Rule 4 (drawdown circuit breaker) and Rule 5 (approval escalation for the first N trades).** Enforcement means a breach blocks the action, rather than only recording it.
2. **Rule 2 (position-sizing discipline) stays advisory** until sizing is verified against the trade record.
3. **Rule 3 (trade structure) is decided at its own review,** not here.

## Reasons
- Realised expectancy is negative (the scorecard, 2026-11-07). An unenforced limit has not prevented losses.
- Enforcement costs little when a rule is correct, and prevents the most costly error when it is not.
- Rule 2 depends on sizing inputs that are not yet verified, so enforcing it could block good trades on bad data.

## Consequences
- Trades that Rule 1, 4 or 5 would block are stopped. Expect fewer entries while the rules are enforced.
- Each block is recorded so the effect can be measured.

## Needed before implementation
- Owner ratification of this ADR.
- Tests for each enforced rule, including the blocked case and the allowed case.
- Quant review of the drawdown threshold used by Rule 4.
