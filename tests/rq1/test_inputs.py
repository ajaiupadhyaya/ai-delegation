import json
from datetime import date
from pathlib import Path

import openpyxl
import polars as pl
import pytest

from aideleg.bls.oews import A_MEDIAN_TOPCODE, load_national, load_national_wages
from aideleg.config import DERIVED, RAW
from aideleg.rq1 import inputs
from aideleg.rq1.result import Coef, HypothesisResult

APR, MAY = date(2026, 4, 1), date(2026, 5, 1)


def _wide(rows):
    return pl.DataFrame(rows, schema={"task": pl.String, "period_start": pl.Date,
                                      "pct": pl.Float64, "automation": pl.Float64},
                        orient="row")


def _mean(rows, n=2):
    return inputs.two_month_mean(_wide(rows), ["automation"], key=["task"], n_periods=n).row(
        0, named=True)


def test_two_month_mean_skips_unpublished_month():
    both = _mean([("t", APR, 3.0, 60.0), ("t", MAY, 1.0, 20.0)])
    assert both["automation"] == pytest.approx(50.0) and both["weight"] == pytest.approx(2.0)
    no_val = _mean([("t", APR, 3.0, 60.0), ("t", MAY, 1.0, None)])
    assert no_val["automation"] == pytest.approx(60.0) and no_val["weight"] == pytest.approx(2.0)
    no_pct = _mean([("t", APR, 3.0, 60.0), ("t", MAY, None, 20.0)])
    assert no_pct["automation"] == pytest.approx(60.0) and no_pct["weight"] == pytest.approx(1.5)


def test_two_month_mean_all_missing_value_is_null():
    r = _mean([("t", APR, 3.0, None), ("t", MAY, 1.0, None)])
    assert r["automation"] is None and r["weight"] == pytest.approx(2.0)


def test_two_month_mean_single_period():
    r = _mean([("t", APR, 3.0, 60.0)], n=1)
    assert r["automation"] == pytest.approx(60.0) and r["weight"] == pytest.approx(3.0)


def test_task_families_split_and_levels(tmp_path):
    t2d = tmp_path / "t2d.txt"
    t2d.write_text(
        "O*NET-SOC Code\tTask ID\tDWA ID\tDate\tDomain Source\r\n"
        "11-1011.00\t1\tA.I01.D01\t07/2014\tAnalyst\r\n"
        "11-1011.00\t1\tA.I02.D01\t07/2014\tAnalyst\r\n"
        "11-1011.00\t1\tA.I01.D02\t07/2014\tAnalyst\r\n"
        "11-1011.00\t1\tA.I01.D02\t07/2014\tAnalyst\r\n"
        "11-1011.00\t2\tA.I01.D01\t07/2014\tAnalyst\r\n", encoding="utf-8")
    ref = tmp_path / "ref.txt"
    ref.write_text(
        "Element ID\tIWA ID\tDWA ID\tDWA Title\r\n"
        'A\tA.I01\tA.I01.D01\tReview "art".\r\n'
        "A\tA.I01\tA.I01.D02\tStudy.\r\n"
        "A\tA.I02\tA.I02.D01\tOther.\r\n", encoding="utf-8")
    kw = dict(tasks_to_dwas=t2d, dwa_reference=ref)
    iwa = inputs.task_families("iwa", **kw).filter(pl.col("task_id") == 1)
    assert sorted(iwa["family"]) == ["A.I01", "A.I02"]
    gwa = inputs.task_families("gwa", **kw).filter(pl.col("task_id") == 1)
    assert gwa["family"].to_list() == ["A"]
    assert len(inputs.task_families("dwa", **kw).filter(pl.col("task_id") == 1)) == 3
    schema = inputs.task_families("iwa", **kw).schema
    assert schema == {"task_id": pl.Int64, "family": pl.String}
    assert 3 not in inputs.task_families("iwa", **kw)["task_id"].to_list()


def test_error_cost_indicator():
    yes = ["23-1011", "29-1141", "13-2011", "11-3031", "41-3031"]
    no = ["13-1111", "11-3021", "41-2031", "15-1252"]
    out = inputs.error_cost_indicator(pl.Series("soc6", yes + no))
    assert out.dtype == pl.Int8
    assert out.to_list() == [1] * 5 + [0] * 4


