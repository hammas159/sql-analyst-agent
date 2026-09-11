# sql-analyst-agent

[![ci](https://github.com/hammas159/sql-analyst-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/hammas159/sql-analyst-agent/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.12-blue)
![postgres](https://img.shields.io/badge/postgres-17-336791)
![license](https://img.shields.io/badge/license-MIT-green)

**Ask a database questions in English. It cannot damage the database, and it shows
you the SQL.**

Schema grounding → SQL generation → **parse-tree validation** → execution as a role
with no write privileges → self-repair from the real database error → plain-English
explanation and a chart.

---

## The part that matters: it is not allowed to write

Most text-to-SQL demos put "do not write to the database" in the prompt and hope.
Here there are three layers, and the weakest one is the prompt:

| Layer | Enforced by | Defeated by |
|---|---|---|
| 1. Instructions | the prompt | any model that ignores it |
| 2. **Validator** | `sqlglot` parse tree — statement type, forbidden nodes, function allowlist, unknown tables, injected `LIMIT` | a bug in layer 2 |
| 3. **`agent_ro` role** | Postgres: `SELECT`-only grants, `default_transaction_read_only`, `statement_timeout`, no `CREATE` | nothing in the application |

Layer 2 parses rather than pattern-matches, because regex guards lose to comments,
casing, nested CTEs and string literals that contain keywords. Every one of those is
in [`tests/test_validate.py`](tests/test_validate.py) as a test that must fail closed:

```sql
SELECT 1 FROM orders; DROP TABLE customers          -- rejected: stacked statements
WITH gone AS (DELETE FROM orders RETURNING *)       -- rejected: write inside a CTE
SELECT name FROM customers WHERE name = 'delete from orders'   -- accepted: it is a string
```

Layer 3 is verified **in CI on every push** — a job attempts five real writes as
`agent_ro` against a live Postgres and fails the build if any of them succeeds.
A security claim in a README is not evidence.

`make status` runs the same proof locally, by actually trying to create a table.

## Self-repair

A model writing SQL against an unfamiliar schema gets it wrong, and the useful
question is not how to avoid that but what happens next. Failures are fed back with
the exact Postgres error, which names the column and usually implies the fix:

```
attempt 1  SELECT region, sum(total) FROM orders GROUP BY region
           ERROR: column "total" does not exist
attempt 2  SELECT r.name, sum(oi.quantity * oi.unit_price * (1 - oi.discount)) ...
           42 rows
```

Every attempt is kept and returned, failures included. `mean_attempts` and
`repaired_after_failure` are reported metrics, not hidden behaviour.

## A schema built to be hard

The demo database is not three flat tables. It has the shapes that break naive
text-to-SQL, on purpose:

- `orders.status` and `orders.payment_status` — an order can be **delivered and
  refunded**; filtering the wrong one quietly changes every revenue number
- `order_items.unit_price` is the negotiated price, not `products.list_price`
- `customers.region_id` is nullable — online customers have no region, so "sales by
  region" has to decide what to do about them
- `employees.manager_id` self-references, so the org chart needs a recursive CTE
- `categories.parent_id` self-references for subcategories

Column comments are pulled from the catalog into the prompt, because they are the
cheapest disambiguation signal available and almost nobody uses them.

## Quick start

```bash
make up        # Postgres on :5434
make install   # uv sync, writes .env
make seed      # generate the dataset — offline, deterministic, no download
make status    # checks everything, and proves the agent role cannot write
make ask Q="total revenue by region"
make ui        # Streamlit on :8502
```

The dataset is generated from a fixed seed, so your database is byte-identical to
the one the numbers in [`RESULTS.md`](RESULTS.md) were measured on.

### LLM backend

`LLM_BACKEND=ollama` (local, free), `anthropic`, or `huggingface`. Same interface —
nothing above `llm.py` knows which is active.

## Evaluation

Scored on **what the query returns**, not on how the SQL reads. Many different
queries are correct, and string comparison would fail all but one of them. Each case
carries a reference query; a generated query passes when the result sets match,
compared order-insensitively.

The question set also contains requests that ask for writes. For those, **failing is
the correct outcome**, and `unsafe_requests_refused` scores it.

```bash
make eval      # writes RESULTS.md
```

## Layout

```
src/sqlanalyst/
  config.py          two DSNs: admin for introspection, agent_ro for queries
  llm.py             ollama | anthropic | huggingface behind one ABC
  types.py           Table, Validation, Attempt, QueryResult
  schema/            catalog introspection -> DDL prompt, with comments and row counts
  sql/validate.py    the parse-tree validator
  sql/execute.py     read-only execution, fresh connection per query
  agent/analyst.py   ground -> generate -> validate -> execute -> repair -> explain
  agent/charts.py    chart chosen from column types, never from the model
  eval_harness.py    execution-based scoring
docker/01-schema.sql the schema, with comments
docker/02-roles.sql  the read-only role — the third safety layer
scripts/seed.py      deterministic offline data generator
```

## Requirements

- Docker (Postgres only)
- [uv](https://docs.astral.sh/uv/) — no system Python needed
- An LLM backend: Ollama locally, or an API key

No GPU required.

## License

MIT

---

## Run it yourself

```bash
git clone https://github.com/hammas159/sql-analyst-agent
cd sql-analyst-agent

make up        # Postgres 17 on :5434
make install   # uv sync, writes .env
make seed      # 2,219 orders / 4,457 line items — generated offline, deterministic
make status    # checks everything, and *proves* the agent role cannot write
```

`make status` on a real database:

```
| admin connection  | up  | 8 tables                    |
| agent (read-only) | up  | postgresql://agent_ro@...   |
| write blocked     | yes | ReadOnlySqlTransaction      |   <- attempted, not claimed
```

A real query against the seeded warehouse:

```
"total revenue by region"
  Punjab 1,503,870.64 | Sindh 812,435.02 | KPK 727,101.85
```

And the attacks, each refused with a specific reason:

```
DELETE FROM orders                          → only SELECT is permitted
SELECT 1 FROM orders; DROP TABLE customers  → expected exactly one statement, got 2
SELECT pg_sleep(30) FROM orders             → function pg_sleep() is not permitted
SELECT * FROM sales_summary                 → unknown table: sales_summary
```

To ask questions in English, add an LLM backend — `ollama pull qwen2.5:3b-instruct`, or
set `ANTHROPIC_API_KEY`. Everything above works without one.

## Problems hit while building this

**The dangerous version of this project is the one that looks finished.** A text-to-SQL
demo that works on happy-path questions is easy; the failure modes are all adversarial
and none of them show up in a demo. So the validator is tested against the techniques
that actually defeat naive guards — stacked statements, a `DELETE` hidden inside a CTE, a
keyword inside a string literal, casing, comments — and each is a test that must fail
closed.

**A regex-based guard was the first design, and it is indefensible.** `"DELETE" not in
sql.upper()` is defeated by a comment, by casing, by a nested query, and by the perfectly
legitimate query `WHERE name = 'delete from orders'`. *Replaced* with a `sqlglot` parse
tree, so the check inspects what the SQL *is* rather than what it looks like.

**Unknown tables are caught before the database sees them.** Not for safety — for the
repair loop. `unknown table 'sales_summary'. Available: categories, customers, ...` is a
far stronger prompt for self-correction than Postgres's `relation does not exist`, and it
saves a round trip.
