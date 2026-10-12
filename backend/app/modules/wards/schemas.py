from pydantic import BaseModel


class WardCreateRequest(BaseModel):
    ward_id: str
    name: str


class WardResponse(BaseModel):
    ward_id: str
    name: str
