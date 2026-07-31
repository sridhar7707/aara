# Release Evidence Layer

Purpose: immutable validation evidence, freeze reports, and release
verification artifacts for Sentinel governance milestones.

Rules:
- Contents are generated during release preparation (see
  `tools/generate_freeze_report.py`), not hand-written.
- Every report references the validator suite version and the Git commit
  SHA it was generated against.
- Contains no proprietary strategy information: no content from
  `docs/architecture/` may ever be copied or referenced here.
- Contains no customer, broker, account, or portfolio data.
