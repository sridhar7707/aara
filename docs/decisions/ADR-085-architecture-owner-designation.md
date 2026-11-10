# ADR-085: Architecture Owner Designation

**Status:** Accepted by ksri77 on 2026-11-07 (explicit instruction in session: "name me as owner").
**Decision Type:** Governance: role definition for the owner confirmation that ADR-013 through ADR-056 require.
**Related ADRs:** ADR-057 (defines the owner role and an acceptance mechanism; its mechanism stays Proposed), ADR-058, ADR-082 (accepted by the same owner).

---

## Context

ADR-057 §4 records that no repository document names the architecture owner, yet many ADRs wait on that person's confirmation before they are Accepted. ADR-082 was accepted by ksri77. This ADR removes the ambiguity for the owner role only.

## Decision

1. **Architecture owner:** ksri77, the repository owner.
2. The owner's explicit confirmation satisfies the "architecture owner has confirmed" condition in the ADRs that name it.
3. The owner has final authority over:
   - acceptance of ADRs;
   - product direction and release decisions, including any release to external users;
   - any change to a governed value (`stop_loss`, `daily_loss_limit`, `max_position`, the XGB threshold). These also require an ADR.
4. Advisory roles in `.claude/agents/` (architect, developer, ml-expert, stock-strategist, risk-officer, data-engineer, compliance-advisor, product-manager, security-reviewer, qa-tester, go-to-market, support-docs) cannot accept an ADR, approve a release, or override a risk-officer veto. Only the owner can.
5. An agent's output is never recorded as owner approval.

## Explicitly Not Done By This ADR

- No change to ADR-057's acceptance mechanism. Its §8 re-attestation of ADR-054 to ADR-056 remains open.
- No change to any governed trading value.
- No authorization of a customer-facing release.
