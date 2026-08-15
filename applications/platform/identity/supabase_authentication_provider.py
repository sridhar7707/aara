"""Concrete AuthenticationProvider backed by Supabase Auth.

Authorized by ADR-028 Section 2.1 exactly: implements the existing,
unmodified AuthenticationProvider interface only -- constructor-injected
with an already-established supabase_auth client, translating its response
into AARA's own User(user_id, display_name). No login flow, no token
refresh, no MFA, no session-acquisition mechanism -- those remain deferred
per ADR-027 Section 7 and ADR-028 Section 3. This module never constructs a
client itself and never uses real credentials; per ADR-028 Section 3, no
real Supabase network call is created or required by this implementation.

Client API confirmed directly against the installed supabase-auth==2.31.0
package source (supabase_auth/_sync/gotrue_client.py and
supabase_auth/types.py), not guessed:
    SyncGoTrueClient.get_user(jwt: Optional[str] = None) -> Optional[UserResponse]
    UserResponse.user -> supabase_auth.types.User, with typed `id: str` and
    `email: Optional[str]` fields.

The `SyncGoTrueClient` import below is TYPE_CHECKING-only, not a runtime
import: this class only needs the duck-typed `get_user()` method any
supabase_auth client (sync or async-wrapped, real or fake) exposes, so it
never needs supabase_auth to actually import at runtime -- keeping this
adapter's runtime coupling to the SDK minimal, matching the constructor-
injection pattern already used throughout this codebase (DecisionSource,
SentinelAuditSource, etc.), which never import their concrete collaborators'
packages at the abstraction's own call sites either.

display_name maps from the Supabase user's `email` field -- the only
always-typed, human-readable field on supabase_auth.types.User; that type
has no separate "display_name"/"full_name" field. Falls back to the
Supabase user's `id` when email is absent (Optional on that type), rather
than inventing a placeholder string.
"""
from typing import TYPE_CHECKING, Optional

from applications.platform.identity.authentication_provider import AuthenticationProvider
from applications.platform.identity.user import User

if TYPE_CHECKING:
    from supabase_auth import SyncGoTrueClient


class SupabaseAuthenticationProvider(AuthenticationProvider):
    def __init__(self, client: "SyncGoTrueClient"):
        self._client = client

    def get_current_user(self) -> Optional[User]:
        response = self._client.get_user()
        if response is None:
            return None
        supabase_user = response.user
        return User(
            user_id=supabase_user.id,
            display_name=supabase_user.email or supabase_user.id,
        )
