"""Typed results. Every stage of the agent returns one of these, never a bare dict."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Column(BaseModel):
    name: str
    type: str
    nullable: bool
    comment: str = ""


class Table(BaseModel):
    name: str
    columns: list[Column]
    primary_key: list[str] = Field(default_factory=list)
    # (column, referenced_table, referenced_column)
    foreign_keys: list[tuple[str, str, str]] = Field(default_factory=list)
    row_estimate: int = 0
    comment: str = ""


class Validation(BaseModel):
    ok: bool
    reason: str = ""
    # SQL after rewriting (LIMIT injected, etc). Only set when ok.
    rewritten: str = ""
    tables_touched: list[str] = Field(default_factory=list)


class Attempt(BaseModel):
    """One try. Kept even when it failed - the repair loop is the interesting part."""

    sql: str
    validation: Validation
    error: str = ""
    row_count: int | None = None


class QueryResult(BaseModel):
    question: str
    sql: str = ""
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    explanation: str = ""
    chart: dict | None = None
    attempts: list[Attempt] = Field(default_factory=list)
    failed: bool = False
    failure_reason: str = ""
    latency_ms: int = 0
    backend: str = ""
