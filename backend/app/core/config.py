"""
Centralized configuration. Every value that could plausibly change between
environments (dev/demo/prod) lives here and is read from the environment —
never hardcoded in business logic. See .env.example for the full list.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # MongoDB
    database_url: str = "mongodb://localhost:27017"
    database_name: str = "kabadiwala_connect"

    # JWT
    jwt_secret: str = "dev-only-secret-override-in-real-env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Demo admin seed — DEMO ONLY. Production must override via real secrets.
    admin_default_username: str = "admin1"
    admin_default_password: str = "admin1234"

    # API
    api_base_url: str = "http://localhost:8000"

    # CORS — the mobile app's web build (and, later, the RRR/Recycler/Admin
    # SPAs) call this API cross-origin from a browser. Loopback-only by
    # default (any port) since local dev/demo is the only case today;
    # override with each real deployed frontend's origin in production —
    # never widen this to a blanket "*", since browsers block reading
    # cross-origin responses without an explicit allow-listed origin, and a
    # wildcard here would defeat that protection for every route, not just
    # the public ones.
    cors_allowed_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    # Geo verification (Phase 2+)
    max_handover_distance_meters: float = 150.0
    max_handover_window_hours: float = 48.0

    # AI classification (Phase 8): threshold and model version were
    # pre-declared in Phase 5 and unused until now.
    classification_confidence_threshold: float = 0.6
    ai_model_version: str = "ewaste-classifier-v1"
    # Reserved for a future real-provider integration — no code path reads
    # this yet (Phase 8 ships only the deterministic mock classifier; see
    # PROJECT_STATUS.md for why). Its presence/absence cannot affect
    # today's behavior, which is exactly how "the app must still work if
    # AI credentials are absent" is proven structurally rather than by a
    # dead if/else branch. Never logged, never returned in any API
    # response, never sent to any frontend.
    ai_provider_api_key: str | None = None

    # User price estimates: the current model returns one per-kg prediction.
    # This configured band communicates model uncertainty without inventing
    # market data; trend remains unavailable until a time-series source exists.
    pricing_estimate_range_percent: float = 0.10
    pricing_model_version: str = "collector_price_model.joblib"
    # Translation is intentionally configured separately from the existing
    # production AI models. The model loads lazily only when a translation is
    # requested, and its cache can live outside the repository.
    translation_model_id: str = "ai4bharat/indictrans2-en-indic-dist-200M"
    translation_model_cache_dir: str | None = None
    translation_max_text_length: int = 2000
    translation_max_batch_size: int = 64
    translation_max_new_tokens: int = 256

    # Payments (Phase 9): payment_mode was pre-declared in Phase 1, unused
    # until now. MOCK_PAYMENT_GATEWAY is the only mode this phase
    # implements — no real provider integration exists.
    payment_mode: str = "MOCK_PAYMENT_GATEWAY"

    # Rewards (Phase 9): no item ever has a recorded weight anywhere in
    # this system (no scale/weighing step exists), so points-per-item is
    # the only feasible formula, not points-per-kg. Both the points
    # awarded per collected item and the INR value of one point are
    # configurable, deliberately kept as separate knobs rather than one
    # combined "amount per item" so a future non-linear scheme (bonus
    # tiers, category-weighted points) has somewhere to plug in without
    # another config rename.
    reward_points_per_item: int = 10
    reward_value_per_point_inr: str = "0.50"  # -> Decimal("0.50") INR/point; 10 points = Rs 5.00/item

    # Lots / bidding window (Phase 5+): how long a published lot stays
    # open for bids once an RRR publishes it. Actual bid placement is
    # Phase 6 scope; Phase 5 only sets this deadline on the lot.
    lot_bid_window_days: int = 7

    # Bidding (Phase 6): how long after acceptance an RRR may still cancel
    # it (architecture Section 6.2: "only within 24h AND before payment").
    # Phase 9 completes the payment half of this guard, now that a
    # payments module and real payment records exist.
    bid_acceptance_cancel_window_hours: int = 24


settings = Settings()
