"""Unit tests for RepoFit data models."""

from pathlib import Path

from repofit.models import CheckResult, CheckStatus, RepoReport


def test_check_status_values() -> None:
    """Verify that CheckStatus defines expected string values."""
    assert CheckStatus.PASS == "pass"
    assert CheckStatus.WARNING == "warning"
    assert CheckStatus.FAIL == "fail"


def test_check_result_properties() -> None:
    """Verify CheckResult attributes and passed property."""
    passed_result = CheckResult(
        name="README",
        status=CheckStatus.PASS,
        message="Found README.md",
        score=10,
        max_score=10,
    )
    assert passed_result.passed is True
    assert passed_result.name == "README"
    assert passed_result.score == 10
    assert passed_result.max_score == 10

    failed_result = CheckResult(
        name="LICENSE",
        status=CheckStatus.FAIL,
        message="LICENSE file missing",
        score=0,
        max_score=10,
    )
    assert failed_result.passed is False


def test_repo_report_scoring_all_pass() -> None:
    """Verify RepoReport calculations when all checks pass."""
    results = (
        CheckResult("README", CheckStatus.PASS, "Found", 10, 10),
        CheckResult("LICENSE", CheckStatus.PASS, "Found", 10, 10),
        CheckResult(".gitignore", CheckStatus.PASS, "Found", 10, 10),
        CheckResult("Environment hygiene", CheckStatus.PASS, "Found", 15, 15),
        CheckResult(".env.example", CheckStatus.PASS, "Found", 5, 5),
        CheckResult("Dependency lockfile", CheckStatus.PASS, "Found", 10, 10),
        CheckResult("Tests", CheckStatus.PASS, "Found", 15, 15),
        CheckResult("CI", CheckStatus.PASS, "Found", 15, 15),
        CheckResult("TODO/FIXME", CheckStatus.PASS, "Found", 5, 5),
        CheckResult("Large files", CheckStatus.PASS, "Found", 5, 5),
    )
    report = RepoReport(target_path=Path("/tmp/test"), results=results)

    assert report.total_score == 100
    assert report.max_score == 100
    assert report.health_score == 100


def test_repo_report_scoring_partial_pass() -> None:
    """Verify RepoReport calculations when some checks fail or warn."""
    results = (
        CheckResult("README", CheckStatus.PASS, "Found", 10, 10),
        CheckResult("LICENSE", CheckStatus.PASS, "Found", 10, 10),
        CheckResult(".gitignore", CheckStatus.PASS, "Found", 10, 10),
        CheckResult("Environment hygiene", CheckStatus.PASS, "Found", 15, 15),
        CheckResult(".env.example", CheckStatus.WARNING, ".env.example missing", 0, 5),
        CheckResult("Dependency lockfile", CheckStatus.PASS, "Found", 10, 10),
        CheckResult("Tests", CheckStatus.PASS, "Found", 15, 15),
        CheckResult("CI", CheckStatus.FAIL, "CI configuration missing", 0, 15),
        CheckResult("TODO/FIXME", CheckStatus.WARNING, "17 TODO/FIXME comments", 3, 5),
        CheckResult("Large files", CheckStatus.PASS, "Found", 5, 5),
    )
    report = RepoReport(target_path=Path("/tmp/test"), results=results)

    # 10 + 10 + 10 + 15 + 0 + 10 + 15 + 0 + 3 + 5 = 78
    assert report.total_score == 78
    assert report.max_score == 100
    assert report.health_score == 78


def test_repo_report_scoring_all_fail() -> None:
    """Verify RepoReport calculations when all checks fail."""
    results = (
        CheckResult("README", CheckStatus.FAIL, "Missing", 0, 10),
        CheckResult("LICENSE", CheckStatus.FAIL, "Missing", 0, 10),
        CheckResult(".gitignore", CheckStatus.FAIL, "Missing", 0, 10),
    )
    report = RepoReport(target_path=Path("/tmp/test"), results=results)

    assert report.total_score == 0
    assert report.max_score == 30
    assert report.health_score == 0


def test_repo_report_empty_results() -> None:
    """Verify RepoReport calculations when results are empty."""
    report = RepoReport(target_path=Path("/tmp/test"), results=())

    assert report.total_score == 0
    assert report.max_score == 0
    assert report.health_score == 0
