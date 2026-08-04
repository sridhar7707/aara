# Sentinel Intelligence Engine Event Architecture

**Version:** 1.0
**Status:** Architecture Foundation
**Platform:** Aara Systems
**Engine:** Sentinel Intelligence Engine

---

# 1. Purpose

This document defines the event-driven architecture of the Sentinel Intelligence Engine.

Sentinel is not a stateless AI service.

It is a continuously evolving intelligence system that learns through:

* observations
* evidence
* evaluations
* decisions
* outcomes
* historical memory

Every meaningful intelligence transition is represented as an immutable event.

---

# 2. Core Event Philosophy

Sentinel follows the principle:

```
Nothing important happens silently.
```

Every important state transition creates an event.

Example:

```
Portfolio Changed

        ↓

Observation Created

        ↓

Evidence Attached

        ↓

Risk Evaluated

        ↓

Decision Generated

        ↓

Outcome Recorded

        ↓

Memory Updated
```

---

# 3. Why Events Instead of Direct Database Updates

Traditional application:

```
User Data
    |
    ↓
Database Row Updated
```

Sentinel:

```
Something happened

        ↓

Event Created

        ↓

State Projection Updated

        ↓

Intelligence Generated

        ↓

Memory Preserved
```

Benefits:

* complete history
* explainability
* reproducibility
* auditability
* debugging
* future model training
* regulatory readiness

---

# 4. Event Categories

Sentinel events are grouped into six categories.

```
1. Context Events

2. State Events

3. Intelligence Events

4. Decision Events

5. Outcome Events

6. Memory Events
```

---

# 5. Context Events

## Purpose

Represent changes in the environment Sentinel is analyzing.

Examples:

```
User Profile Updated

Product Context Created

Risk Preference Changed

Business Context Added
```

---

Example:

```json
{
"event_type":

"context.created",

"entity":

"user_context",

"payload":{

"context_type":"wealth",

"horizon":"long_term"

}
}
```

---

# 6. State Events

## Purpose

Represent changes in the analyzed object.

Examples:

Aara Wealth Intelligence:

```
Portfolio Connected

Holdings Updated

Allocation Changed

Net Worth Snapshot Created
```

---

Example:

```json
{
"event_type":

"portfolio.snapshot.created",

"payload":{

"equity":0.72,

"cash":0.10,

"fixed_income":0.18

}
}
```

---

# 7. Intelligence Events

These represent Sentinel reasoning output.

They are generated from deterministic analysis.

---

## 7.1 Observation Event

Example:

```
Hidden ETF overlap detected
```

Event:

```json
{
"event_type":

"intelligence.observation.created",

"payload":{

"type":

"overlap_detection",

"confidence":

0.94

}
}
```

---

## 7.2 Evidence Event

Evidence must always support intelligence.

Example:

```
VOO and SPY contain overlapping holdings
```

```json
{
"event_type":

"evidence.attached",

"payload":{

"source":

"holdings_analysis",

"confidence":

0.96

}
}
```

---

## 7.3 Evaluation Event

Determines importance.

Example:

```
Moderate concentration concern
```

```json
{
"event_type":

"risk.evaluation.completed",

"payload":{

"severity":

"medium"

}
}
```

---

# 8. Decision Events

## Purpose

Capture recommended actions.

Important:

Sentinel does not execute user decisions.

Sentinel provides intelligence.

---

Example:

```json
{
"event_type":

"decision.created",

"payload":{

"recommendation":

"review allocation",

"approval_required":

true

}
}
```

---

# 9. Approval Events

For future governance workflows.

Examples:

```
User approved recommendation

Advisor approved action

System rejected action
```

---

Example:

```json
{
"event_type":

"decision.approved",

"payload":{

"approved_by":

"user"

}
}
```

---

# 10. Outcome Events

## Purpose

Close the intelligence loop.

Without outcomes Sentinel cannot improve.

---

Example:

Decision:

```
Review technology allocation
```

Outcome:

```
User adjusted allocation
```

---

Event:

```json
{
"event_type":

"decision.outcome.recorded",

"payload":{

"result":

"accepted",

"impact":

"reduced concentration"

}
}
```

---

# 11. Memory Events

Memory is created from accumulated events.

Examples:

```
User behavior learned

Portfolio baseline created

Preference updated

Historical pattern detected
```

---

Example:

```json
{
"event_type":

"memory.created",

"payload":{

"type":

"behavioral",

"pattern":

"prefers_monthly_review"

}
}
```

---

# 12. Event Envelope Standard

All Sentinel events follow the same structure.

```json
{
"event_id":

"uuid",

"event_type":

"decision.created",

"aggregate_id":

"portfolio_uuid",

"source":

"sentinel_engine",

"version":

1,

"timestamp":

"ISO-8601",

"payload":{},

"metadata":{

"correlation_id":

"uuid"

}
}
```

---

# 13. Event Storage Rules

Events are:

* append-only
* immutable
* timestamped
* hashable
* replayable

Events are never:

* deleted
* modified
* overwritten

---

# 14. Current Code Mapping

Existing Sentinel implementation:

| Current Code    | Future Role               |
| --------------- | ------------------------- |
| sentinel/events | Core event infrastructure |
| event.py        | Event definition          |
| event_writer.py | Event persistence         |
| event_types.py  | Event registry            |
| hash_chain.py   | Integrity verification    |
| ledger.py       | Event ledger              |
| projections     | Read models               |

---

# 15. Event Flow Architecture

```
PRODUCT APPLICATION

Aara Wealth Intelligence

        |
        |
        ↓

Sentinel API Boundary

        |
        ↓

Event Creation

        |
        ↓

Sentinel Event Store

        |
        ↓

Analysis Services

        |
        ↓

Evidence + Evaluation

        |
        ↓

Decision Event

        |
        ↓

Memory Update

        |
        ↓

Product Presentation Layer

```

---

# 16. Product Isolation Rules

Products create events.

Sentinel processes events.

Products own:

```
User identity

Raw financial connections

Private credentials

External integrations
```

Sentinel owns:

```
Event definitions

Reasoning lifecycle

Evidence chain

Memory evolution

```

---

# 17. Future Multi-Product Support

The same event architecture supports:

## Aara Wealth Intelligence

Events:

```
portfolio.snapshot.created

allocation.changed

risk.evaluated

```

---

## Aara CFO

Events:

```
financial.statement.created

cashflow.changed

expense.detected

```

---

## Aara Tax Intelligence

Events:

```
tax_document.received

deduction.detected

tax_strategy.evaluated

```

---

# 18. Sentinel Intelligence Principle

The event ledger is the memory backbone of Sentinel.

AI models may change.

Algorithms may improve.

Interfaces may evolve.

But the event history remains the source of truth.

---

# End of Document
