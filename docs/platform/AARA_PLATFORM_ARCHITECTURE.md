# Aara Platform Architecture

**Version:** 1.0
**Status:** Platform Foundation Architecture
**Owner:** Aara Systems
**Classification:** Strategic Architecture Document

---

# 1. Purpose

This document defines the long-term architecture of the Aara ecosystem.

The goal is to establish a scalable platform where multiple financial intelligence products can evolve independently while sharing a common intelligence foundation.

Aara is not a single application.

Aara is a product ecosystem.

---

# 2. Aara Identity Model

The architecture consists of three layers:

```
AARA SYSTEMS
(Company / Brand)

        |

SENTINEL INTELLIGENCE ENGINE
(Shared Intelligence Foundation)

        |

AARA PRODUCTS
(Customer Applications)
```

---

# 3. Brand Architecture

## Parent Brand

```
Aara
```

Aara represents:

* trust
* intelligence
* personal wealth understanding
* long-term financial relationships

Aara is the umbrella brand.

---

# 4. Sentinel Intelligence Engine

## Purpose

Sentinel is the reusable intelligence infrastructure powering all Aara products.

Sentinel is responsible for:

* reasoning
* memory
* evidence management
* governance
* confidence evaluation
* intelligence generation

Sentinel is NOT:

* a consumer application
* a trading bot
* a financial advisor
* a standalone user experience

---

## Sentinel Mission

> Transform complex financial information into explainable, evidence-based intelligence.

---

# 5. Product Architecture

Each Aara product is an independent application.

Each product has:

* independent repository
* independent deployment
* independent database
* independent user experience
* independent roadmap

Products consume Sentinel capabilities through defined interfaces.

---

# 6. Initial Product Ecosystem

Future structure:

```
AARA ECOSYSTEM


                    Sentinel Intelligence Engine

                              |
        ------------------------------------------------

        |                    |                         |

        v                    v                         v


Aara Wealth          Aara CFO Intelligence       Aara Tax Intelligence

Intelligence


        |

        v


Aara Estate Intelligence
```

**Note (per ADR-001):** Aara Trading Intelligence (Product #1) also
branches directly from Sentinel Intelligence Engine, alongside the
products shown above.

---

# 7. Repository Strategy

Aara follows a multi-repository architecture.

## Repository 1

```
sentinel-intelligence-engine
```

Purpose:

Shared intelligence infrastructure.

Contains:

```
core/
memory/
reasoning/
evidence/
governance/
projections/
contracts/
```

---

## Repository 2

```
aara-wealth-intelligence
```

Purpose:

Consumer wealth intelligence application.

Contains:

```
frontend/
backend/

portfolio/
wealth_xray/
accounts/
reports/
subscriptions/
user_experience/
```

---

## Future Repository Examples

```
aara-cfo-intelligence

aara-tax-intelligence

aara-estate-intelligence
```

---

# 8. Product Independence Principle

Each product must be able to evolve independently.

A change in:

```
Aara Wealth Intelligence
```

must not require changes to:

```
Aara CFO Intelligence
```

unless a shared Sentinel capability changes.

---

# 9. Sentinel Communication Model

Products communicate with Sentinel through stable contracts.

Example:

```
Aara Wealth Intelligence

        |
        |
        v

Sentinel Intelligence Engine

        |
        |
        v

Intelligence Response
```

---

Example request:

```
Analyze portfolio structure
```

Sentinel returns:

```
{
 observation,
 evidence,
 confidence,
 explanation,
 recommended_actions
}
```

---

# 10. Data Ownership Rules

## Product-Owned Data

Each Aara product owns its customer data.

Examples:

Aara Wealth Intelligence owns:

* brokerage connections
* financial accounts
* holdings
* transactions
* personal preferences

---

## Sentinel-Owned Data

Sentinel owns intelligence artifacts.

Examples:

* reasoning events
* evidence records
* confidence measurements
* intelligence history
* model evaluations

---

# 11. Privacy Boundary

Customer financial data must never become shared platform data.

Incorrect:

```
Sentinel Database

All customer accounts
All holdings
All transactions
```

---

Correct:

```
Aara Wealth Database

Customer Financial Data

        |

        |

Approved Intelligence State

        |

        v

Sentinel Engine
```

---

# 12. Current Project Migration Mapping

The current Sentinel Intelligence repository contains multiple responsibilities.

They must be separated.

---

## Move to Sentinel Intelligence Engine

Current:

```
sentinel/

ledger/
governance/
events/
evidence/
projections/
decision lifecycle
trust architecture
```

Future:

```
sentinel-intelligence-engine
```

---

## Move to Aara Wealth Intelligence

Current:

```
dashboard/

portfolio views
user screens
reports
wealth visualization
```

Future:

```
aara-wealth-intelligence
```

---

## Preserve as Sentinel Modules

Current:

```
bot/

models/
strategy/
risk/
execution/
market intelligence
```

Future:

```
Sentinel Market Intelligence Module
```

Status:

Internal intelligence capability.

Not exposed directly to consumers.

**Note (per ADR-001):** `bot/`'s eventual role is Aara Trading
Intelligence, Product #1 on the platform's product model. This section
describes its current internal-module framing; it does not remove
Trading Intelligence from the platform's product set.

---

# 13. Development Principles

## Principle 1

Do not build one giant Aara application.

---

## Principle 2

Do not duplicate intelligence logic across products.

---

## Principle 3

Move reusable intelligence into Sentinel.

---

## Principle 4

Keep customer experience inside individual products.

---

## Principle 5

Prefer APIs and contracts over shared code dependencies.

---

# 14. Long-Term Vision

Aara becomes a family of intelligent financial products.

Sentinel becomes the intelligence layer connecting them.

The future architecture:

```
                AARA

                 |

     Sentinel Intelligence Engine

                 |

 ------------------------------------------------

 |              |              |                |

Wealth        CFO            Tax             Estate

Intelligence  Intelligence   Intelligence   Intelligence
```

**Note (per ADR-001):** These branches also include Aara Trading
Intelligence (Product #1), consuming the same Sentinel Intelligence
Engine as Wealth/CFO/Tax/Estate Intelligence.

---

# 15. Architectural Success Criteria

The platform succeeds when:

1. New Aara products can launch without rebuilding intelligence.

2. Sentinel improves every product simultaneously.

3. Customer data remains isolated and protected.

4. Products maintain independent development velocity.

5. Intelligence becomes more valuable with time and memory.

---

# End of Document
