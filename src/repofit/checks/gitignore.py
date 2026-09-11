"""Check for the presence of a .gitignore file."""

from pathlib import Path

from repofit.checks.base import BaseCheck
from repofit.models import CheckResult, CheckStatus


class GitignoreCheck(BaseCheck):
    """Checks if a .gitignore file exists in the repository root."""

    name = ".gitignore"
    max_score = 10

    def run(self, repo_path: Path) -> CheckResult:
        try:
            gitignore_path = repo_path / ".gitignore"
            if gitignore_path.is_file():
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.PASS,
                    message="Found .gitignore",
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
            message="No .gitignore file found",
            score=0,
            max_score=self.max_score,
        )
