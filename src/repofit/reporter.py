"""Terminal report rendering using Rich."""

from rich.console import Console

from repofit import __version__
from repofit.models import CheckResult, CheckStatus, RepoReport


def format_check_line(result: CheckResult) -> str:
    """Return a single-line description for a check result.

    The check owns the diagnosis; this only decides how to lay it out. An
    earlier version pattern-matched the message and fell back to
    `f"{name} missing"` when nothing matched, which turned "Error reading
    repository directory: Permission denied" into "README missing" — a
    different, and wrong, diagnosis. Presentation may prefix a message. It may
    not replace one.
    """
    msg = result.message.strip()
    name = result.name

    if not msg:
        return name
    if result.status is CheckStatus.PASS:
        return f"{name}: {msg}"
    if msg.lower().startswith(name.lower()):
        return msg
    return f"{name}: {msg}"


def render_report(report: RepoReport, console: Console | None = None) -> None:
    """Render the repository audit report to the terminal.

    Args:
        report: The audit report to display.
        console: Optional Rich Console instance (useful for testing or custom output).
    """
    if console is None:
        console = Console(highlight=False)

    console.print(f"RepoFit {__version__}")
    console.print(f"Scanning: {report.target_path}\n", soft_wrap=True)

    for result in report.results:
        display_text = format_check_line(result)
        match result.status:
            case CheckStatus.PASS:
                console.print(f"[bold green]✓[/bold green] {display_text}")
            case CheckStatus.WARNING:
                console.print(f"[bold yellow]![/bold yellow] {display_text}")
            case CheckStatus.FAIL:
                console.print(f"[bold red]✗[/bold red] {display_text}")
            case CheckStatus.UNVERIFIED:
                console.print(f"[bold magenta]?[/bold magenta] {display_text}")

    console.print()

    passed = report.checks_passed
    total = report.checks_total
    if passed == total:
        style = "bold green"
    elif passed >= total * 0.5:
        style = "bold yellow"
    else:
        style = "bold red"

    # Deliberately "checks passed", not "health". This counts a fixed
    # checklist; it is not a measurement of repository quality, and a placeholder
    # repository that happens to satisfy every item should not be told it scored
    # 100/100 on anything.
    console.print(
        f"Readiness checklist: [{style}]{passed}/{total} checks passed[/{style}]"
    )

    if report.unverified:
        count = len(report.unverified)
        plural = "" if count == 1 else "s"
        console.print(
            f"[magenta]{count} check{plural} could not be verified.[/magenta]"
        )
