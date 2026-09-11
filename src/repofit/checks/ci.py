"""Check for the presence of continuous integration (CI) workflows."""

from pathlib import Path

from repofit.checks.base import BaseCheck
from repofit.filesystem import sorted_entries
from repofit.models import CheckResult, CheckStatus

ROOT_CI_FILES: frozenset[str] = frozenset(
    {
        ".gitlab-ci.yml",
        ".gitlab-ci.yaml",
        ".travis.yml",
        "azure-pipelines.yml",
        "azure-pipelines.yaml",
        "bitbucket-pipelines.yml",
        "jenkinsfile",
    }
)


class CiCheck(BaseCheck):
    """Checks whether a CI configuration file is present.

    Presence only: the workflow is not parsed, validated, or known to have ever
    run or passed."""

    name = "CI configuration"
    max_score = 15

    def run(self, repo_path: Path) -> CheckResult:
        # Check GitHub Actions workflows
        workflows_dir = repo_path / ".github" / "workflows"
        if workflows_dir.is_dir():
            try:
                workflow_files = [
                    f
                    for f in sorted_entries(workflows_dir)
                    if f.is_file() and f.suffix.lower() in (".yml", ".yaml")
                ]
                if workflow_files:
                    first_wf = workflow_files[0].name
                    return CheckResult(
                        name=self.name,
                        status=CheckStatus.PASS,
                        message=f"Found GitHub Actions workflows ({first_wf})",
                        score=self.max_score,
                        max_score=self.max_score,
                    )
            except OSError:
                pass

        # Check CircleCI config
        circleci_dir = repo_path / ".circleci"
        if circleci_dir.is_dir():
            for name in ("config.yml", "config.yaml"):
                if (circleci_dir / name).is_file():
                    return CheckResult(
                        name=self.name,
                        status=CheckStatus.PASS,
                        message="Found CircleCI configuration file",
                        score=self.max_score,
                        max_score=self.max_score,
                    )

        # Check root-level CI files
        try:
            for entry in sorted_entries(repo_path):
                if entry.is_file() and entry.name.lower() in ROOT_CI_FILES:
                    return CheckResult(
                        name=self.name,
                        status=CheckStatus.PASS,
                        message=f"Found {entry.name}",
                        score=self.max_score,
                        max_score=self.max_score,
                    )
        except OSError:
            pass

        return CheckResult(
            name=self.name,
            status=CheckStatus.FAIL,
            message="No CI configuration file found",
            score=0,
            max_score=self.max_score,
        )
