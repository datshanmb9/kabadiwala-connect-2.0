"""
Structured, consistent error responses across the whole API. No endpoint
should raise a raw HTTPException with a bare string — everything goes
through AppError so every client gets {success, error_code, message}.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, *, status_code: int, error_code: str, message: str):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(message)


# Common, reusable error instances for Phase 1's auth/RBAC surface.
def invalid_credentials() -> AppError:
    # Deliberately identical whether the username doesn't exist or the
    # password is wrong — no username enumeration.
    return AppError(status_code=401, error_code="INVALID_CREDENTIALS", message="Invalid username or password.")


def account_disabled() -> AppError:
    return AppError(status_code=403, error_code="ACCOUNT_DISABLED", message="This account is disabled.")


def invalid_token() -> AppError:
    return AppError(status_code=401, error_code="INVALID_TOKEN", message="Invalid or expired token.")


def forbidden_role() -> AppError:
    return AppError(status_code=403, error_code="FORBIDDEN_ROLE", message="You do not have permission to perform this action.")


# Generic, reusable factories for Phase 2+ modules — named factories above
# stay for the well-known Phase 1 auth/RBAC cases; new modules compose their
# own error_code/message through these rather than constructing AppError
# directly, so the {success, error_code, message} contract never drifts.
def not_found(error_code: str, message: str) -> AppError:
    return AppError(status_code=404, error_code=error_code, message=message)


def conflict(error_code: str, message: str) -> AppError:
    return AppError(status_code=409, error_code=error_code, message=message)


def forbidden(error_code: str, message: str) -> AppError:
    return AppError(status_code=403, error_code=error_code, message=message)


def bad_request(error_code: str, message: str) -> AppError:
    return AppError(status_code=400, error_code=error_code, message=message)

def service_unavailable(error_code: str, message: str) -> AppError:
    return AppError(status_code=503, error_code=error_code, message=message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error_code": exc.error_code, "message": exc.message},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error_code": "HTTP_ERROR", "message": str(exc.detail)},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Never leak stack traces / internals to the client.
        return JSONResponse(
            status_code=500,
            content={"success": False, "error_code": "INTERNAL_ERROR", "message": "An unexpected error occurred."},
        )
