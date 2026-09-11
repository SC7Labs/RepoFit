"""Check for the presence of a repository README file."""

from pathlib import Path

from repofit.checks.base import BaseCheck
from repofit.filesystem import sorted_entries
from repofit.models import CheckResult, CheckStatus

README_EXTENSIONS: frozenset[str] = frozenset({".md", ".markdown", ".rst", ".txt", ""})


class ReadmeCheck(BaseCheck):
    """Checks if a recognizable README file exists in the repository root."""

    name = "README"
    max_score = 10

    def run(self, repo_path: Path) -> CheckResult:
        try:
            for entry in sorted_entries(repo_path):
                if entry.is_file():
                    stem = entry.stem.lower()
                    suffix = entry.suffix.lower()
                    if stem == "readme" and suffix in README_EXTENSIONS:
                        return CheckResult(
                            name=self.name,
                            status=CheckStatus.PASS,
                            message=f"Found {entry.name}",
                            score=self.max_score,
                            max_score=self.max_score,
                        )
        except OSError as err:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                message=f"Error reading repository directory: {err}",
                score=0,
                max_score=self.max_score,
            )

        return CheckResult(
            name=self.name,
            status=CheckStatus.FAIL,
            message="No README file found",
            score=0,
            max_score=self.max_score,
        )
