"""Ad-hoc schema migrations run at lifespan startup.

Tiny on purpose — we're not carrying alembic for a single SQLite app.
Each function is idempotent (check before altering) so running on an
already-migrated DB is a no-op.
"""

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_columns(conn, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def _sqlite_tables(conn) -> set[str]:
    rows = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'")
    ).fetchall()
    return {r[0] for r in rows}


def migrate(engine: Engine) -> None:
    """Bring an existing SQLite DB up to the current schema."""
    with engine.begin() as conn:
        tables = _sqlite_tables(conn)
        if "conversations" in tables:
            cols = _sqlite_columns(conn, "conversations")
            if "model" not in cols:
                conn.execute(
                    text("ALTER TABLE conversations ADD COLUMN model TEXT")
                )
