"""Post-seal market reads need the committed confirmatory record (PAP section 0.5, P-H5 step 5).

The single confirmatory run is Task 1's; nothing else on this branch may read market data
until its result and attempt marker are committed, and unmodified, at HEAD.
"""

import subprocess
from pathlib import Path

from aideleg.config import ROOT

CONFIRMATORY = ("docs/results/confirmatory_h5.md", "docs/results/confirmatory_h5.attempt")
# Blob IDs of the two files at ebe59be, the commit that recorded the single confirmatory run.
PINNED = {
    CONFIRMATORY[0]: "72d3fcb2dc376d27d1dc44deb10b65ccd78dcedf",
    CONFIRMATORY[1]: "4f02b7fd710e8d163d92b842a6ae62dafad70d35",
}
RESULT_HEADING = "# Confirmatory test of H5 and H5b"


class ConfirmatoryNotRecorded(RuntimeError):
    """Raised when a market read is requested without the committed confirmatory record."""


def _git_ok(repo: Path, *args: str) -> bool:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                              check=False).returncode == 0
    except OSError:
        return False


def _head_blob(repo: Path, rel: str) -> str:
    try:
        out = subprocess.run(["git", "-C", str(repo), "rev-parse", f"HEAD:{rel}"],
                             capture_output=True, text=True, check=False)
    except OSError:
        return ""
    return out.stdout.strip()


def assert_confirmatory_recorded(repo: Path = ROOT) -> None:
    for rel in CONFIRMATORY:
        # tracked, and present in HEAD (a staged-only file is not a record)
        if not (_git_ok(repo, "ls-files", "--error-unmatch", rel)
                and _git_ok(repo, "cat-file", "-e", f"HEAD:{rel}")):
            raise ConfirmatoryNotRecorded(
                f"{rel} is not committed in {repo}: market data are not read until the "
                "confirmatory H5 result and its attempt marker are committed")
    for rel in CONFIRMATORY:
        if _head_blob(repo, rel) != PINNED[rel]:
            raise ConfirmatoryNotRecorded(
                f"{rel} at HEAD differs from the pinned confirmatory record "
                f"({PINNED[rel]}): a later committed edit is not the recorded result")
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
