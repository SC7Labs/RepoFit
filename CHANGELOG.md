# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-09-11

Initial public release of RepoFit.

### Checklist engine

- Typer CLI (`repofit`) with a scanner that runs a fixed list of ten checks over
  a local directory and reports how many passed.
- Result is **`checks passed / checks total`** — a count of this checklist, not a
  measurement of repository quality.
- Four per-check statuses: `pass`, `warning`, `fail`, and `unverified` for a
  check whose evidence could not be gathered.
- Exit codes: `0` every check passed · `1` any failure, warning or unverified
  check · `2` the target could not be scanned.
- Rich terminal reporter that renders each check's own message and never
  substitutes its own diagnosis.

### Checks

Each verifies less than its name suggests, and the README states the limits.

- **README** — a file with a recognised README filename exists.
- **License file** — a file with a recognised license filename exists. The
  contents are not read, so nothing is known about which license it is.
- **.gitignore** — a root `.gitignore` exists.
- **Environment hygiene** — whether `.env`-style files are tracked by Git and
  whether they are gitignored. Filenames only; contents are never read, and this
  is not a secret scanner.
- **.env.example** — a template exists when env files are present.
- **Dependency lockfile** — each detected ecosystem (Node, Python, Rust, Go) is
  evaluated separately under a documented per-ecosystem policy.
- **Test structure** — test directories and filenames exist. Tests are not run.
- **CI configuration** — a CI config file exists. It is not parsed or known to
  have run.
- **TODO/FIXME** — counts task comments in source files.
- **Large files** — working-tree files above a configurable threshold. The check
  scans the working tree, so a listed file is not necessarily tracked by Git.

### Traversal

- Shared walker that skips a fixed list of directory names, never follows
  symlinks, returns files in sorted order, and **reports what it could not
  reach**. A check whose tree was only partly readable reports `unverified`
  rather than passing on data nobody inspected.
- Defensive nesting bound of 64 directories; exceeding it is reported, not
  silently truncated.

### Validation

- Test suite over models, traversal, individual checks, scanner and CLI,
  including regression tests for every defect found during pre-release audits.
- GitHub Actions workflow running lint, format check and tests.
- Validated against several large real-world repositories from a local multi-repository validation corpus:
  - Discovered a TODO/FIXME false-positive class where bare `TODO:` / `FIXME:` patterns counted strings, object keys, types, prose, assertions, and fixture data.
  - Fixed by requiring supported comment syntax and excluding standard fixture/snapshot/cassette directories (`fixtures`, `testdata`, `test_data`, `snapshots`, `__snapshots__`, `cassettes`).
  - Real-world before/after examples:
    - 96 -> 20
    - 17 -> 9
    - 42 -> 29
    - 22 -> 21
  - Existing clean repositories remained unchanged:
    - RepoFit: 5 -> 5
    - PermLint: 0 -> 0
    - MCP TypeScript SDK: 6 -> 6
  - Final verification:
    - 163 tests passed
    - `ruff check .` clean
    - `ruff format --check .` clean
