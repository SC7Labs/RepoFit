"""Repository checks suite for RepoFit."""

from repofit.checks.base import BaseCheck
from repofit.checks.ci import CiCheck
from repofit.checks.env_example import EnvExampleCheck
from repofit.checks.env_hygiene import EnvHygieneCheck
from repofit.checks.gitignore import GitignoreCheck
from repofit.checks.large_files import LargeFilesCheck
from repofit.checks.license import LicenseCheck
from repofit.checks.lockfile import LockfileCheck
from repofit.checks.readme import ReadmeCheck
from repofit.checks.tests_check import TestsCheck
from repofit.checks.todos import TodosCheck


def get_default_checks() -> list[BaseCheck]:
    """Return an ordered list of default checks for repository auditing."""
    return [
        ReadmeCheck(),
        LicenseCheck(),
        GitignoreCheck(),
        EnvHygieneCheck(),
        EnvExampleCheck(),
        LockfileCheck(),
        TestsCheck(),
        CiCheck(),
        TodosCheck(),
        LargeFilesCheck(),
    ]


__all__ = [
    "BaseCheck",
    "CiCheck",
    "EnvExampleCheck",
    "EnvHygieneCheck",
    "GitignoreCheck",
    "LargeFilesCheck",
    "LicenseCheck",
    "LockfileCheck",
    "ReadmeCheck",
    "TestsCheck",
    "TodosCheck",
    "get_default_checks",
]
