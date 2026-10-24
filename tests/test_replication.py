"""Task 33: seeding raw data from a frozen archive, `make all` offline, and the output compare."""

import gzip
import hashlib
import io
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

from aideleg.acquire import __main__ as acquire_main
from aideleg.acquire import fetch, seed, sources
from aideleg.config import ROOT

ZIP_KEY = "ff49_daily"  # a registry key with unzip=True
TEXT_KEY = "aei_r1_wage"  # a registry key with unzip=False


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _record(key: str, dest: str, body: bytes) -> fetch.FetchRecord:
    return fetch.FetchRecord(
        key, f"https://x.test/{key}", dest, "2026-10-01T00:00:00Z", len(body), _sha(body)
    )


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buf.getvalue()


def _archive(tmp_path: Path, files: dict[str, tuple[str, bytes]]) -> tuple[Path, Path]:
    """A source archive (`src/<dest>`) and a fresh raw dir holding only the committed MANIFEST."""
    src, raw = tmp_path / "src", tmp_path / "raw"
    records = {}
    for key, (dest, body) in files.items():
        (src / dest).parent.mkdir(parents=True, exist_ok=True)
        (src / dest).write_bytes(body)
        records[key] = _record(key, dest, body)
    fetch.write_manifest(raw, records)
    return src, raw


def test_from_dir_refuses_hash_mismatch(tmp_path, capsys):
    dest = sources.by_key(TEXT_KEY).dest
    src, raw = _archive(tmp_path, {TEXT_KEY: (dest, b"frozen bytes\n")})
    (src / dest).write_bytes(b"revised bytes\n")
    rc = acquire_main.main(["--from-dir", str(src), "--raw-dir", str(raw)])
    err = capsys.readouterr().err
    assert rc == 1
    assert TEXT_KEY in err
    assert not (raw / dest).exists()
    assert not list(raw.rglob("*.part"))


def test_from_dir_copies_matching(tmp_path):
    zip_dest = sources.by_key(ZIP_KEY).dest
    body = _zip_bytes({"49_Industry_Portfolios_Daily.csv": b"a,b\n1,2\n"})
    src, raw = _archive(
        tmp_path,
        {ZIP_KEY: (zip_dest, body), TEXT_KEY: (sources.by_key(TEXT_KEY).dest, b"x,y\n")},
    )
    assert seed.from_dir(src, raw_dir=raw) == []
    assert (raw / zip_dest).read_bytes() == body
    extracted = raw / zip_dest[: -len(".zip")] / "49_Industry_Portfolios_Daily.csv"
    assert extracted.read_bytes() == b"a,b\n1,2\n"
    assert (raw / sources.by_key(TEXT_KEY).dest).read_bytes() == b"x,y\n"


def _docs_archive(tmp_path: Path, docs: dict[str, bytes]) -> tuple[Path, Path, list[dict]]:
    lines = []
    for i, (key, body) in enumerate(docs.items()):
        dest = f"sec/docs/{100 + i}/{key}/doc.htm.gz"
        lines.append(
            {
                "key": key,
                "url": f"https://x.test/{key}",
                "dest": dest,
                "retrieved_utc": "2026-10-23T00:00:00Z",
                "bytes": len(body),
                "sha256": _sha(body),
            }
        )
    index = "".join(json.dumps(r) + "\n" for r in lines).encode()
    src, raw = _archive(tmp_path, {"sec_docs_index": ("sec/docs/INDEX.jsonl", index)})
    for r, body in zip(lines, docs.values(), strict=True):
        (src / r["dest"]).parent.mkdir(parents=True, exist_ok=True)
        (src / r["dest"]).write_bytes(gzip.compress(body, mtime=0))
    return src, raw, lines


def test_from_dir_restores_sec_docs_and_verifies_index(tmp_path, capsys):
    docs = {"0000000001-24-000001": b"<html>one</html>", "0000000002-24-000002": b"<p>two</p>"}
    src, raw, lines = _docs_archive(tmp_path, docs)
    assert seed.from_dir(src, raw_dir=raw) == []
    for r, body in zip(lines, docs.values(), strict=True):
        assert gzip.decompress((raw / r["dest"]).read_bytes()) == body

    # a document that decompresses to different bytes is refused, by key
    bad = lines[1]
    (src / bad["dest"]).write_bytes(gzip.compress(b"<p>TWO</p>", mtime=0))
    raw2 = tmp_path / "raw2"
    shutil.copytree(raw, raw2, ignore=shutil.ignore_patterns("docs"))
    rc = acquire_main.main(["--from-dir", str(src), "--raw-dir", str(raw2)])
    assert rc == 1
    assert bad["key"] in capsys.readouterr().err
    assert not (raw2 / bad["dest"]).exists()

    # a document listed in INDEX.jsonl but absent from the archive is refused, by key
    (src / bad["dest"]).unlink()
    raw3 = tmp_path / "raw3"
    shutil.copytree(raw, raw3, ignore=shutil.ignore_patterns("docs"))
    rc = acquire_main.main(["--from-dir", str(src), "--raw-dir", str(raw3)])
    assert rc == 1
    assert bad["key"] in capsys.readouterr().err


def test_from_dir_refuses_its_own_raw_dir(tmp_path):
    src, raw = _archive(tmp_path, {TEXT_KEY: (sources.by_key(TEXT_KEY).dest, b"x\n")})
    with pytest.raises(ValueError, match="same directory"):
        seed.from_dir(raw, raw_dir=raw)


