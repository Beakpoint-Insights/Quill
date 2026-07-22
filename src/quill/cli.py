"""Command-line interface for Quill."""

import atexit
import logging

import click
from dotenv import load_dotenv
from rich.console import Console

from quill import __version__
from quill.analyzer import analyze_document, analyze_document_all_roles
from quill.output import display_analysis, display_multi_analysis
from quill.progress import ProgressTracker
from quill.reader import read_file
from quill.roles import ALL_ROLES
from quill.tracing import init_tracing, shutdown_tracing

__all__ = ["main"]

_atexit_registered = False


@click.group()
@click.version_option(version=__version__, prog_name="quill")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
def main(verbose: bool) -> None:
    """Quill - AI-powered legal document analyzer."""
    global _atexit_registered
    load_dotenv()
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s")
    if not _atexit_registered:
        atexit.register(shutdown_tracing)
        _atexit_registered = True


@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--single-role",
    is_flag=True,
    default=False,
    help="Run only the Senior Partner role instead of all five.",
)
@click.option(
    "--project",
    required=True,
    help="Project or matter name for cost attribution (e.g. 'Acme-Acquisition').",
)
@click.option(
    "--department",
    required=True,
    help="Department name for cost attribution (e.g. 'M&A').",
)
def analyze(
    file: str,
    single_role: bool,
    project: str,
    department: str,
) -> None:
    """Analyze a legal document."""
    init_tracing(project=project, department=department)
    text = read_file(file)
    console = Console()

    if single_role:
        with console.status("Analyzing document...", spinner="dots"):
            result = analyze_document(text)
        display_analysis(result)
    else:
        with ProgressTracker(ALL_ROLES, console=console) as tracker:
            results = analyze_document_all_roles(
                text, on_progress=tracker.make_callback()
            )
        display_multi_analysis(results)
        if all(r.error for r in results):
            raise click.ClickException(results[0].error or "All roles failed.")
