from fastapi import APIRouter, Depends, Header, Query

from app.core.rbac import require_role
from app.modules.rewards import service
from app.modules.rewards.schemas import ComputeRewardsRequest, RewardTransactionResponse

router = APIRouter(tags=["rewards"])


@router.get("/api/v1/rewards/mine")
async def list_my_rewards_route(current_user: dict = Depends(require_role("HOME_USER"))):
    docs = await service.list_my_rewards(current_user)
    return {"success": True, "rewards": docs}


@router.get("/api/v1/rewards/transactions/mine")
async def list_my_transactions_route(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(require_role("HOME_USER")),
):
    return {"success": True, **await service.list_my_transactions(current_user, limit=limit, offset=offset)}


@router.get("/api/v1/rewards/transactions/summary/mine")
async def transactions_summary_route(current_user: dict = Depends(require_role("HOME_USER"))):
    return {"success": True, **await service.summarize_my_transactions(current_user)}


@router.post("/api/v1/rewards/{reward_id}/redeem", response_model=RewardTransactionResponse)
async def redeem_reward_route(
    reward_id: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("HOME_USER")),
):
    result = await service.redeem_reward(current_user=current_user, reward_id=reward_id, idempotency_key=idempotency_key)
    return RewardTransactionResponse(**result)


@router.post("/api/v1/admin/rewards/compute")
async def compute_rewards_route(
    body: ComputeRewardsRequest,
    current_user: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    created = await service.compute_rewards_for_period(period=body.period, actor=current_user)
    return {"success": True, "created": created, "count": len(created)}


@router.get("/api/v1/admin/rewards")
async def admin_list_rewards_route(
    period: str | None = Query(default=None),
    _admin: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    docs = await service.list_all_for_admin(period=period)
    return {"success": True, "rewards": docs}
