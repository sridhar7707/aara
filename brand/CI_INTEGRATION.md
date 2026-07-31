# Brand Validation CI Pipeline Integration

**Status: Phase A (informational), effective 2026-07-31.** `tools/validate_brand_system.py` runs on every push/PR to `main` as a step in `.github/workflows/ci.yml` ("Sentinel brand governance validation"), but the step is `continue-on-error: true` -- findings are visible in the CI log and step annotation, but **do not fail the build or block merge**.

This is deliberate, not a placeholder for something better already built elsewhere. Design Governance v1.1 was sequenced as: (1) resolve open architectural questions in `COMPONENT_REGISTRY.yaml`, (2) reconcile the registry against the catalog and implementation, (3) only then gate on the result -- and even within stage 3, informational-first so the team can see what a mandatory gate would actually flag before it starts blocking anyone. See `BRAND_CHANGELOG.md` v1.0.1-v1.0.3 for the reconciliation work that preceded this.

## Promotion to Phase B (enforcing)
Not yet scheduled. When it happens, it means changing the CI step's `continue-on-error: true` to `false` (or removing the line) in `.github/workflows/ci.yml` -- nothing else. At that point:
* A hardcoded hex color, forbidden term (e.g. `"AI Confidence"`), or missing required token in `sentinel/frontend/` fails the build.
* A `COMPONENT_REGISTRY.yaml` entry with a broken `file:`/`specification:` reference, an undocumented `lifecycle: unresolved`, or a duplicate YAML key fails the build.
* `REGISTRY_COVERAGE` and any other `INFO`-severity findings remain non-blocking even after promotion -- only `BLOCK`/`ERROR` severities gate the build (see `tools/validators/types.py`'s `ValidationResult.blocking`).

Do not flip this before confirming a clean (or fully-triaged) baseline -- gating on an imperfect baseline trains people to route around the check instead of trusting it.

## What this validator does NOT do
It has no connection to a "frontend build stage" or "production deployment" pipeline -- Sentinel has no build step and no deployment target yet (Phase 2A scaffolding only, `NotImplementedError` throughout `sentinel/backend/` and `sentinel/frontend/`). It also has no relationship to `deploy_ui.yml`, which deploys the unrelated, already-shipped TradeGenius dashboard.
