"""Unit tests for the filesystem utility functions."""

from pathlib import Path

from repofit.filesystem import (
    is_binary_file,
    is_ignored_directory,
    walk_repository_files,
)


def test_is_ignored_directory() -> None:
    """Verify recognized ignored directories."""
    assert is_ignored_directory(".git") is True
    assert is_ignored_directory(".venv") is True
    assert is_ignored_directory("node_modules") is True
    assert is_ignored_directory("__pycache__") is True
    assert is_ignored_directory("dist") is True
    assert is_ignored_directory("mypackage.egg-info") is True
    assert is_ignored_directory("src") is False
    assert is_ignored_directory("tests") is False


def test_walk_repository_files(tmp_path: Path) -> None:
    """Verify traversal includes regular files and skips ignored dirs and symlinks."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("console.log('ignored');\n")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib.py").write_text("# ignored\n")

    files = list(walk_repository_files(tmp_path))
    file_names = [f.name for f in files]

    assert "main.py" in file_names
    assert "pkg.js" not in file_names
    assert "lib.py" not in file_names


def test_walk_repository_files_skips_symlinks(tmp_path: Path) -> None:
    """Verify symlinks are not traversed."""
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "target.py").write_text("target")

    link_dir = tmp_path / "linked"
    try:
        link_dir.symlink_to(real_dir, target_is_directory=True)
    except OSError:
        pass  # In case symlinks are restricted in the environment

    files = list(walk_repository_files(tmp_path))
    file_paths = [str(f.relative_to(tmp_path)) for f in files]
    assert "real/target.py" in file_paths
    assert "linked/target.py" not in file_paths


def test_walk_repository_files_skips_symlink_pointing_outside(tmp_path: Path) -> None:
    """Verify symlinked files pointing outside repository root are skipped."""
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("secret content")

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    symlink_in_repo = repo_dir / "symlink_secret.txt"
    try:
        symlink_in_repo.symlink_to(outside_file)
    except OSError:
        pass

    files = list(walk_repository_files(repo_dir))
    assert outside_file not in files
    assert symlink_in_repo not in files


def test_is_binary_file(tmp_path: Path) -> None:
    """Verify text vs binary file detection."""
    text_file = tmp_path / "sample.txt"
    text_file.write_text("Hello, world!")
    assert is_binary_file(text_file) is False

    binary_file = tmp_path / "sample.bin"
    binary_file.write_bytes(b"GIF89a\x00\x00\x00\x00")
    assert is_binary_file(binary_file) is True
