# Contributing to RepoFit

Thank you for your interest in improving RepoFit!

## Development Setup

1. Clone the repository:
   ```bash
   # from a clone of this repository
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install -e ".[dev]"
   ```

## Running Tests & Linting

Before opening a pull request, ensure all tests and quality checks pass:

```bash
# Run tests
python -m pytest

# Run linter
ruff check .

# Check formatting
ruff format --check .
```

## Adding New Checks

To add a new check:

1. Create a new check class in `src/repofit/checks/<check_name>.py` inheriting from `BaseCheck`.
2. Implement the `run(self, repo_path: Path) -> CheckResult` method.
3. Register the check in `src/repofit/checks/__init__.py`.
4. Add unit tests in `tests/test_checks.py` covering the pass, fail and
   unverified paths.

## Pull Requests

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Commit your changes with clear, descriptive commit messages.
3. Push to your branch and open a Pull Request against `main`.
4. Ensure all CI checks pass.
