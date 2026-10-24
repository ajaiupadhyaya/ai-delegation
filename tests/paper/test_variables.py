"""Generated paper variables and table/figure includes (Plan 4 Task 18)."""

import csv
import json
import re
from pathlib import Path

import pytest

from aideleg.config import ROOT
from aideleg.paper import confirmatory_md, headlines, includes, variables

PAPER = ROOT / "docs/paper"
HEADLINES = ROOT / "docs/redteam/headlines.csv"


def _rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _flat(d: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flat(v, key + "."))
        else:
            out[key] = v
    return out


@pytest.fixture(scope="module")
def built() -> dict:
    return variables.build(variables.MAP)


@pytest.fixture(scope="module")
def flat(built) -> dict[str, str]:
    return _flat(built)


def test_fmt_rules():
    assert variables.fmt(1.234, "pp") == "1.23"
    assert variables.fmt("-0.5347910778604343", "coef") == "-0.53"
    assert variables.fmt(0.76312, "rho") == "0.763"
    assert variables.fmt(0.0004, "p") == "< 0.001"
    assert variables.fmt("0.3611081162653986", "p") == "0.361"
    assert variables.fmt("49", "int") == "49"
    assert variables.fmt(5.0, "int") == "5"
    assert variables.fmt("12.14", "pct") == "12.14"
    assert variables.fmt("not_rejected", "text") == "not_rejected"
    assert variables.fmt("2025-04-01", "date") == "2025-04-01"
    with pytest.raises(ValueError):
        variables.fmt(2.5, "int")
    with pytest.raises(ValueError):
        variables.fmt("nan", "pp")
    with pytest.raises(ValueError):
        variables.fmt("x", "pp")
    with pytest.raises(ValueError):
        variables.fmt("1", "stat")


def test_printed_values_keep_their_precision(tmp_path):
    """A value read from a printed markdown file (the confirmatory record, a regex cell) keeps
    the precision it was printed with; only CSV, JSON and computed values are formatted."""
    m = tmp_path / "map.csv"
    m.write_text(
        "key,source,locator,fmt\n"
        "a.b,confirmatory_md,H5.p_primary,p\n"
        "a.c,docs/pap/power.md,"
        '"regex=^\\| H5 \\| overlapping \\| (\\d+\\.\\d+) \\|",pp\n',
        encoding="utf-8",
    )
    got = variables.build(m)
    assert got["a"]["b"] == confirmatory_md.parse()["H5"]["p_primary"] == "0.8934"
    assert got["a"]["c"] == "2.271"


def test_map_rows_resolve_once(tmp_path):
    src = tmp_path / "t.csv"
    src.write_text("g,h,v\nx,1,0.5\nx,2,0.7\ny,1,0.9\n", encoding="utf-8")
    ok = tmp_path / "ok.csv"
    ok.write_text(f'key,source,locator,fmt\nk.one,{src},"column=v;filter=g:x,h:2",pp\n')
    assert variables.build(ok) == {"k": {"one": "0.70"}}
    for name, loc in (("two", "column=v;filter=g:x"), ("none", "column=v;filter=g:z")):
        bad = tmp_path / f"{name}.csv"
        bad.write_text(f"key,source,locator,fmt\nk.{name},{src},{loc},pp\n")
        with pytest.raises(ValueError, match=rf"k\.{name}"):
            variables.build(bad)


def test_map_rejects_duplicate_and_conflicting_keys(tmp_path):
    src = tmp_path / "t.csv"
    src.write_text("g,v\nx,0.5\n", encoding="utf-8")
    for keys in (("a.b", "a.b"), ("a.b", "a.b.c")):
        m = tmp_path / "m.csv"
        m.write_text(
            "key,source,locator,fmt\n"
            + "".join(f"{k},{src},column=v;filter=g:x,pp\n" for k in keys)
        )
        with pytest.raises(ValueError, match="a.b"):
            variables.build(m)


def test_write_is_sorted_json(tmp_path):
    out = tmp_path / "v.yml"
    variables.write({"b": {"y": "1", "x": "2"}, "a": "3"}, out)
    text = out.read_text(encoding="utf-8")
    assert json.loads(text) == {"a": "3", "b": {"x": "2", "y": "1"}}
    assert text.index('"a"') < text.index('"b"') and text.index('"x"') < text.index('"y"')


