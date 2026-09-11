"""Scanner engine to orchestrate checks and produce repository audit reports."""

from collections.abc import Sequence
from pathlib import Path

from repofit.checks import BaseCheck, get_default_checks
from repofit.models import RepoReport


class InvalidRepositoryError(Exception):
    """Raised when the specified target path is not a valid directory."""


class Scanner:
    """Runs the readiness checklist and aggregates the results."""

    def __init__(self, checks: Sequence[BaseCheck] | None = None) -> None:
        self.checks: list[BaseCheck] = (
            list(checks) if checks is not None else get_default_checks()
        )

    def scan(self, target_path: Path | str) -> RepoReport:
        """Scan a repository directory and return an aggregated audit report.

        Args:
            target_path: Path to the repository directory to audit.

        Returns:
            RepoReport containing all executed check results.

        Raises:
            InvalidRepositoryError: If the target path does not exist or is
                not a directory.
        """
        path = Path(target_path).resolve()

        if not path.exists():
            raise InvalidRepositoryError(f"Target path does not exist: {path}")

        if not path.is_dir():
            raise InvalidRepositoryError(f"Target path is not a directory: {path}")

        results = [check.run(path) for check in self.checks]
        return RepoReport(target_path=path, results=tuple(results))
