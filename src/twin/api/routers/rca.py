from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from twin.api.deps import get_repository
from twin.api.repository import Repository
from twin.api.schemas import RcaResultOut
from twin.common.topology import Edge
from twin.rca.graph import AssetGraph
from twin.rca.service import RcaRun, analyze, describe

router = APIRouter(prefix="/rca", tags=["rca"])


def to_results(runs: list[RcaRun]) -> list[RcaResultOut]:
    created = datetime.now(timezone.utc)
    return [
        RcaResultOut(
            run_id=run.run_id,
            created_at=created,
            rank=rank,
            root_cause_key=candidate.node,
            fault_kind=candidate.fault_kind,
            score=candidate.score,
            alert_ids=candidate.explained_alert_ids,
            evidence=candidate.evidence,
            summary=describe(candidate),
        )
        for run in runs
        for rank, candidate in enumerate(run.candidates, start=1)
    ]


@router.get("", response_model=list[RcaResultOut])
async def recent(limit: int = Query(30, ge=1, le=200), repo: Repository = Depends(get_repository)) -> list[RcaResultOut]:
    return await repo.recent_rca(limit)


@router.post("/analyze", response_model=list[RcaResultOut])
async def run_analysis(
    window_minutes: float = Query(30.0, gt=0, le=720),
    top_n: int = Query(3, ge=1, le=10),
    repo: Repository = Depends(get_repository),
) -> list[RcaResultOut]:
    alerts = await repo.open_alert_records()
    graph = AssetGraph(Edge(src, dst, relation) for src, dst, relation in await repo.asset_edges())
    runs = analyze(alerts, graph, window_minutes * 60.0, top_n)
    if runs:
        await repo.save_rca_runs(runs)
    return to_results(runs)
