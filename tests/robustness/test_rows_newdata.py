"""Plan 4 Task 9: the new-data market rows R6 (FF30/FF48) and R32 (strict real-time Design B).
Stubbed runners (no data), plus the OEWS May 2023 crosswalk-coverage data test that must pass
before R32 is run."""

import polars as pl
import pytest

from aideleg.config import RAW
from aideleg.robustness import report, rows
from aideleg.robustness.exposure_variants import OUT_COLUMNS


def _fake_variant(spec):
    n = spec.industries
    data = {
        "industry": list(range(1, n + 1)),
        "industry_short": [f"J{n}_{i:02d}" for i in range(1, n + 1)],
        **{c: [float(k % 7) - 3.0 for k in range(n)] for c in OUT_COLUMNS[2:]},
    }
    return pl.DataFrame(data).select(OUT_COLUMNS)


@pytest.fixture
def stubbed(monkeypatch, tmp_path):
    calls: list[dict] = []

    def fake_variant(spec):
        calls.append({"spec": spec})
        return _fake_variant(spec)

    def fake_market(row_id, part, expo, *, rs="ff49_vw", label="robustness", **kw):
        calls.append({"row_id": row_id, "part": part, "rs": rs, "n": expo.height, **kw})
        out = []
        for hyp in ("H5", "H5b"):
            rec = dict.fromkeys(report.ROBUSTNESS_COLUMNS)
            rec |= {
                "row_id": row_id,
                "part": part,
                "variant": f"returns={rs}",
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
                "n": expo.height,
                "n_dropped": 0,
                "dropped": "",
                "note": "secondary",
            }
            out.append(rec)
        return out

    monkeypatch.setattr(rows, "variant_exposure", fake_variant)
    monkeypatch.setattr(rows, "market_variant", fake_market)
    monkeypatch.setattr(rows, "zero_assigned_share", lambda spec: 12.345)
    monkeypatch.setattr(rows, "OUT_DIR", tmp_path)
    return calls


def _run(row_id):
    csv, md = rows.RUNNERS[row_id]()
    return pl.read_csv(csv), md.read_text(encoding="utf-8")


def test_r6_has_two_parts_and_industry_counts(stubbed):
    df, md = _run("R6")
    assert set(df["part"]) == {"ff30", "ff48"}
    assert set(df["applies_to"]) == {"H5", "H5b"}
    by = {c["part"]: c for c in stubbed if "part" in c}
    assert by["ff30"]["n"] == 30 and by["ff30"]["rs"] == "ff30_vw"
    assert by["ff48"]["n"] == 48 and by["ff48"]["rs"] == "ff48_vw"
    specs = [c["spec"] for c in stubbed if "spec" in c]
    assert {s.industries for s in specs} == {30, 48}
    assert all(s == rows.ExposureSpec(industries=s.industries) for s in specs)
    assert dict(zip(df["part"], df["n"], strict=True)) == {"ff30": 30, "ff48": 48}
    assert (
        "FF30/FF48 files retrieved after the freeze; their history may reflect French's "
        "later revisions" in md
    )
    assert "C-65" in md
    assert md.count("Zero-assigned employment share (D3): 12.35%") == 2


def test_r32_spec_is_strict_real_time(stubbed):
    df, md = _run("R32")
    (spec,) = [c["spec"] for c in stubbed if "spec" in c]
    assert spec.oews_year == 2023
    assert spec.onet == "29.2"
    assert spec == rows.ExposureSpec(oews_year=2023, onet="29.2")  # Design B, r2
    (call,) = [c for c in stubbed if "part" in c]
    assert call["rs"] == "ff49_vw" and call["n"] == 49
    assert set(df["applies_to"]) == {"H5", "H5b"}
    assert "inputs public at 2025-03-27" in md
    assert "C-74" in md
    assert "C-65" in md
    assert "Zero-assigned employment share (D3): 12.35%" in md


@pytest.mark.data
@pytest.mark.skipif(not (RAW / "bls/oesm23in4").exists(), reason="needs OEWS 2023")
def test_unmapped_private_below_1pct_2023():
    """R32 precondition: private OEWS May 2023 employment with no FF49 mapping is < 1% (as the
    May 2024 test in tests/crosswalk); a failure means a NAICS vintage mismatch (Ajai's call)."""
    from aideleg.bls.oews import load_industry_matrix
    from aideleg.crosswalk.naics_ff49 import coverage_by_code, coverage_report

    m = load_industry_matrix(2023, 4)
    rep = coverage_report(m, employment=m)
    share = rep.filter(pl.col("status") == "unmapped")["share_of_private"].sum()
    print(f"unmapped private OEWS May 2023 employment share: {share:.6f}")
    assert share < 0.01, coverage_by_code(m).sort("unmapped_emp", descending=True).head(20)
