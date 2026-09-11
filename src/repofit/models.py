"""Data models for RepoFit check results and scan reports."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class CheckStatus(StrEnum):
    """Status outcomes for an individual check.

    `UNVERIFIED` exists because a check whose evidence was unavailable has not
    passed. Collapsing "I looked and it was fine" into the same value as "I
    could not look" is the failure mode this tool is meant to avoid, not
    reproduce.
    """

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Result of an individual check execution."""

    name: str
    status: CheckStatus
    message: str
    score: int
    max_score: int

    @property
    def passed(self) -> bool:
        """Return True if the check passed."""
        return self.status == CheckStatus.PASS

    @property
    def verified(self) -> bool:
        """Return True if the check was able to reach a conclusion at all."""
        return self.status is not CheckStatus.UNVERIFIED


@dataclass(frozen=True, slots=True)
class RepoReport:
    """Aggregated audit report containing all check results for a target repository."""

    target_path: Path
    results: tuple[CheckResult, ...]

    @property
    def total_score(self) -> int:
        """Sum of all check scores."""
        return sum(result.score for result in self.results)

    @property
    def max_score(self) -> int:
        """Sum of all possible maximum check scores."""
        return sum(result.max_score for result in self.results)

    @property
    def health_score(self) -> int:
        """Deprecated weighted score, retained only for the JSON contract.

        Not shown in the terminal any more: it invited reading a checklist total
        as a quality measurement. Prefer `checks_passed` / `checks_total`.
        """
        if self.max_score <= 0:
            return 0
        return round((self.total_score / self.max_score) * 100)

    @property
    def checks_passed(self) -> int:
        """Number of checks that passed outright."""
        return sum(1 for result in self.results if result.status is CheckStatus.PASS)

    @property
    def checks_total(self) -> int:
        """Number of checks that ran."""
        return len(self.results)

    @property
    def failures(self) -> tuple[CheckResult, ...]:
        """Checks that failed."""
        return tuple(r for r in self.results if r.status is CheckStatus.FAIL)

    @property
    def warnings(self) -> tuple[CheckResult, ...]:
        """Checks that produced a warning."""
        return tuple(r for r in self.results if r.status is CheckStatus.WARNING)

    @property
    def unverified(self) -> tuple[CheckResult, ...]:
        """Checks that could not be evaluated."""
        return tuple(r for r in self.results if r.status is CheckStatus.UNVERIFIED)

    @property
    def exit_code(self) -> int:
        """Process exit code for this report.

        `0` only when every check passed. A warning or an unverified check is a
        finding the user should see, so both produce `1`: a checklist that exits
        clean while telling you it could not check something would be useless in
        CI, which is the only place an exit code matters.
        """
        return 0 if self.checks_passed == self.checks_total else 1
