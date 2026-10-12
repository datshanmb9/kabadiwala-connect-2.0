"""
Requires the full stack (fastapi, etc.) — same as the other integration
tests. These specifically guard the fix for the missing Swagger "Authorize"
button: they assert the bearer scheme is registered in
components.securitySchemes and that the protected endpoints actually
declare it as a requirement in the generated OpenAPI schema, not just that
the endpoints happen to work at runtime.

Run with: pytest tests/integration/test_openapi_schema.py
"""
import pytest

from app.main import create_app


@pytest.fixture
def openapi_schema():
    app = create_app()
    return app.openapi()


def test_bearer_security_scheme_is_registered(openapi_schema):
    schemes = openapi_schema.get("components", {}).get("securitySchemes", {})
    assert "BearerAuth" in schemes, (
        "No 'BearerAuth' scheme found in components.securitySchemes — this is exactly what "
        "makes Swagger UI hide the Authorize button."
    )
    bearer = schemes["BearerAuth"]
    assert bearer["type"] == "http"
    assert bearer["scheme"] == "bearer"
    assert bearer.get("bearerFormat") == "JWT"


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/v1/auth/me", "get"),
        ("/api/v1/auth/logout", "post"),
        ("/api/v1/audit-logs", "get"),
    ],
)
def test_protected_endpoint_declares_bearer_security_requirement(openapi_schema, path, method):
    operation = openapi_schema["paths"][path][method]
    security = operation.get("security", [])
    assert any("BearerAuth" in requirement for requirement in security), (
        f"{method.upper()} {path} does not declare the BearerAuth security requirement in "
        "its OpenAPI operation — Swagger would not show a lock icon or send the token for it."
    )


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/v1/auth/login", "post"),
        ("/api/v1/auth/refresh", "post"),
        ("/api/v1/health", "get"),
    ],
)
def test_public_endpoint_does_not_require_bearer_security(openapi_schema, path, method):
    """Login/refresh/health must stay open — they're how you GET a token in
    the first place, or need no auth at all. This guards against
    accidentally making require_role/get_current_user global."""
    operation = openapi_schema["paths"][path][method]
    security = operation.get("security", [])
    assert not any("BearerAuth" in requirement for requirement in security)
