from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from app.core.config import settings
from app.core.errors import bad_request


def predict_price(
    *,
    product_type: str,
    condition: str,
    quantity: int,
    total_weight_kg: float,
    location: str,
) -> float:
    normalized_product_type = product_type.strip()
    normalized_condition = condition.strip()
    normalized_location = location.strip()

    if not normalized_product_type:
        raise bad_request("PRODUCT_TYPE_REQUIRED", "Product type is required.")
    if not normalized_condition:
        raise bad_request("CONDITION_REQUIRED", "Condition is required.")
    if not normalized_location:
        raise bad_request("LOCATION_REQUIRED", "Location is required.")
    if quantity <= 0:
        raise bad_request("INVALID_QUANTITY", "Quantity must be greater than zero.")
    if total_weight_kg <= 0:
        raise bad_request("INVALID_TOTAL_WEIGHT", "Total weight must be greater than zero.")

    # Load the model only when pricing is requested, not during API startup.
    from ai.pricing.price_predictor import predict_collector_price

    return predict_collector_price(
        product_type=normalized_product_type,
        condition=normalized_condition,
        quantity=quantity,
        total_weight_kg=total_weight_kg,
        location=normalized_location,
    )


def estimate_price(
    *,
    product_type: str,
    condition: str,
    quantity: int,
    total_weight_kg: float,
    location: str,
) -> dict:
    """Build a user estimate from the existing single-value price model.

    The model currently exposes no uncertainty interval or market trend. The
    configured percentage band is therefore an explicit estimate range around
    the model output, not a fabricated market-price series.
    """
    predicted_price_per_kg = predict_price(
        product_type=product_type,
        condition=condition,
        quantity=quantity,
        total_weight_kg=total_weight_kg,
        location=location,
    )
    band = settings.pricing_estimate_range_percent
    min_price = round(predicted_price_per_kg * (1 - band), 2)
    max_price = round(predicted_price_per_kg * (1 + band), 2)
    estimated_total_min, estimated_total_max = estimated_total_range(min_price, max_price, total_weight_kg)
    return {
        "predicted_price_per_kg": predicted_price_per_kg,
        "min_price": min_price,
        "max_price": max_price,
        "estimated_total_value": round(predicted_price_per_kg * total_weight_kg, 2),
        "estimated_total_min": estimated_total_min,
        "estimated_total_max": estimated_total_max,
        "trend": None,
        "product_type": product_type.strip(),
        "condition": condition.strip(),
        "weight_kg": total_weight_kg,
        "is_estimate": True,
        "model_version": settings.pricing_model_version,
        "estimated_at": datetime.now(timezone.utc),
    }


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def estimated_total_range(min_price: float, max_price: float, weight_kg: float) -> tuple[float, float]:
    """The single source of truth for an estimated total range: the per-kg
    range (as shown to users, already rounded to paise) multiplied by the
    weight, rounded half-up to 2 decimals. Decimal arithmetic avoids float
    artefacts such as 98.21 * 0.40 == 39.284000000000006."""
    weight = Decimal(str(weight_kg))
    return _money(Decimal(str(min_price)) * weight), _money(Decimal(str(max_price)) * weight)


def with_estimated_totals(price_estimate: dict | None, weight_kg: float | None = None) -> dict | None:
    """Return a copy of a stored estimate whose total range is derived from
    its own per-kg range and `weight_kg` (defaults to the weight the
    estimate was made for). Never re-runs the ML model."""
    if not price_estimate:
        return price_estimate
    weight = weight_kg if weight_kg is not None else price_estimate.get("weight_kg")
    min_price = price_estimate.get("min_price")
    max_price = price_estimate.get("max_price")
    if weight is None or weight <= 0 or min_price is None or max_price is None:
        return price_estimate
    estimated_total_min, estimated_total_max = estimated_total_range(min_price, max_price, weight)
    return {
        **price_estimate,
        "weight_kg": weight,
        "estimated_total_min": estimated_total_min,
        "estimated_total_max": estimated_total_max,
    }


def lot_price_estimate(items: list[tuple[dict | None, float | None]]) -> dict | None:
    """Aggregate the stored per-submission estimates of a lot's items into
    one lot-level estimate. `items` is (stored price_estimate, actual
    collected weight) per item; an item without a collected weight falls
    back to the weight its estimate was made for. Returns None unless every
    item carries an estimate, so a partial total is never shown.

    Totals are the sum of each item's per-kg range times its weight; the
    per-kg range is taken as-is for a single item (or when all items share
    it), otherwise the weight-averaged range."""
    if not items:
        return None
    priced = [with_estimated_totals(estimate, weight) for estimate, weight in items]
    if any(not p or p.get("estimated_total_min") is None for p in priced):
        return None

    total_weight = sum(Decimal(str(p["weight_kg"])) for p in priced)
    total_min = sum(Decimal(str(p["estimated_total_min"])) for p in priced)
    total_max = sum(Decimal(str(p["estimated_total_max"])) for p in priced)
    ranges = {(p["min_price"], p["max_price"]) for p in priced}
    if len(ranges) == 1:
        min_price, max_price = next(iter(ranges))
    else:
        min_price = _money(total_min / total_weight)
        max_price = _money(total_max / total_weight)

    first = priced[0]
    return {
        "predicted_price_per_kg": first["predicted_price_per_kg"] if len(priced) == 1 else None,
        "min_price": min_price,
        "max_price": max_price,
        "weight_kg": float(total_weight),
        "estimated_total_min": _money(total_min),
        "estimated_total_max": _money(total_max),
        "is_estimate": True,
        "model_version": first.get("model_version"),
        "estimated_at": first.get("estimated_at"),
    }


