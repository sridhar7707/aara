# Claude Code Migration Instructions

# Sentinel Intelligence → Aara Platform Architecture Migration

**Version:** 1.0
**Status:** Active Migration Plan

> **Naming clarification (per ADR-007):** The retired identity is only the
> old top-level **"Sentinel Intelligence"** brand. **Sentinel Intelligence
> Engine** is not deprecated, renamed, or absorbed — it continues as a
> permanent architectural layer under AARA Systems.

---

# 1. Mission

This document defines the migration strategy for transforming the existing Sentinel Intelligence project into the foundation of the Aara platform.

The goal is architectural evolution, not a rewrite.

Existing intelligence capabilities must be preserved while repositioning the system into a multi-product platform.

## Current Identity

Sentinel Intelligence:

* Investment intelligence application
* Decision support system
* Portfolio analysis and governance platform

## Future Identity

Aara:

* Parent brand and product platform

Sentinel Intelligence Engine:

* Shared intelligence infrastructure powering multiple Aara products

Aara Wealth Intelligence:

* First customer-facing product built on top of Sentinel Intelligence Engine

---

# 2. Core Migration Principles

## Principle 1: Preserve Existing Intelligence Assets

Do not delete or replace:

* Trust Ledger
* Event architecture
* Evidence model
* Governance framework
* Decision lifecycle
* Risk framework
* Projection architecture
* Audit capabilities
* Calibration systems
* Explainability systems

These are foundational Sentinel assets.

---

# Principle 2: Separate Engine From Product

Every future code decision must answer:

"Does this belong to Sentinel Intelligence Engine or Aara Wealth Intelligence?"

## Sentinel Intelligence Engine

Contains reusable intelligence capabilities:

* reasoning
* evidence evaluation
* memory
* governance
* confidence evaluation
* decision explanation
* risk interpretation
* learning loops
* analytical projections

Future Aara products may use this layer:

* Aara Trading Intelligence (Product #1, per ADR-001)
* Aara Wealth Intelligence
* Aara CFO
* Aara Tax Intelligence
* Aara Estate Intelligence
* Future intelligence products

---

## Aara Wealth Intelligence

Contains wealth-domain functionality:

* account aggregation
* holdings analysis
* portfolio structure
* wealth X-Ray
* concentration analysis
* diversification analysis
* wealth health scoring
* financial reports
* user-facing dashboards

---

# 3. Data Privacy Boundary

Consumer financial information must remain isolated.

The Sentinel Intelligence Engine must not directly own:

* Plaid access tokens
* bank credentials
* account numbers
* brokerage identifiers
* raw transaction history
* personally identifiable financial information

Product boundaries own user financial data.

Sentinel receives only controlled analytical representations.

Example:

Product Layer:

```
User Portfolio
Accounts
Holdings
Transactions
Tax Information
```

↓

Transformation Layer:

```
Financial State Object
Risk Profile
Exposure Map
Behavioral Signals
```

↓

Sentinel Intelligence Engine:

```
Analyze
Evaluate
Explain
Remember
Recommend
```

---

# 4. Target Logical Architecture

Future structure:

```
aara/

├── sentinel/
│   ├── core/
│   ├── intelligence/
│   ├── events/
│   ├── evidence/
│   ├── memory/
│   ├── governance/
│   ├── reasoning/
│   └── projections/
│
├── products/
│   └── wealth_intelligence/
│       ├── portfolio/
│       ├── wealth_xray/
│       ├── risk/
│       ├── insights/
│       └── reports/
│
└── shared/
    ├── authentication/
    ├── users/
    ├── notifications/
    └── infrastructure/
```

Note: this diagram reflects physical repository/folder layout only, not
the `AARA Systems → Sentinel Intelligence Engine → Products` brand/
ownership hierarchy defined in ADR-007. `sentinel/` and `products/`
appearing as sibling folders here is a code-organization choice, not a
statement that products sit outside the engine's hierarchy.

---

# 5. Current Repository Mapping

## sentinel/

Current:

```
sentinel/
```

Future:

```
Sentinel Intelligence Engine
```

Contains:

* event system
* governance
* evidence
* projections
* decision intelligence

---

## bot/

Current:

```
bot/
```

Future:

```
Sentinel Market Intelligence Module
```

Status:

Preserved.

It becomes an internal intelligence/research module.

It is NOT the consumer product.

Do not expose trading bot behavior directly to Aara Wealth Intelligence users.

Future possibilities:

* market research module
* investment analysis module
* institutional intelligence component

Note (per ADR-001): Aara Trading Intelligence is Product #1 alongside
Aara Wealth Intelligence (Product #2) — both consume the shared Sentinel
Intelligence Engine. This entry describes `bot/`'s current internal-
research framing; it does not remove Trading Intelligence from the
platform's product set.

---

## dashboard/

Current:

```
dashboard/
```

Future:

```
Aara Wealth Intelligence Experience
```

This evolves into the customer-facing application.

---

# 6. Sentinel Intelligence Engine Contracts

Future engine interfaces should move toward:

## Analyze

```
analyze(financial_state)
```

Purpose:

Produces structured analytical observations.

Example output:

* concentration risk
* exposure analysis
* portfolio structure
* anomalies

---

## Explain

```
explain(context)
```

Purpose:

Converts intelligence into understandable human language.

Example:

"Your portfolio contains multiple funds with overlapping technology exposure."

---

## Remember

```
remember(event)
```

Purpose:

Maintains long-term intelligence memory.

Examples:

* user decisions
* behavioral patterns
* portfolio evolution
* milestones

---

## Evaluate

```
evaluate(risk_state)
```

Purpose:

Applies governance and risk frameworks.

---

## Recommend

```
recommend(insights)
```

Purpose:

Provides possible actions while maintaining human control.

---

# 7. MVP Product Direction

Aara Wealth Intelligence V1 prioritizes:

## Build

1. Account aggregation
2. Wealth X-Ray
3. Portfolio structural analysis
4. Wealth Health Dashboard
5. Monthly Wealth Review
6. Personal Wealth Memory foundation

---

## Deprioritize

Do not optimize for:

* day trading
* automated execution
* market prediction
* real-time trading alerts
* social investing feeds

The product is a wealth intelligence system, not a trading bot.

---

# 8. Migration Rules For Claude Code

## DO

* Make incremental changes
* Preserve existing tests
* Add migration adapters
* Document architectural decisions
* Maintain backward compatibility
* Move functionality gradually

## DO NOT

* Rewrite the repository
* Delete working modules
* Rename everything at once
* Merge engine and product layers
* Remove governance systems
* Remove trading intelligence assets

---

# 9. Naming Rules

## Approved Naming

Company:

```
Aara
```

Platform Engine:

```
Sentinel Intelligence Engine
```

Product:

```
Aara Wealth Intelligence
```

Positioning:

```
Aara Wealth Intelligence
Powered by Sentinel Intelligence Engine
```

---

## Avoid

Do not use:

* Sentinel Trading Bot
* AI Trading System
* Market Prediction Engine
* Autonomous Trading AI

---

# 10. Migration Success Criteria

Migration succeeds when:

1. Sentinel Intelligence Engine can power multiple Aara products.

2. Aara Wealth Intelligence operates independently as a customer product.

3. Existing intelligence assets remain preserved.

4. Financial data privacy boundaries are maintained.

5. The architecture supports future service extraction.

6. Claude Code can safely evolve the repository without destructive rewrites.

---

End of Migration Plan
