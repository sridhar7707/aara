# ADR-091: Reconcile Verification Window for Confirmed-Empty Broker Reads

**Status:** Decided 2026-11-09 by the financial expert on the owner's delegation: option B, require a matching broker fill before any SELL_RECONCILE, with option A as the fallback when order history is unavailable. Implementation is not yet started and needs owner acceptance of this ADR before it touches the frozen reconcile path.
**Decision Type:** Trading-behaviour policy for position reconciliation. Touches a frozen path (`bot/main.py`, `bot/_main_positions.py`). Does not change a governed value.
**Related:** ADR-088 (section 6), ADR-075 (capital-pool reconciliation), ADR-002.

## 1. Context

When the broker's positions read is empty while the database holds open positions, the bot re-verifies up to three times, about 8 seconds in total. If all reads stay empty, it treats the positions as genuinely closed and writes SELL_RECONCILE rows. The sanity check (portfolio value below 50% of the last snapshot) blocks reconcile entirely.

A broker outage longer than about 8 seconds would therefore close every position in the database as a phantom sell. The data shows no confirmed case so far. The logs that could show one have expired.

## 2. Options (owner decides)

- **A. Longer verification window.** For example, 60 seconds, with more attempts. Cheap; delays reconcile slightly.
- **B. Require an independent confirmation.** Before a SELL_RECONCILE, check the broker's order history and account activity for a matching fill. No fill, no reconcile. This is the strongest guard.
- **C. Keep the current policy and disclose.** Accept the risk, and add an alert when a confirmed-empty read is followed by reconcile.

Recommendation: B, with A as a fallback when order history is unavailable.

## 3. Consequences

- Option B needs an extra broker call per reconcile event, and an owner-approved rule for what counts as a matching fill.
- Any change must be tested against the existing reconcile tests and shadowed before live use.

## 4. Acceptance

Owner: __________________ Date: __________
