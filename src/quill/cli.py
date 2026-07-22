import click

from quill import __version__


@click.group()
@click.version_option(version=__version__, prog_name="quill")
def main():
    """Quill - AI-powered legal document analyzer."""


@main.command()
@click.argument("file", type=click.Path(exists=True))
def analyze(file):
    """Analyze a legal document."""
    click.echo(f"Analyzing {file}...")
