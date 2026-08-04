# Sentinel Intelligence Engine Data Model

**Version:** 1.0
**Status:** Architecture Foundation
**Platform:** Aara Systems
**Engine:** Sentinel Intelligence Engine

---

# 1. Purpose

This document defines the canonical data model used by the Sentinel Intelligence Engine.

The goal is to create a reusable intelligence foundation that supports multiple Aara products.

Sentinel does not store product-specific customer data.

Instead, Sentinel operates on structured intelligence objects:

* Context
* State
* Observation
* Evidence
* Evaluation
* Decision
* Memory
* Outcome

---

# 2. Core Data Philosophy

Sentinel follows this principle:

```
Data → Understanding → Evidence → Intelligence → Memory
```

Raw data alone has no intelligence value.

Sentinel transforms states into explainable knowledge.

---

# 3. Core Domain Objects

The Sentinel Engine consists of eight primary objects.

```
Context
   |
   ↓
State
   |
   ↓
Observation
   |
   ↓
Evidence
   |
   ↓
Evaluation
   |
   ↓
Decision
   |
   ↓
Outcome
   |
   ↓
Memory
```

---

# 4. Context Model

## Purpose

Defines who or what Sentinel is analyzing.

Context is provided by Aara products.

Example:

Aara Wealth Intelligence:

```
Investor Context
```

Aara CFO:

```
Business Context
```

---

## Schema

```json
{
"context_id":"uuid",

"context_type":
"wealth",

"product":
"aara_wealth_intelligence",

"user_profile":{

"time_horizon":"long_term",

"risk_preference":"moderate"

},

"created_at":"timestamp"

}
```

---

## Rules

Sentinel does not own:

* identity information
* authentication
* billing information
* account credentials

---

# 5. State Model

## Purpose

Represents the current condition of something.

Examples:

Portfolio State:

```
Current asset allocation

Risk exposure

Concentration

Cash position

```

Business State:

```
Revenue

Expenses

Margins

Cash flow

```

---

## Schema

```json
{
"state_id":"uuid",

"context_id":"uuid",

"state_type":
"portfolio_state",

"attributes":{

"equity_exposure":0.72,

"technology_exposure":0.41,

"cash":0.08

},

"timestamp":"timestamp"

}
```

---

# 6. Observation Model

## Purpose

A factual finding produced by analysis.

Observations are NOT recommendations.

Example:

Observation:

```
Technology exposure increased from 31% to 41%
```

---

## Schema

```json
{
"observation_id":"uuid",

"state_id":"uuid",

"type":

"concentration_change",

"value":{

"previous":0.31,

"current":0.41

},

"detected_at":"timestamp"

}
```

---

# 7. Evidence Model

## Purpose

Provides the proof behind every Sentinel insight.

No intelligence should exist without evidence.

---

## Schema

```json
{
"evidence_id":"uuid",

"observation_id":"uuid",

"sources":[

{
"type":"holding",

"value":"QQQ"
},

{
"type":"holding",

"value":"NVDA"
}

],

"calculation":

"weighted technology exposure",

"confidence":0.91

}
```

---

# 8. Evaluation Model

## Purpose

Determines importance.

An observation becomes meaningful only after evaluation.

---

Example:

Observation:

```
Technology exposure = 41%
```

Evaluation:

```
Above target range.

Monitor.
```

---

## Schema

```json
{
"evaluation_id":"uuid",

"observation_id":"uuid",

"severity":

"medium",

"confidence":

0.87,

"impact":

"portfolio_structure"

}
```

---

# 9. Decision Model

## Purpose

Represents a recommended action or user choice.

Important:

Sentinel recommends.

Humans or products decide.

---

Example:

```
Review technology concentration
```

---

## Schema

```json
{
"decision_id":"uuid",

"evaluation_id":"uuid",

"type":

"review",

"recommendation":

"evaluate allocation balance",

"approval_required":

true

}
```

---

# 10. Outcome Model

## Purpose

Records what happened after intelligence was delivered.

This enables learning.

---

Example:

Before:

```
Concentration warning
```

After:

```
User rebalanced allocation
```

---

## Schema

```json
{
"outcome_id":"uuid",

"decision_id":"uuid",

"result":

"accepted",

"impact":

"reduced concentration",

"timestamp":

"timestamp"

}
```

---

# 11. Memory Model

## Purpose

Creates Sentinel's long-term intelligence advantage.

Memory allows Sentinel to understand history.

---

## Memory Types

## 11.1 Structural Memory

Tracks changing states.

Example:

```
Portfolio allocation history

Risk evolution

Financial milestones

```

---

## 11.2 Behavioral Memory

Tracks user interaction patterns.

Example:

```
User prefers monthly reviews

User ignores daily market noise

User tolerates volatility

```

---

## 11.3 Decision Memory

Tracks previous intelligence cycles.

Example:

```
Insight generated

User response

Outcome

```

---

## Schema

```json
{
"memory_id":"uuid",

"memory_type":

"behavioral",

"entity":

"user",

"pattern":

"prefers_low_frequency_updates",

"confidence":

0.82

}
```

---

# 12. Intelligence Object

This is the final object returned to products.

---

Example:

```json
{
"intelligence_id":"uuid",

"title":

"Hidden Technology Concentration",

"summary":

"Your portfolio has increased exposure to technology companies.",

"evidence_id":

"abc123",

"confidence":

0.91,

"severity":

"awareness"

}
```

---

# 13. Wealth Intelligence Example

Complete lifecycle:

```
User connects accounts

        ↓

Aara creates Portfolio State

        ↓

Sentinel analyzes

        ↓

Observation:

Fund overlap detected

        ↓

Evidence:

23 duplicate underlying holdings

        ↓

Evaluation:

Moderate concentration risk

        ↓

Decision:

Review allocation

        ↓

Memory:

Portfolio baseline created

        ↓

Aara displays:

Wealth X-Ray Insight

```

---

# 14. Relationship To Existing Sentinel Code

Current implementation mapping:

| Existing Component | Future Role               |
| ------------------ | ------------------------- |
| trust_ledger       | Memory + Evidence history |
| decisions.py       | Decision Model            |
| evidence.py        | Evidence Model            |
| outcomes.py        | Outcome Model             |
| projections        | Derived State Models      |
| governance.py      | Evaluation Controls       |
| user_context.py    | Context Model             |
| risk models        | Evaluation Layer          |

---

# 15. Data Ownership Rules

## Aara Products Own:

```
User identity

Financial connections

Raw transactions

Broker credentials

Billing

UI state

```

---

## Sentinel Owns:

```
Derived intelligence

Evidence

Reasoning

Evaluations

Memory

Decision history

```

---

# 16. Privacy Boundary

Sensitive data should not flow unnecessarily into Sentinel.

Example:

Allowed:

```
Technology exposure = 41%
```

Not required:

```
User account number

Broker login

Individual transaction history

```

Products sanitize context before engine processing.

---

# 17. Future Product Extension

The same model supports:

## Aara Wealth Intelligence

Context:

Investor

State:

Portfolio

---

## Aara CFO Intelligence

Context:

Business

State:

Financial operations

---

## Aara Tax Intelligence

Context:

Taxpayer

State:

Tax position

---

# 18. Final Principle

> Sentinel does not store everyone's financial life.
> Sentinel stores the intelligence required to understand it.

---

# End of Document
