"""Rich-formatted output for analysis results."""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from quill.analyzer import AnalysisResult

__all__ = ["display_analysis", "display_multi_analysis"]


def display_analysis(result: AnalysisResult) -> None:
    """Display a single analysis result with Rich formatting.

    Args:
        result: The analysis result to display.
    """
    console = Console()

    md = Markdown(result.text)
    panel = Panel(md, title=f"[bold]{result.role}[/bold]", border_style="blue")
    console.print(panel)

    source = "cached" if result.cache_hit else "live"
    table = Table(title=f"Usage Summary ({source})", show_header=True)
    table.add_column("Role", style="bold")
    table.add_column("Model")
    table.add_column("Input Tokens", justify="right")
    table.add_column("Output Tokens", justify="right")
    table.add_row(
        result.role,
        result.model,
        f"{result.input_tokens:,}",
        f"{result.output_tokens:,}",
    )
    console.print(table)


def display_multi_analysis(results: list[AnalysisResult]) -> None:
    """Display multiple analysis results as a structured report.

    Each role gets a panel; a summary table with totals follows.

    Args:
        results: The analysis results to display, in role order.
    """
    console = Console()

    for result in results:
        if result.error:
            panel = Panel(
                f"[red]Error: {result.error}[/red]",
                title=f"[bold]{result.role}[/bold]",
                border_style="red",
            )
        else:
            md = Markdown(result.text)
            panel = Panel(
                md,
                title=f"[bold]{result.role}[/bold]",
                border_style="blue",
            )
        console.print(panel)

    table = Table(title="Usage Summary", show_header=True)
    table.add_column("Role", style="bold")
    table.add_column("Model")
    table.add_column("Input Tokens", justify="right")
    table.add_column("Output Tokens", justify="right")

    total_input = 0
    total_output = 0

    for result in results:
        status_suffix = ""
        if result.error:
            status_suffix = " [red](failed)[/red]"
        elif result.cache_hit:
            status_suffix = " [dim](cached)[/dim]"

        table.add_row(
            f"{result.role}{status_suffix}",
            result.model,
            f"{result.input_tokens:,}",
            f"{result.output_tokens:,}",
        )
        total_input += result.input_tokens
        total_output += result.output_tokens

    table.add_section()
    table.add_row(
        "[bold]Total[/bold]",
        "",
        f"[bold]{total_input:,}[/bold]",
        f"[bold]{total_output:,}[/bold]",
    )

    console.print(table)
