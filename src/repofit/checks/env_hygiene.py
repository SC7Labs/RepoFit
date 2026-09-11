"""Check for environment and secret file hygiene in repositories."""

import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from repofit.checks.base import BaseCheck
from repofit.filesystem import walk_repository
from repofit.models import CheckResult, CheckStatus

ENV_TEMPLATE_SUFFIXES: frozenset[str] = frozenset(
    {".example", ".sample", ".template", ".dist"}
)


def is_env_file(path: Path) -> bool:
    """Return True if path is an environment file (excluding templates)."""
    name = path.name.lower()
    if name == ".env":
        return True
    if name.startswith(".env."):
        # Check if the file is a template/example
        if any(name.endswith(suffix) for suffix in ENV_TEMPLATE_SUFFIXES):
            return False
        return True
    return False


class GitQueryStatus(StrEnum):
    """Whether a Git query actually answered the question."""

    OK = "ok"
    UNAVAILABLE = "unavailable"
    """No `git` on PATH, or the directory is not a repository."""
    ERROR = "error"
    """Git ran and failed, or timed out."""


@dataclass(frozen=True, slots=True)
class GitQuery:
    """A Git answer, together with whether Git was able to give one.

    The original shape of this returned a bare list, so a failed query and a
    query that legitimately matched nothing were the same empty list. That made
    every downstream check fail open: "git broke" rendered as "no environment
    files are tracked".
    """

    status: GitQueryStatus
    paths: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """True when the answer can be relied on."""
        return self.status is GitQueryStatus.OK


def _safe_relative_to(path: Path, root: Path) -> str:
    """Return path relative to root, resolving if root is a symlink."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path.resolve().relative_to(root.resolve()))


def _run_git(
    repo_path: Path, args: list[str], input_str: str | None = None
) -> tuple[GitQueryStatus, str]:
    """Run a read-only Git command, never through a shell."""
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotePath=false", *args],
            cwd=repo_path,
            input=input_str,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except FileNotFoundError:
        return GitQueryStatus.UNAVAILABLE, ""
    except (OSError, subprocess.TimeoutExpired):
        return GitQueryStatus.ERROR, ""

    # `git check-ignore` uses exit code 1 for "no path was ignored", which is an
    # answer rather than a failure. Anything above that is a real error.
    if result.returncode > 1:
        stderr = result.stderr.lower()
        if "not a git repository" in stderr:
            return GitQueryStatus.UNAVAILABLE, ""
        return GitQueryStatus.ERROR, ""

    return GitQueryStatus.OK, result.stdout


def get_git_tracked_files(repo_path: Path, files: list[Path]) -> GitQuery:
    """Ask Git which of `files` it tracks.

    Paths are passed as separate argv entries after `--`, never interpolated
    into a shell command.
    """
    rel_paths = [_safe_relative_to(f, repo_path) for f in files]
    if not rel_paths:
        return GitQuery(GitQueryStatus.OK)

    status, stdout = _run_git(repo_path, ["ls-files", "-z", "--", *rel_paths])
    if status is not GitQueryStatus.OK:
        return GitQuery(status)
    return GitQuery(
        GitQueryStatus.OK,
        tuple(p for p in stdout.split("\0") if p),
    )


def get_git_ignored_files(repo_path: Path, files: list[Path]) -> GitQuery:
    """Ask Git which of `files` are matched by an ignore rule."""
    rel_paths = [_safe_relative_to(f, repo_path) for f in files]
    if not rel_paths:
        return GitQuery(GitQueryStatus.OK)

    # Note: `git check-ignore -z` requires `--stdin`.
    # Using NUL-separated input and output preserves exact filenames with
    # Unicode, quotes, and whitespace without Git C-quoting them.
    input_payload = "\0".join(rel_paths) + "\0"
    status, stdout = _run_git(
        repo_path, ["check-ignore", "-z", "--stdin"], input_str=input_payload
    )
    if status is not GitQueryStatus.OK:
        return GitQuery(status)
    return GitQuery(
        GitQueryStatus.OK,
        tuple(p for p in stdout.split("\0") if p),
    )


def is_git_repository(repo_path: Path) -> bool:
    """Check if the target directory is a Git repository."""
    if (repo_path / ".git").exists():
        return True
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except (OSError, subprocess.TimeoutExpired):
        return False


class EnvHygieneCheck(BaseCheck):
    """Checks how a repository handles `.env`-style files.

    Four states, deliberately kept apart:

    | State | Result |
    |---|---|
    | tracked by Git | FAIL — the file is in version control |
    | untracked and ignored | PASS |
    | untracked and not ignored | WARNING — one `git add .` from being committed |
    | Git could not answer | UNVERIFIED — nothing was checked |

    This looks only at `.env`-style filenames. It is not a secret scanner and
    does not read file contents.
    """

    name = "Environment hygiene"
    max_score = 15

    def run(self, repo_path: Path) -> CheckResult:
        walk = walk_repository(repo_path)
        env_files = [f for f in walk.files if is_env_file(f)]

        if not walk.is_complete:
            # Part of the tree was never listed, so a verdict here would be a
            # claim about somewhere nobody looked.
            return self.unverified_traversal(walk)

        if not env_files:
            return CheckResult(
                name=self.name,
                status=CheckStatus.PASS,
                message="No .env-style files present",
                score=self.max_score,
                max_score=self.max_score,
            )

        names = ", ".join(sorted(f.name for f in env_files)[:3])

        tracked = get_git_tracked_files(repo_path, env_files)
        if not tracked.ok:
            # Verification failed. Saying "properly untracked" here would be an
            # assertion about something nobody looked at.
            return self._unverified(tracked.status, names)

        if tracked.paths:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                message=f"Tracked by Git: {', '.join(sorted(tracked.paths)[:3])}",
                score=0,
                max_score=self.max_score,
            )

        ignored = get_git_ignored_files(repo_path, env_files)
        if not ignored.ok:
            return self._unverified(ignored.status, names)

        unignored = sorted(
            f.name
            for f in env_files
            if _safe_relative_to(f, repo_path) not in ignored.paths
        )
        if unignored:
            return CheckResult(
                name=self.name,
                status=CheckStatus.WARNING,
                message=(
                    f"Untracked but not gitignored: {', '.join(unignored[:3])} "
                    "(one `git add .` from being committed)"
                ),
                score=5,
                max_score=self.max_score,
            )

        return CheckResult(
            name=self.name,
            status=CheckStatus.PASS,
            message=f"Untracked and gitignored: {names}",
            score=self.max_score,
            max_score=self.max_score,
        )

    def _unverified(self, status: GitQueryStatus, names: str) -> CheckResult:
        """Report that the question could not be answered."""
        reason = {
            GitQueryStatus.UNAVAILABLE: "not a Git repository, or git is not installed",
            GitQueryStatus.ERROR: "the git command failed",
        }.get(status, "git could not be queried")
        return CheckResult(
            name=self.name,
            status=CheckStatus.UNVERIFIED,
            message=f"{names} present, but Git status is unknown ({reason})",
            score=0,
            max_score=self.max_score,
        )
