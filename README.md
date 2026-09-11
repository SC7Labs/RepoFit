# RepoFit

**Is your repository fit to ship?**

> A deterministic pre-publication repository-hygiene checklist for common
> release mistakes.

*Status: `0.1.0` release candidate — not yet published anywhere.*

---

## Quick Start

Audit the current repository:

```bash
repofit .
```

### Example Output

```text
RepoFit 0.1.0
Scanning: /path/to/project

✓ README: Found README.md
✓ License file: Found LICENSE
✓ .gitignore: Found .gitignore
✓ Environment hygiene: Untracked and gitignored: .env
✓ .env.example: Found .env.example
✓ Dependency lockfile: Lockfile present for Python (uv.lock)
✓ Test structure: Found test file test_app.py
✓ CI configuration: Found GitHub Actions workflows (ci.yml)
✓ TODO/FIXME: No TODO/FIXME comments
✓ Large files: No oversized files

Readiness checklist: 10/10 checks passed
```

---

## Overview

Shipping an open-source project is a checklist, and checklists should be
executable. **RepoFit** runs a fixed list of ten deterministic checks over a
local repository directory and reports how many passed.

The score is `checks passed / checks total`. It measures **this checklist**, not
repository quality: a project can satisfy all ten and still be a bad project, and
a good project can legitimately fail several. Read it as a pre-flight list, not
as a grade.

What it is not: a security scanner, a secret scanner, a linter, or a judgement
about whether your tests are any good. Every check below states exactly what it
inspects.

---

## Checks Suite (10 Checks)

Each row says what is actually inspected — deliberately narrower than the check
name might suggest.

| Check | What it verifies | What it does **not** verify |
|---|---|---|
| **README** | A file named `README` with a recognised extension exists | That it says anything useful |
| **License file** | A file with a recognised license filename exists | Which license it is, or that it is valid |
| **.gitignore** | A root `.gitignore` exists | That it ignores the right things |
| **Environment hygiene** | Whether `.env`-style files are tracked by Git, and whether they are gitignored | Anything about file *contents*; this is not a secret scanner |
| **.env.example** | A template file exists when env files are present | That the template is complete |
| **Dependency lockfile** | Each detected ecosystem is checked for its own dependency-state file, under the per-ecosystem policy below | That the pinned versions are current or safe |
| **Test structure** | Test directories and filenames exist | That the tests run, pass, or assert anything |
| **CI configuration** | A CI config file exists | That the workflow is valid, or has ever run |
| **TODO/FIXME** | Counts `TODO`/`FIXME` comments in source files | Whether any of them matter |
| **Large files** | Files over 10 MB in the **working tree** | Whether Git tracks them, or would commit them |

### Dependency lockfile policy

Ecosystems are detected by manifest and evaluated **separately** — a `Cargo.lock`
does not satisfy a Node project. They are not treated identically, because the
conventions genuinely differ:

| Ecosystem | Manifests | Dependency-state file | Missing file |
|---|---|---|---|
| Node | `package.json` | `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`, `bun.lock` | **warning** — committing a lockfile is near-universal |
| Python | `pyproject.toml`, `requirements.txt`, `Pipfile`, `setup.py`, `setup.cfg` | `uv.lock`, `poetry.lock`, `Pipfile.lock`, `pdm.lock`, `requirements.lock` | pass — libraries routinely and correctly omit one |
| Rust | `Cargo.toml` | `Cargo.lock` | pass — binaries commit it, libraries historically do not |
| Go | `go.mod` | `go.sum` | pass |

For a repository with several ecosystems the result is aggregated: it warns if
**any** ecosystem whose lockfile is expected lacks one, and the message names
every ecosystem it found — for example
`Node has no lockfile; found Rust (Cargo.lock)`.

Only Node currently produces a warning. That is a judgement about convention,
not a rule about correctness, and it is the whole of the policy.

### Statuses

| Status | Meaning |
|---|---|
| `✓` pass | The check ran and was satisfied |
| `!` warning | The check ran and found something worth looking at |
| `✗` fail | The check ran and was not satisfied |
| `?` unverified | The check could not run — for example, Git was unavailable |

`unverified` exists so that a check which could not gather its evidence is never
reported as a pass. That distinction was a real bug: a failed `git` invocation
used to render as "environment files are properly untracked".

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Every check passed |
| `1` | At least one check failed, warned, or could not be verified |
| `2` | The target could not be scanned (missing path, not a directory) |

A warning or an unverified check exits `1`: a checklist that exits clean while
telling you it could not check something is useless as a CI gate.

---

## Incomplete traversal

A check cannot pass on a tree it could not read. If any directory cannot be
listed, or nesting exceeds the defensive depth bound of 64, the traversal says
so and the checks that depend on it report `unverified` rather than passing:

```text
? Environment hygiene: Repository could not be fully traversed (1 directory could not be read)
? Large files: Repository could not be fully traversed (1 directory could not be read)
```

This was a real defect: an unreadable subtree containing a `.env` and an 11 MB
file previously produced "No .env-style files present" and "No oversized files".

File order is sorted at the point of traversal, so the same tree produces
byte-identical output between runs.

---

## Limitations

- **Filename and structure only.** No check reads file contents to judge them.
  RepoFit does not know whether your license is valid, your tests assert
  anything, or your CI has ever passed.
- **Not a secret scanner.** The environment check looks at `.env`-style
  filenames and their Git status. It does not search for credentials.
- **Large files are working-tree based.** A listed file is not necessarily
  tracked by Git or about to be committed.
- **The score is this checklist.** `N/N checks passed` measures the ten checks
  below and nothing else. A repository can pass all ten and still be poor, or
  fail several for good reasons.
- **Git is required for the environment check.** Without it, that check reports
  `unverified` rather than guessing.
- **Depth bound of 64 directories.** Deeper trees are reported, not silently
  truncated.

---

## Installation

### Development Installation

Clone the repository and install it locally in editable mode:

```bash
# from a clone of this repository

# Using uv (recommended)
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Or using standard pip
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Usage

Audit the current working directory:

```bash
repofit .
```

Audit a specific project directory:

```bash
repofit /path/to/project
```

Check the installed version:

```bash
repofit --version
```

### Incomplete Repository Example

When checks fail or warn:

```text
RepoFit 0.1.0
Scanning: /path/to/incomplete-project

✓ README: Found README.md
✓ License file: Found LICENSE
✓ .gitignore: Found .gitignore
? Environment hygiene: .env present, but Git status is unknown (not a Git repository, or git is not installed)
! .env.example: .env.example missing
! Dependency lockfile: Node has no lockfile; found Rust (Cargo.lock)
✓ Test structure: Found test file test_app.py
✗ CI configuration: No CI configuration file found
! TODO/FIXME: 17 TODO/FIXME comments
✓ Large files: No oversized files

Readiness checklist: 5/10 checks passed
1 check(s) could not be verified.
```

---

## Development & Testing

Run the test suite with `pytest`:

```bash
python -m pytest
```

Check code style and formatting with `ruff`:

```bash
ruff check .
ruff format --check .
```

To auto-format code:

```bash
ruff format .
```

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on local development, testing, and submitting pull requests.

---

## License

This project is licensed under the [MIT License](LICENSE).
