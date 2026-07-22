import atexit

import click
from rich.console import Console

from quill import __version__
from quill.analyzer import analyze_document
from quill.output import display_analysis
from quill.reader import read_file
from quill.tracing import init_tracing, shutdown_tracing


@click.group()
@click.version_option(version=__version__, prog_name="quill")
def main():
    """Quill - AI-powered legal document analyzer."""
    init_tracing()
    atexit.register(shutdown_tracing)


@main.command()
@click.argument("file", type=click.Path(exists=True))
def analyze(file):
    """Analyze a legal document."""
    text = read_file(file)
    console = Console()
    with console.status("Analyzing document...", spinner="dots"):
        result = analyze_document(text)
    display_analysis(result)
