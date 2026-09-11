"""Shared filesystem traversal and inspection utilities for RepoFit."""

import stat
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

MAX_WALK_DEPTH: int = 64
"""Defensive nesting bound.

Symlinks are never followed, so this is not loop protection — it is a guard
against pathological trees exhausting the recursion limit. Set far above any
real repository; when it bites, traversal reports it rather than returning
silently truncated results.
"""

DEFAULT_IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "ENV",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "dist",
        "build",
        ".eggs",
        ".tox",
        ".nox",
        ".idea",
        ".vscode",
        "target",
        "vendor",
        "coverage",
        "htmlcov",
    }
)


def is_ignored_directory(name: str) -> bool:
    """Return True if the directory name matches standard ignored patterns."""
    return name in DEFAULT_IGNORED_DIRS or name.endswith(".egg-info")


@dataclass(frozen=True, slots=True)
class WalkResult:
    """The files a traversal found, and what it could not reach.

    Traversal used to swallow `OSError` and return, so an unreadable subtree
    simply vanished: a `.env` and an 11 MB file inside one produced
    "No .env-style files present" and "No oversized files". A check cannot pass
    on data nobody looked at, so the walker now reports its own gaps and the
    checks refuse to conclude when there are any.
    """

    files: tuple[Path, ...]
    directories_skipped: int = 0
    """Directories that could not be listed. Each hides a whole subtree."""
    depth_truncated: int = 0
    """Directories not descended into because of the depth bound."""

    @property
    def is_complete(self) -> bool:
        """True when every reachable directory was listed."""
        return self.directories_skipped == 0 and self.depth_truncated == 0

    def incompleteness_reason(self) -> str:
        """A short phrase naming what was missed, for a check's message."""
        parts: list[str] = []
        if self.directories_skipped:
            count = self.directories_skipped
            parts.append(
                f"{count} director{'y' if count == 1 else 'ies'} could not be read"
            )
        if self.depth_truncated:
            limit = MAX_WALK_DEPTH
            parts.append(
                f"{self.depth_truncated} path(s) exceeded the depth limit of {limit}"
            )
        return "; ".join(parts)


def _is_directory(entry: Path) -> bool:
    try:
        return entry.is_dir()
    except OSError:
        st = entry.stat(follow_symlinks=True)
        return stat.S_ISDIR(st.st_mode)


def _is_file(entry: Path) -> bool:
    try:
        return entry.is_file()
    except OSError:
        st = entry.stat(follow_symlinks=True)
        return stat.S_ISREG(st.st_mode)


def walk_repository(
    repo_path: Path,
    max_depth: int = MAX_WALK_DEPTH,
) -> WalkResult:
    """Walk a repository, reporting both the files found and the gaps.

    Directories are visited in sorted order and files are returned sorted, so a
    report over the same tree is byte-identical between runs. Directory
    enumeration order is not guaranteed by the OS, and RepoFit describes its
    checks as deterministic.

    Symlinks are never followed, so the depth bound guards against pathological
    nesting rather than loops. It is set well above any real repository; when it
    does bite, the affected checks say so instead of quietly returning less.
    """
    root_resolved = repo_path.resolve()
    files: list[Path] = []
    skipped = 0
    truncated = 0

    def _walk(current_dir: Path, current_depth: int) -> None:
        nonlocal skipped, truncated

        if current_depth > max_depth:
            truncated += 1
            return

        try:
            entries = sorted(current_dir.iterdir())
        except OSError:
            # Counted, not swallowed.
            skipped += 1
            return

        for entry in entries:
            try:
                # Skip symlinks to avoid loops and traversing outside the repository
                if entry.is_symlink():
                    continue

                if _is_directory(entry):
                    if not is_ignored_directory(entry.name):
                        _walk(entry, current_depth + 1)
                elif _is_file(entry):
                    # Ensure the resolved file path stays within the repository root
                    try:
                        entry.resolve().relative_to(root_resolved)
                    except (ValueError, OSError):
                        continue
                    files.append(entry)
            except OSError:
                skipped += 1

    _walk(root_resolved, current_depth=0)
    return WalkResult(
        files=tuple(sorted(files)),
        directories_skipped=skipped,
        depth_truncated=truncated,
    )


def walk_repository_files(
    repo_path: Path,
    max_depth: int = MAX_WALK_DEPTH,
) -> Iterator[Path]:
    """Yield repository files in deterministic order, discarding traversal gaps.

    Only for callers that genuinely do not care whether the walk was complete.
    Anything that reports a pass/fail verdict should use `walk_repository` and
    consult `WalkResult.is_complete`.
    """
    yield from walk_repository(repo_path, max_depth=max_depth).files


def sorted_entries(directory: Path) -> list[Path]:
    """List a directory in a fixed order.

    Directory enumeration order is not guaranteed by the OS, and RepoFit
    describes its checks as deterministic. Checks that pick the *first* matching
    candidate — the README, the license, a CI workflow — reported different
    evidence for the same tree depending on enumeration order until they went
    through here.

    `OSError` propagates deliberately. Swallowing it and returning an empty list
    would turn "this directory cannot be read" into "this directory is empty",
    which is the fail-open every caller here already handles for itself.
    """
    return sorted(directory.iterdir())


def is_binary_file(path: Path, sample_size: int = 8192) -> bool | None:
    """Whether a file looks binary, or None when it could not be read.

    Returning True for an unreadable file was a fail-open: callers that skip
    binaries then skipped unreadable ones too, and reported their own checks as
    clean. "Unreadable" is not "binary", and neither is "fine".

    Args:
        path: Path to the file to inspect.
        sample_size: Number of initial bytes to inspect (default: 8192).

    Returns:
        True if null bytes are present, False if not, None if unreadable.
    """
    try:
        with open(path, "rb") as f:
            chunk = f.read(sample_size)
            return b"\x00" in chunk
    except OSError:
        return None
