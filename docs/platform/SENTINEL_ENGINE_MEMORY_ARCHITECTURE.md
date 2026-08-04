# Sentinel Intelligence Engine Memory Architecture

**Version:** 1.0
**Status:** Architecture Definition
**Parent Platform:** Aara Platform
**Engine:** Sentinel Intelligence Engine
**First Product Consumer:** Aara Wealth Intelligence

---

# 1. Purpose

The Sentinel Intelligence Engine Memory Architecture defines how Sentinel maintains historical understanding across decisions, observations, user context, and system evolution.

Memory is a core differentiator.

Traditional applications store data.

Sentinel maintains understanding.

The purpose of memory is to allow Sentinel-powered products to answer:

* What happened?
* Why did it happen?
* What did we know at the time?
* What decisions were made?
* What was the outcome?
* What patterns have emerged over time?

---

# 2. Memory Design Principles

## Principle 1: Memory Is Not Raw Data Storage

Sentinel does not become the owner of product-specific private data.

Products own user data.

Sentinel owns intelligence derived from that data.

Example:

Product Layer:

```
User owns:
- Vanguard account
- Brokerage holdings
- Tax information
- Account identifiers
```

Sentinel Layer:

```
Understands:
- Portfolio concentration increased
- Risk exposure changed
- Decision quality trend improved
- User behavior pattern detected
```

---

# 3. Memory Boundary Model

```
                    AARA PLATFORM

+-----------------------------------------+
|                                         |
|        Aara Wealth Intelligence         |
|                                         |
|  User Financial Data                    |
|  Accounts                              |
|  Holdings                              |
|  Transactions                          |
|  Tax Data                              |
|                                         |
+-------------------+---------------------+
                    |
                    |
          Abstract Intelligence Events
                    |
                    v

+-----------------------------------------+
|                                         |
|       Sentinel Intelligence Engine       |
|                                         |
|  Memory                                |
|  Evidence                              |
|  Reasoning                             |
|  Governance                            |
|  Learning                              |
|                                         |
+-----------------------------------------+
```

---

# 4. Memory Layers

Sentinel memory consists of five layers.

---

# Layer 1: Event Memory

Purpose:

Capture important occurrences.

Examples:

* portfolio evaluation completed
* risk threshold crossed
* recommendation generated
* user approved action
* market regime changed

Example:

```
Portfolio concentration increased from 35% to 52%.

Detected:
2026-08-01

Source:
Portfolio Analysis Module

Confidence:
92%
```

Stored through:

```
event_store
```

---

# Layer 2: Decision Memory

Purpose:

Remember decisions and their reasoning.

Every significant intelligence output should answer:

```
What decision was considered?

What evidence supported it?

What alternatives existed?

What happened afterward?
```

Example:

```
Decision:
Maintain technology allocation

Reason:
Long-term horizon
No liquidity requirement
Risk tolerance stable

Outcome:
Reviewed after 90 days
```

---

# Layer 3: User Intelligence Memory

Purpose:

Build understanding of the user's financial behavior.

Examples:

```
User prefers:
- explanation before action
- conservative recommendations
- long-term perspective

User behavior:
- does not panic sell
- reviews monthly
- responds well to visual explanations
```

Important:

This is not psychological profiling.

It is interaction preference and financial decision behavior.

---

# Layer 4: Pattern Memory

Purpose:

Identify recurring structures.

Examples:

Portfolio Patterns:

```
Repeated overlap:
VOO + retirement fund + brokerage ETF

Pattern:
Unintentional S&P concentration
```

Behavior Patterns:

```
Market decline:
-10%

Historical behavior:
No emotional selling
```

---

# Layer 5: Institutional Memory

Purpose:

Maintain Sentinel's operational history.

Examples:

* model versions
* reasoning changes
* governance changes
* architecture decisions
* evaluation results

This allows Sentinel to explain:

"Why does the system behave this way today?"

---

# 5. Memory Objects

Core memory entities:

## Memory Event

```
MemoryEvent

id
timestamp
source
event_type
entity_reference
payload
confidence
```

---

## Decision Record

```
DecisionMemory

id
decision_type
context
evidence
reasoning
recommendation
outcome
confidence
```

---

## User Context

```
UserMemory

id
preference
behavior_pattern
confidence
created_at
updated_at
```

---

## Pattern Record

```
PatternMemory

id
pattern_type
observation
frequency
confidence
status
```

---

# 6. Memory Lifecycle

```
Observation
     |
     v
Event Created
     |
     v
Evidence Attached
     |
     v
Reasoning Generated
     |
     v
Decision Recorded
     |
     v
Outcome Observed
     |
     v
Memory Updated
```

---

# 7. Memory Rules

## Rule 1: Append Before Update

Historical intelligence must never disappear.

Incorrect:

```
Risk changed from Medium to Low
```

Correct:

```
Risk assessment event:
August 1:
Medium

September 1:
Low

Reason:
Allocation changed
```

---

## Rule 2: Confidence Is Mandatory

Every memory object should include confidence.

Examples:

```
Confidence:
95% calculated metric

75% inferred behavior pattern

60% predicted preference
```

---

## Rule 3: Memory Must Be Explainable

Sentinel must always answer:

"Why do you believe this?"

Every memory item should link to:

* evidence
* source
* timestamp
* calculation

---

# 8. Relationship With Trust Ledger

The Trust Ledger records:

```
What Sentinel did
```

Memory records:

```
What Sentinel learned
```

Together:

```
Event History
      +
Decision History
      +
Outcome History
      =
Institutional Intelligence
```

---

# 9. Product Isolation Rules

Future Aara products may consume Sentinel memory capabilities.

Examples:

```
Aara Wealth Intelligence
        |
        uses
        |
Sentinel Memory
```

Future:

```
Aara CFO
        |
        uses
        |
Sentinel Memory
```

However:

Products maintain separate user data boundaries.

No cross-product memory sharing without explicit authorization.

---

# 10. MVP Implementation Strategy

Initial implementation:

Phase 1:

Use existing:

```
sentinel/events
sentinel/projections
sentinel/evidence
sentinel/repositories
```

Extend with:

```
sentinel/memory
```

---

Phase 2:

Add:

```
memory_service.py

Responsibilities:
- store intelligence memories
- retrieve relevant context
- summarize historical patterns
```

---

Phase 3:

Expose APIs:

```
remember(event)

retrieve_context(query)

explain_history(entity)

summarize_evolution(user)
```

---

# 11. Success Criteria

Sentinel Memory is successful when:

1. The system remembers previous intelligence.
2. Decisions become explainable over time.
3. Products do not need to rebuild history systems.
4. Users experience continuity.
5. Sentinel becomes a reusable intelligence layer.

---

# Final Principle

Sentinel is not valuable because it can answer today's question.

Sentinel is valuable because it remembers yesterday's decisions, understands today's context, and improves tomorrow's guidance.
