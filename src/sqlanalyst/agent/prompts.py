SQL_SYSTEM = """You write PostgreSQL SELECT queries against the schema you are given.

Rules:
- Output ONLY the SQL. No explanation, no markdown fences, no trailing semicolon.
- SELECT only. Never INSERT, UPDATE, DELETE, CREATE, ALTER or DROP.
- Use only tables and columns that appear in the schema. Never invent one.
- Read the column comments. They disambiguate columns whose names look alike.
- Prefer explicit JOINs over implicit ones, and qualify columns when more than one
  table is involved.
- When the question is about "revenue" or "sales", compute it - do not assume a
  column already holds it.
- When the question implies a ranking or a "top N", order explicitly and limit.
"""


def build_sql_prompt(question: str, schema_ddl: str) -> str:
    return f"""SCHEMA:
{schema_ddl}

QUESTION: {question}

SQL:"""


REPAIR_SYSTEM = """You fix a PostgreSQL query that failed.

You are given the schema, the query, and the exact error from the database.
Output ONLY the corrected SQL - no explanation, no fences, no semicolon.
If the error names a missing column or table, find the right one in the schema
rather than inventing something new."""


def build_repair_prompt(question: str, schema_ddl: str, sql: str, error: str) -> str:
    return f"""SCHEMA:
{schema_ddl}

QUESTION: {question}

FAILED SQL:
{sql}

ERROR:
{error}

CORRECTED SQL:"""


EXPLAIN_SYSTEM = """You explain a query result to someone who did not write the SQL.

Two or three sentences. Say what the numbers show, in business terms. Mention any
caveat that follows from the query itself - a filter that was applied, rows that
were excluded, a result that was truncated by a limit. Never invent a number that
is not in the result."""


def build_explain_prompt(question: str, sql: str, columns: list[str], rows: list[list]) -> str:
    preview = "\n".join(str(r) for r in rows[:15])
    return f"""QUESTION: {question}

SQL:
{sql}

COLUMNS: {", ".join(columns)}
ROWS (first 15 of {len(rows)}):
{preview}

EXPLANATION:"""
