"""AARA Trading Intelligence — Product #1 of the AARA platform.

This package is AARA Product #1, per docs/platform/AARA_ARCHITECTURE_AUTHORITY.md's
Product Model. It consumes Sentinel Intelligence Engine (sentinel_engine/)
capabilities through adapters; it does not own the engine.

It does not replace bot/ yet. bot/ remains the live production trading runtime,
protected under docs/decisions/ADR-002-bot-runtime-protection.md. This package
is currently an empty application boundary skeleton only — see README.md for
scope, dependency rules, and status.
"""
