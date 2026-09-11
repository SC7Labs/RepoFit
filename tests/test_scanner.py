"""Unit and integration tests for the repository scanner engine."""

from pathlib import Path

import pytest

from repofit.checks.gitignore import GitignoreCheck
from repofit.models import CheckStatus
from repofit.scanner import InvalidRepositoryError, Scanner


def create_healthy_repo(repo_path: Path) -> None:
    """Populate a repository directory with compliant files for all 10 checks."""
    (repo_path / "README.md").write_text("# Healthy Project\n")
    (repo_path / "LICENSE").write_text("MIT License\n")
    (repo_path / ".gitignore").write_text("*.pyc\n.venv/\n")
    (repo_path / "pyproject.toml").write_text("[project]\nname='healthy'\n")
    (repo_path / "uv.lock").write_text("version = 1\n")
    (repo_path / "tests").mkdir()
    (repo_path / "tests" / "test_app.py").write_text("def test_ok(): pass\n")
    workflows = repo_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("name: CI\n")
    (repo_path / "src").mkdir()
    (repo_path / "src" / "app.py").write_text("# Clean production code\n")


def test_scanner_all_10_checks_pass(tmp_path: Path) -> None:
    """Verify scanner output when all 10 standard checks pass."""
    create_healthy_repo(tmp_path)

    scanner = Scanner()
    report = scanner.scan(tmp_path)

    assert report.target_path == tmp_path.resolve()
    assert len(report.results) == 10
    assert all(r.status == CheckStatus.PASS for r in report.results)
    assert report.total_score == 100
    assert report.max_score == 100
    assert report.health_score == 100


def test_scanner_partial_checks_fail(tmp_path: Path) -> None:
    """Verify scanner scoring when some checks fail."""
    (tmp_path / "README.md").write_text("# Minimal Project\n")
    (tmp_path / "LICENSE").write_text("MIT\n")
    # Missing .gitignore (10 pts), Tests (15 pts), CI (15 pts)
    # Total score should be 100 - 10 - 15 - 15 = 60

    scanner = Scanner()
    report = scanner.scan(tmp_path)

    results_by_name = {r.name: r for r in report.results}
    assert results_by_name["README"].status == CheckStatus.PASS
    assert results_by_name["License file"].status == CheckStatus.PASS
    assert results_by_name[".gitignore"].status == CheckStatus.FAIL
    assert results_by_name["Test structure"].status == CheckStatus.FAIL
    assert results_by_name["CI configuration"].status == CheckStatus.FAIL
    assert report.health_score == 60


def test_scanner_empty_repository(tmp_path: Path) -> None:
    """Verify scanner output on an empty repository directory."""
    scanner = Scanner()
    report = scanner.scan(tmp_path)

    assert len(report.results) == 10
    results_by_name = {r.name: r for r in report.results}
    assert results_by_name["README"].status == CheckStatus.FAIL
    assert results_by_name["License file"].status == CheckStatus.FAIL
    assert results_by_name[".gitignore"].status == CheckStatus.FAIL
    assert results_by_name["Test structure"].status == CheckStatus.FAIL
    assert results_by_name["CI configuration"].status == CheckStatus.FAIL


def test_scanner_nonexistent_path(tmp_path: Path) -> None:
    """Verify scanner raises InvalidRepositoryError on nonexistent path."""
    nonexistent = tmp_path / "does_not_exist"
    scanner = Scanner()

    with pytest.raises(InvalidRepositoryError, match="Target path does not exist"):
        scanner.scan(nonexistent)


def test_scanner_file_path_error(tmp_path: Path) -> None:
    """Verify scanner raises InvalidRepositoryError when given a file path."""
    file_path = tmp_path / "regular_file.txt"
    file_path.write_text("Hello")
    scanner = Scanner()

    with pytest.raises(InvalidRepositoryError, match="Target path is not a directory"):
        scanner.scan(file_path)


def test_scanner_custom_checks(tmp_path: Path) -> None:
    """Verify scanner accepts a custom list of checks."""
    (tmp_path / ".gitignore").write_text("*.pyc\n")

    scanner = Scanner(checks=[GitignoreCheck()])
    report = scanner.scan(tmp_path)

    assert len(report.results) == 1
    assert report.results[0].name == ".gitignore"
    assert report.health_score == 100
