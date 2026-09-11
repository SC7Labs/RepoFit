"""Check for the presence of a file with a recognised license filename."""

from pathlib import Path

from repofit.checks.base import BaseCheck
from repofit.filesystem import sorted_entries
from repofit.models import CheckResult, CheckStatus

LICENSE_STEMS: frozenset[str] = frozenset(
    {"license", "licence", "copying", "unlicense"}
)
LICENSE_EXTENSIONS: frozenset[str] = frozenset({".md", ".markdown", ".rst", ".txt", ""})
LICENSE_PREFIXES: tuple[str, ...] = (
    "license-",
    "licence-",
    "copying-",
    "license_",
    "licence_",
    "copying_",
)


def is_license_file(entry: Path) -> bool:
    """Return True if path is a recognizable license file."""
    stem = entry.stem.lower()
    suffix = entry.suffix.lower()

    if stem in LICENSE_STEMS and suffix in LICENSE_EXTENSIONS:
        return True

    if any(stem.startswith(prefix) for prefix in LICENSE_PREFIXES):
        if suffix in LICENSE_EXTENSIONS or suffix in {".0", ".mit", ".apache", ".bsd"}:
            return True

    if stem in LICENSE_STEMS and suffix in {".mit", ".apache", ".bsd"}:
        return True

    return False


class LicenseCheck(BaseCheck):
    """Checks whether a file with a recognizable license filename exists.

    Filename only: the contents are never read, so this says nothing about which
    license it is, whether it is a recognised open-source licence, or whether it
    is filled in."""

    name = "License file"
    max_score = 10

    def run(self, repo_path: Path) -> CheckResult:
        try:
            for entry in sorted_entries(repo_path):
                if entry.is_file() and is_license_file(entry):
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
            message="No recognizable license file found",
            score=0,
            max_score=self.max_score,
        )
