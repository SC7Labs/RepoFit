"""Command-line interface for RepoFit."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from repofit import __version__
from repofit.reporter import render_report
from repofit.scanner import InvalidRepositoryError, Scanner

app = typer.Typer(
    name="repofit",
    help="Run a deterministic pre-publication repository-hygiene checklist.",
    add_completion=False,
)

err_console = Console(stderr=True, highlight=False)


def version_callback(value: bool) -> None:
    """Print version string and exit."""
    if value:
        typer.echo(f"RepoFit {__version__}")
        raise typer.Exit()


@app.command()
def main(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to the repository to audit.",
            show_default=False,
        ),
    ] = Path("."),
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            help="Show the RepoFit version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Run the readiness checklist against a repository.

    Exit codes:

    * ``0`` — every check passed.
    * ``1`` — at least one check failed, warned, or could not be verified.
    * ``2`` — the target could not be scanned at all.
    """
    scanner = Scanner()
    try:
        report = scanner.scan(path)
    except InvalidRepositoryError as err:
        err_console.print(f"[bold red]Error:[/bold red] {err}", soft_wrap=True)
        raise typer.Exit(code=2) from err
    except Exception as err:
        err_console.print(f"[bold red]Error:[/bold red] {err}", soft_wrap=True)
        raise typer.Exit(code=2) from err

    render_report(report)
    raise typer.Exit(code=report.exit_code)


if __name__ == "__main__":
    app()
