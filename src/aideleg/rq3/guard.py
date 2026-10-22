"""Post-seal market reads need the committed confirmatory record (PAP section 0.5, P-H5 step 5).

The single confirmatory run is Task 1's; nothing else on this branch may read market data
until its result and attempt marker are committed, and unmodified, at HEAD.
"""

import subprocess
from pathlib import Path

from aideleg.config import ROOT

CONFIRMATORY = ("docs/results/confirmatory_h5.md", "docs/results/confirmatory_h5.attempt")
RESULT_HEADING = "# Confirmatory test of H5 and H5b"


class ConfirmatoryNotRecorded(RuntimeError):
    """Raised when a market read is requested without the committed confirmatory record."""


def _git_ok(repo: Path, *args: str) -> bool:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                              check=False).returncode == 0
    except OSError:
        return False


def assert_confirmatory_recorded(repo: Path = ROOT) -> None:
    for rel in CONFIRMATORY:
        # tracked, and present in HEAD (a staged-only file is not a record)
        if not (_git_ok(repo, "ls-files", "--error-unmatch", rel)
                and _git_ok(repo, "cat-file", "-e", f"HEAD:{rel}")):
            raise ConfirmatoryNotRecorded(
                f"{rel} is not committed in {repo}: market data are not read until the "
                "confirmatory H5 result and its attempt marker are committed")
    for rel in CONFIRMATORY:
        if not _git_ok(repo, "diff", "--quiet", "HEAD", "--", rel):
            raise ConfirmatoryNotRecorded(
                f"{rel} is modified against HEAD: the confirmatory record is committed unedited")
    path = repo / CONFIRMATORY[0]
    with path.open(encoding="utf-8") as fh:
        first = fh.readline().rstrip("\r\n")
    if first != RESULT_HEADING:
        kind = "an attempt record" if first.startswith(RESULT_HEADING) else "not a result"
        raise ConfirmatoryNotRecorded(
            f"{CONFIRMATORY[0]} first line is {first!r}, which is {kind}, not the "
            f"result heading {RESULT_HEADING!r}; a failed attempt is not a recorded result")
