from datetime import datetime

from pydantic import BaseModel


class ComplaintCreateRequest(BaseModel):
    """target_type/target_id are opaque, caller-supplied references (e.g.
    "lot"/"<lot_id>", "collector"/"<user_id>") — this module does not
    validate that the referenced entity exists; it is a citizen/actor
    report, not a foreign-key-enforced relationship."""

    target_type: str
    target_id: str
    category: str
    description: str


class ComplaintResponse(BaseModel):
    complaint_id: str
    reporter_id: str
    reporter_role: str
    target_type: str
    target_id: str
    category: str
    description: str
    status: str
    resolution_notes: str | None = None
    created_at: datetime


class ComplaintReviewRequest(BaseModel):
    """new_status must be one of the complaint_states allow-listed
    transitions from the complaint's current status — the service layer
    enforces this via state_machines/complaint_states.py, not this
    schema."""

    new_status: str
    resolution_notes: str | None = None
