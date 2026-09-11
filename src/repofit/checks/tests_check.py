"""Check for the presence of a test suite in the repository."""

from pathlib import Path

from repofit.checks.base import BaseCheck
from repofit.filesystem import walk_repository
from repofit.models import CheckResult, CheckStatus

TEST_DIR_NAMES: frozenset[str] = frozenset(
    {"tests", "test", "spec", "specs", "__tests__"}
)

TEST_FILE_EXTENSIONS: tuple[str, ...] = (
    ".test.js",
    ".test.ts",
    ".test.jsx",
    ".test.tsx",
    ".test.mjs",
    ".test.cjs",
    ".spec.js",
    ".spec.ts",
    ".spec.jsx",
    ".spec.tsx",
    ".spec.mjs",
    ".spec.cjs",
)


#: Files that mark a directory as a package rather than contain tests.
PACKAGE_MARKER_FILENAMES: frozenset[str] = frozenset({"__init__.py"})


def is_test_file(path: Path, repo_path: Path) -> bool:
    """Whether a file counts as evidence of test structure.

    Presence only. Nothing here judges whether the tests are any good — this
    reports that a test layout exists, not that it works.
    """
    name = path.name.lower()

    # A package marker is not a test. `tests/__init__.py` alone used to satisfy
    # this check and report "Found test file __init__.py".
    if name in PACKAGE_MARKER_FILENAMES:
        return False

    # Python test files
    if name.endswith(".py"):
        if (
            name.startswith("test_")
            or name.endswith("_test.py")
            or name == "conftest.py"
        ):
            return True

    # JavaScript / TypeScript test files
    if any(name.endswith(ext) for ext in TEST_FILE_EXTENSIONS):
        return True

    # Go and Rust test files
    if (
        name.endswith("_test.go")
        or name.endswith("_test.rs")
        or (name.startswith("test_") and name.endswith(".rs"))
    ):
        return True

    # Ruby / PHP / Java test files
    if (
        name.endswith("_test.rb")
        or name.endswith("_spec.rb")
        or (name.startswith("test_") and name.endswith(".rb"))
    ):
        return True
    if name.endswith("test.php") or (
        name.startswith("test_") and name.endswith(".php")
    ):
        return True
    if (
        name.endswith("test.java")
        or name.endswith("tests.java")
        or name.endswith("testcase.java")
        or name.endswith("test.kt")
    ):
        return True

    # C / C++ test files
    if name.startswith("test_") and name.endswith((".c", ".cpp", ".cc", ".cxx")):
        return True
    if name.endswith(("_test.c", "_test.cpp", "_test.cc", "_test.cxx")):
        return True

    # Any source file within a recognized test directory
    try:
        try:
            rel_parts = path.relative_to(repo_path).parts[:-1]
        except ValueError:
            rel_parts = path.resolve().relative_to(repo_path.resolve()).parts[:-1]
        in_test_dir = any(part.lower() in TEST_DIR_NAMES for part in rel_parts)
        if in_test_dir and path.suffix.lower() in (
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".java",
            ".kt",
            ".c",
            ".cpp",
        ):
            # Exclude documentation or config inside test dir
            if not name.startswith(("readme", "license", "setup", "config")):
                return True
    except ValueError:
        pass

    return False


class TestsCheck(BaseCheck):
    """Checks whether the repository has a recognisable test layout.

    Detects test directories and filenames. It does not run the tests, count
    them, or judge whether they assert anything."""

    name = "Test structure"
    max_score = 15

    def run(self, repo_path: Path) -> CheckResult:
        walk = walk_repository(repo_path)
        if not walk.is_complete:
            return self.unverified_traversal(walk)

        for file_path in walk.files:
            if is_test_file(file_path, repo_path):
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.PASS,
                    message=f"Found test file {file_path.name}",
                    score=self.max_score,
                    max_score=self.max_score,
                )

        return CheckResult(
            name=self.name,
            status=CheckStatus.FAIL,
            message="No test structure detected",
            score=0,
            max_score=self.max_score,
        )
