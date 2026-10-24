"""`python scripts/compare_outputs.py ROOT WORK`: compare a fresh clone's rebuilt outputs with the
committed ones (Task 33) and print a Markdown table; exit 1 on any difference.

Scope: every file tracked under `docs/results/**`, `docs/paper/_variables.yml`,
`docs/paper/_generated/**`, `docs/paper/figures/*.png` and `*.pdf`, `docs/pap/power.md` and
`docs/audit/**` (in ROOT or WORK), plus any untracked file the rebuild left there in WORK, and
the rendered `docs/paper/_output/{paper,brief}.pdf` when ROOT has them.

- CSVs under `docs/results/robustness/` and `docs/results/diagnostics/` reproduce under the
  PAP §11 C-80 / C-82 tolerance (`aideleg.robustness.reproduce.csv_equivalent`: relative 1e-9,
  absolute 1e-12, non-numeric cells exact).
- PNGs are compared by pixel arrays (`matplotlib.image.imread`, exact equality).
- PDFs embed timestamps, so only their page count is compared.
- Every other file is compared byte for byte.
"""

import csv
import io
import math
import subprocess
import sys
from pathlib import Path

ROBUSTNESS_CSV = ("docs/results/robustness/", "docs/results/diagnostics/")
RENDERED = ("docs/paper/_output/paper.pdf", "docs/paper/_output/brief.pdf")


def in_scope(rel: str) -> bool:
    if rel.startswith(("docs/results/", "docs/paper/_generated/", "docs/audit/")):
        return True
    if rel in ("docs/paper/_variables.yml", "docs/pap/power.md"):
        return True
    head, _, name = rel.rpartition("/")
    return head == "docs/paper/figures" and name.endswith((".png", ".pdf"))


def _git(repo: Path, *args: str) -> list[str]:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return r.stdout.splitlines() if r.returncode == 0 else []


def tracked(repo: Path) -> set[str]:
    return {p for p in _git(repo, "ls-files") if in_scope(p)}


def untracked(repo: Path) -> set[str]:
    return {p for p in _git(repo, "ls-files", "--others", "--exclude-standard") if in_scope(p)}


def _float(s: str) -> float | None:
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def csv_detail(a: bytes, b: bytes) -> str:
    """Where two CSVs differ: the number of differing cells, the first, and the largest
    relative difference among numeric cells."""
    ra = list(csv.reader(io.StringIO(a.decode("utf-8", "replace"))))
    rb = list(csv.reader(io.StringIO(b.decode("utf-8", "replace"))))
    if len(ra) != len(rb):
        return f"{len(ra)} rows committed, {len(rb)} rebuilt"
    if ra and rb and ra[0] != rb[0]:
        return "header differs"
    header = ra[0] if ra else []
    cells, first, worst, nonnum = 0, None, 0.0, 0
    for i, (x, y) in enumerate(zip(ra, rb, strict=True)):
        if len(x) != len(y):
            return f"row {i}: {len(x)} cells committed, {len(y)} rebuilt"
        for j, (p, q) in enumerate(zip(x, y, strict=True)):
            if p == q:
                continue
            cells += 1
            col = header[j] if j < len(header) else str(j)
            fp, fq = _float(p), _float(q)
            if fp is None or fq is None:
                nonnum += 1
            else:
                rel = abs(fp - fq) / max(abs(fp), abs(fq), 1e-300)
                worst = max(worst, rel)
            if first is None:
                first = f"row {i} `{col}`: {p} -> {q}"
    out = f"{cells} cell(s) differ; first {first}"
    if cells > nonnum:
        out += f"; max relative difference {worst:.1e}"
    if nonnum:
        out += f"; {nonnum} non-numeric"
    return out


def text_detail(a: bytes, b: bytes) -> str:
    la, lb = a.splitlines(), b.splitlines()
    for i, (x, y) in enumerate(zip(la, lb, strict=False), start=1):
        if x != y:
            return f"first difference at line {i}"
    return f"{len(la)} lines committed, {len(lb)} rebuilt"


