"""
Pure, dependency-free RBAC decision logic. Deliberately has NO imports of
FastAPI, Mongo, or anything else external — this is the one function every
other RBAC/ownership check in the codebase is built on, and it needs to be
testable with nothing but the Python standard library.
"""


def role_is_allowed(user_role: str, allowed_roles: tuple[str, ...]) -> bool:
    """No allowed_roles means any authenticated role passes; otherwise the
    user's role must be in the allow-list."""
    if not allowed_roles:
        return True
    return user_role in allowed_roles


def is_owner(resource_owner_id: str, current_user_id: str) -> bool:
    """The ownership half of every 'own X only' rule in the permission
    matrix (Section 7 of the architecture doc). A role check alone is never
    sufficient — every service-layer method that touches a specific
    resource must also pass it through this function (or an equivalent
    field-specific comparison) before allowing a read/write."""
    return resource_owner_id == current_user_id
