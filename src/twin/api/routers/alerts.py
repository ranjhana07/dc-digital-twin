from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from twin.api.deps import get_repository
from twin.api.repository import Repository
from twin.api.schemas import AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    status: Literal["open", "acknowledged", "resolved"] | None = None,
    severity: Literal["warning", "critical"] | None = None,
    limit: int = Query(100, ge=1, le=1000),
    repo: Repository = Depends(get_repository),
) -> list[AlertOut]:
    return await repo.alerts(status, severity, limit)


async def transition(alert_id: int, status: str, repo: Repository) -> AlertOut:
    updated = await repo.set_alert_status(alert_id, status)
    if updated is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return updated


@router.post("/{alert_id}/ack", response_model=AlertOut)
async def acknowledge(alert_id: int, repo: Repository = Depends(get_repository)) -> AlertOut:
    return await transition(alert_id, "acknowledged", repo)


@router.post("/{alert_id}/resolve", response_model=AlertOut)
async def resolve(alert_id: int, repo: Repository = Depends(get_repository)) -> AlertOut:
    return await transition(alert_id, "resolved", repo)