def png_same(a: Path, b: Path) -> tuple[bool, str]:
    import numpy as np
    from matplotlib import image

    x, y = image.imread(a), image.imread(b)
    if x.shape != y.shape:
        return False, f"shape {x.shape} -> {y.shape}"
    if np.array_equal(x, y):
        return True, ""
    n = int(np.count_nonzero(np.any(x != y, axis=-1) if x.ndim == 3 else x != y))
    return False, f"{n} pixel(s) differ"


def pdf_pages(p: Path) -> int:
    from pypdf import PdfReader

    return len(PdfReader(p).pages)


def compare(root: Path, work: Path, rel: str) -> tuple[str, str, str]:
    """(method, result, detail) for one path."""
    a, b = root / rel, work / rel
    if rel.endswith(".png"):
        method = "pixels"
    elif rel.endswith(".pdf"):
        method = "page count"
    elif rel.endswith(".csv") and rel.startswith(ROBUSTNESS_CSV):
        method = "C-80/C-82 tolerance"
    else:
        method = "bytes"
    if not a.exists():
        return method, "NEW (not in the committed tree)", ""
    if not b.exists():
        return method, "MISSING (not rebuilt)", ""
    if method == "pixels":
        if a.read_bytes() == b.read_bytes():
            return method, "identical", ""
        same, detail = png_same(a, b)
        return method, "identical pixels" if same else "DIFFERENT", detail
    if method == "page count":
        pa, pb = pdf_pages(a), pdf_pages(b)
        return method, "identical" if pa == pb else "DIFFERENT", f"{pa} pages -> {pb}"
    ba, bb = a.read_bytes(), b.read_bytes()
    if ba == bb:
        return method, "identical", ""
    if method == "C-80/C-82 tolerance":
        from aideleg.robustness.reproduce import csv_equivalent

        if csv_equivalent(ba, bb):
            return method, "equivalent (within C-80)", csv_detail(ba, bb)
        return method, "DIFFERENT", csv_detail(ba, bb)
    detail = csv_detail(ba, bb) if rel.endswith(".csv") else text_detail(ba, bb)
    return method, "DIFFERENT", detail


def _head(repo: Path) -> str:
    out = _git(repo, "rev-parse", "--short", "HEAD")
    return out[0] if out else "(no commit)"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    root, work = Path(argv[0]), Path(argv[1])
    paths = sorted(tracked(root) | tracked(work) | untracked(work))
    paths += [p for p in RENDERED if (root / p).exists()]
    rows = [(p, *compare(root, work, p)) for p in paths]
    bad = [r for r in rows if r[2].startswith(("DIFFERENT", "NEW", "MISSING"))]
    tol = [r for r in rows if r[2].startswith(("equivalent", "identical pixels"))]
    print("# Fresh-clone replication check")
    print()
    print(
        "Generated by `scripts/replicate.sh` (`scripts/compare_outputs.py`): the outputs a fresh "
        f"clone rebuilt with `make all` (clone at commit `{_head(work)}`) against the committed "
        f"tree (commit `{_head(root)}`). Text files are compared byte for byte; CSVs under "
        "`docs/results/robustness/` and `docs/results/diagnostics/` under the PAP §11 C-80/C-82 "
        "tolerance (relative 1e-9, absolute 1e-12, non-numeric cells exact); PNGs by pixels; "
        "PDFs, which embed timestamps, by page count."
    )
    print()
    n_same = len(rows) - len(bad) - len(tol)
    print(
        f"**{len(rows)} files compared: {n_same} identical, {len(tol)} equivalent within the "
        f"stated tolerance, {len(bad)} different.**"
    )
    print()
    if bad:
        print("## Differences")
        print()
        print("| file | method | result | detail |")
        print("|---|---|---|---|")
        for p, m, res, d in bad:
            print(f"| `{p}` | {m} | {res} | {d} |")
        print()
    print("## Every file")
    print()
    print("| file | method | result | detail |")
    print("|---|---|---|---|")
    for p, m, res, d in rows:
        print(f"| `{p}` | {m} | {res} | {d} |")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
