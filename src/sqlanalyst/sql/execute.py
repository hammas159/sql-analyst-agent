"""Execute validated SQL as the read-only role.

Every guard here is redundant with a guard somewhere else, on purpose. The role
cannot write, the transaction is read-only, the statement times out, and the cursor
is capped. Any one of them failing leaves the others standing.
"""

from __future__ import annotations

from typing import Any

import psycopg

from ..config import get_settings


class QueryError(RuntimeError):
    """A database-level failure, carrying the message the repair loop will read."""


def run(sql: str, *, max_rows: int | None = None) -> tuple[list[str], list[list[Any]]]:
    s = get_settings()
    max_rows = max_rows or s.max_rows

    try:
        # A fresh connection per query: no pooled session can carry state - a SET, a
        # temp table, an open transaction - from one question into the next.
        with psycopg.connect(s.agent_dsn, autocommit=False) as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute(f"SET LOCAL statement_timeout = {int(s.statement_timeout_ms)}")
                cur.execute(sql)  # already parsed and rewritten by sql.validate
                if cur.description is None:
                    raise QueryError("statement returned no result set")
                columns = [d.name for d in cur.description]
                rows = [list(r) for r in cur.fetchmany(max_rows)]
            conn.rollback()  # nothing to commit; be explicit about it
    except psycopg.errors.InsufficientPrivilege as exc:
        raise QueryError(f"permission denied: {exc}") from exc
    except psycopg.errors.QueryCanceled as exc:
        raise QueryError(
            f"query exceeded the {s.statement_timeout_ms} ms limit - "
            "narrow the filters or aggregate earlier"
        ) from exc
    except psycopg.Error as exc:
        # Postgres error text is the single most useful input to the repair loop:
        # it names the column, the table and often the fix.
        raise QueryError(str(exc).strip()) from exc

    return columns, rows


def healthy() -> bool:
    try:
        with psycopg.connect(get_settings().agent_dsn, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False
