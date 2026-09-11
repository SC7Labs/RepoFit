"""Regression tests: a check must not pass on a tree it could not read.

Traversal used to swallow `OSError` and silently stop at an arbitrary depth, so
a `.env` and an 11 MB file behind an unreadable directory produced
"No .env-style files present" and "No oversized files".

Fault injection is preferred over `chmod`, because permission bits are not
enforced for root and several CI sandboxes run as root.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest

from repofit.checks.env_hygiene import EnvHygieneCheck
from repofit.checks.large_files import LargeFilesCheck, format_file_size
from repofit.filesystem import MAX_WALK_DEPTH, WalkResult, walk_repository
from repofit.models import CheckStatus


def _git_repo(path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.invalid"], cwd=path, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    return path


def _block_directory(monkeypatch, blocked_name: str) -> None:
    """Make `iterdir` raise for one directory, whatever the real permissions."""
    real_iterdir = Path.iterdir

    def _iterdir(self: Path):
        if self.name == blocked_name:
            raise PermissionError(13, "Permission denied", str(self))
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", _iterdir)


# ---------------------------------------------------------------------------
# Unreadable subtrees
# ---------------------------------------------------------------------------


def test_walk_reports_a_directory_it_could_not_read(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "visible.txt").write_text("x\n")
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (blocked / "hidden.txt").write_text("y\n")

    _block_directory(monkeypatch, "blocked")
    result = walk_repository(tmp_path)

    assert result.directories_skipped == 1
    assert not result.is_complete
    assert "could not be read" in result.incompleteness_reason()
    assert all(p.name != "hidden.txt" for p in result.files)


def test_env_hygiene_is_unverified_when_a_subtree_is_unreadable(
    tmp_path: Path, monkeypatch
) -> None:
    """Regression: reported PASS "No .env-style files present"."""
    _git_repo(tmp_path)
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (blocked / ".env").write_text("SECRET=1\n")

    _block_directory(monkeypatch, "blocked")
    result = EnvHygieneCheck().run(tmp_path)

    assert result.status is CheckStatus.UNVERIFIED
    assert result.score == 0
    assert "could not be fully traversed" in result.message


def test_large_files_is_unverified_when_a_subtree_is_unreadable(
    tmp_path: Path, monkeypatch
) -> None:
    """Regression: reported PASS "No oversized files"."""
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (blocked / "big.bin").write_bytes(b"0" * 1024)

    _block_directory(monkeypatch, "blocked")
    result = LargeFilesCheck(threshold_bytes=512).run(tmp_path)

    assert result.status is CheckStatus.UNVERIFIED
    assert "could not be fully traversed" in result.message


def test_a_readable_tree_is_complete(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.txt").write_text("x\n")

    result = walk_repository(tmp_path)
    assert result.is_complete
    assert result.directories_skipped == 0
    assert result.depth_truncated == 0


# ---------------------------------------------------------------------------
# Depth bound
# ---------------------------------------------------------------------------


def _nest(root: Path, levels: int) -> Path:
    current = root
    for index in range(levels):
        current = current / f"d{index}"
        current.mkdir()
    return current


def test_content_well_within_the_bound_is_found(tmp_path: Path) -> None:
    """Depth 17 used to be silently past the old limit of 15."""
    deep = _nest(tmp_path, 17)
    (deep / ".env").write_text("SECRET=1\n")

    result = walk_repository(tmp_path)
    assert result.is_complete
    assert any(p.name == ".env" for p in result.files)


def test_content_at_the_boundary_is_found(tmp_path: Path) -> None:
    deep = _nest(tmp_path, MAX_WALK_DEPTH - 1)
    (deep / "marker.txt").write_text("x\n")

    result = walk_repository(tmp_path)
    assert result.is_complete
    assert any(p.name == "marker.txt" for p in result.files)


def test_content_beyond_the_boundary_is_reported_not_dropped(tmp_path: Path) -> None:
    deep = _nest(tmp_path, MAX_WALK_DEPTH + 5)
    (deep / "marker.txt").write_text("x\n")

    result = walk_repository(tmp_path)
    assert not result.is_complete
    assert result.depth_truncated >= 1
    assert "depth limit" in result.incompleteness_reason()


def test_truncation_makes_a_check_unverified(tmp_path: Path) -> None:
    _git_repo(tmp_path)
    deep = _nest(tmp_path, MAX_WALK_DEPTH + 2)
    (deep / ".env").write_text("SECRET=1\n")

    result = EnvHygieneCheck().run(tmp_path)
    assert result.status is CheckStatus.UNVERIFIED
    assert "depth limit" in result.message


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------


def test_files_are_returned_in_sorted_order(tmp_path: Path) -> None:
    for name in ["z.txt", "a.txt", "m.txt", "b.txt", "A.txt"]:
        (tmp_path / name).write_text("x\n")

    files = walk_repository(tmp_path).files
    assert list(files) == sorted(files)


def test_repeated_walks_produce_identical_order(tmp_path: Path) -> None:
    for name in ["z.txt", "a.txt", "m.txt"]:
        (tmp_path / name).write_text("x\n")
    (tmp_path / "sub").mkdir()
    for name in ["q.txt", "c.txt"]:
        (tmp_path / "sub" / name).write_text("x\n")

    orders = {tuple(str(p) for p in walk_repository(tmp_path).files) for _ in range(5)}
    assert len(orders) == 1


def test_shuffled_enumeration_still_produces_one_order(
    tmp_path: Path, monkeypatch
) -> None:
    """Directory order is not guaranteed by the OS; the walker must not rely on it."""
    for name in ["z.txt", "a.txt", "m.txt", "b.txt"]:
        (tmp_path / name).write_text("x\n")

    real_iterdir = Path.iterdir

    def _reversed(self: Path):
        return reversed(sorted(real_iterdir(self)))

    baseline = tuple(str(p) for p in walk_repository(tmp_path).files)
    monkeypatch.setattr(Path, "iterdir", _reversed)
    shuffled = tuple(str(p) for p in walk_repository(tmp_path).files)

    assert baseline == shuffled


def test_walk_result_reason_is_empty_when_complete() -> None:
    assert WalkResult(files=()).incompleteness_reason() == ""
    assert WalkResult(files=()).is_complete


# ---------------------------------------------------------------------------
# Large-file threshold message
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "threshold,expected",
    [(1024, "1 KB"), (10 * 1024 * 1024, "10 MB"), (3_000_000, "2.9 MB")],
)
def test_message_states_the_configured_threshold(
    tmp_path: Path, threshold: int, expected: str
) -> None:
    """Regression: the message said ">10MB" whatever the threshold was."""
    (tmp_path / "big.bin").write_bytes(b"0" * (11 * 1024 * 1024))

    result = LargeFilesCheck(threshold_bytes=threshold).run(tmp_path)
    assert expected in result.message
    assert "10MB" not in result.message.replace("10 MB", "")


def test_clean_message_also_states_the_threshold(tmp_path: Path) -> None:
    (tmp_path / "small.txt").write_text("x\n")
    result = LargeFilesCheck(threshold_bytes=1024).run(tmp_path)
    assert result.status is CheckStatus.PASS
    assert "1 KB" in result.message


@pytest.mark.parametrize(
    "size,expected",
    [(512, "512 B"), (1024, "1 KB"), (1536, "1.5 KB"), (11 * 1024 * 1024, "11 MB")],
)
def test_size_formatter_scales(size: int, expected: str) -> None:
    """It used to be fixed to megabytes, rendering 4 KiB as "0.0 MB"."""
    assert format_file_size(size) == expected


def test_sample_sizes_are_deterministic(tmp_path: Path) -> None:
    for name in ["z.bin", "a.bin", "m.bin"]:
        (tmp_path / name).write_bytes(b"0" * 2048)

    messages = {
        LargeFilesCheck(threshold_bytes=1024).run(tmp_path).message for _ in range(5)
    }
    assert len(messages) == 1


def test_walk_of_a_missing_directory_is_reported(tmp_path: Path) -> None:
    with tempfile.TemporaryDirectory() as scratch:
        missing = Path(scratch) / "gone"
    result = walk_repository(missing)
    assert not result.is_complete
    assert result.directories_skipped == 1


# ---------------------------------------------------------------------------
# Traversal completeness must reach every traversal-dependent check
# ---------------------------------------------------------------------------
#
# `WalkResult` reported incompleteness, but several checks called
# `walk_repository(...).files` and threw the rest away. `TestsCheck` was the
# worst: it returned a *fabricated* FAIL — "No test structure detected" — about
# a subtree it had never listed.


@pytest.mark.parametrize(
    "check_factory",
    [
        lambda: __import__(
            "repofit.checks.env_example", fromlist=["EnvExampleCheck"]
        ).EnvExampleCheck(),
        lambda: __import__(
            "repofit.checks.tests_check", fromlist=["TestsCheck"]
        ).TestsCheck(),
        lambda: __import__(
            "repofit.checks.todos", fromlist=["TodosCheck"]
        ).TodosCheck(),
        lambda: __import__(
            "repofit.checks.env_hygiene", fromlist=["EnvHygieneCheck"]
        ).EnvHygieneCheck(),
        lambda: __import__(
            "repofit.checks.large_files", fromlist=["LargeFilesCheck"]
        ).LargeFilesCheck(),
    ],
)
def test_every_traversal_check_is_unverified_on_a_blocked_subtree(
    tmp_path: Path, monkeypatch, check_factory
) -> None:
    _git_repo(tmp_path)
    (tmp_path / "blocked").mkdir()
    (tmp_path / "blocked" / "test_hidden.py").write_text("def test_a(): pass\n")

    _block_directory(monkeypatch, "blocked")
    result = check_factory().run(tmp_path)

    assert result.status is CheckStatus.UNVERIFIED, (
        f"{result.name} concluded {result.status.value} about a tree it could not read"
    )
    assert result.score == 0


def test_blocked_subtree_makes_the_scan_exit_nonzero(
    tmp_path: Path, monkeypatch
) -> None:
    from repofit.scanner import Scanner

    _git_repo(tmp_path)
    (tmp_path / "blocked").mkdir()
    _block_directory(monkeypatch, "blocked")

    assert Scanner().scan(tmp_path).exit_code == 1


# ---------------------------------------------------------------------------
# TODO/FIXME must not treat an unreadable file as clean
# ---------------------------------------------------------------------------


def test_unreadable_source_makes_todos_unverified(tmp_path: Path, monkeypatch) -> None:
    """Regression: reported PASS "No TODO/FIXME comments"."""
    from repofit.checks import todos as todos_module
    from repofit.checks.todos import TodosCheck

    (tmp_path / "a.py").write_text("# TODO: fix\n" * 30)
    monkeypatch.setattr(todos_module, "is_binary_file", lambda path, **kwargs: None)

    result = TodosCheck().run(tmp_path)

    assert result.status is CheckStatus.UNVERIFIED
    assert "could not be read" in result.message
    assert "No TODO" not in result.message


def test_unreadable_source_via_open_failure_is_unverified(
    tmp_path: Path, monkeypatch
) -> None:
    from repofit.checks import todos as todos_module
    from repofit.checks.todos import TodosCheck

    target = tmp_path / "a.py"
    target.write_text("# TODO: fix\n")
    monkeypatch.setattr(todos_module, "is_binary_file", lambda path, **kwargs: False)

    real_open = todos_module.open if hasattr(todos_module, "open") else open

    def _boom(path, *args, **kwargs):
        if str(path).endswith("a.py"):
            raise PermissionError(13, "denied", str(path))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", _boom)
    result = TodosCheck().run(tmp_path)
    assert result.status is CheckStatus.UNVERIFIED


def test_readable_sources_still_count_todos(tmp_path: Path) -> None:
    from repofit.checks.todos import TodosCheck

    (tmp_path / "a.py").write_text("# TODO: one\n# FIXME: two\n")
    result = TodosCheck().run(tmp_path)
    assert result.status is CheckStatus.PASS
    assert "2" in result.message


def test_is_binary_file_reports_unknown_rather_than_binary(tmp_path: Path) -> None:
    from repofit.filesystem import is_binary_file

    text = tmp_path / "t.txt"
    text.write_text("hello\n")
    assert is_binary_file(text) is False

    binary = tmp_path / "b.bin"
    binary.write_bytes(b"\x00\x01")
    assert is_binary_file(binary) is True

    assert is_binary_file(tmp_path / "missing.txt") is None


# ---------------------------------------------------------------------------
# Large files: a file that cannot be measured cannot be ruled out
# ---------------------------------------------------------------------------


def test_stat_failure_makes_large_files_unverified(tmp_path: Path, monkeypatch) -> None:
    """Regression: reported PASS "No files over 1 KB"."""
    (tmp_path / "big.bin").write_bytes(b"0" * 4096)

    real_stat = Path.stat

    def _boom(self: Path, *args, **kwargs):
        if self.name == "big.bin" and not args and not kwargs:
            raise PermissionError(13, "denied", str(self))
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _boom)
    result = LargeFilesCheck(threshold_bytes=1024).run(tmp_path)

    assert result.status is CheckStatus.UNVERIFIED
    assert "could not be measured" in result.message


# ---------------------------------------------------------------------------
# Candidate enumeration must be order-independent
# ---------------------------------------------------------------------------


def _both_orders(tmp_path: Path, monkeypatch, run) -> tuple[str, str]:
    """Run `run` with ascending and descending directory enumeration."""
    real_iterdir = Path.iterdir

    monkeypatch.setattr(Path, "iterdir", lambda self: iter(sorted(real_iterdir(self))))
    ascending = run()
    monkeypatch.setattr(
        Path, "iterdir", lambda self: iter(sorted(real_iterdir(self), reverse=True))
    )
    descending = run()
    return ascending, descending


def test_readme_choice_is_order_independent(tmp_path: Path, monkeypatch) -> None:
    from repofit.checks.readme import ReadmeCheck

    for name in ("README.md", "README.rst", "README.txt"):
        (tmp_path / name).write_text("x\n")

    first, second = _both_orders(
        tmp_path, monkeypatch, lambda: ReadmeCheck().run(tmp_path).message
    )
    assert first == second == "Found README.md"


def test_license_choice_is_order_independent(tmp_path: Path, monkeypatch) -> None:
    from repofit.checks.license import LicenseCheck

    for name in ("LICENSE", "LICENSE.md", "COPYING"):
        (tmp_path / name).write_text("MIT\n")

    first, second = _both_orders(
        tmp_path, monkeypatch, lambda: LicenseCheck().run(tmp_path).message
    )
    assert first == second


def test_ci_workflow_choice_is_order_independent(tmp_path: Path, monkeypatch) -> None:
    from repofit.checks.ci import CiCheck

    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    for name in ("a.yml", "b.yml", "c.yml"):
        (workflows / name).write_text("on: push\n")

    first, second = _both_orders(
        tmp_path, monkeypatch, lambda: CiCheck().run(tmp_path).message
    )
    assert first == second


def test_whole_report_is_byte_identical_across_runs(tmp_path: Path) -> None:
    """The public claim is deterministic output; this checks the rendered text."""
    import io

    from rich.console import Console

    from repofit.reporter import render_report
    from repofit.scanner import Scanner

    _git_repo(tmp_path)
    (tmp_path / "README.md").write_text("# P\n")
    (tmp_path / "README.rst").write_text("P\n")
    (tmp_path / "LICENSE").write_text("MIT\n")
    (tmp_path / "LICENSE.md").write_text("MIT\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_a(): pass\n")

    renders = set()
    for _ in range(5):
        buffer = io.StringIO()
        render_report(Scanner().scan(tmp_path), Console(file=buffer, width=100))
        renders.add(buffer.getvalue())
    assert len(renders) == 1


# ---------------------------------------------------------------------------
# Package markers are not test evidence
# ---------------------------------------------------------------------------


def test_tests_directory_with_only_an_init_does_not_pass(tmp_path: Path) -> None:
    """Regression: reported PASS "Found test file __init__.py"."""
    from repofit.checks.tests_check import TestsCheck

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "__init__.py").write_text("")

    result = TestsCheck().run(tmp_path)
    assert result.status is not CheckStatus.PASS
    assert "__init__" not in result.message


def test_a_real_test_file_still_passes(tmp_path: Path) -> None:
    from repofit.checks.tests_check import TestsCheck

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "__init__.py").write_text("")
    (tmp_path / "tests" / "test_app.py").write_text("def test_app(): pass\n")

    result = TestsCheck().run(tmp_path)
    assert result.status is CheckStatus.PASS
    assert "test_app.py" in result.message
