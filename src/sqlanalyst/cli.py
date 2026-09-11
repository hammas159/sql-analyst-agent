"""sqlanalyst ask | schema | status | eval"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table as RichTable

from .config import get_settings

app = typer.Typer(add_completion=False, help="sql-analyst-agent")
console = Console()


@app.command()
def ask(
    question: str,
    show_trace: bool = typer.Option(
        False, "--trace", help="Show every attempt, including failures"
    ),
) -> None:
    """Ask a question in English."""
    from .agent import answer

    result = answer(question)

    if result.failed:
        console.print(Panel(result.failure_reason, title="failed", border_style="red"))
    else:
        console.print(Syntax(result.sql, "sql", theme="ansi_dark", word_wrap=True))
        table = RichTable(*result.columns)
        for row in result.rows[:30]:
            table.add_row(*("" if v is None else str(v) for v in row))
        console.print(table)
        if len(result.rows) > 30:
            console.print(f"[dim]... {len(result.rows) - 30} more rows[/]")
        console.print(Panel(result.explanation, title="explanation", border_style="green"))
        if result.chart:
            console.print(f"[dim]suggested chart: {result.chart}[/]")

    if show_trace:
        for i, attempt in enumerate(result.attempts, start=1):
            status = "ok" if attempt.validation.ok and not attempt.error else "failed"
            console.print(
                Panel(
                    f"{attempt.sql}\n\n[red]{attempt.error}[/]" if attempt.error else attempt.sql,
                    title=f"attempt {i} - {status}",
                    border_style="red" if attempt.error else "green",
                )
            )

    console.print(
        f"[dim]backend={result.backend}  attempts={len(result.attempts)}  "
        f"rows={len(result.rows)}  latency={result.latency_ms}ms[/]"
    )


@app.command()
def schema() -> None:
    """Print the schema exactly as the model sees it."""
    from .schema import schema_prompt

    console.print(Syntax(schema_prompt(), "sql", theme="ansi_dark"))


@app.command()
def status() -> None:
    """Check every dependency, and prove the read-only role really is read-only."""
    import psycopg

    from .schema import describe_schema
    from .sql.execute import healthy

    s = get_settings()
    table = RichTable("component", "status", "detail")

    try:
        tables = describe_schema()
        table.add_row("admin connection", "[green]up[/]", f"{len(tables)} tables")
    except Exception as exc:
        table.add_row("admin connection", "[red]down[/]", str(exc)[:70])

    table.add_row("agent (read-only)", "[green]up[/]" if healthy() else "[red]down[/]", s.agent_dsn)

    # Not a claim in a README - an actual attempted write, every time you run status.
    try:
        with psycopg.connect(s.agent_dsn, connect_timeout=3) as conn:
            conn.execute("CREATE TABLE should_not_exist (x int)")
        table.add_row("write blocked", "[red]NO - ROLE CAN WRITE[/]", "check docker/02-roles.sql")
    except psycopg.Error as exc:
        table.add_row("write blocked", "[green]yes[/]", type(exc).__name__)
    except Exception as exc:
        table.add_row("write blocked", "[yellow]unknown[/]", str(exc)[:60])

    if s.llm_backend == "ollama":
        import httpx

        try:
            r = httpx.get(f"{s.ollama_base_url}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            hit = any(m.startswith(s.ollama_model.split(":")[0]) for m in models)
            table.add_row(
                "llm (ollama)",
                "[green]up[/]" if hit else "[yellow]no model[/]",
                f"{s.ollama_model} | {', '.join(models) or 'none installed'}",
            )
        except Exception as exc:
            table.add_row("llm (ollama)", "[red]down[/]", str(exc)[:60])
    else:
        key = s.anthropic_api_key if s.llm_backend == "anthropic" else s.hf_token
        table.add_row(f"llm ({s.llm_backend})", "[green]ok[/]" if key else "[red]no key[/]", "")

    console.print(table)


@app.command("eval")
def evaluate() -> None:
    """Run the question set and write RESULTS.md."""
    from .eval_harness import run_eval

    run_eval()


if __name__ == "__main__":
    app()
