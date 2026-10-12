from pydantic import BaseModel, Field


class RecyclerRegisterRequest(BaseModel):
    username: str  # = license_id, self-asserted at registration
    # Phase 11 security fix: enforced server-side, not just client-side.
    password: str = Field(min_length=8)
    company_name: str


class RecyclerProfileResponse(BaseModel):
    user_id: str
    username: str
    license_id: str
    company_name: str
    status: str
