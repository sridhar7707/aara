# Platform Product Registry

**Status:** Abstract contracts only. No database, no real product wiring.

## What this is

`Product` (`product_registry.py`) — registry-level product metadata only:
`product_id`, `name`. Not a product's internals — per
`docs/platform/AARA_PLATFORM_SHELL_ARCHITECTURE.md` Section 4, the platform
layer knows "which products exist, their names... a registry-level
knowledge, not their internals."

`ProductRegistry` (`product_registry.py`) — `register(product)` /
`list_products() -> List[Product]`. No concrete implementation exists; no
product (Trading Intelligence, Wealth Intelligence) is registered anywhere
in this codebase yet.

## Dependency rules

Must not know Trading Intelligence services, Wealth Intelligence services,
Sentinel Engine, `bot`, or `dashboard` — the registry holds metadata *about*
products, it does not import them. Checked in
`../tests/test_platform_structure.py`.