def test_power_mdes_equal_printed(flat):
    """MDE = (c_0.025 + t_21,0.80) * s from `confirm_h5.FROZEN`, equal to the printed values."""
    rec = confirmatory_md.parse()
    assert flat["power.mde.h5"] == "7.43"
    assert flat["power.mde.h5b"] == "8.38"
    assert flat["power.mde.h5_r13"] == rec["decision"]["H5"]["mde_r13"]
    assert flat["power.mde.h5b_r13"] == rec["decision"]["H5b"]["mde_r13"]
    assert flat["power.mde.h5"] == flat["rq3.h5.mde"]
    assert flat["power.mde.h5b"] == flat["rq3.h5b.mde"]
    assert flat["design.plausibility_pp"] == "5"


def test_headline_keys_match_variables(flat):
    """Every red-team headline key (lower-cased) is a variable equal to the headline value, as
    `headlines.resolve` reads it and the map's format formats it."""
    fmts = {r["key"]: r["fmt"] for r in _rows(variables.MAP)}
    for row in _rows(HEADLINES):
        key = row["key"].lower()
        assert key in flat, row["key"]
        assert flat[key] == variables.fmt(
            headlines.resolve(row), fmts[key], printed=row["source_file"].endswith(".md")
        ), row["key"]


def test_generated_includes_current(tmp_path, built):
    assert json.loads(variables.OUT.read_text(encoding="utf-8")) == built
    for kind, fn, csv_path in (
        ("tables", includes.build_tables, includes.TABLES),
        ("figures", includes.build_figures, includes.FIGURES),
    ):
        fresh = fn(csv_path, tmp_path / kind)
        committed = sorted((includes.GENERATED / kind).glob("*.md"))
        assert [p.name for p in committed] == sorted(p.name for p in fresh), kind
        for p in fresh:
            assert (includes.GENERATED / kind / p.name).read_text(encoding="utf-8") == (
                p.read_text(encoding="utf-8")
            ), p.name


def test_every_var_used_is_mapped(flat):
    used = set()
    for qmd in PAPER.rglob("*.qmd"):
        used |= set(re.findall(r"\{\{<\s*var\s+([^\s>]+)\s*>\}\}", qmd.read_text("utf-8")))
    assert used, "no var shortcode found"
    assert sorted(used - set(flat)) == []


def test_table_and_figure_sources_exist():
    for row in _rows(includes.TABLES):
        path, _, n = row["source"].partition("#")
        assert (ROOT / path).is_file(), row["id"]
        includes.extract_table((ROOT / path).read_text("utf-8"), int(n) if n else None)
    for row in _rows(includes.FIGURES):
        for ext in (".pdf", ".png"):
            assert (PAPER / "figures" / f"{row['stem']}{ext}").is_file(), row["id"]


def test_every_result_table_and_figure_is_mapped():
    """Every pipe table in `docs/results/**/*.md` and every figure in `docs/paper/figures/`."""
    have = {r["source"] for r in _rows(includes.TABLES)}
    for md in sorted((ROOT / "docs/results").rglob("*.md")):
        n = len(includes.tables_in(md.read_text("utf-8")))
        rel = md.relative_to(ROOT).as_posix()
        want = {rel} if n == 1 else {f"{rel}#{i}" for i in range(1, n + 1)}
        assert want <= have, rel
    stems = {p.stem for p in (PAPER / "figures").glob("*.pdf")}
    assert {r["stem"] for r in _rows(includes.FIGURES)} == stems


def test_tables_keep_source_bytes():
    """A table include holds the source table lines unchanged, then the caption and notes."""
    for row in _rows(includes.TABLES):
        path, _, n = row["source"].partition("#")
        table = includes.extract_table((ROOT / path).read_text("utf-8"), int(n) if n else None)
        text = (includes.GENERATED / "tables" / f"{row['id']}.md").read_text("utf-8")
        assert "\n".join(table) + "\n" in text, row["id"]
        assert f": {row['caption']} {{#tbl-{row['id']}}}" in text, row["id"]


def test_extract_table_refuses_ambiguity():
    text = "a\n\n| x |\n|---|\n| 1 |\n\nb\n\n| y |\n|---|\n| 2 |\n"
    assert includes.extract_table(text, 2) == ["| y |", "|---|", "| 2 |"]
    with pytest.raises(ValueError, match="2 tables"):
        includes.extract_table(text, None)
    with pytest.raises(ValueError):
        includes.extract_table(text, 3)


_IDENT = re.compile(r"\b[A-Za-z][A-Za-z*]*\d+[A-Za-z]*\b")


