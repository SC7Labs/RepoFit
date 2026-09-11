"""Check for the presence of a safe .env.example template file."""

from pathlib import Path

from repofit.checks.base import BaseCheck
from repofit.checks.env_hygiene import is_env_file
from repofit.filesystem import walk_repository
from repofit.models import CheckResult, CheckStatus

ENV_TEMPLATE_NAMES: frozenset[str] = frozenset(
    {
        ".env.example",
        ".env.sample",
        ".env.template",
        ".env.dist",
        "env.example",
        "env.sample",
        "env.template",
    }
)


def is_env_template_file(path: Path) -> bool:
    """Return True if a file is an environment template/example file."""
    name = path.name.lower()
    if name in ENV_TEMPLATE_NAMES:
        return True
    if name.startswith(".env.") and any(
        name.endswith(ext) for ext in (".example", ".sample", ".template", ".dist")
    ):
        return True
    return False


class EnvExampleCheck(BaseCheck):
    """Checks for .env.example when environment configuration is in use."""

    name = ".env.example"
    max_score = 5

    def run(self, repo_path: Path) -> CheckResult:
        walk = walk_repository(repo_path)
        if not walk.is_complete:
            return self.unverified_traversal(walk)
        all_files = list(walk.files)

        env_files = [f for f in all_files if is_env_file(f)]
        template_files = [f for f in all_files if is_env_template_file(f)]

        if template_files:
            return CheckResult(
                name=self.name,
                status=CheckStatus.PASS,
                message=f"Found {template_files[0].name}",
                score=self.max_score,
                max_score=self.max_score,
            )

        if not env_files:
            return CheckResult(
                name=self.name,
                status=CheckStatus.PASS,
                message="No environment configuration needed (N/A)",
                score=self.max_score,
                max_score=self.max_score,
            )

        return CheckResult(
            name=self.name,
            status=CheckStatus.WARNING,
            message=".env.example missing",
            score=0,
            max_score=self.max_score,
        )
