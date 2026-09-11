"""Unit and integration tests for the RepoFit CLI."""

from pathlib import Path

from typer.testing import CliRunner

from repofit import __version__
from repofit.cli import app
from tests.test_scanner import create_healthy_repo

runner = CliRunner(env={"COLUMNS": "200"})


def test_cli_version_long_flag() -> None:
    """Verify repofit --version outputs correct version string and exits with 0."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"RepoFit {__version__}" in result.stdout


def test_cli_version_short_flag() -> None:
    """Verify repofit -v outputs correct version string and exits with 0."""
    result = runner.invoke(app, ["-v"])
    assert result.exit_code == 0
    assert f"RepoFit {__version__}" in result.stdout


def test_cli_scan_all_pass(tmp_path: Path) -> None:
    """Verify CLI audit on a fully compliant repository."""
    create_healthy_repo(tmp_path)

    result = runner.invoke(app, [str(tmp_path)])
    assert result.exit_code == 0
    assert f"RepoFit {__version__}" in result.stdout
    assert f"Scanning: {tmp_path.resolve()}" in result.stdout
    assert "✓ README" in result.stdout
    assert "✓ License file" in result.stdout
    assert "✓ .gitignore" in result.stdout
    assert "✓ Environment hygiene" in result.stdout
    assert "✓ .env.example" in result.stdout
    assert "✓ Dependency lockfile" in result.stdout
    assert "✓ Test structure" in result.stdout
    assert "✓ CI configuration" in result.stdout
    assert "✓ TODO/FIXME" in result.stdout
    assert "✓ Large files" in result.stdout
    assert "Readiness checklist: 10/10 checks passed" in result.stdout


def test_cli_scan_partial_fail(tmp_path: Path) -> None:
    """A repository with failing checks must not exit 0.

    Regression: it previously reported six failures and still exited 0, which
    made the CLI useless as a CI gate.
    """
    (tmp_path / "README.md").write_text("# My Project\n")

    result = runner.invoke(app, [str(tmp_path)])
    assert result.exit_code == 1
    assert "✓ README" in result.stdout
    assert "✗ License file" in result.stdout
    assert "✗ .gitignore" in result.stdout
    assert "✗ CI configuration" in result.stdout


def test_cli_scan_default_current_directory(tmp_path: Path, monkeypatch) -> None:
    """Verify running CLI with no arguments defaults to scanning current directory."""
    create_healthy_repo(tmp_path)

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert f"Scanning: {tmp_path.resolve()}" in result.stdout
    assert "Readiness checklist: 10/10 checks passed" in result.stdout


def test_cli_nonexistent_path(tmp_path: Path) -> None:
    """Verify CLI behavior when given a nonexistent path."""
    nonexistent = tmp_path / "does_not_exist"
    result = runner.invoke(app, [str(nonexistent)])
    assert result.exit_code == 2
    assert "Error: Target path does not exist" in result.output


def test_cli_file_instead_of_dir(tmp_path: Path) -> None:
    """Verify CLI behavior when given a path to a file instead of a directory."""
    file_path = tmp_path / "single_file.txt"
    file_path.write_text("hello")
    result = runner.invoke(app, [str(file_path)])
    assert result.exit_code == 2
    assert "Error: Target path is not a directory" in result.output