def test_captions_have_no_typed_numerals():
    """Light guard (Task 19 owns the full scanner): no digit in a caption, note or alt text once
    identifier tokens, section signs and inline-code paths are removed."""
    for path, cols in (
        (includes.TABLES, ("caption", "notes")),
        (includes.FIGURES, ("caption", "alt")),
    ):
        for row in _rows(path):
            for c in cols:
                t = re.sub(r"`[A-Za-z0-9_./*-]*[A-Za-z][A-Za-z0-9_./*-]*`", "", row[c])
                t = re.sub(r"\{\{<[^>]*>\}\}", "", t)
                t = re.sub(r"§\d+(\.\d+)*", "", t)
                t = _IDENT.sub("", t)
                assert not re.search(r"\d", t), (path.name, row["id"], c, row[c])


def test_prose_formats():
    assert variables.fmt("False", "verdict") == "not rejected"
    assert variables.fmt("True", "verdict") == "rejected"
    assert variables.fmt("supported", "verdict") == "supported"
    assert variables.fmt("not_rejected", "verdict") == "not supported"
    with pytest.raises(ValueError):
        variables.fmt("contradicts", "verdict")
    assert variables.fmt("-2.764", "pp2", printed=True) == "-2.76"


def test_prose_forms_beside_raw(flat):
    """Prose never prints `False` or mixes precisions: verdicts and 2-dp interval ends sit beside
    the raw and printed-precision values, and the 2-dp ends equal the P14 wording's interval."""
    rec = confirmatory_md.parse()
    for hyp in ("H5", "H5b"):
        k = f"rq3.{hyp.lower()}"
        assert flat[f"{k}.decision"] == rec["decision"][hyp]["rejected"]
        assert flat[f"{k}.decision_text"] == (
            "rejected" if rec["decision"][hyp]["rejected"] == "True" else "not rejected"
        )
        lo, hi = flat[f"{k}.ci_005.lo_pp2"], flat[f"{k}.ci_005.hi_pp2"]
        assert f"Interval [{lo}, {hi}] pp per 1 SD" in flat[f"{k}.wording"]
        assert flat[f"{k}.ci_0025.lo_pp2"] == f"{float(flat[f'{k}.ci_0025.lo']):.2f}"
        assert flat[f"{k}.b_pp2"] == f"{float(flat[f'{k}.b']):.2f}"
    for h in ("h1", "h2", "h3", "h4"):
        raw = flat[f"rq1.{h}.decision"]
        assert flat[f"rq1.{h}.decision_text"] == variables.VERDICTS[raw]


def _git(*args, cwd=None):
    import subprocess

    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _committed_date() -> str:
    return json.loads(variables.OUT.read_text(encoding="utf-8"))["meta"]["date"]


def test_no_git_falls_back_to_committed(tmp_path):
    """An archive with no `.git`: meta.date from the committed `_variables.yml`, the PAP from
    the pinned constants."""
    repo = tmp_path / "archive"
    (repo / "docs/paper").mkdir(parents=True)
    (repo / "docs/paper/_variables.yml").write_text(variables.OUT.read_text("utf-8"), "utf-8")
    assert variables.results_date(repo) == _committed_date()
    assert variables.pap_values(repo) == variables.pap_values(ROOT)
    with pytest.raises(ValueError, match="no git history"):
        variables.results_date(tmp_path / "empty")


@pytest.mark.parametrize("depth", [["--depth", "1"], []])
def test_shallow_and_full_clone_agree(tmp_path, depth):
    """A `--depth 1` clone falls back to the committed date; a full clone reads git. Both give
    the committed values, and the PAP pins agree with the tag where git has it."""
    clone = tmp_path / "clone"
    _git("clone", "-q", "--no-local", *depth, f"file://{ROOT}", str(clone))
    shallow = bool(depth)
    assert variables._has_history(clone) is (not shallow)
    committed = json.loads((clone / "docs/paper/_variables.yml").read_text("utf-8"))
    assert variables.results_date(clone) == committed["meta"]["date"]
    assert variables.pap_values(clone) == {
        "tag": "pap-v1",
        "commit": variables.PAP_COMMIT,
        "date": variables.PAP_DATE,
    }


def test_pap_pins_match_git():
    assert variables._has_history(ROOT)
    assert variables._git(ROOT, "rev-list", "-n", "1", "pap-v1") == variables.PAP_COMMIT
    assert variables.results_date(ROOT) == _committed_date()
