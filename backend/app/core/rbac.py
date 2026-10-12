"""
Role-based access control — FastAPI plumbing layer.

The actual "is this role allowed here" decision lives in the dependency-free
app/core/rbac_core.py so it can be unit-tested with plain Python regardless
of whether FastAPI/Mongo are available. This file only wraps that pure
function with the real request/token/DB machinery.

Why HTTPBearer instead of a raw Header() param (fix for the missing Swagger
"Authorize" button): FastAPI only adds a scheme to the OpenAPI
`components.securitySchemes` section — and only shows the Authorize button
and marks endpoints as requiring auth — when a dependency's callable is an
instance of `fastapi.security.SecurityBase` (HTTPBearer, OAuth2PasswordBearer,
etc.). A plain `Header(default="")` parameter is just a regular string
parameter to FastAPI's schema generator: it has no way to know that string
represents a bearer token, so no security scheme was ever registered and
Swagger had nothing to attach an Authorize button to. Using `HTTPBearer` as
the dependency fixes this at the framework level without changing the wire
protocol at all — clients still send exactly `Authorization: Bearer <token>`,
byte for byte the same as before.
"""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import account_disabled, invalid_token
from app.core.rbac_core import role_is_allowed
from app.core.security import TokenError, decode_token
from app.db.repositories import users_repo

# auto_error=False: we want our own structured {success, error_code, message}
# response (via invalid_token()) for a missing/malformed header, not
# FastAPI's default plain-text 403 "Not authenticated". Because this is a
# SecurityBase subclass instance used as a dependency, FastAPI still
# registers it as a bearer scheme in OpenAPI regardless of auto_error.
bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    bearerFormat="JWT",
    description="Paste the access_token returned by POST /api/v1/auth/login (without the word 'Bearer').",
    auto_error=False,
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Extracts and verifies the bearer token, then re-fetches the user's
    CURRENT record from the database — the role/status used for the
    authorization decision always comes from the database, never solely
    from the token's claims, so a revoked/downgraded account can't keep
    acting on a stale token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise invalid_token()

    token = credentials.credentials
    try:
        payload = decode_token(token, expected_type="access")
    except TokenError as exc:
        raise invalid_token() from exc

    user_id = payload.get("sub")
    user = await users_repo.find_by_id(user_id)
    if user is None:
        raise invalid_token()
    if user.get("status") != "ACTIVE":
        raise account_disabled()

    return user


def require_role(*allowed_roles: str):
    """FastAPI dependency factory: `Depends(require_role("GOVERNMENT_ADMIN"))`.
    Delegates the actual yes/no decision to `role_is_allowed` so that logic
    is tested once and reused everywhere. Because this wraps `get_current_user`
    (which depends on the `HTTPBearer` instance above) via `Depends`, FastAPI
    walks the nested dependency tree and still attaches the same security
    requirement to any endpoint that uses `require_role(...)`, not just ones
    that use `get_current_user` directly."""

    async def _dependency(current_user: dict = Depends(get_current_user)) -> dict:
        from app.core.errors import forbidden_role  # local import avoids a cycle at module load time

        if not role_is_allowed(current_user["role"], allowed_roles):
            raise forbidden_role()
        return current_user

    return _dependency

