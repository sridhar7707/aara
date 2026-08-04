# Sentinel Engine Boundary And API Contracts

**Version:** 1.0
**Status:** Architecture Foundation Document
**Platform:** Aara Systems
**Engine:** Sentinel Intelligence Engine

---

# 1. Purpose

This document defines the architectural boundary between the Sentinel Intelligence Engine and Aara product applications.

The goal is to create a reusable intelligence platform where multiple Aara products can consume shared reasoning capabilities without tightly coupling product-specific data, workflows, or user experiences.

Initial consumer:

```
Aara Wealth Intelligence
```

Future consumers:

```
Aara CFO Intelligence
Aara Tax Intelligence
Aara Estate Intelligence
Aara Retirement Intelligence
```

---

# 2. Core Architecture Principle

## Sentinel is the Intelligence Layer.

## Aara products are the Experience Layers.

The separation:

```
                 AARA PLATFORM


        +-----------------------------+
        |                             |
        |   Aara Wealth Intelligence  |
        |   Aara CFO                  |
        |   Aara Tax                  |
        |   Aara Estate               |
        |                             |
        +-------------+---------------+
                      |
                      |
                      v

        +-----------------------------+
        |                             |
        | Sentinel Intelligence Engine|
        |                             |
        | Reasoning                   |
        | Memory                      |
        | Evidence                    |
        | Governance                  |
        | Evaluation                  |
        | Risk Intelligence           |
        | Explanation                 |
        |                             |
        +-----------------------------+

```

---

# 3. Ownership Boundary

## Aara Product Owns

Product applications own user-specific financial information.

Examples:

* user identity
* linked accounts
* brokerage connections
* Plaid tokens
* holdings
* transactions
* portfolio configuration
* financial goals
* user preferences
* subscription state

Example:

```
Aara Wealth Intelligence Database

User
 |
Accounts
 |
Holdings
 |
Portfolio State

```

---

# 4. Sentinel Engine Owns

Sentinel owns intelligence capabilities.

Examples:

* reasoning workflows
* evidence evaluation
* confidence scoring
* decision lifecycle
* memory processing
* governance rules
* analytical frameworks
* explanation generation
* intelligence evaluation

Sentinel does NOT own:

* user credentials
* brokerage credentials
* raw account data
* personally identifiable financial information

---

# 5. Data Privacy Boundary

Critical rule:

> Sentinel processes financial intelligence states. It does not become the owner of consumer financial data.

Example:

Incorrect:

```
Plaid Data
     |
     v
Sentinel Database
```

Correct:

```
Plaid Data

     |
     v

Aara Wealth Intelligence

     |
     v

Abstract Financial State

     |
     v

Sentinel Intelligence Engine

```

---

# 6. Sentinel Input Contract

Products provide structured intelligence requests.

Example:

```json
{
  "request_type": "portfolio_analysis",
  "product": "wealth_intelligence",
  "context": {
    "asset_classes": [
      {
        "name": "equity",
        "allocation": 65
      },
      {
        "name": "fixed_income",
        "allocation": 25
      }
    ],
    "risk_profile": "moderate",
    "investment_horizon": "long_term"
  }
}
```

Sentinel should receive:

* normalized state
* analytical context
* required evidence

Sentinel should not receive:

* passwords
* account credentials
* unnecessary personal data

---

# 7. Sentinel Core API Contracts

## 7.1 Analyze

Purpose:

Evaluate financial or business state.

Contract:

```
analyze(state)
```

Input:

```
Structured domain state
```

Output:

```
AnalysisResult
```

Example:

```json
{
  "observations": [
    {
      "type": "concentration_risk",
      "severity": "medium",
      "confidence": 0.87
    }
  ]
}
```

---

# 7.2 Explain

Purpose:

Convert intelligence output into understandable reasoning.

Contract:

```
explain(context)
```

Input:

```
Observation + Evidence + User Context
```

Output:

```
Human-readable explanation
```

Example:

```
Your portfolio contains overlapping exposure across multiple funds.
The concentration exists because several funds hold similar underlying companies.
```

---

# 7.3 Remember

Purpose:

Store meaningful intelligence events.

Contract:

```
remember(event)
```

Input:

```
Intelligence Event
```

Output:

```
Memory Record
```

Examples:

* portfolio milestones
* decisions
* user preferences
* behavioral patterns

---

# 7.4 Evaluate

Purpose:

Measure intelligence quality.

Contract:

```
evaluate(result)
```

Measures:

* confidence calibration
* accuracy
* historical performance
* reliability

---

# 7.5 Recommend

Purpose:

Generate structured considerations.

Contract:

```
recommend(insights)
```

Output:

```
RecommendationResult
```

Important:

Recommendations are not automatic actions.

Sentinel provides intelligence.

The product maintains user control.

---

# 8. Sentinel Internal Modules

Future structure:

```
sentinel/

├── core/
│   ├── intelligence_context.py
│   └── engine.py
│
├── reasoning/
│   ├── analyzer.py
│   ├── evaluator.py
│   └── explainer.py
│
├── memory/
│   ├── memory_store.py
│   └── timeline.py
│
├── evidence/
│   ├── evidence_manager.py
│   └── provenance.py
│
├── governance/
│   ├── policies.py
│   └── controls.py
│
├── risk/
│   └── risk_engine.py
│
└── projections/
    └── state_projection.py

```

---

# 9. Existing Code Mapping

Current project assets:

## Becomes Sentinel Engine

```
sentinel/
```

Contains:

* event architecture
* governance
* evidence
* projections
* repositories
* services

---

## Becomes Market Intelligence Module

```
bot/
```

Future role:

```
sentinel/modules/market_intelligence/
```

Contains:

* models
* signals
* market analysis
* research experiments

It is preserved.

It is not the consumer product.

---

## Becomes Evaluation Layer

```
analytics/
```

Contains:

* calibration
* scorecards
* experiments
* model evaluation

---

# 10. Product Communication Pattern

Recommended flow:

```
Aara Wealth Intelligence

1. Collect user financial data

        |

2. Normalize wealth state

        |

3. Request Sentinel analysis

        |

4. Receive intelligence output

        |

5. Present calm user experience

```

---

# 11. Non-Goals

Sentinel Engine will not:

* build user interfaces
* manage subscriptions
* store consumer credentials
* replace product databases
* directly communicate with end users
* execute financial transactions

---

# 12. Future Product Expansion

New Aara products should follow the same pattern:

```
Aara CFO

Financial Data
      |
      v
Sentinel Analysis
      |
      v
Business Intelligence


Aara Tax Intelligence

Tax Data
      |
      v
Sentinel Analysis
      |
      v
Tax Optimization Intelligence

```

---

# 13. Migration Rule

During migration:

DO:

* extract reusable intelligence
* preserve existing capabilities
* introduce clean interfaces
* maintain backward compatibility

DO NOT:

* merge product logic into Sentinel
* move user data into engine storage
* create product-specific dependencies inside Sentinel

---

# 14. Success Criteria

This architecture is successful when:

1. Aara Wealth Intelligence can operate independently.
2. Sentinel can power multiple Aara products.
3. Consumer data remains isolated.
4. Intelligence capabilities are reusable.
5. Product teams can evolve without changing the engine.

---

# Final Principle

> Aara products provide experiences. Sentinel provides intelligence.

The strength of the Aara platform comes from keeping those responsibilities permanently separated.

---

# End of Document
