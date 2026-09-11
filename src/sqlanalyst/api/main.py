"""HTTP surface. The full attempt trace is returned, failures included - a caller
that cannot see what the agent tried cannot audit it."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ..agent import answer
from ..schema import describe_schema, schema_prompt
from ..sql.execute import healthy
from ..types import QueryResult

app = FastAPI(
    title="sql-analyst-agent",
    version="0.1.0",
    description="Natural language to SQL with validation before execution and a read-only sandbox.",
)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


@app.get("/health")
def health() -> dict:
    return {"status": "ok" if healthy() else "degraded"}


@app.get("/schema")
def schema() -> dict:
    tables = describe_schema()
    return {
        "tables": {
            name: {
                "columns": [c.model_dump() for c in t.columns],
                "primary_key": t.primary_key,
                "foreign_keys": t.foreign_keys,
                "rows": t.row_estimate,
            }
            for name, t in tables.items()
        },
        "ddl": schema_prompt(tables),
    }


@app.post("/ask", response_model=QueryResult)
def ask(req: AskRequest) -> QueryResult:
    if not healthy():
        raise HTTPException(503, "database unavailable")
    return answer(req.question)
