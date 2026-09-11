"""Pick a chart from the shape of the result, not from the model's opinion.

Chart choice is a deterministic function of column types and cardinality, so the
same result always renders the same way and a hallucinated chart spec is impossible.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

_NUMERIC = (int, float, Decimal)
_TEMPORAL = (dt.date, dt.datetime)


def _kind(values: list[Any]) -> str:
    sample = [v for v in values if v is not None][:50]
    if not sample:
        return "empty"
    if all(isinstance(v, _TEMPORAL) for v in sample):
        return "temporal"
    if all(isinstance(v, _NUMERIC) and not isinstance(v, bool) for v in sample):
        return "quantitative"
    return "nominal"


def suggest(columns: list[str], rows: list[list[Any]]) -> dict | None:
    """Return a small chart spec, or None when a table is the honest answer."""
    if not rows or len(columns) < 2 or len(rows) < 2:
        return None

    kinds = [_kind([r[i] for r in rows]) for i in range(len(columns))]

    temporal = next((i for i, k in enumerate(kinds) if k == "temporal"), None)
    numeric = next((i for i, k in enumerate(kinds) if k == "quantitative"), None)
    nominal = next((i for i, k in enumerate(kinds) if k == "nominal"), None)

    if numeric is None:
        return None

    # A time series is a line; a ranking is a bar.
    if temporal is not None:
        return {"type": "line", "x": columns[temporal], "y": columns[numeric]}

    if nominal is not None:
        distinct = len({r[nominal] for r in rows})
        # Too many categories and a bar chart is just a noisy table.
        if 2 <= distinct <= 40:
            return {"type": "bar", "x": columns[nominal], "y": columns[numeric]}

    return None
