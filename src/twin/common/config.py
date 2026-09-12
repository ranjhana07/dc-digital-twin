from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://twin:twin@localhost:5432/twin"

    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_qos: int = 0

    topo_sites: int = 1
    topo_halls: int = 2
    topo_racks_per_hall: int = 6
    topo_servers_per_rack: int = 4
    topo_cracs_per_hall: int = 2
    topo_xcvrs_per_switch: int = 2

    ingest_batch_size: int = 2000
    ingest_flush_seconds: float = 1.0
    ingest_mode: str = "copy"

    inference_interval_s: float = 30.0
    checkpoint_dir: str = "checkpoints"

    cors_origins: str = "*"
    live_interval_s: float = 1.0

    @property
    def psycopg_dsn(self) -> str:
        return self.database_url.replace("+asyncpg", "").replace("+psycopg2", "")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
