"""The market seal: no French returns dated on or after SEAL_DATE until pap-v1 exists."""

import subprocess
from datetime import date
from pathlib import Path

from aideleg.config import PAP_TAG, ROOT, SEAL_DATE


class SealedPeriodError(Exception):
    """Raised when sealed-period market data is requested before the PAP is frozen."""


def pap_frozen(repo: Path = ROOT) -> bool:
    """True iff the git tag `pap-v1` exists in `repo`. Any git failure counts as not frozen."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "tag", "--list", PAP_TAG],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return False
    return bool(out.strip())


def assert_unsealed(end: date, repo: Path = ROOT) -> None:
    if end >= SEAL_DATE and not pap_frozen(repo):
        raise SealedPeriodError(
            f"market data through {end} requested, but dates on or after {SEAL_DATE} "
            f"are sealed until the git tag {PAP_TAG} exists"
        )
