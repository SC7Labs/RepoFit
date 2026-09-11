"""Check for dependency manifests and corresponding lockfiles."""

from dataclasses import dataclass
from pathlib import Path

from repofit.checks.base import BaseCheck
from repofit.filesystem import sorted_entries
from repofit.models import CheckResult, CheckStatus

# Ecosystem definitions: manifest files and corresponding lockfile candidates
PYTHON_MANIFESTS: frozenset[str] = frozenset(
    {"pyproject.toml", "requirements.txt", "pipfile", "setup.py", "setup.cfg"}
)
PYTHON_LOCKFILES: frozenset[str] = frozenset(
    {"uv.lock", "poetry.lock", "pipfile.lock", "pdm.lock", "requirements.lock"}
)

NODE_MANIFESTS: frozenset[str] = frozenset({"package.json"})
NODE_LOCKFILES: frozenset[str] = frozenset(
    {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "bun.lock"}
)

RUST_MANIFESTS: frozenset[str] = frozenset({"cargo.toml"})
RUST_LOCKFILES: frozenset[str] = frozenset({"cargo.lock"})

GO_MANIFESTS: frozenset[str] = frozenset({"go.mod"})
GO_LOCKFILES: frozenset[str] = frozenset({"go.sum"})


@dataclass(frozen=True, slots=True)
class Ecosystem:
    """One dependency ecosystem and what a pinned dependency set looks like in it."""

    label: str
    manifests: frozenset[str]
    lockfiles: frozenset[str]
    lock_expected: bool
    """Whether a missing lockfile is worth reporting.

    Application ecosystems commit a lockfile; library ecosystems often and
    legitimately do not. Rust is the awkward one — a binary crate commits
    `Cargo.lock`, a library crate historically did not — so a missing one is
    reported as informational rather than as a finding.
    """


ECOSYSTEMS: tuple[Ecosystem, ...] = (
    Ecosystem("Node", NODE_MANIFESTS, NODE_LOCKFILES, lock_expected=True),
    Ecosystem("Python", PYTHON_MANIFESTS, PYTHON_LOCKFILES, lock_expected=False),
    Ecosystem("Rust", RUST_MANIFESTS, RUST_LOCKFILES, lock_expected=False),
    Ecosystem("Go", GO_MANIFESTS, GO_LOCKFILES, lock_expected=False),
)


class LockfileCheck(BaseCheck):
    """Checks each detected ecosystem for its own lockfile.

    Evaluated per ecosystem rather than repository-wide. The original version
    accepted any lockfile from any ecosystem, so a repository with
    `package.json`, `Cargo.toml` and `Cargo.lock` passed on the strength of the
    Rust lockfile while Node had none.
    """

    name = "Dependency lockfile"
    max_score = 10

    def run(self, repo_path: Path) -> CheckResult:
        try:
            root_files = {
                entry.name.lower(): entry.name
                for entry in sorted_entries(repo_path)
                if entry.is_file()
            }
        except OSError as err:
            return CheckResult(
                name=self.name,
                status=CheckStatus.UNVERIFIED,
                message=f"Repository directory could not be read: {err}",
                score=0,
                max_score=self.max_score,
            )

        detected: list[tuple[Ecosystem, str | None]] = []
        for ecosystem in ECOSYSTEMS:
            if not any(m in root_files for m in ecosystem.manifests):
                continue
            found = next(
                (
                    root_files[lock]
                    for lock in sorted(ecosystem.lockfiles)
                    if lock in root_files
                ),
                None,
            )
            detected.append((ecosystem, found))

        if not detected:
            return CheckResult(
                name=self.name,
                status=CheckStatus.PASS,
                message="No dependency manifest detected",
                score=self.max_score,
                max_score=self.max_score,
            )

        missing_expected = [
            e.label for e, lock in detected if lock is None and e.lock_expected
        ]
        missing_optional = [
            e.label for e, lock in detected if lock is None and not e.lock_expected
        ]
        satisfied = [f"{e.label} ({lock})" for e, lock in detected if lock is not None]

        if missing_expected:
            parts = [f"{', '.join(missing_expected)} has no lockfile"]
            if satisfied:
                parts.append(f"found {'; '.join(satisfied)}")
            return CheckResult(
                name=self.name,
                status=CheckStatus.WARNING,
                message="; ".join(parts),
                score=0,
                max_score=self.max_score,
            )

        if satisfied:
            message = f"Lockfile present for {'; '.join(satisfied)}"
            if missing_optional:
                message += f" (optional for {', '.join(missing_optional)})"
            return CheckResult(
                name=self.name,
                status=CheckStatus.PASS,
                message=message,
                score=self.max_score,
                max_score=self.max_score,
            )

        return CheckResult(
            name=self.name,
            status=CheckStatus.PASS,
            message=f"Lockfile optional for {', '.join(missing_optional)}",
            score=self.max_score,
            max_score=self.max_score,
        )
