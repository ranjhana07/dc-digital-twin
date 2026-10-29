# api

FastAPI service over the telemetry, asset and analytics tables. Routes are thin; they call a `Repository` (see `repository.py`). `SqlRepository` in `sql/` implements it with SQLAlchemy 2.0 async and asyncpg, and the tests swap in an in-memory fake through `create_app(repository=...)`.

```
uvicorn twin.api.main:app --host 0.0.0.0 --port 8000
```

Interactive docs are served at `/docs`. Settings come from the environment (`DATABASE_URL`, `CORS_ORIGINS`, `LIVE_INTERVAL_S`).

Health scores (`health.py`): each metric with a threshold contributes a penalty (0.35 at the warning limit, 1.0 at the critical limit, interpolated in log space for BER). A device scores 100 minus its worst penalty. A rack scores `0.6 * worst device + 0.4 * mean device`, minus 5 per open alert up to 20. Healthy is 85 and up, degraded 60 and up.
