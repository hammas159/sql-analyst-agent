import datetime as dt
from decimal import Decimal

from sqlanalyst.agent.charts import suggest


def test_time_series_becomes_a_line():
    rows = [[dt.date(2025, m, 1), Decimal(m * 10)] for m in range(1, 7)]
    assert suggest(["month", "revenue"], rows) == {"type": "line", "x": "month", "y": "revenue"}


def test_category_totals_become_a_bar():
    rows = [["Punjab", 100], ["Sindh", 80], ["KPK", 60]]
    assert suggest(["region", "revenue"], rows)["type"] == "bar"


def test_single_row_is_not_a_chart():
    assert suggest(["total"], [[42]]) is None


def test_high_cardinality_is_a_table_not_a_bar():
    """400 bars is a noisy table, not a chart."""
    rows = [[f"customer {i}", i] for i in range(400)]
    assert suggest(["customer", "spend"], rows) is None


def test_no_numeric_column_means_no_chart():
    assert suggest(["name", "segment"], [["a", "retail"], ["b", "business"]]) is None


def test_nulls_do_not_break_type_detection():
    assert suggest(["region", "revenue"], [["Punjab", 10], [None, 20], ["KPK", 30]]) is not None
