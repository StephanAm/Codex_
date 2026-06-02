import click

from scribe import __version__


@click.group()
@click.version_option(__version__, prog_name="scribe")
def main() -> None:
    """Scribe — context-aware LLM integration for the Codex workspace."""
