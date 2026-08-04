# Sentinel Intelligence Engine Runtime Flow

**Version:** 1.0
**Status:** Architecture Foundation
**Platform:** Aara Systems
**Engine:** Sentinel Intelligence Engine

---

# 1. Purpose

This document defines the runtime lifecycle of the Sentinel Intelligence Engine.

The purpose is to establish how information moves through Sentinel from product input to user-facing intelligence.

Sentinel is not a user application.

Sentinel is an intelligence processing layer that transforms financial and operational states into:

* observations
* explanations
* evaluations
* recommendations
* long-term memory

---

# 2. Runtime Philosophy

Sentinel follows this lifecycle:

```
Observe

↓

Understand

↓

Evaluate

↓

Explain

↓

Remember

↓

Improve
```

Every intelligence output must be:

* explainable
* evidence-backed
* reproducible
* historically aware

---

# 3. High-Level Runtime Architecture

```
AARA PRODUCT

(Aara Wealth Intelligence)

        |

        |

Product Context Adapter

        |

        ↓

SENTINEL INTELLIGENCE ENGINE

        |

        |

+-----------------------+
| Context Intake Layer  |
+-----------------------+

        |

        ↓

+-----------------------+
| Intelligence Pipeline |
+-----------------------+

        |

        ↓

+-----------------------+
| Evidence Layer        |
+-----------------------+

        |

        ↓

+-----------------------+
| Memory Layer          |
+-----------------------+

        |

        ↓

+-----------------------+
| Response Layer        |
+-----------------------+

        |

        ↓

AARA PRODUCT EXPERIENCE

```

---

# 4. Stage 1 — Context Intake

## Purpose

Receive structured information from an Aara product.

Sentinel does not directly connect to:

* banks
* brokers
* Plaid
* user accounts

The product owns data ownership.

---

## Example Input

Aara Wealth Intelligence sends:

```json
{
"user_id":"123",

"portfolio_state":{

"assets":500000,

"equity_percentage":72,

"technology_exposure":0.41,

"fund_overlap":3

},

"user_context":{

"horizon":"long_term",

"risk_profile":"moderate"

}

}
```

---

## Rule

Sentinel receives intelligence-ready context.

It does not receive unnecessary private financial information.

---

# 5. Stage 2 — State Normalization

## Purpose

Convert different product inputs into a common Sentinel format.

Example:

Aara Wealth Intelligence:

```
Portfolio State
```

Aara CFO:

```
Business Financial State
```

Aara Tax:

```
Tax Position State
```

becomes:

```
Sentinel Context Model
```

---

# 6. Stage 3 — Intelligence Processing

The intelligence pipeline executes.

---

## 6.1 Analysis

Location:

```
sentinel/intelligence/analysis
```

Purpose:

Find measurable facts.

Examples:

```
Technology exposure increased 12%

Portfolio overlap detected

Risk concentration increased

Savings velocity changed

```

Output:

```json
{
"type":"observation",

"metric":"technology_exposure",

"value":0.41

}
```

---

# 6.2 Evaluation

Location:

```
sentinel/intelligence/evaluation
```

Purpose:

Determine significance.

Example:

Input:

```
Technology exposure = 41%
```

Evaluation:

```
Higher than target range.

Requires awareness.

```

Output:

```json
{
"severity":"medium",

"confidence":0.87

}
```

---

# 6.3 Reasoning

Location:

```
sentinel/intelligence/reasoning
```

Purpose:

Understand relationships.

Example:

Raw facts:

```
VOO holding

QQQ holding

NVDA holding

MSFT holding

```

Reasoning:

```
Portfolio has overlapping technology exposure.

```

---

# 7. Stage 4 — Evidence Creation

Every Sentinel insight requires evidence.

Structure:

```
Insight

+

Supporting Data

+

Calculation

+

Timestamp

+

Confidence

```

Example:

```json
{
"claim":

"Technology concentration increased",

"evidence":[

"QQQ allocation",

"Individual stock exposure"

],

"confidence":0.91

}
```

---

# 8. Stage 5 — Memory Update

Sentinel maintains intelligence continuity.

Memory captures:

## Structural Memory

Examples:

```
Portfolio allocation history

Risk changes

Financial milestones

```

---

## Behavioral Memory

Examples:

```
User remained invested during downturn

User prefers fewer notifications

User ignores short-term volatility

```

---

## Decision Memory

Examples:

```
Previous insight

User response

Outcome

```

---

# 9. Stage 6 — Explanation Generation

The explanation layer converts intelligence into human understanding.

Important:

The explanation layer does NOT create financial conclusions.

It communicates existing conclusions.

---

Example:

Internal:

```
Technology concentration:
41%

Benchmark:
30%

Deviation:
+11%

```

User explanation:

```
Aara noticed your portfolio has gradually become more dependent on technology companies. This is not necessarily a problem, but it is something worth understanding within your long-term plan.
```

---

# 10. Stage 7 — Product Response

Sentinel returns structured intelligence.

Example:

```json
{
"insight":

{

"title":
"Technology Exposure Review",

"severity":
"awareness",

"message":
"...",

"evidence_id":
"abc123"

}

}
```

---

The product decides:

* where to display it
* when to notify
* how to personalize UX

---

# 11. Complete Example Flow

Scenario:

User connects investment accounts.

---

## Step 1

Aara collects accounts.

```
Vanguard

Robinhood

401K

IRA

```

---

## Step 2

Aara calculates portfolio state.

```
Total assets:

$350,000

```

---

## Step 3

Sentinel receives:

```
Portfolio Context
```

---

## Step 4

Sentinel analyzes:

```
Overlap detected

Technology concentration high

```

---

## Step 5

Evidence created:

```
23 overlapping holdings

41% technology exposure

```

---

## Step 6

Memory stored:

```
Initial Wealth X-Ray completed

```

---

## Step 7

Aara displays:

```
Your Wealth X-Ray

We discovered 3 hidden structural patterns.

```

---

# 12. Scheduled Intelligence

Sentinel supports recurring analysis.

Examples:

Daily:

```
Risk state refresh

```

Weekly:

```
Portfolio health review

```

Monthly:

```
Wealth evolution report

```

Yearly:

```
Long-term structural assessment

```

---

# 13. Event Driven Architecture

Sentinel should evolve toward event-driven processing.

Example:

```
PortfolioUpdatedEvent

        ↓

RiskAnalysisRequested

        ↓

EvidenceCreated

        ↓

InsightGenerated

        ↓

MemoryUpdated

```

---

# 14. Failure Handling

Sentinel must fail safely.

Rules:

If data is incomplete:

```
Do not guess.

Return insufficient evidence.

```

If confidence is low:

```
Reduce recommendation strength.

```

If external service fails:

```
Preserve existing memory.

Retry later.

```

---

# 15. Runtime Separation Rules

## Sentinel owns:

```
reasoning

analysis

memory

evidence

governance

evaluation

```

---

## Aara Products own:

```
authentication

customer data

billing

UI

notifications

account connections

```

---

# 16. Future Multi-Product Flow

Example:

```
Aara Wealth Intelligence

        |
        |
        ↓

Sentinel Intelligence Engine

        |
        |
        +---- Wealth Intelligence Module

        +---- CFO Intelligence Module

        +---- Tax Intelligence Module

        +---- Real Estate Intelligence Module

```

---

# Final Principle

> Sentinel does not replace human decisions.
> Sentinel creates the intelligence foundation that makes better decisions possible.

---

# End of Document
