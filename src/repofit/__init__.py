"""RepoFit.

A deterministic pre-publication repository-hygiene checklist for common
release mistakes.
"""

__version__ = "0.1.0"

from repofit.models import CheckResult, CheckStatus, RepoReport
from repofit.scanner import Scanner

__all__ = ["CheckResult", "CheckStatus", "RepoReport", "Scanner", "__version__"]
