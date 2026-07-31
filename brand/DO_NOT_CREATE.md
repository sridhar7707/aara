# Forbidden Component Creation Rules

Before creating any new component or module, AI coding agents and human developers MUST query:
1. `brand/design_system/COMPONENT_REGISTRY.yaml`
2. `brand/design_system/COMPONENT_LIBRARY.md`

## Anti-Duplication Rule
The core governance and decision components MUST NEVER be duplicated under alternative names.

**Strictly Prohibited Filenames:**
* ❌ `DecisionCardNew.jsx` / `DecisionCardV2.jsx` / `DecisionCardFinal.jsx`
* ❌ `PortfolioCardV2.jsx` / `PortfolioHealthNew.jsx`
* ❌ `RiskBadgeEnhanced.jsx` / `RiskGovernorNew.jsx`
* ❌ `NewScoreWidget.jsx` / `ConvictionScoreBadge.jsx`

## Correct Action
If new props, layout variations, or additional metrics are required:
**Extend the existing registered component specified in `COMPONENT_REGISTRY.yaml` and update its corresponding markdown specification.**
