from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from twin.api.sql.assets import AssetQueries
from twin.api.sql.insights import InsightQueries
from twin.api.sql.telemetry import TelemetryQueries


class SqlRepository(AssetQueries, TelemetryQueries, InsightQueries):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions
