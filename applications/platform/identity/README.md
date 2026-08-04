# Platform Identity

**Status:** Abstract contracts only. No authentication implementation, no
OAuth integration, no login screen, no database.

## What this is

`User` (`user.py`) — the current-user abstraction: `user_id`, `display_name`.
Framework-independent, no session/token concept implied.

`AuthenticationProvider` (`authentication_provider.py`) — the interface a
future concrete provider (Google OAuth / a managed auth provider / an
internal identity service — see
`docs/platform/AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md` Section 4, no
selection made) will implement. `get_current_user() -> Optional[User]` is the
only method — deliberately minimal, since specifying more (login, logout,
token refresh) would mean designing an authentication flow ahead of that
selection.

## Dependency rules

Same as the rest of `applications/platform/`: may know users/roles/entitlements/
products; must not know Trading Intelligence services, Wealth Intelligence
services, Sentinel Engine, `bot`, or `dashboard`. Checked in
`../tests/test_platform_structure.py`.
