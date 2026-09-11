"""Streamlit UI.

The SQL and the attempt trace are shown by default rather than hidden behind a
toggle. A text-to-SQL tool that shows only the answer asks to be trusted; showing
the query lets the user check it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlanalyst.agent import answer  # noqa: E402
from sqlanalyst.config import get_settings  # noqa: E402
from sqlanalyst.schema import describe_schema  # noqa: E402
from sqlanalyst.sql.execute import healthy  # noqa: E402

st.set_page_config(page_title="sql-analyst-agent", page_icon="*", layout="wide")
settings = get_settings()

st.title("sql-analyst-agent")
st.caption("English in · validated SQL out · executed as a role that cannot write")

with st.sidebar:
    st.subheader("Database")
    if healthy():
        tables = describe_schema()
        st.success(f"{len(tables)} tables")
        for name, t in sorted(tables.items()):
            with st.expander(f"{name}  ({t.row_estimate:,} rows)"):
                st.dataframe(
                    pd.DataFrame(
                        [{"column": c.name, "type": c.type, "null": c.nullable} for c in t.columns]
                    ),
                    hide_index=True,
                )
    else:
        st.error("Database unreachable — run `make up && make seed`")

    st.write(f"**LLM** `{settings.llm_backend}`")
    st.write(f"**Row cap** `{settings.max_rows}`")
    st.caption(f"Repairs allowed: {settings.max_repair_attempts}")

question = st.text_input("Ask a question", placeholder="total revenue by region")

if question:
    with st.spinner("grounding, generating, validating, executing…"):
        result = answer(question)

    if result.failed:
        st.error(f"Could not answer after {len(result.attempts)} attempts.")
        st.code(result.failure_reason)
    else:
        st.code(result.sql, language="sql")

        df = pd.DataFrame(result.rows, columns=result.columns)
        st.dataframe(df, hide_index=True, use_container_width=True)

        if result.chart is not None:
            spec = result.chart
            chart_df = df[[spec["x"], spec["y"]]]
            if spec["type"] == "line":
                st.line_chart(chart_df, x=spec["x"], y=spec["y"])
            else:
                st.bar_chart(chart_df, x=spec["x"], y=spec["y"])

        st.info(result.explanation)

    c1, c2, c3 = st.columns(3)
    c1.metric("Attempts", len(result.attempts))
    c2.metric("Rows", len(result.rows))
    c3.metric("Latency", f"{result.latency_ms} ms")

    if len(result.attempts) > 1:
        with st.expander(f"Repair trace — {len(result.attempts)} attempts"):
            for i, attempt in enumerate(result.attempts, start=1):
                st.markdown(f"**Attempt {i}**")
                st.code(attempt.sql, language="sql")
                if attempt.error:
                    st.error(attempt.error)
                else:
                    st.success(f"{attempt.row_count} rows")
                st.divider()
