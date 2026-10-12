import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

logger = logging.getLogger("kabadiwala.startup")

# Phase 11 security fix: known, publicly-visible-in-source default
# values that must never be used outside local dev/demo. This is a
# loud, non-blocking WARNING (not a hard failure) — failing startup
# would break the exact local demo flow this whole project is built
# around, and no "unnecessary infrastructure" (secret managers, config
# validators) is being introduced to enforce it. A human reading the
# startup log is the deliberate, minimal mitigation here.
_INSECURE_DEFAULTS = {
    "JWT_SECRET": "dev-only-secret-override-in-real-env",
    "ADMIN_DEFAULT_PASSWORD": "admin1234",
}


def _warn_if_insecure_defaults_active() -> None:
    active = []
    if settings.jwt_secret == _INSECURE_DEFAULTS["JWT_SECRET"]:
        active.append("JWT_SECRET")
    if settings.admin_default_password == _INSECURE_DEFAULTS["ADMIN_DEFAULT_PASSWORD"]:
        active.append("ADMIN_DEFAULT_PASSWORD")
    if active:
        logger.warning(
            "INSECURE DEMO DEFAULT(S) STILL ACTIVE: %s — override via environment "
            "variables before any real deployment. This warning is expected and "
            "harmless for local development/demo use.",
            ", ".join(active),
        )
from app.core.errors import register_exception_handlers
from app.db.mongo import create_indexes
from app.modules.admin.router import router as admin_router
from app.modules.audit_logs.router import router as audit_logs_router
from app.modules.auth.router import router as auth_router
from app.modules.bids.router import router as bids_router
from app.modules.bids.router import admin_router as bids_admin_router
from app.modules.classification.router import router as classification_router
from app.modules.collectors.router import router as collectors_router
from app.modules.complaints.router import router as complaints_router
from app.modules.ewaste.router import router as ewaste_router
from app.modules.ewaste.router import admin_router as ewaste_admin_router
from app.modules.home_users.router import router as home_users_router
from app.modules.logistics.router import router as logistics_router
from app.modules.lots.router import router as lots_router
from app.modules.lots.router import admin_router as lots_admin_router
from app.modules.payments.router import router as payments_router
from app.modules.payments.router import admin_router as payments_admin_router
from app.modules.pricing.router import router as pricing_router
from app.modules.recyclers.router import router as recyclers_router
from app.modules.rewards.router import router as rewards_router
from app.modules.rrr_centres.router import router as rrr_centres_router
from app.modules.translation.router import router as translation_router
from app.modules.wards.router import router as wards_router
from app.modules.notifications.router import router as notifications_router


def create_app() -> FastAPI:
    app = FastAPI(title="Kabadiwala Connect 2.0 API", version="0.11.0-phase11")

    # Auth is Bearer-token-in-header, not cookie-based, so this never needs
    # allow_credentials=True — the browser isn't asked to send any
    # automatic credential on our behalf, only what the JS code sets
    # explicitly on the request, which CORS's "credentials" mode doesn't
    # gate. allow_origin_regex is loopback-only by default (see Settings);
    # deliberately not allow_origins=["*"].
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=settings.cors_allowed_origin_regex,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )

    register_exception_handlers(app)

    app.include_router(auth_router)
    app.include_router(audit_logs_router)
    app.include_router(wards_router)
    app.include_router(home_users_router)
    app.include_router(collectors_router)
    app.include_router(rrr_centres_router)
    app.include_router(recyclers_router)
    app.include_router(ewaste_router)
    app.include_router(ewaste_admin_router)
    app.include_router(lots_router)
    app.include_router(lots_admin_router)
    app.include_router(bids_router)
    app.include_router(bids_admin_router)
    app.include_router(complaints_router)
    app.include_router(admin_router)
    app.include_router(classification_router)
    app.include_router(logistics_router)
    app.include_router(payments_router)
    app.include_router(payments_admin_router)
    app.include_router(pricing_router)
    app.include_router(rewards_router)
    app.include_router(translation_router)
    app.include_router(notifications_router)

    @app.get("/api/v1/health")
    async def health():
        return {"success": True, "status": "ok"}

    @app.on_event("startup")
    async def on_startup():
        # Index creation only — never seeds/resets/deletes data automatically.
        await create_indexes()
        _warn_if_insecure_defaults_active()

    return app


app = create_app()
