"""Regression tests for bugs where RepoFit reported something it had not verified.

Each of these was reproduced against the previous implementation before being
fixed. The common shape: a check that could not answer a question answered it
anyway, and answered "fine".
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from repofit.checks.env_hygiene import EnvHygieneCheck, GitQueryStatus
from repofit.checks.large_files import LargeFilesCheck
from repofit.checks.license import LicenseCheck
from repofit.checks.lockfile import LockfileCheck
from repofit.checks.tests_check import TestsCheck
from repofit.cli import app
from repofit.models import CheckResult, CheckStatus, RepoReport
from repofit.reporter import format_check_line

runner = CliRunner()


def _git_repo(path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.invalid"], cwd=path, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    return path


def _git_available() -> bool:
    try:
        return subprocess.run(["git", "--version"], capture_output=True).returncode == 0
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


def test_failing_repository_exits_nonzero(tmp_path: Path) -> None:
    """Original bug: a repository failing six checks still exited 0."""
    result = runner.invoke(app, [str(tmp_path)])
    assert result.exit_code == 1


def test_invalid_target_exits_two(tmp_path: Path) -> None:
    assert runner.invoke(app, [str(tmp_path / "nope")]).exit_code == 2
    target = tmp_path / "f.txt"
    target.write_text("x\n")
    assert runner.invoke(app, [str(target)]).exit_code == 2


def test_warning_only_repository_exits_one(tmp_path: Path) -> None:
    """A warning is a finding: exiting 0 would hide it in CI."""
    report = RepoReport(
        target_path=tmp_path,
        results=(
            CheckResult(
                name="a", status=CheckStatus.PASS, message="", score=1, max_score=1
            ),
            CheckResult(
                name="b", status=CheckStatus.WARNING, message="", score=0, max_score=1
            ),
        ),
    )
    assert report.exit_code == 1


def test_unverified_check_exits_one(tmp_path: Path) -> None:
    report = RepoReport(
        target_path=tmp_path,
        results=(
            CheckResult(
                name="a",
                status=CheckStatus.UNVERIFIED,
                message="",
                score=0,
                max_score=1,
            ),
        ),
    )
    assert report.exit_code == 1


# ---------------------------------------------------------------------------
# Git fail-open
# ---------------------------------------------------------------------------


def test_git_failure_does_not_look_like_a_clean_result(
    tmp_path: Path, monkeypatch
) -> None:
    """Original bug: a raised OSError produced PASS 'properly untracked/gitignored'."""
    _git_repo(tmp_path)
    (tmp_path / ".env").write_text("SECRET=x\n")

    from repofit.checks import env_hygiene

    def _boom(*args, **kwargs):
        raise OSError("git exploded")

    monkeypatch.setattr(env_hygiene.subprocess, "run", _boom)
    result = EnvHygieneCheck().run(tmp_path)

    assert result.status is CheckStatus.UNVERIFIED
    assert result.score == 0
    assert "unknown" in result.message.lower()


def test_missing_git_is_unverified_not_pass(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("SECRET=x\n")
    from repofit.checks import env_hygiene

    def _no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(env_hygiene.subprocess, "run", _no_git)
    result = EnvHygieneCheck().run(tmp_path)
    assert result.status is CheckStatus.UNVERIFIED


def test_not_a_git_repository_is_unverified(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SECRET=x\n")
    result = EnvHygieneCheck().run(tmp_path)
    assert result.status is CheckStatus.UNVERIFIED
    assert "not a git repository" in result.message.lower()


def test_git_query_status_is_reported(tmp_path: Path) -> None:
    from repofit.checks.env_hygiene import get_git_tracked_files

    query = get_git_tracked_files(tmp_path, [tmp_path / ".env"])
    assert query.status is GitQueryStatus.UNAVAILABLE
    assert not query.ok


# ---------------------------------------------------------------------------
# .env states
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _git_available(), reason="git unavailable")
def test_env_tracked_fails(tmp_path: Path) -> None:
    _git_repo(tmp_path)
    (tmp_path / ".env").write_text("SECRET=x\n")
    subprocess.run(["git", "add", "-f", ".env"], cwd=tmp_path, check=True)

    result = EnvHygieneCheck().run(tmp_path)
    assert result.status is CheckStatus.FAIL
    assert result.score == 0


@pytest.mark.skipif(not _git_available(), reason="git unavailable")
def test_env_untracked_and_ignored_passes(tmp_path: Path) -> None:
    _git_repo(tmp_path)
    (tmp_path / ".env").write_text("SECRET=x\n")
    (tmp_path / ".gitignore").write_text(".env\n")

    result = EnvHygieneCheck().run(tmp_path)
    assert result.status is CheckStatus.PASS
    assert "gitignored" in result.message.lower()


@pytest.mark.skipif(not _git_available(), reason="git unavailable")
def test_env_untracked_and_unignored_warns(tmp_path: Path) -> None:
    """Original bug: this reported PASS 'properly untracked/gitignored'."""
    _git_repo(tmp_path)
    (tmp_path / ".env").write_text("SECRET=x\n")

    result = EnvHygieneCheck().run(tmp_path)
    assert result.status is CheckStatus.WARNING
    assert "not gitignored" in result.message.lower()


def test_no_env_files_passes(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# x\n")
    result = EnvHygieneCheck().run(tmp_path)
    assert result.status is CheckStatus.PASS


# ---------------------------------------------------------------------------
# Polyglot lockfiles
# ---------------------------------------------------------------------------


def test_rust_lockfile_does_not_satisfy_node(tmp_path: Path) -> None:
    """Original bug: Cargo.lock made a Node project without a lockfile pass."""
    (tmp_path / "package.json").write_text("{}\n")
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "x"\n')
    (tmp_path / "Cargo.lock").write_text("version = 3\n")

    result = LockfileCheck().run(tmp_path)
    assert result.status is CheckStatus.WARNING
    assert "Node" in result.message


def test_each_ecosystem_named_in_the_message(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}\n")
    (tmp_path / "go.mod").write_text("module x\n")
    (tmp_path / "go.sum").write_text("\n")

    result = LockfileCheck().run(tmp_path)
    assert "Node" in result.message
    assert "Go" in result.message


def test_node_with_lockfile_passes(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}\n")
    (tmp_path / "package-lock.json").write_text("{}\n")
    assert LockfileCheck().run(tmp_path).status is CheckStatus.PASS


def test_no_manifest_passes(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# x\n")
    assert LockfileCheck().run(tmp_path).status is CheckStatus.PASS


def test_unreadable_directory_is_unverified_not_failed(
    tmp_path: Path, monkeypatch
) -> None:
    def _boom(self):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "iterdir", _boom)
    result = LockfileCheck().run(tmp_path)
    assert result.status is CheckStatus.UNVERIFIED


# ---------------------------------------------------------------------------
# Reporter fidelity
# ---------------------------------------------------------------------------


def test_reporter_preserves_an_error_diagnosis() -> None:
    """Original bug: this rendered as 'README missing'."""
    message = "Error reading repository directory: [Errno 13] Permission denied: '/x'"
    result = CheckResult(
        name="README", status=CheckStatus.FAIL, message=message, score=0, max_score=10
    )
    rendered = format_check_line(result)
    assert message in rendered
    assert rendered != "README missing"


@pytest.mark.parametrize(
    "name,message",
    [
        ("LICENSE", "Error reading repository directory: Permission denied"),
        ("Large files", "Traversal aborted: filesystem loop detected"),
        ("Dependency lockfile", "Repository directory could not be read: boom"),
    ],
)
def test_reporter_never_substitutes_missing(name: str, message: str) -> None:
    result = CheckResult(
        name=name, status=CheckStatus.FAIL, message=message, score=0, max_score=10
    )
    rendered = format_check_line(result)
    assert message in rendered, f"diagnosis lost for {name}"


def test_reporter_renders_name_and_message_without_losing_either() -> None:
    """Formatting may prefix the check name; it may never drop the message."""
    result = CheckResult(
        name="README",
        status=CheckStatus.FAIL,
        message="No README file found",
        score=0,
        max_score=1,
    )
    rendered = format_check_line(result)
    assert "No README file found" in rendered
    assert "README" in rendered


def test_reporter_does_not_repeat_a_name_the_message_already_starts_with() -> None:
    result = CheckResult(
        name="README",
        status=CheckStatus.FAIL,
        message="README file missing",
        score=0,
        max_score=1,
    )
    assert format_check_line(result) == "README file missing"


# ---------------------------------------------------------------------------
# Unicode .env, dual licenses, and symlink repository roots
# ---------------------------------------------------------------------------


def test_env_hygiene_unicode_filenames(tmp_path: Path) -> None:
    _git_repo(tmp_path)
    env_file = tmp_path / ".env.テスト"
    env_file.write_text("SECRET=1\n")
    (tmp_path / ".gitignore").write_text(".env.*\n")

    # Untracked and gitignored should PASS and not warn about unignored
    result = EnvHygieneCheck().run(tmp_path)
    assert result.status is CheckStatus.PASS
    assert ".env.テスト" in result.message

    # When tracked, it should FAIL and display clean unicode name without octal escaping
    subprocess.run(["git", "add", "-f", ".env.テスト"], cwd=tmp_path, check=True)
    result_tracked = EnvHygieneCheck().run(tmp_path)
    assert result_tracked.status is CheckStatus.FAIL
    assert ".env.テスト" in result_tracked.message
    assert "\\343" not in result_tracked.message


@pytest.mark.parametrize(
    "filenames",
    [
        ("LICENSE-MIT", "LICENSE-APACHE"),
        ("LICENSE-MIT.md", "LICENSE-APACHE.txt"),
        ("LICENCE-MIT",),
        ("LICENSE_MIT",),
        ("COPYING-LGPL",),
    ],
)
def test_dual_license_recognition(tmp_path: Path, filenames: tuple[str, ...]) -> None:
    for name in filenames:
        (tmp_path / name).write_text("License text\n")
    result = LicenseCheck().run(tmp_path)
    assert result.status is CheckStatus.PASS
    assert result.score == 10
    assert any(name in result.message for name in filenames)


def test_symlink_repository_root_does_not_crash(tmp_path: Path) -> None:
    real_repo = tmp_path / "real_repo"
    real_repo.mkdir()
    _git_repo(real_repo)

    # Oversized file
    (real_repo / "large.bin").write_bytes(b"x" * 15 * 1024 * 1024)
    # Env file
    (real_repo / ".env").write_text("KEY=val\n")
    (real_repo / ".gitignore").write_text(".env\n")
    # Test file
    test_dir = real_repo / "tests"
    test_dir.mkdir()
    (test_dir / "test_foo.py").write_text("def test_dummy(): pass\n")

    symlink_root = tmp_path / "symlink_root"
    symlink_root.symlink_to(real_repo)

    # LargeFilesCheck
    large_result = LargeFilesCheck().run(symlink_root)
    assert large_result.status is CheckStatus.WARNING
    assert "large.bin" in large_result.message

    # EnvHygieneCheck
    env_result = EnvHygieneCheck().run(symlink_root)
    assert env_result.status is CheckStatus.PASS
    assert ".env" in env_result.message

    # TestsCheck
    tests_result = TestsCheck().run(symlink_root)
    assert tests_result.status is CheckStatus.PASS
