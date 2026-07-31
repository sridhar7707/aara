"""Knowledge API adapter (FastAPI). Signatures only, no implementation.

Contract: API_REQUIREMENTS_v1.0.md "4. Knowledge & Learning" (authoritative
REST contract). Added during scaffold expansion -- not in
IMPLEMENTATION_HANDOFF.md's Phase 2A workflow-priority endpoint list, since
the knowledge/learning loop is explicitly out of Phase 2A scope
(PHASE_2A_ARCHITECTURE_FREEZE_ADDENDUM.md: "Learning Loop / Continuous
Improvement" is not built in Phase 2A). Route signatures exist to satisfy
the frozen contract; no service wiring or logic until a later phase.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("")
def list_knowledge_entries() -> dict:
    """Knowledge entries list. Backing view: knowledge_graph_nodes."""
    raise NotImplementedError


@router.get("/graph")
def get_knowledge_graph() -> dict:
    """Knowledge graph (nodes + edges). Backing views: knowledge_graph_nodes,
    knowledge_graph_edges."""
    raise NotImplementedError
