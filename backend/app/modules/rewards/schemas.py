from datetime import datetime

from pydantic import BaseModel


class ComputeRewardsRequest(BaseModel):
    period: str  # "YYYY-MM"


class RewardResponse(BaseModel):
    reward_id: str
    home_user_id: str
    period: str
    points: int
    amount: str
    status: str  # "CREDITED" or "REDEEMED"
    created_at: datetime


class RewardTransactionResponse(BaseModel):
    txn_id: str
    home_user_id: str
    reward_id: str
    type: str  # "CREDIT" or "REDEMPTION"
    amount: str
    status: str
    created_at: datetime
