# Brand Validation CI Pipeline Integration

Brand governance validation is automatically executed via `tools/validate_brand_system.py` during:
1. **Pull Request Validation:** Fails PR merge if hardcoded colors, unapproved terms, or missing tokens exist.
2. **Frontend Build Stage:** Fails compilation before bundle creation if component contracts are broken.
3. **Production Deployment:** Mandatory check in release workflows.

## Failure Conditions & Pipeline Halts
The CI pipeline will immediately terminate with an error code if:
* Any forbidden vocabulary (e.g., `"Decision Conviction"`, `"AI Confidence"`) is detected in `frontend/`.
* Any raw hex color string (e.g., `#0B1F3A`) is hardcoded instead of using CSS token variables.
* Any required token listed in `tools/validate_brand_system.py` is removed from `tokens.css`.
* Any component listed in `COMPONENT_REGISTRY.yaml` lacks a matching markdown contract.
* Any YAML contract fails syntax parsing or version matching against `VERSION_LOCK.yaml`.
