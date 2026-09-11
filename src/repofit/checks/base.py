"""Abstract base class definition for readiness checks."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repofit.filesystem import WalkResult

from repofit.models import CheckResult, CheckStatus


class BaseCheck(ABC):
    """Abstract base class for all readiness checks."""

    name: str
    max_score: int = 10

    @abstractmethod
    def run(self, repo_path: Path) -> CheckResult:
        """Execute the check against the given repository directory."""
        ...

    def unverified_traversal(self, walk: "WalkResult") -> CheckResult:
        """Result for a check whose verdict depends on a tree it could not read.

        Shared so every traversal-dependent check reports incompleteness the
        same way, rather than each inventing its own handling — or, as before,
        none at all.
        """
        return CheckResult(
            name=self.name,
            status=CheckStatus.UNVERIFIED,
            message=(
                "Repository could not be fully traversed "
                f"({walk.incompleteness_reason()})"
            ),
            score=0,
            max_score=self.max_score,
        )