def test_check_download_reports_without_touching_raw(tmp_path, monkeypatch):
    same, revised = b"unchanged\n", b"revised\n"
    _, raw = _archive(
        tmp_path,
        {
            TEXT_KEY: (sources.by_key(TEXT_KEY).dest, same),
            ZIP_KEY: (sources.by_key(ZIP_KEY).dest, b"old zip"),
            "sec_fts/2024-01-01_2024-12-31/chatgpt/00000": ("sec/fts/2024/c.json", b"{}"),
            "sec_docs_index": ("sec/docs/INDEX.jsonl", b""),
        },
    )
    before = sorted(p.relative_to(raw) for p in raw.rglob("*"))
    fetched = []

    def fake_download(src, path):
        fetched.append(src.key)
        assert raw not in Path(path).parents
        Path(path).write_bytes(same if src.key == TEXT_KEY else revised)

    monkeypatch.setattr(fetch, "download", fake_download)
    out = tmp_path / "download_check.md"
    rows = seed.check_download(out=out, raw_dir=raw)
    assert sorted(fetched) == sorted([TEXT_KEY, ZIP_KEY])  # bulk SEC sets are not re-downloaded
    assert sorted(p.relative_to(raw) for p in raw.rglob("*")) == before
    status = {r["key"]: r["match"] for r in rows}
    assert status[TEXT_KEY] == "yes" and status[ZIP_KEY] == "no"
    text = out.read_text()
    assert f"| `{ZIP_KEY}` | no |" in text and f"| `{TEXT_KEY}` | yes |" in text
    assert "not re-downloaded (bulk; verified from the frozen archive by --from-dir)" in text


def _make_n_all() -> str:
    r = subprocess.run(["make", "-n", "all"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_make_all_never_runs_confirm_h5():
    assert "aideleg.confirm_h5" not in _make_n_all()


def test_make_all_never_runs_rq1_confirm():
    out = _make_n_all()
    for banned in (
        "aideleg.rq1.confirm",
        "aideleg.h6 acquire",
        "python -m aideleg.acquire",
        "--check-download",
    ):
        assert banned not in out, banned
    for needed in ("aideleg.robustness --offline", "aideleg.h6 all"):
        assert needed in out, needed


def test_make_all_rebuilds_what_it_compares():
    """T-2: the D-3 diagnostics, the audit tables and power.md's generated block are rebuilt,
    and the committed confirmatory records are checked, not rebuilt."""
    out = _make_n_all()
    for needed in (
        "aideleg.robustness --diagnostics",
        "python -m aideleg.audit",
        "require_confirmatory_committed",
        "require_rq1_run_committed",
        "scripts/power_block.py",
    ):
        assert needed in out, needed


def _git_tree(root: Path, files: dict[str, bytes]) -> Path:
    for rel, body in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(body)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    return root


def _compare(root: Path, work: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/compare_outputs.py"), str(root), str(work)],
        capture_output=True,
        text=True,
    )


def _png(path: Path, value: float) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    a = np.full((4, 4, 3), value)
    plt.imsave(path, a)
    return path.read_bytes()


def test_compare_outputs_detects_change(tmp_path):
    files = {
        "docs/results/rq1/a.csv": b"x,y\n1,2.5\n",
        "docs/results/rq1/a.md": b"# a\n",
        "docs/paper/_variables.yml": b"k: 1\n",
        "docs/pap/power.md": b"power\n",
        "docs/audit/tables/t.md": b"t\n",
    }
    root = _git_tree(tmp_path / "root", files)
    same = _git_tree(tmp_path / "same", files)
    r = _compare(root, same)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "docs/results/rq1/a.csv" in r.stdout

    changed = _git_tree(tmp_path / "changed", {**files, "docs/results/rq1/a.csv": b"x,y\n1,2.6\n"})
    r = _compare(root, changed)
    assert r.returncode == 1
    line = next(ln for ln in r.stdout.splitlines() if "docs/results/rq1/a.csv" in ln)
    assert "DIFFERENT" in line


def test_compare_outputs_robustness_csv_tolerance_and_png_pixels(tmp_path):
    rob = "docs/results/robustness/R15.csv"
    base = {rob: b"row,v\nR15,0.1234567890123456\n", "docs/results/rq2/g.csv": b"v\n1.0\n"}
    root = _git_tree(tmp_path / "root", base)
    # last-digit noise in a robustness CSV is within C-80; in a Plan 2 CSV it is a difference
    work = _git_tree(
        tmp_path / "work",
        {
            rob: b"row,v\nR15,0.1234567890123457\n",
            "docs/results/rq2/g.csv": b"v\n1.0000000000001\n",
        },
    )
    r = _compare(root, work)
    assert r.returncode == 1
    lines = r.stdout.splitlines()
    assert "DIFFERENT" not in next(ln for ln in lines if rob in ln)
    assert "DIFFERENT" in next(ln for ln in lines if "rq2/g.csv" in ln)

    fig = "docs/paper/figures/fig_x.png"
    (tmp_path / "p").mkdir()
    a = _png(tmp_path / "p/a.png", 0.2)
    b = _png(tmp_path / "p/b.png", 0.8)
    root = _git_tree(tmp_path / "root2", {fig: a})
    assert _compare(root, _git_tree(tmp_path / "w2", {fig: a})).returncode == 0
    r = _compare(root, _git_tree(tmp_path / "w3", {fig: b}))
    assert r.returncode == 1 and fig in r.stdout


def test_compare_outputs_reports_missing_and_new_files(tmp_path):
    root = _git_tree(tmp_path / "root", {"docs/results/a.md": b"a\n"})
    work = _git_tree(tmp_path / "work", {"docs/results/b.md": b"b\n"})
    r = _compare(root, work)
    assert r.returncode == 1
    assert "docs/results/a.md" in r.stdout and "docs/results/b.md" in r.stdout
