"""Protocol order (PAP §0.5), enforced in code.

- No market robustness row reads a post-seal return until Plan 3's confirmatory H5 record is
  committed unedited (`require_confirmatory_committed`, through Plan 3's guard).
- No RQ1 robustness row runs until Plan 2's single logged first run of H1–H4 is committed,
  unedited and unscrambled (`require_rq1_run_committed`).
- `protected_files` lists Plan 2's bound RQ1 modules, which Plan 4 never edits.

Git is called through subprocess, as `confirm_h5._run_git` does; `confirm_h5` is not imported.
"""

import json
import subprocess
from pathlib import Path

from aideleg.config import ROOT
from aideleg.robustness import upstream

RQ1_FILES = tuple(
    f"docs/results/rq1/confirmatory_rq1.{ext}" for ext in ("json", "md", "log", "attempt")
)
H5_FILES = ("docs/results/confirmatory_h5.md", "docs/results/confirmatory_h5.attempt")


class ProtocolError(RuntimeError):
    """Raised when a robustness row would run before the record it must follow is committed."""


def _run_git(repo: Path, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    except OSError as exc:
        return 1, str(exc)
    return r.returncode, r.stdout.strip()


def require_confirmatory_committed(repo: Path = ROOT) -> None:
    """Refuse unless both H5 files are committed, unmodified and the `.md` is the result."""
    try:
        upstream.assert_confirmatory_recorded(Path(repo))
    except upstream.ConfirmatoryNotRecorded as exc:
        raise ProtocolError(f"market robustness refused: {exc}") from exc


def require_rq1_run_committed(repo: Path = ROOT) -> str:
    """The commit of Plan 2's P-RQ1 run; refuse unless its four files are committed unedited
    and the run was not scrambled."""
    repo = Path(repo)
    for rel in RQ1_FILES:
        tracked = _run_git(repo, "ls-files", "--error-unmatch", rel)[0] == 0
        in_head = _run_git(repo, "cat-file", "-e", f"HEAD:{rel}")[0] == 0
        if not (tracked and in_head):
            raise ProtocolError(f"RQ1 robustness refused: {rel} is not committed in {repo}")
    for rel in RQ1_FILES:
        if _run_git(repo, "diff", "--quiet", "HEAD", "--", rel)[0] != 0:
            raise ProtocolError(f"RQ1 robustness refused: {rel} is modified against HEAD")
    meta = json.loads((repo / RQ1_FILES[0]).read_text(encoding="utf-8")).get("meta", {})
    if meta.get("scrambled") is not False:
        raise ProtocolError(
            f"RQ1 robustness refused: {RQ1_FILES[0]} meta.scrambled is "
            f"{meta.get('scrambled')!r}, not false; a scrambled run is a dry run"
        )
    rc, commit = _run_git(repo, "log", "-1", "--format=%H", "--", RQ1_FILES[0])
    if rc or not commit:
        raise ProtocolError(f"RQ1 robustness refused: no commit touches {RQ1_FILES[0]}")
    return commit


def protected_files(repo: Path = ROOT) -> list[str]:
    """Plan 2's bound RQ1 modules: the keys of `meta.blobs` in `confirmatory_rq1.json`."""
    doc = json.loads((Path(repo) / RQ1_FILES[0]).read_text(encoding="utf-8"))
    return sorted(doc["meta"]["blobs"])
