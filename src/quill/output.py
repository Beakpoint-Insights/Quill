"""Rich-formatted output for analysis results."""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from quill.analyzer import AnalysisResult

__all__ = ["display_analysis"]


def display_analysis(result: AnalysisResult) -> None:
    """Display the analysis result with Rich formatting.

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
