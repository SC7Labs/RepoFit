"""Unit tests for all 10 individual RepoFit checks."""

import subprocess
from pathlib import Path

import pytest

from repofit.checks.ci import CiCheck
from repofit.checks.env_example import EnvExampleCheck
from repofit.checks.env_hygiene import EnvHygieneCheck
from repofit.checks.gitignore import GitignoreCheck
from repofit.checks.large_files import LargeFilesCheck
from repofit.checks.license import LicenseCheck
from repofit.checks.lockfile import LockfileCheck
from repofit.checks.readme import ReadmeCheck
from repofit.checks.tests_check import TestsCheck
from repofit.checks.todos import TodosCheck
from repofit.models import CheckStatus


class TestReadmeCheck:
    """Tests for README check."""

    def test_missing_readme(self, tmp_path: Path) -> None:
        check = ReadmeCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.FAIL
        assert result.score == 0
        assert result.max_score == 10

    @pytest.mark.parametrize(
        "filename",
        [
            "README.md",
            "README.rst",
            "README.txt",
            "README",
            "readme.md",
            "Readme.md",
            "README.markdown",
        ],
    )
    def test_readme_variants(self, tmp_path: Path, filename: str) -> None:
        (tmp_path / filename).write_text("# Test Project\n")
        check = ReadmeCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 10

    def test_readme_as_directory_fails(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").mkdir()
        check = ReadmeCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.FAIL


class TestLicenseCheck:
    """Tests for LICENSE check."""

    def test_missing_license(self, tmp_path: Path) -> None:
        check = LicenseCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.FAIL
        assert result.score == 0

    @pytest.mark.parametrize(
        "filename",
        [
            "LICENSE",
            "LICENSE.md",
            "LICENSE.txt",
            "LICENSE.rst",
            "license",
            "COPYING",
            "UNLICENSE",
        ],
    )
    def test_license_variants(self, tmp_path: Path, filename: str) -> None:
        (tmp_path / filename).write_text("MIT License\n")
        check = LicenseCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 10

    def test_license_as_directory_fails(self, tmp_path: Path) -> None:
        (tmp_path / "LICENSE").mkdir()
        check = LicenseCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.FAIL


class TestGitignoreCheck:
    """Tests for .gitignore check."""

    def test_missing_gitignore(self, tmp_path: Path) -> None:
        check = GitignoreCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.FAIL
        assert result.score == 0

    def test_found_gitignore(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("*.pyc\n")
        check = GitignoreCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 10

    def test_gitignore_as_directory_fails(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").mkdir()
        check = GitignoreCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.FAIL


class TestEnvHygieneCheck:
    """Tests for Environment and secrets hygiene check."""

    def test_no_env_files(self, tmp_path: Path) -> None:
        check = EnvHygieneCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 15

    def test_template_only_passes(self, tmp_path: Path) -> None:
        (tmp_path / ".env.example").write_text("API_KEY=\n")
        check = EnvHygieneCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 15

    def test_non_git_repo_with_env_is_unverified(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("SECRET=12345\n")
        check = EnvHygieneCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.UNVERIFIED
        assert "not a git repository" in result.message.lower()

    def test_tracked_env_fails(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Tester"], cwd=tmp_path, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
        )
        (tmp_path / ".env").write_text("SECRET=12345\n")
        subprocess.run(["git", "add", ".env"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-m", "commit env"], cwd=tmp_path, check=True)

        check = EnvHygieneCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.FAIL
        assert result.score == 0
        assert "tracked" in result.message.lower()

    def test_untracked_env_passes_in_git(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        (tmp_path / ".gitignore").write_text(".env\n")
        (tmp_path / ".env").write_text("SECRET=12345\n")

        check = EnvHygieneCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 15


class TestEnvExampleCheck:
    """Tests for .env.example template check."""

    def test_no_env_configuration_passes_na(self, tmp_path: Path) -> None:
        check = EnvExampleCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 5

    def test_env_used_and_example_exists(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("SECRET=123\n")
        (tmp_path / ".env.example").write_text("SECRET=\n")
        check = EnvExampleCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 5
        assert ".env.example" in result.message

    @pytest.mark.parametrize(
        "template_name", [".env.sample", ".env.template", ".env.dist"]
    )
    def test_env_template_variants(self, tmp_path: Path, template_name: str) -> None:
        (tmp_path / ".env").write_text("SECRET=123\n")
        (tmp_path / template_name).write_text("SECRET=\n")
        check = EnvExampleCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert template_name in result.message

    def test_env_used_without_example_warns(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("SECRET=123\n")
        check = EnvExampleCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.WARNING
        assert result.score == 0
        assert ".env.example missing" in result.message


class TestLockfileCheck:
    """Tests for dependency lockfile check."""

    def test_no_manifest_passes_na(self, tmp_path: Path) -> None:
        check = LockfileCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 10

    def test_python_with_uv_lock(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='app'\n")
        (tmp_path / "uv.lock").write_text("version = 1\n")
        check = LockfileCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert "uv.lock" in result.message

    def test_python_manifest_without_lockfile_passes(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='lib'\n")
        check = LockfileCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 10

    def test_node_with_package_lock(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"name": "app"}\n')
        (tmp_path / "package-lock.json").write_text('{"name": "app"}\n')
        check = LockfileCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert "package-lock.json" in result.message

    def test_node_without_lockfile_warns(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"name": "app"}\n')
        check = LockfileCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.WARNING
        assert result.score == 0

    def test_rust_with_cargo_lock(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text('[package]\nname="app"\n')
        (tmp_path / "Cargo.lock").write_text("version = 3\n")
        check = LockfileCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert "Cargo.lock" in result.message


class TestTestsCheck:
    """Tests for test suite presence check."""

    def test_empty_tests_directory_fails(self, tmp_path: Path) -> None:
        """Regression test: An empty tests/ directory must FAIL."""
        (tmp_path / "tests").mkdir()
        check = TestsCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.FAIL
        assert result.score == 0
        assert "no test structure" in result.message.lower()

    def test_tests_directory_with_unrelated_files_fails(self, tmp_path: Path) -> None:
        """Regression test: tests/ directory with only unrelated files must FAIL."""
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "notes.txt").write_text("TODO later\n")
        (tmp_path / "tests" / "data.csv").write_text("a,b,c\n")
        check = TestsCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.FAIL
        assert result.score == 0

    def test_tests_directory_with_valid_test_passes(self, tmp_path: Path) -> None:
        """Verify tests/ with valid test file passes."""
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_app.py").write_text("def test_ok(): pass\n")
        check = TestsCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 15

    @pytest.mark.parametrize(
        "test_filename",
        [
            "test_sample.py",
            "sample_test.py",
            "conftest.py",
            "app.test.js",
            "app.spec.ts",
            "main_test.go",
            "lib_test.rs",
            "UserTest.php",
            "AppTest.java",
        ],
    )
    def test_test_filename_patterns(self, tmp_path: Path, test_filename: str) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / test_filename).write_text("// test\n")
        check = TestsCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 15

    def test_no_tests_fails(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('hello')\n")
        check = TestsCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.FAIL
        assert result.score == 0

    def test_fake_tests_in_ignored_dirs_fails(self, tmp_path: Path) -> None:
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "foo.test.js").write_text("// test\n")
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "test_venv.py").write_text("# test\n")
        check = TestsCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.FAIL


class TestCiCheck:
    """Tests for CI configuration check."""

    def test_empty_workflows_dir_fails(self, tmp_path: Path) -> None:
        """Regression test: Empty .github/workflows directory must FAIL."""
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        check = CiCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.FAIL
        assert result.score == 0

    def test_workflows_with_non_yaml_fails(self, tmp_path: Path) -> None:
        """Regression test: .github/workflows with only non-yaml files must FAIL."""
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "README.md").write_text("Workflows go here")
        check = CiCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.FAIL
        assert result.score == 0

    def test_github_actions_passes(self, tmp_path: Path) -> None:
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("name: CI\n")
        check = CiCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 15
        assert "GitHub Actions" in result.message

    def test_gitlab_ci_passes(self, tmp_path: Path) -> None:
        (tmp_path / ".gitlab-ci.yml").write_text("stages:\n  - test\n")
        check = CiCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 15

    def test_circleci_passes(self, tmp_path: Path) -> None:
        circleci = tmp_path / ".circleci"
        circleci.mkdir()
        (circleci / "config.yml").write_text("version: 2.1\n")
        check = CiCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS

    def test_no_ci_fails(self, tmp_path: Path) -> None:
        check = CiCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.FAIL
        assert result.score == 0


class TestTodosCheck:
    """Tests for actionable task comments check."""

    def test_zero_todos_passes(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('clean code')\n")
        check = TodosCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 5

    def test_low_todos_passes(self, tmp_path: Path) -> None:
        tag = "TO" + "DO"
        (tmp_path / "src").mkdir()
        content = "\n".join(f"# {tag}: task {i}" for i in range(5))
        (tmp_path / "src" / "app.py").write_text(content)
        check = TodosCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 5
        assert "5 TODO/FIXME" in result.message

    def test_warning_todos(self, tmp_path: Path) -> None:
        tag = "FIX" + "ME"
        (tmp_path / "src").mkdir()
        content = "\n".join(f"# {tag}: fix {i}" for i in range(20))
        (tmp_path / "src" / "app.py").write_text(content)
        check = TodosCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.WARNING
        assert result.score == 3
        assert "20 TODO/FIXME" in result.message

    def test_fail_todos(self, tmp_path: Path) -> None:
        tag = "TO" + "DO"
        (tmp_path / "src").mkdir()
        content = "\n".join(f"# {tag}: item {i}" for i in range(35))
        (tmp_path / "src" / "app.py").write_text(content)
        check = TodosCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.FAIL
        assert result.score == 0
        assert "35 TODO/FIXME" in result.message

    def test_todos_in_ignored_dirs_not_counted(self, tmp_path: Path) -> None:
        tag = "TO" + "DO"
        (tmp_path / "node_modules").mkdir()
        content = "\n".join(f"# {tag}: {i}" for i in range(50))
        (tmp_path / "node_modules" / "vendor.js").write_text(content)
        check = TodosCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 5

    def test_strings_and_code_containing_todo_not_counted(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "code.py").write_text(
            'msg = "TODO: fix this"\nif line.startswith("todo:"):\n    pass\n'
        )
        (tmp_path / "src" / "types.ts").write_text(
            "const obj = { todo: 'checklist' };\ntype Item = { todo: string };\n"
        )
        check = TodosCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 5
        assert "No TODO/FIXME" in result.message

    def test_test_fixtures_directory_not_counted(self, tmp_path: Path) -> None:
        tag = "TO" + "DO"
        fixtures_dir = tmp_path / "tests" / "fixtures"
        fixtures_dir.mkdir(parents=True)
        (fixtures_dir / "gold.txt").write_text(
            f"# {tag}: in fixture\n{tag}: in fixture\n" * 20
        )
        testdata_dir = tmp_path / "testdata"
        testdata_dir.mkdir()
        (testdata_dir / "sample.go").write_text(f"// {tag}: in testdata\n")
        snapshots_dir = tmp_path / "__snapshots__"
        snapshots_dir.mkdir()
        (snapshots_dir / "test.snap").write_text(f"# {tag}: in snapshot\n")

        # Genuine developer TODO in test source should still be counted
        (tmp_path / "tests" / "test_main.py").write_text(f"# {tag}: test assertion\n")

        check = TodosCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 5
        assert "1 TODO/FIXME comments" in result.message

    def test_documentation_mentioning_todo_not_counted(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "# Title\n"
            "| **TODO/FIXME** | Counts TODO/FIXME comments |\n"
            "TODO: describe usage\n"
            "El instalador se encarga de todo:\n"
        )
        check = TodosCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 5
        assert "No TODO/FIXME" in result.message

    def test_supported_comment_syntaxes_counted(self, tmp_path: Path) -> None:
        todo = "TO" + "DO"
        fixme = "FIX" + "ME"
        (tmp_path / "src").mkdir()
        content = (
            f"# {todo}: python\n"
            f"// {todo}: js\n"
            f"/* {todo}: block */\n"
            f" * {todo}: mid-block\n"
            f"<!-- {todo}: html -->\n"
            f"-- {todo}: sql\n"
            f"; {todo}: ini\n"
            f"// {todo}(alice): tagged\n"
            f"// {fixme}: fixme\n"
            f"{{/* {todo}: jsx */}}\n"
        )
        (tmp_path / "src" / "all_comments.txt").write_text(content)
        check = TodosCheck()
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 5
        assert "10 TODO/FIXME comments" in result.message


class TestLargeFilesCheck:
    """Tests for large files check."""

    def test_no_large_files_passes(self, tmp_path: Path) -> None:
        (tmp_path / "small.txt").write_text("hello")
        check = LargeFilesCheck(threshold_bytes=1000)
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 5

    def test_large_file_warns(self, tmp_path: Path) -> None:
        (tmp_path / "large.bin").write_bytes(b"x" * 2000)
        check = LargeFilesCheck(threshold_bytes=1000)
        result = check.run(tmp_path)
        assert result.status == CheckStatus.WARNING
        assert result.score == 0
        assert "large.bin" in result.message

    def test_large_file_in_ignored_dir_ignored(self, tmp_path: Path) -> None:
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "large.bin").write_bytes(b"x" * 2000)
        check = LargeFilesCheck(threshold_bytes=1000)
        result = check.run(tmp_path)
        assert result.status == CheckStatus.PASS
        assert result.score == 5
