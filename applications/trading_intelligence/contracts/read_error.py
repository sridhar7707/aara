"""Trading Intelligence's own read-failure type -- the boundary between
Sentinel Engine infrastructure exceptions and everything above the adapter
layer (query services, controller, Gradio).

sentinel_engine.repositories.ProjectionRepository and
sentinel_engine.queries.decision_query.DecisionQuery are ABCs with no
documented exception contract -- a future persistent backend (SQLite,
network, etc.) may raise anything. Adapters (applications/trading_intelligence/
adapters/) catch those arbitrary exceptions at the point they cross into
Trading Intelligence and re-raise this type instead, via
`raise TradingIntelligenceReadError(...) from exc`, so nothing above the
adapter layer -- including the UI -- ever needs to know what kind of
infrastructure failed or how.

Deliberately a single type, not one subclass per read concern (decision/
evidence/governance): every caller that needs to know which concern failed
already knows it structurally, from which of its own sequential calls
raised (see DecisionCenterController.load_decision_detail) -- a type
hierarchy would duplicate information the call site already has.
"""


class TradingIntelligenceReadError(RuntimeError):
    pass
