from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from quill.analyzer import AnalysisResult


def display_analysis(result: AnalysisResult) -> None:
    console = Console()

    md = Markdown(result.text)
    panel = Panel(md, title=f"[bold]{result.role}[/bold]", border_style="blue")
    console.print(panel)

    table = Table(title="Usage Summary", show_header=True)
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
