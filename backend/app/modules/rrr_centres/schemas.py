from pydantic import BaseModel, Field


class RrrCentreRegisterRequest(BaseModel):
    username: str
    # Phase 11 security fix: enforced server-side, not just client-side.
    password: str = Field(min_length=8)
    rrr_id: str
    tender_id: str
    ward_id: str
    licence_doc_ref: str | None = None


class RrrCentreProfileResponse(BaseModel):
    user_id: str
    username: str
    rrr_id: str
    tender_id: str
    ward_id: str
    licence_doc_ref: str | None = None
    status: str
