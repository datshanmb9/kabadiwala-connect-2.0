from pydantic import BaseModel, Field


class CollectorCreateRequest(BaseModel):
    """Admin-only. `employee_id` becomes the collector's login username —
    issued by Government Admin, never chosen by the collector."""

    employee_id: str
    # Phase 11 security fix: enforced server-side, not just client-side.
    password: str = Field(min_length=8)
    ward_id: str
    rrr_id: str | None = None
    assigned_area_radius_m: float | None = None


class CollectorProfileResponse(BaseModel):
    user_id: str
    employee_id: str
    ward_id: str
    rrr_id: str | None = None
    assigned_area_radius_m: float | None = None


class CollectorAdminListItem(BaseModel):
    """Admin list view (Phase 7). Deliberately excludes password_hash —
    never expose password/credential material in any listing."""

    user_id: str
    employee_id: str
    ward_id: str
    rrr_id: str | None = None
    assigned_area_radius_m: float | None = None
    status: str


class CollectorAssignmentUpdateRequest(BaseModel):
    """Admin-only PATCH. Every field is optional; only fields explicitly
    supplied are changed (see collectors_repo.update_assignment)."""

    ward_id: str | None = None
    rrr_id: str | None = None
    assigned_area_radius_m: float | None = None


class CollectorStatusUpdateRequest(BaseModel):
    status: str  # "ACTIVE" or "DISABLED"
