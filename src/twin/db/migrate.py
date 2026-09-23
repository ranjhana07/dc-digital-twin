import argparse
import logging
from pathlib import Path

import psycopg2

from twin.common.config import get_settings

log = logging.getLogger("twin.migrate")

DEFAULT_DIR = Path(__file__).resolve().parents[3] / "db" / "migrations"


def pending_migrations(directory: Path, applied: set[str]) -> list[Path]:
    return [path for path in sorted(directory.glob("*.sql")) if path.name not in applied]


def migrate(dsn: str, directory: Path = DEFAULT_DIR) -> list[str]:
    ran: list[str] = []
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "filename text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            cur.execute("SELECT filename FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}
        for path in pending_migrations(directory, applied):
            with conn.cursor() as cur:
                cur.execute(path.read_text())
                cur.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,))
            conn.commit()
            log.info("applied %s", path.name)
            ran.append(path.name)
    return ran


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Apply SQL migrations")
    parser.add_argument("--dsn", default=get_settings().psycopg_dsn)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    ran = migrate(args.dsn, args.dir)
    print(f"applied {len(ran)} migrations")


if __name__ == "__main__":
    main()
