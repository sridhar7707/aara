# Sentinel Intelligence

Governance-first Decision Intelligence Platform. Phase 2A architectural
scaffolding only -- see `../docs/architecture/IMPLEMENTATION_HANDOFF.md`
for the frozen requirements this structure implements.

## Status

Scaffolding only. No business logic, no persistence, no execution.
Every service, repository, and API function raises `NotImplementedError`.

## Layering

```
frontend (Gradio)  ->  api  ->  services  ->  domain
                                    v
                              repositories  ->  events
```

Frontend has zero domain knowledge. All business logic lives in
`backend/services`. See `docs/architecture/GRADIO_IMPLEMENTATION_GUIDE.md`
for the callback safety rules that govern `frontend/`.

## Phase 2A scope

Single-user, mock-data-only decision governance sandbox: RESEARCH,
PAPER, and SUPERVISED operational modes. No auth, no broker
integration, no real execution -- see `IMPLEMENTATION_HANDOFF.md`
"Phase 2A Implementation Boundaries" for the full exclusion list.

## Running

```bash
pip install -r requirements.txt
python -m sentinel.frontend.app
```

(Not yet functional -- scaffolding only.)