# --- Historical price trend ---------------------------------------------------
#
# Source: real agreed sale prices on this platform — ACCEPTED recycler bids
# on lots. One observation = accepted bid amount / the lot's collected
# weight (INR/kg), dated by accepted_at, for the lot's category and ward.
# ML predictions and the synthetic training dataset are never used here.
#
# Method:
#   1. Keep observations from the last TREND_WINDOW_DAYS days.
#   2. One point per calendar day (UTC): the mean INR/kg of that day's sales.
#   3. Scope: the requested ward if it has at least MIN_TREND_POINTS days of
#      data, otherwise all wards; if neither does, the trend is
#      "insufficient_data" (no direction is claimed).
#   4. Split the points chronologically into an earlier and a recent half
#      (the middle point is left out when the count is odd) and compare their
#      averages: change% = (recent - earlier) / earlier * 100.
#      |change%| < STABLE_THRESHOLD_PERCENT -> "stable", otherwise
#      "increasing" / "decreasing".
#   5. Latest price = the most recent day's point.

TREND_WINDOW_DAYS = 90
MIN_TREND_POINTS = 4
STABLE_THRESHOLD_PERCENT = 5.0


def normalize_item(value: str | None) -> str:
    """'TV-Remote-Control', 'tv remote control ' -> 'tv remote control'."""
    return " ".join((value or "").replace("-", " ").replace("_", " ").lower().split())


def daily_price_points(observations: list[tuple[datetime, float]]) -> list[dict]:
    """[(timestamp, INR/kg)] -> chronological daily points (mean per day)."""
    by_day: dict = {}
    for timestamp, price in observations:
        by_day.setdefault(timestamp.date(), []).append(price)
    return [
        {"date": day, "price_per_kg": round(sum(prices) / len(prices), 2), "sales": len(prices)}
        for day, prices in sorted(by_day.items())
    ]


def trend_direction(points: list[dict]) -> tuple[str, float | None]:
    """(trend, change_percent) for chronological daily points."""
    if len(points) < MIN_TREND_POINTS:
        return "insufficient_data", None
    half = len(points) // 2
    earlier = [p["price_per_kg"] for p in points[:half]]
    recent = [p["price_per_kg"] for p in points[-half:]]
    earlier_avg = sum(earlier) / len(earlier)
    recent_avg = sum(recent) / len(recent)
    if earlier_avg <= 0:
        return "insufficient_data", None
    change = round((recent_avg - earlier_avg) / earlier_avg * 100, 2)
    if abs(change) < STABLE_THRESHOLD_PERCENT:
        return "stable", change
    return ("increasing" if change > 0 else "decreasing"), change


async def price_trend(*, item: str, ward_id: str | None, now: datetime | None = None) -> dict:
    from app.db.repositories import bids_repo, lots_repo

    item_key = normalize_item(item)
    if not item_key:
        raise bad_request("ITEM_REQUIRED", "An item/category is required.")

    now = now or datetime.now(timezone.utc)
    since = now.replace(tzinfo=None) - timedelta(days=TREND_WINDOW_DAYS)
    accepted = await bids_repo.list_accepted_since(since)
    lots = {lot["lot_id"]: lot for lot in await lots_repo.list_by_lot_ids([b["lot_id"] for b in accepted])}

    ward_obs: list[tuple[datetime, float]] = []
    all_obs: list[tuple[datetime, float]] = []
    for bid in accepted:
        lot = lots.get(bid["lot_id"])
        weight = (lot or {}).get("total_weight_kg")
        if not lot or not weight or weight <= 0 or normalize_item(lot.get("category")) != item_key:
            continue
        amount = bid["amount"].to_decimal() if hasattr(bid["amount"], "to_decimal") else bid["amount"]
        observation = (bid["accepted_at"], float(Decimal(str(amount))) / weight)
        all_obs.append(observation)
        if ward_id and lot.get("ward_id") == ward_id:
            ward_obs.append(observation)

    ward_points = daily_price_points(ward_obs)
    if ward_id and len(ward_points) >= MIN_TREND_POINTS:
        scope, points = "ward", ward_points
    else:
        all_points = daily_price_points(all_obs)
        scope, points = ("all_wards", all_points) if not ward_id or len(all_points) > len(ward_points) else ("ward", ward_points)

    trend, change = trend_direction(points)
    latest = points[-1] if points else None
    return {
        "item": item.strip(),
        "ward_id": ward_id if scope == "ward" else None,
        "scope": scope,
        "unit": "INR/kg",
        "source": "accepted_bids",
        "window_days": TREND_WINDOW_DAYS,
        "min_points": MIN_TREND_POINTS,
        "points": points,
        "trend": trend,
        "change_percent": change,
        "latest_price_per_kg": latest["price_per_kg"] if latest else None,
        "latest_date": latest["date"] if latest else None,
    }
