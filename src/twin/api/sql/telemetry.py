from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from twin.api.schemas import PointOut, ReadingOut, SeriesPoint

LATEST_SQL = """
SELECT DISTINCT ON (device_key, metric) device_key, metric, value, ts
FROM telemetry
WHERE ts > now() - interval '10 minutes'
  AND (CAST(:device_key AS text) IS NULL OR device_key = :device_key)
  AND (CAST(:rack_key AS text) IS NULL OR device_key LIKE :rack_pattern)
  AND (CAST(:metric AS text) IS NULL OR metric = :metric)
ORDER BY device_key, metric, ts DESC
"""

SINCE_SQL = """
SELECT device_key, metric, value, ts
FROM telemetry
WHERE ts > :since AND ts <= now()
  AND (CAST(:device_key AS text) IS NULL OR device_key = :device_key)
ORDER BY ts
LIMIT 20000
"""

RANGE_SQL = """
SELECT ts, value
FROM telemetry
WHERE device_key = :device_key AND metric = :metric AND ts >= :start AND ts < :end
ORDER BY ts
LIMIT :limit
"""

SERIES_SQL = """
SELECT to_timestamp(floor(extract(epoch FROM ts) / :bucket_s) * :bucket_s) AS bucket,
       avg(value) AS avg_value, min(value) AS min_value, max(value) AS max_value
FROM telemetry
WHERE device_key = :device_key AND metric = :metric AND ts >= :start AND ts < :end
GROUP BY 1
ORDER BY 1
"""


class TelemetryQueries:
    sessions: async_sessionmaker[AsyncSession]

    async def latest_readings(
        self, device_key: str | None = None, rack_key: str | None = None, metric: str | None = None
    ) -> list[ReadingOut]:
        params = {
            "device_key": device_key,
            "rack_key": rack_key,
            "rack_pattern": f"{rack_key}/%" if rack_key else None,
            "metric": metric,
        }
        async with self.sessions() as session:
            rows = (await session.execute(text(LATEST_SQL), params)).all()
        return [ReadingOut(device_key=key, metric=name, value=value, ts=ts) for key, name, value, ts in rows]

    async def readings_since(self, since: datetime, device_key: str | None = None) -> list[ReadingOut]:
        async with self.sessions() as session:
            rows = (await session.execute(text(SINCE_SQL), {"since": since, "device_key": device_key})).all()
        return [ReadingOut(device_key=key, metric=name, value=value, ts=ts) for key, name, value, ts in rows]

    async def telemetry_range(
        self, device_key: str, metric: str, start: datetime, end: datetime, limit: int
    ) -> list[PointOut]:
        params = {"device_key": device_key, "metric": metric, "start": start, "end": end, "limit": limit}
        async with self.sessions() as session:
            rows = (await session.execute(text(RANGE_SQL), params)).all()
        return [PointOut(ts=ts, value=value) for ts, value in rows]

    async def telemetry_series(
        self, device_key: str, metric: str, start: datetime, end: datetime, bucket_s: int
    ) -> list[SeriesPoint]:
        params = {"device_key": device_key, "metric": metric, "start": start, "end": end, "bucket_s": bucket_s}
        async with self.sessions() as session:
            rows = (await session.execute(text(SERIES_SQL), params)).all()
        return [SeriesPoint(ts=ts, avg=avg, min=low, max=high) for ts, avg, low, high in rows]
