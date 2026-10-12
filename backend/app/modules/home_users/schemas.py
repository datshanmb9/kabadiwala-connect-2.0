from datetime import datetime

from pydantic import BaseModel, Field


class HomeUserRegisterRequest(BaseModel):
    username: str
    # Phase 11 security fix: minimum length is enforced server-side, not
    # just in the frontend form — the backend must be authoritative for
    # every input, password strength included.
    password: str = Field(min_length=8)
    full_name: str
    address: str
    ward_id: str
    household_lat: float
    household_lng: float
    upi_id: str | None = None


class HomeUserProfileResponse(BaseModel):
    user_id: str
    username: str
    full_name: str
    address: str
    ward_id: str
    household_lat: float
    household_lng: float
    upi_id: str | None = None
    account_status: str = "ACTIVE"
    created_at: datetime | None = None
    preferences: dict[str, bool | str] = Field(default_factory=dict)


class HomeUserProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, min_length=1, max_length=500)


class HomeUserPreferencesRequest(BaseModel):
    language: str | None = None
    collection_updates: bool | None = None
    status_updates: bool | None = None
    account_updates: bool | None = None
