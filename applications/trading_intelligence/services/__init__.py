"""Trading Intelligence services.

Internal services (query/read services and, eventually, domain services:
signal/screening, decision-orchestration, execution), conceptually parallel to
sentinel_engine's DecisionService/EvidenceService/GovernanceService pattern.

Implemented: DecisionQueryService + the DecisionSource abstraction it depends
on (decision_query_service.py). No concrete DecisionSource is implemented —
wiring a real source is deferred until ADR-004's backend/read-model strategy
is approved.

See ../README.md for scope and dependency rules.
"""
