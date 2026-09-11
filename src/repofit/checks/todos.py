"""Check for actionable task comments (TODO/FIXME) in source files."""

import re
from pathlib import Path

from repofit.checks.base import BaseCheck
from repofit.filesystem import is_binary_file, walk_repository
from repofit.models import CheckResult, CheckStatus

TODO_PATTERN = re.compile(
    r"(?:#|//|/\*|<!--|--|;)\s*(?:TODO|FIXME)\b|^\s*\*\s*(?:TODO|FIXME)\b",
    re.IGNORECASE,
)
MAX_TEXT_FILE_SIZE = 1_048_576  # 1 MB

FIXTURE_DIR_NAMES: frozenset[str] = frozenset(
    {"fixtures", "testdata", "test_data", "snapshots", "__snapshots__", "cassettes"}
)


class TodosCheck(BaseCheck):
    """Counts actionable task comment occurrences across repository source files."""

    name = "TODO/FIXME"
    max_score = 5

    def run(self, repo_path: Path) -> CheckResult:
        walk = walk_repository(repo_path)
        if not walk.is_complete:
            return self.unverified_traversal(walk)

        count = 0
        unreadable = 0

        for file_path in walk.files:
            try:
                rel_parts = file_path.relative_to(repo_path).parts[:-1]
            except ValueError:
                try:
                    rel_parts = (
                        file_path.resolve().relative_to(repo_path.resolve()).parts[:-1]
                    )
                except ValueError:
                    rel_parts = ()
            if any(part.lower() in FIXTURE_DIR_NAMES for part in rel_parts):
                continue

            try:
                # Skip files larger than 1MB
                if file_path.stat().st_size > MAX_TEXT_FILE_SIZE:
                    continue
            except OSError:
                unreadable += 1
                continue

            # None means the file could not be read at all. Treating that as
            # "binary, therefore skip" made this check report "No TODO/FIXME
            # comments" about files it never opened.
            binary = is_binary_file(file_path)
            if binary is None:
                unreadable += 1
                continue
            if binary:
                continue

            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        count += len(TODO_PATTERN.findall(line))
            except OSError:
                unreadable += 1
                continue

        if unreadable:
            # Neither counted as TODOs nor as clean.
            return CheckResult(
                name=self.name,
                status=CheckStatus.UNVERIFIED,
                message=(
                    f"{unreadable} candidate file(s) could not be read; "
                    f"TODO/FIXME count is incomplete"
                ),
                score=0,
                max_score=self.max_score,
            )

        if count <= 10:
            msg = (
                f"{count} TODO/FIXME comments"
                if count > 0
                else "No TODO/FIXME comments"
            )
            return CheckResult(
                name=self.name,
                status=CheckStatus.PASS,
                message=msg,
                score=self.max_score,
                max_score=self.max_score,
            )
        elif count <= 30:
            return CheckResult(
                name=self.name,
                status=CheckStatus.WARNING,
                message=f"{count} TODO/FIXME comments",
                score=3,
                max_score=self.max_score,
            )
        else:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                message=f"{count} TODO/FIXME comments",
                score=0,
                max_score=self.max_score,
            )
