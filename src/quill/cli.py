import click

from quill import __version__
from quill.reader import read_file


@click.group()
@click.version_option(version=__version__, prog_name="quill")
def main():
    """Quill - AI-powered legal document analyzer."""


@main.command()
@click.argument("file", type=click.Path(exists=True))
def analyze(file):
    """Analyze a legal document."""
    text = read_file(file)
    click.echo(f"Read {len(text)} characters from {file}")
