"""Check for suspiciously large files in the repository."""

from pathlib import Path

from repofit.checks.base import BaseCheck
from repofit.filesystem import walk_repository
from repofit.models import CheckResult, CheckStatus

DEFAULT_LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10 MiB


def format_file_size(num_bytes: int) -> str:
    """Format a byte count readably at any magnitude.

    Previously fixed to megabytes, which rendered a 4 KiB file as "0.0 MB" —
    useless once the threshold is configurable.
    """
    if num_bytes < 1024:
        return f"{num_bytes} B"
    value = float(num_bytes)
    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1024
        if value < 1024 or unit == "TB":
            # Whole numbers read better without a trailing .0
            if value == int(value):
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
    return f"{value:.1f} TB"


class LargeFilesCheck(BaseCheck):
    """Checks the working tree for files above a size threshold.

    Scans the working tree, so a listed file is not necessarily tracked by Git
    or destined to be committed — it is simply large and present."""

    name = "Large files"
    max_score = 5

    def __init__(self, threshold_bytes: int = DEFAULT_LARGE_FILE_THRESHOLD) -> None:
        self.threshold_bytes = threshold_bytes

    def run(self, repo_path: Path) -> CheckResult:
        walk = walk_repository(repo_path)
        if not walk.is_complete:
            return self.unverified_traversal(walk)

        oversized: list[tuple[str, int]] = []

        unmeasured = 0
        for file_path in walk.files:
            try:
                size = file_path.stat().st_size
            except OSError:
                # A file whose size is unknown cannot be ruled out.
                unmeasured += 1
                continue
            if size > self.threshold_bytes:
                try:
                    rel_path = str(file_path.relative_to(repo_path))
                except ValueError:
                    rel_path = str(file_path.resolve().relative_to(repo_path.resolve()))
                oversized.append((rel_path, size))

        if unmeasured:
            return CheckResult(
                name=self.name,
                status=CheckStatus.UNVERIFIED,
                message=(
                    f"{unmeasured} file(s) could not be measured; "
                    f"cannot confirm nothing exceeds "
                    f"{format_file_size(self.threshold_bytes)}"
                ),
                score=0,
                max_score=self.max_score,
            )

        if not oversized:
            return CheckResult(
                name=self.name,
                status=CheckStatus.PASS,
                message=f"No files over {format_file_size(self.threshold_bytes)}",
                score=self.max_score,
                max_score=self.max_score,
            )

        count = len(oversized)
        threshold_text = format_file_size(self.threshold_bytes)
        sample = [f"{path} ({format_file_size(size)})" for path, size in oversized[:3]]
        sample_str = ", ".join(sample)
        if count > 3:
            sample_str += f", and {count - 3} more"

        return CheckResult(
            name=self.name,
            status=CheckStatus.WARNING,
            message=(f"{count} file(s) over {threshold_text}: {sample_str}"),
            score=0,
            max_score=self.max_score,
        )
