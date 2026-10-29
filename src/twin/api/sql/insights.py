import json
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from twin.api.orm import AlertRow, PredictionRow, RcaResultRow, RiskScoreRow
from twin.api.schemas import AlertOut, PredictionOut, RcaResultOut, RiskOut
from twin.rca.engine import AlertRecord
from twin.rca.service import RcaRun, describe


class InsightQueries:
    sessions: async_sessionmaker[AsyncSession]

    async def forecast(self, device_key: str, metric: str) -> list[PredictionOut]:
        latest = (
            select(func.max(PredictionRow.made_at))
            .where(PredictionRow.device_key == device_key, PredictionRow.metric == metric)
            .scalar_subquery()
        )
        statement = (
            select(PredictionRow)
            .where(PredictionRow.device_key == device_key, PredictionRow.metric == metric, PredictionRow.made_at == latest)
            .order_by(PredictionRow.horizon_step)
        )
        async with self.sessions() as session:
            rows = (await session.execute(statement)).scalars().all()
        return [PredictionOut.model_validate(row) for row in rows]

    async def risk_scores(self, min_risk: float, limit: int) -> list[RiskOut]:
        statement = select(RiskScoreRow).where(RiskScoreRow.risk >= min_risk).order_by(RiskScoreRow.risk.desc()).limit(limit)
        async with self.sessions() as session:
            rows = (await session.execute(statement)).scalars().all()
        return [RiskOut.model_validate(row) for row in rows]

    async def alerts(self, status: str | None, severity: str | None, limit: int) -> list[AlertOut]:
        statement = select(AlertRow).order_by(AlertRow.raised_at.desc()).limit(limit)
        if status:
            statement = statement.where(AlertRow.status == status)
        if severity:
            statement = statement.where(AlertRow.severity == severity)
        async with self.sessions() as session:
            rows = (await session.execute(statement)).scalars().all()
        return [AlertOut.model_validate(row) for row in rows]

    async def set_alert_status(self, alert_id: int, status: str) -> AlertOut | None:
        now = datetime.now(timezone.utc)
        values: dict = {"status": status}
        if status == "acknowledged":
            values["acknowledged_at"] = now
        if status == "resolved":
            values["resolved_at"] = now
        statement = update(AlertRow).where(AlertRow.id == alert_id).values(**values).returning(AlertRow)
        async with self.sessions() as session:
            row = (await session.execute(statement)).scalar_one_or_none()
            await session.commit()
        return AlertOut.model_validate(row) if row else None

    async def open_alert_records(self) -> list[AlertRecord]:
        statement = select(AlertRow).where(AlertRow.status != "resolved")
        async with self.sessions() as session:
            rows = (await session.execute(statement)).scalars().all()
        return [AlertRecord(row.id, row.device_key, row.metric, row.severity, row.raised_at) for row in rows]

    async def save_rca_runs(self, runs: list[RcaRun]) -> None:
        rows = [
            RcaResultRow(
                run_id=run.run_id,
                created_at=datetime.now(timezone.utc),
                rank=rank,
                root_cause_key=candidate.node,
                fault_kind=candidate.fault_kind,
                score=candidate.score,
                alert_ids=candidate.explained_alert_ids,
                evidence={**candidate.evidence, "summary": describe(candidate)},
            )
            for run in runs
            for rank, candidate in enumerate(run.candidates, start=1)
        ]
        async with self.sessions() as session:
            session.add_all(rows)
            await session.commit()

    async def recent_rca(self, limit: int) -> list[RcaResultOut]:
        statement = (
            select(RcaResultRow)
            .where(RcaResultRow.run_id.in_(select(RcaResultRow.run_id).order_by(RcaResultRow.created_at.desc()).limit(limit)))
            .order_by(RcaResultRow.created_at.desc(), RcaResultRow.rank)
        )
        async with self.sessions() as session:
            rows = (await session.execute(statement)).scalars().all()
        return [
            RcaResultOut(
                run_id=row.run_id,
                created_at=row.created_at,
                rank=row.rank,
                root_cause_key=row.root_cause_key,
                fault_kind=row.fault_kind,
                score=row.score,
                alert_ids=list(row.alert_ids),
                evidence=json.loads(json.dumps(row.evidence)),
                summary=row.evidence.get("summary"),
            )
            for row in rows
        ]
