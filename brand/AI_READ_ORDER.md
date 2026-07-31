# AI Agent Reading Order

To ensure full compliance with Sentinel's Design Governance Layer, AI agents MUST consume repository files in this exact sequence before modifying or creating frontend code:

1. **`brand/BRAND_MANIFEST.yaml`** — Core identity, metric vocabulary, and taglines.
2. **`brand/AI_READ_ORDER.md` & `brand/AI_IMPLEMENTATION_RULES.md`** — Mandatory AI execution instructions.
3. **`brand/STATE_MAPPING.yaml`** — Domain state-to-token mappings and semantic definitions.
4. **`brand/METRIC_CONTRACT.yaml`** — Approved metric names, data types, and API linkages.
5. **`brand/design_system/tokens.css`** — CSS variable registry (colors, typography, breakpoints).
6. **`brand/design_system/COMPONENT_REGISTRY.yaml`** — Machine-readable inventory of existing components.
7. **`brand/design_system/<COMPONENT_NAME>.md`** — Specific component specifications and accessibility contracts.
8. **`brand/guidelines/FORBIDDEN_UI_PATTERNS.md`** — Prohibited UI patterns and terminology.

**Do not skip steps or infer rules from lower-order files.**
