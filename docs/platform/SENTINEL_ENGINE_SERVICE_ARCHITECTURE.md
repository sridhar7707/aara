# Sentinel Intelligence Engine Service Architecture

**Version:** 1.0
**Status:** Architecture Foundation
**Platform:** Aara Systems
**Engine:** Sentinel Intelligence Engine

---

# 1. Purpose

This document defines the service architecture of the Sentinel Intelligence Engine.

The goal is to transform existing Sentinel Intelligence capabilities into a reusable intelligence platform that powers multiple Aara products.

Sentinel is not an application.

Sentinel is an intelligence operating layer.

---

# 2. Architectural Philosophy

The Sentinel Engine follows five principles:

## 1. Intelligence Before Interface

Sentinel does not own screens.

Products own user experiences.

---

## 2. Evidence Before Conclusions

Every insight must have supporting evidence.

---

## 3. Memory Before Recommendations

Sentinel learns from historical states before producing new conclusions.

---

## 4. Deterministic Before Generative

Calculations, evaluations, and risk analysis must be deterministic.

LLMs provide explanation and interaction, not financial truth.

---

## 5. Product Independence

Sentinel must never depend on a single Aara product.

---

# 3. Target Service Architecture

Future structure:

```
sentinel/

├── core/
│
│   ├── engine.py
│   ├── context.py
│   ├── lifecycle.py
│   └── contracts.py
│
├── intelligence/
│
│   ├── analysis/
│   ├── reasoning/
│   ├── evaluation/
│   └── recommendation/
│
├── memory/
│
│   ├── event_store.py
│   ├── memory_store.py
│   └── retrieval.py
│
├── evidence/
│
│   ├── evidence_service.py
│   └── evidence_registry.py
│
├── governance/
│
│   ├── rules.py
│   ├── controls.py
│   └── approvals.py
│
├── projections/
│
│   ├── health.py
│   ├── intelligence_views.py
│   └── summaries.py
│
└── api/
    
    ├── analyze.py
    ├── explain.py
    ├── remember.py
    └── evaluate.py

```

---

# 4. Core Services

## 4.1 Intelligence Orchestrator

Location:

```
sentinel/core/
```

Purpose:

Coordinates the intelligence lifecycle.

Responsibilities:

* receive context
* invoke analysis
* collect evidence
* generate insight
* store memory
* return result

Example:

```python
analyze(context)

    ↓

analysis services

    ↓

evidence collection

    ↓

insight generation

    ↓

memory update

```

---

# 4.2 Analysis Service

Location:

```
sentinel/intelligence/analysis/
```

Purpose:

Convert state into measurable observations.

Examples:

```
risk analysis

pattern detection

trend analysis

anomaly detection

structural analysis

```

Does:

```
Input:

financial_state


Output:

metrics

observations

risk factors

```

Does NOT:

* create UI text
* communicate with users
* store raw customer data

---

# 4.3 Reasoning Service

Location:

```
sentinel/intelligence/reasoning/
```

Purpose:

Convert observations into meaningful intelligence.

Example:

Input:

```
Technology concentration increased 18%
```

Output:

```
Portfolio has increased dependency on technology sector.
```

Responsibilities:

* relationship discovery
* context interpretation
* prioritization

---

# 4.4 Explanation Service

Location:

```
sentinel/intelligence/explanation/
```

Purpose:

Generate human-understandable explanations.

Powered by:

* deterministic findings
* evidence
* memory

Possible implementation:

LLM wrapper.

Rules:

LLM cannot invent:

* numbers
* risk scores
* recommendations
* financial facts

---

# 4.5 Memory Service

Location:

```
sentinel/memory/
```

Purpose:

Maintain long-term intelligence continuity.

Responsibilities:

Store:

* historical observations
* behavioral patterns
* previous insights
* user preferences

Example:

```
User historically ignores short-term volatility.

Previous market events:

-10%
-15%

No panic actions.

```

---

# 4.6 Evidence Service

Location:

```
sentinel/evidence/
```

Purpose:

Maintain auditability.

Every insight requires:

```
Claim

+

Evidence

+

Confidence

+

Timestamp

```

---

# 4.7 Governance Service

Location:

```
sentinel/governance/
```

Purpose:

Ensure safe operation.

Existing assets:

```
risk governor

approval workflow

constitution

trust ledger

```

remain here.

---

# 4.8 Evaluation Service

Location:

```
sentinel/intelligence/evaluation/
```

Purpose:

Measure intelligence quality.

Examples:

```
confidence calibration

decision quality

outcome accuracy

model drift

```

---

# 5. API Contracts

Sentinel exposes capability APIs.

---

## analyze()

Purpose:

Analyze a state.

Input:

```python
SentinelContext
```

Output:

```python
AnalysisResult
```

Example:

```python
{
 observations:[
   "High technology concentration"
 ],
 metrics:{
   concentration:0.62
 }
}
```

---

## explain()

Purpose:

Explain intelligence.

Input:

```python
Insight + Evidence
```

Output:

```python
HumanExplanation
```

---

## remember()

Purpose:

Store intelligence memory.

Input:

```python
MemoryEvent
```

Output:

```python
MemoryReference
```

---

## evaluate()

Purpose:

Evaluate outcomes.

Input:

```python
Decision + Result
```

Output:

```python
EvaluationResult
```

---

## recommend()

Purpose:

Generate possible actions.

Important:

Sentinel recommends.

Products decide how to present actions.

---

# 6. Existing Code Migration Map

## Current:

```
sentinel/events/
```

Future:

```
sentinel/memory/event_store
```

---

## Current:

```
sentinel/services/
```

Future:

```
sentinel/intelligence/services
```

---

## Current:

```
sentinel/projections/
```

Future:

```
sentinel/projections
```

---

## Current:

```
ledger/
```

Future:

```
sentinel/memory/trust_ledger
```

---

## Current:

```
bot/risk/
bot/decision/
bot/eval/
```

Future:

```
sentinel/intelligence/
```

---

# 7. What Moves To Aara Wealth Intelligence

These remain product-specific:

```
portfolio screens

account aggregation

Plaid integration

holdings display

wealth dashboard

monthly reports

user onboarding

subscription logic

```

---

# 8. What Does NOT Belong In Sentinel

Never add:

```
React components

Gradio pages

broker credentials

Plaid tokens

customer accounts

product-specific workflows

```

---

# 9. Runtime Flow

Example:

Aara Wealth Intelligence:

```
User connects accounts

        |

Portfolio state created

        |

Send abstract context

        |

Sentinel analyzes

        |

Evidence created

        |

Insight generated

        |

Memory updated

        |

Aara displays calm explanation

```

---

# 10. Future Product Expansion

The same services support:

## Aara Wealth Intelligence

```
Portfolio intelligence
Risk intelligence
Investment memory
```

---

## Aara CFO

```
Financial intelligence
Cash-flow analysis
Business memory
```

---

## Aara Tax

```
Tax intelligence
Optimization analysis
Compliance memory
```

---

# 11. Migration Rules For Claude Code

Claude must:

DO:

* preserve existing services
* create adapters
* move gradually
* maintain tests

DO NOT:

* rewrite Sentinel
* merge product and engine
* remove trading intelligence
* replace event architecture

---

# Final Architecture Principle

> Sentinel provides intelligence.
> Aara products provide experiences.

---

# End of Document
