from fastapi import APIRouter, Depends, Query

from twin.api.deps import get_repository
from twin.api.repository import Repository
from twin.api.schemas import PredictionOut, RiskOut

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("", response_model=list[PredictionOut])
async def forecast(device_key: str, metric: str, repo: Repository = Depends(get_repository)) -> list[PredictionOut]:
    return await repo.forecast(device_key, metric)


@router.get("/risk", response_model=list[RiskOut])
async def risk(
    min_risk: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=500),
    repo: Repository = Depends(get_repository),
) -> list[RiskOut]:
    return await repo.risk_scores(min_risk, limit)
