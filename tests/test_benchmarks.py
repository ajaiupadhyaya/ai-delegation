"""Benchmarks (AIOE, Eloundou et al.) on toy inputs, and coverage on the real files."""

import polars as pl
import pytest

from aideleg.benchmarks import (
    benchmark_ff49,
    load_aioe,
    load_aioe_raw,
    load_eloundou,
    map_soc2010_to_2018,
    rank_correlations,
    to_oews,
)

SOC = r"^\d{2}-\d{4}$"


def test_aioe_soc_codes_valid_format():
    for df in (load_aioe_raw(), load_aioe()):
        assert df["soc6"].str.contains(SOC).all()
        assert df["soc6"].is_unique().all()
        assert df["aioe"].null_count() == 0
    assert load_aioe_raw().height == 774


def test_eloundou_soc_codes_valid_format():
    df = load_eloundou()
    assert df["soc6"].str.contains(SOC).all() and df["soc6"].is_unique().all()
    assert df.columns == ["soc6", "beta_human", "beta_gpt4"]
    assert df.select(pl.col("beta_human", "beta_gpt4").is_between(0, 1).all()).row(0) == (
        True, True)


XW = pl.DataFrame({
    "o2010": ["11-1011.00", "11-1011.03", "15-1131.00", "15-1132.00", "29-1060.00"],
    "o2019": ["11-1011.00", "11-1011.03", "15-1252.00", "15-1252.00", "29-1061.00"],
})
XW2 = pl.DataFrame({"o2010": ["29-1060.00", "29-1060.00"],
                    "o2019": ["29-1061.00", "29-1062.00"]})


def test_vintage_merge_takes_simple_mean_and_split_copies():
    aioe = pl.DataFrame({"soc6": ["15-1131", "15-1132", "11-1011"], "aioe": [1.0, 3.0, 0.5]})
    out = map_soc2010_to_2018(aioe, XW).sort("soc6")
    assert out.to_dicts() == [{"soc6": "11-1011", "aioe": 0.5}, {"soc6": "15-1252", "aioe": 2.0}]
    split = map_soc2010_to_2018(pl.DataFrame({"soc6": ["29-1060"], "aioe": [2.0]}), XW2)
    assert sorted(split["soc6"]) == ["29-1061", "29-1062"] and split["aioe"].to_list() == [2.0, 2.0]


def test_unmapped_2010_code_is_reported_not_dropped_silently():
    with pytest.raises(ValueError, match="99-9999"):
        map_soc2010_to_2018(pl.DataFrame({"soc6": ["99-9999"], "aioe": [1.0]}), XW)


def test_to_oews_means_over_codes_sharing_an_oews_code():
    df = pl.DataFrame({"soc6": ["15-1252", "15-1253", "11-1011"], "x": [1.0, 3.0, 5.0]})
    out = to_oews(df, ["x"], {"15-1250", "11-1011"}).sort("soc6")
    assert out.to_dicts() == [{"soc6": "11-1011", "x": 5.0}, {"soc6": "15-1250", "x": 2.0}]


def test_rank_correlations_spearman():
    b = pl.DataFrame({"ff49": [1, 2, 3, 4], "z_aioe": [1.0, 2.0, 3.0, 4.0],
                      "z_eloundou": [4.0, 3.0, 2.0, 1.0]})
    e = pl.DataFrame({"ff49": [1, 2, 3, 4], "z_delegation": [10.0, 20.0, 30.0, 40.0],
                      "z_usage": [1.0, 3.0, 2.0, 4.0]})
    r = rank_correlations(b, e).to_dicts()
    got = {(d["benchmark"], d["aei"]): d["spearman"] for d in r}
    assert got[("z_aioe", "z_delegation")] == pytest.approx(1.0)
    assert got[("z_eloundou", "z_delegation")] == pytest.approx(-1.0)
    assert got[("z_aioe", "z_usage")] == pytest.approx(0.8)


@pytest.mark.data
def test_aioe_coverage_of_national_employment_above_80pct():
    from aideleg.bls.oews import load_national

    nat = load_national(2024).filter(pl.col("tot_emp").is_not_null())
    out = to_oews(load_aioe(), ["aioe"], set(nat["soc6"]))
    hit = nat.filter(pl.col("soc6").is_in(out["soc6"].implode()))
    cov = hit["tot_emp"].sum() / nat["tot_emp"].sum()
    assert cov > 0.80


@pytest.mark.data
def test_benchmark_ff49_has_49_rows_or_reports_missing():
    b = benchmark_ff49()
    assert b.columns[:3] == ["ff49", "z_aioe", "z_eloundou"]
    assert b.height <= 49 and b["ff49"].is_unique().all()
    if b.height < 49:
        missing = set(range(1, 50)) - set(b["ff49"])
        assert missing, "fewer than 49 rows must be explained by missing codes"
        print("FF49 codes without a benchmark row:", sorted(missing))
    assert abs(b["z_aioe"].mean()) < 1e-9 and abs(b["z_aioe"].std(ddof=0) - 1) < 1e-9
