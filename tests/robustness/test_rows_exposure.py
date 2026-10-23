"""Plan 4 Task 7: the exposure-construction rows, on stubbed inputs (no data)."""

import polars as pl
import pytest

from aideleg.robustness import report, rows
from aideleg.robustness.exposure_variants import OUT_COLUMNS
from aideleg.robustness.upstream import AEI_COLS, BENCH_COLS

# 49 names; 26, 27 and 40 are the industries the majority crosswalk leaves out (C-71)
NAMES = {i: f"I{i:02d}" for i in range(1, 50)} | {26: "Guns", 27: "Gold", 40: "Boxes"}

EXPECTED = {
    "R1": ({"market", "rq2"}, "robustness; look-ahead"),
    "R2": ({"market", "rq2"}, "robustness"),
    "R3": ({"market", "rq2"}, "robustness"),
    "R11": ({"market", "rq2"}, "robustness"),
    "R14": ({"market", "rq2"}, "robustness"),
    "R15": ({"market", "rq2"}, "robustness"),
    "R17": ({"rq2"}, "robustness; descriptive"),
    "R20": ({"market", "rq2"}, "robustness"),
    "R33": ({"market", "rq2"}, "robustness"),
}


def _fake_variant(spec):
    keep = [i for i in NAMES if not (spec.crosswalk == "majority" and i in (26, 27, 40))]
    n = len(keep)
    data = {
        "industry": keep,
        "industry_short": [NAMES[i] for i in keep],
        **{c: [float(k % 7) - 3.0 for k in range(n)] for c in OUT_COLUMNS[2:]},
    }
    return pl.DataFrame(data).select(OUT_COLUMNS)


def _fake_market(row_id, part, expo, *, drop=(), label="robustness", control_col="z_aioe", **kw):
    assert sorted(expo["industry"].to_list()) == sorted(NAMES.values())
    kept = [n for n in expo["industry"].to_list() if n not in drop]
    for c in ("z_delegation", control_col):
        vals = expo.filter(pl.col("industry").is_in(kept))[c]
        assert vals.null_count() == 0
    out = []
    for hyp in ("H5", "H5b"):
        rec = dict.fromkeys(report.ROBUSTNESS_COLUMNS)
        rec |= {
            "row_id": row_id,
            "part": part,
            "variant": "returns=ff49_vw",
            "applies_to": hyp,
            "label": label,
            "estimand": "slope",
            "unit": report.MARKET_UNIT,
            "estimate": 1.0,
            "scale": 0.5,
            "ci_lo": 0.0,
            "ci_hi": 2.0,
            "stat": 1.0,
            "p": 0.3,
            "null": "b = bbar",
            "crit_0025": 2.4,
            "crit_005": 2.1,
            "n": len(kept),
            "n_dropped": len(drop),
            "dropped": ", ".join(drop),
            "note": "secondary",
        }
        out.append(rec)
    return out


def _fake_rq2(exposure, bench):
    assert "ff49" in exposure.columns and "ff49" in bench.columns
    return pl.DataFrame(
        [
            {
                "aei": a,
                "benchmark": b,
                "n": exposure.height,
                "spearman": 0.5,
                "ci_low": 0.2,
                "ci_high": 0.7,
                "n_draws_used": 10_000,
            }
            for a in AEI_COLS
            for b in BENCH_COLS
        ]
    )


@pytest.fixture
def stubbed(monkeypatch, tmp_path):
    monkeypatch.setattr(rows, "variant_exposure", _fake_variant)
    monkeypatch.setattr(rows, "market_variant", _fake_market)
    monkeypatch.setattr(rows, "rq2_correlations", _fake_rq2)
    monkeypatch.setattr(rows, "zero_assigned_share", lambda spec: 12.345)
    monkeypatch.setattr(rows, "OUT_DIR", tmp_path)
    return tmp_path


def _run(row_id):
    csv, md = rows.RUNNERS[row_id]()
    return pl.read_csv(csv), md.read_text(encoding="utf-8")


@pytest.mark.parametrize("row_id", sorted(EXPECTED))
def test_every_exposure_row_writes_both_parts(stubbed, row_id):
    parts, label = EXPECTED[row_id]
    df, _ = _run(row_id)
    assert set(df["part"]) == parts
    assert set(df["label"]) == {label}
    assert set(df["row_id"]) == {row_id}


def test_r14_market_has_h5b_only(stubbed):
    df, _ = _run("R14")
    assert df.filter(pl.col("part") == "market")["applies_to"].to_list() == ["H5b"]


def test_r1_note_states_look_ahead(stubbed):
    df, md = _run("R1")
    assert (
        "May 2025 weights were published after the formation date and during the return window"
        in md
    )
    assert set(df["label"]) == {"robustness; look-ahead"}


@pytest.mark.parametrize("row_id", sorted(EXPECTED))
def test_exposure_rows_state_zero_assigned_share(stubbed, row_id):
    _, md = _run(row_id)
    assert "Zero-assigned employment share (D3): 12.35%" in md


def test_rq2_records_shape(stubbed):
    df, _ = _run("R3")
    rq2 = df.filter(pl.col("part") == "rq2")
    assert rq2.height == len(AEI_COLS) * len(BENCH_COLS)
    assert "spearman z_eloundou vs z_delegation" in rq2["estimand"].to_list()
    assert set(rq2["unit"]) == {report.RHO_UNIT}
    for c in ("stat", "p", "crit_0025", "crit_005"):
        assert rq2[c].null_count() == rq2.height
    # D8: the human beta heads the table; R17 puts the GPT-4 beta first
    assert rq2["estimand"][0].startswith("spearman z_eloundou vs")
    r17 = _run("R17")[0]
    assert r17["estimand"][0].startswith("spearman z_eloundou_gpt4 vs")


def test_r20_pads_and_drops_the_three_unassigned(stubbed):
    df, md = _run("R20")
    mk = df.filter(pl.col("part") == "market")
    assert set(mk["dropped"]) == {"Guns, Gold, Boxes"}
    assert set(df.filter(pl.col("part") == "rq2")["n"]) == {46}
    assert "C-71" in md


@pytest.mark.parametrize(
    ("row_id", "c"),
    [("R2", "C-72"), ("R14", "C-73"), ("R15", "C-70"), ("R33", "C-67"), ("R2", "C-66")],
)
def test_rows_cite_their_c_entries(stubbed, row_id, c):
    _, md = _run(row_id)
    assert c in md


def test_r11_states_d4_note(stubbed):
    _, md = _run("R11")
    assert "makes U equal across occupations sharing a task by construction" in md


def test_cli_only_accepts_stems(stubbed, capsys):
    from aideleg.robustness import __main__ as cli

    cli.main(["--only", "R03", "R17"])
    assert sorted(p.name for p in stubbed.iterdir()) == ["R03.csv", "R03.md", "R17.csv", "R17.md"]