def test_log_wage_table():
    import math
    w = pl.DataFrame({"soc6": ["a", "b", "c"], "tot_emp": [1, 2, 3],
                      "a_median": [50000.0, 239200.0, None],
                      "a_median_status": ["published", "topcoded", "suppressed"]})
    t = inputs.log_wage_table(w)
    assert t.columns == ["soc6", "log_wage", "wage_status"]
    assert t["log_wage"].to_list() == [math.log(50000.0), math.log(239200.0), None]
    assert t["wage_status"].to_list() == ["published", "topcoded", "suppressed"]


COLS = ["AREA", "NAICS", "NAICS_TITLE", "I_GROUP", "OWN_CODE", "OCC_CODE", "OCC_TITLE",
        "O_GROUP", "TOT_EMP", "A_MEDIAN"]


def _xlsx(path: Path) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(COLS)
    for occ, med in [("11-1011", "50000"), ("11-1021", "#"), ("15-1252", "*"),
                     ("15-1211", "**"), ("15-1299", "")]:
        ws.append(["99", "000000", "x", "cross", "1235", occ, "T", "detailed", "100", med])
    ws.append(["99", "000000", "x", "cross", "1235", "11-0000", "T", "major", "100", "70000"])
    wb.save(path)
    return path


def test_wages_topcode_and_suppression(tmp_path):
    w = load_national_wages(path=_xlsx(tmp_path / "n.xlsx"))
    assert list(w.columns) == ["soc6", "tot_emp", "a_median", "a_median_status"]
    assert w.schema["tot_emp"] == pl.Int64 and w.schema["a_median"] == pl.Float64
    w = w.sort("soc6")
    assert "11-0000" not in w["soc6"].to_list()
    assert w["a_median"].to_list() == [50000.0, 239200.0, None, None, None]
    assert w["a_median_status"].to_list() == ["published", "topcoded", "suppressed",
                                              "suppressed", "suppressed"]
    assert A_MEDIAN_TOPCODE[2024] == 239_200.0
    with pytest.raises(KeyError):
        load_national_wages(2023, path=_xlsx(tmp_path / "n2.xlsx"))


def test_load_national_unchanged(tmp_path):
    nat = load_national(path=_xlsx(tmp_path / "n.xlsx")).sort("soc6")
    assert nat["a_median"].to_list() == [50000.0, None, None, None, None]


def test_hypothesis_result_to_dict_is_json_safe():
    r = HypothesisResult(
        hypothesis="H1", outcome="automation", p_family=0.0123,
        coefs={"b": Coef("b", 0.5, 0.1, 0.3, 0.7, 0.01, None),
               "c": Coef("c", -1.0, 0.2, -1.4, -0.6, 0.02, 40)},
        sample={"n": 12, "share": 0.5}, drops={"suppressed": 1.5},
        diagnostics={"k": [1, 2], "d": {"a": 1.0}}, notes=["x"])
    d = json.loads(json.dumps(r.to_dict()))
    assert d["p_family"] == 0.0123
    assert d["coefs"]["c"]["df"] == 40 and d["coefs"]["b"]["df"] is None
    from dataclasses import FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        r.coefs["b"].estimate = 1.0  # type: ignore[misc]


_PANEL = DERIVED / "aei_panel.parquet"
_NEEDS = pytest.mark.skipif(not _PANEL.exists() or not (RAW / "onet").exists(),
                            reason="needs the panel and O*NET files")


@pytest.mark.data
@_NEEDS
def test_real_families_cover_r6_tasks():
    p = pl.read_parquet(_PANEL).filter(
        (pl.col("release") == "r6") & (pl.col("source") == "claude_ai")
        & (pl.col("geo_level") == "global") & (pl.col("taxonomy") == "onet_task")
        & (pl.col("metric") == "pct") & ~pl.col("node_id").str.starts_with("unmatched:"))
    w = inputs.two_month_mean(p.with_columns(pct=pl.col("value")).with_columns(v=pl.col("value")),
                              ["v"], key=["node_id"], n_periods=2)
    w = w.with_columns(task_id=pl.col("node_id").cast(pl.Int64, strict=False)).drop_nulls("task_id")
    fam = inputs.task_families("iwa")["task_id"].unique()
    share = w.filter(pl.col("task_id").is_in(fam.to_list()))["weight"].sum() / w["weight"].sum()
    print(f"r6 claude_ai matched-task D13 weight with an IWA: {share:.4f}")
    assert share >= 0.9


@pytest.mark.data
def test_real_topcoded_count():
    try:
        w = load_national_wages(2024)
    except FileNotFoundError:
        pytest.skip("OEWS 2024 not downloaded")
    n = w.filter(pl.col("a_median_status") == "topcoded").height
    print(f"topcoded 2024 occupations: {n}")
    assert n >= 1

