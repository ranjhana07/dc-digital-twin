import inspect

from sqlalchemy.dialects import postgresql
from sqlalchemy import select

from twin.api.orm import AlertRow, Base
from twin.api.repository import Repository
from twin.api.sql.repository import SqlRepository
from twin.api.sql import telemetry


def test_sql_repository_implements_every_protocol_method():
    protocol_methods = {
        name for name, member in inspect.getmembers(Repository, inspect.isfunction) if not name.startswith("_")
    }
    missing = [name for name in protocol_methods if not inspect.iscoroutinefunction(getattr(SqlRepository, name, None))]
    assert missing == []


def test_orm_tables_match_migration_columns():
    migration = open("db/migrations/005_alerts.sql").read()
    for column in AlertRow.__table__.columns:
        assert column.name in migration
    assert {"alerts", "predictions", "risk_scores", "rca_results", "devices", "racks"} <= set(Base.metadata.tables)


def test_alert_query_compiles_for_postgres():
    statement = select(AlertRow).where(AlertRow.status == "open").order_by(AlertRow.raised_at.desc()).limit(5)
    assert "ORDER BY alerts.raised_at DESC" in str(statement.compile(dialect=postgresql.dialect()))


def test_raw_telemetry_queries_cast_optional_parameters():
    assert "CAST(:device_key AS text) IS NULL" in telemetry.LATEST_SQL
    assert "CAST(:metric AS text) IS NULL" in telemetry.LATEST_SQL
