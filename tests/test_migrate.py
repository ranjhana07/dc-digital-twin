from pathlib import Path

from twin.db.migrate import DEFAULT_DIR, pending_migrations


def test_migrations_are_ordered_and_numbered():
    names = [path.name for path in pending_migrations(DEFAULT_DIR, set())]
    assert names == sorted(names)
    assert names[0].startswith("001_")
    prefixes = [name.split("_")[0] for name in names]
    assert prefixes == [f"{index:03d}" for index in range(1, len(names) + 1)]


def test_applied_migrations_are_skipped(tmp_path: Path):
    for name in ("001_a.sql", "002_b.sql", "003_c.sql"):
        (tmp_path / name).write_text("SELECT 1;")
    pending = pending_migrations(tmp_path, {"001_a.sql", "002_b.sql"})
    assert [path.name for path in pending] == ["003_c.sql"]
