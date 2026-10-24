"""PAP §11 D-3: the post-result influence diagnostics (H1, H2, H6), with Plan 2's estimators
stubbed. Exploratory; not a decision."""

import math

import numpy as np
import polars as pl
import pytest
from scipy import stats

from aideleg.results.common import check_text
from aideleg.robustness import __main__ as cli
from aideleg.robustness import diagnostics as dg
from aideleg.robustness import upstream
from aideleg.robustness.upstream import Coef, HypothesisResult, TaskRows


def _coef(name: str, est: float, p: float = 0.5) -> Coef:
    return Coef(name, est, 1.0, est - 2, est + 2, p, 10)


# --- H1 ------------------------------------------------------------------------------------


def _task_rows() -> TaskRows:
    soc = ["15-1299", "15-1299", "15-1252", "25-4022", "27-3043", "27-3043", "41-2031"]
    w = [5.0, 3.0, 2.0, 4.0, 1.0, 1.0, 9.0]
    wage = [4.0, 4.0, 4.1, 3.5, 3.0, 3.0, float("nan")]  # the 41- row never enters H1
    return TaskRows(
        rows=pl.DataFrame(
            {
                "soc6": soc,
                "weight": w,
                "automation_pct": [10.0, 20, 30, 40, 50, 60, 70],
                "human_education_years_mean": [14.0, 15, 16, 13, 12, 12, 11],
                "log_wage": wage,
                "task_code": [0, 1, 2, 3, 4, 5, 6],
            }
        ),
        total_weight=25.0,
    )


def _stub_h1(tr: TaskRows) -> HypothesisResult:
    rows = tr.rows.filter(~pl.col("log_wage").is_nan())
    n = rows.height
    return HypothesisResult(
        hypothesis="H1",
        outcome="automation_pct",
        coefs={
            "human_education_years_mean": _coef("human_education_years_mean", -n, 0.2),
            "log_wage": _coef("log_wage", float(rows["weight"].sum()), 0.3),
        },
        p_family=0.3,
        sample={"n_rows": n, "n_tasks": n, "n_occ": rows["soc6"].n_unique()},
    )


def test_h1_sample_weights_rank_the_rows_that_enter_h1():
    w = dg.h1_sample_weights(_task_rows())
    assert w["soc6"].to_list() == ["15-1299", "25-4022", "15-1252", "27-3043"]
    assert math.isclose(w["share_pct"].sum(), 100.0)
    assert math.isclose(w["share_pct"][0], 8 / 16 * 100)


def test_h1_influence_leaves_out_each_major_group_and_the_top_k():
    df = dg.h1_influence(_task_rows(), estimate=_stub_h1)
    assert df.columns == dg.H1_COLUMNS
    parts = list(zip(df["part"], df["dropped"], strict=True))
    assert parts == [
        ("primary", "none"),
        ("leave_out_soc_major", "15"),
        ("leave_out_soc_major", "25"),
        ("leave_out_soc_major", "27"),
        ("leave_out_soc_major", "41"),
        ("leave_out_top_1", "15-1299"),
        ("leave_out_top_3", "15-1299, 25-4022, 15-1252"),
    ]
    by = {d: r for d, r in zip(df["dropped"], df.iter_rows(named=True), strict=True)}
    assert by["none"]["beta_w"] == 16.0 and by["none"]["dropped_weight_pct"] == 0.0
    assert by["15"]["beta_w"] == 6.0 and math.isclose(by["15"]["dropped_weight_pct"], 62.5)
    assert by["41"]["beta_w"] == 16.0 and by["41"]["dropped_weight_pct"] == 0.0
    assert by["15-1299"]["beta_w"] == 8.0 and by["15-1299"]["n_occ"] == 3
    assert by["15-1299, 25-4022, 15-1252"]["beta_w"] == 2.0
    assert by["15-1299, 25-4022, 15-1252"]["p_H1"] == 0.3


# --- H2 ------------------------------------------------------------------------------------


def _h2_frame(tasks: dict[str, tuple[str, ...]], weights: dict[str, float]) -> pl.DataFrame:
    t = {"r2": 0.0, "r3": 0.4, "r4": 0.7, "r5": 0.9}
    recs = [
        {"task_node": k, "release": r, "t": t[r], "automation_pct": 10.0 + i, "weight": weights[k]}
        for k, rels in tasks.items()
        for i, r in enumerate(rels)
    ]
    return pl.DataFrame(recs)


def _stub_h2(df: pl.DataFrame) -> HypothesisResult:
    rels = df["release"].n_unique()
    if "r2" not in set(df["release"]):
        raise ValueError("stub: no r2")
    return HypothesisResult(
        hypothesis="H2",
        outcome="automation_pct",
        coefs={"trend": _coef("trend", float(rels), 0.01)},
        p_family=0.01,
        diagnostics={"p_wild": 0.5, "n_wild_draws": 6**rels},
    )


def test_h2_influence_leaves_out_each_release_and_counts_the_balancing():
    all4 = ("r2", "r3", "r4", "r5")
    bal = _h2_frame({"a": all4, "b": all4}, {"a": 2.0, "b": 1.0})
    unb = _h2_frame({"a": all4, "b": all4, "c": ("r2", "r3"), "d": ("r3", "r4", "r5")},
                    {"a": 2.0, "b": 1.0, "c": 0.5, "d": 0.5})  # fmt: skip
    df = dg.h2_influence(bal, unb, estimate=_stub_h2)
    assert df.columns == dg.H2_COLUMNS
    assert df["part"].to_list() == ["primary", *["leave_out_release"] * 4, "balancing_removed"]
    rows = df.iter_rows(named=True)
    prim, *loo, balance = rows
    assert prim["beta"] == 4.0 and prim["n_wild_draws"] == 1296 and prim["n_rows"] == 8
    assert [r["dropped"] for r in loo] == list(all4)
    r2 = loo[0]
    assert r2["beta"] is None and r2["note"].startswith("undefined: stub: no r2")
    assert r2["releases"] == "r3 r4 r5" and r2["n_tasks"] == 2
    assert loo[1]["beta"] == 3.0
    assert loo[1]["note"] == "smallest attainable wild bootstrap p = 6/216"
    assert balance["n_tasks"] == 2 and balance["n_rows"] == 5
    assert math.isclose(balance["usage_share_pct"], 1.0 / 4.0 * 100)
    assert "of 4 tasks and 13 rows" in balance["note"]


# --- H6 ------------------------------------------------------------------------------------


def test_spearman_p_nominal_is_the_t_approximation():
    rng = np.random.default_rng(1)
    x = rng.normal(size=30)
    y = x + rng.normal(size=30)
    res = stats.spearmanr(x, y)
    assert math.isclose(dg.spearman_p_nominal(res.statistic, 30), res.pvalue, rel_tol=1e-10)
    assert dg.spearman_p_nominal(1.0, 10) == 0.0
    with pytest.raises(ValueError):
        dg.spearman_p_nominal(0.5, 2)


def _gap() -> pl.DataFrame:
    rng = np.random.default_rng(2)
    u = rng.normal(size=12)
    return pl.DataFrame(
        {
            "ff49_short": [f"I{i:02d}" for i in range(12)][::-1],
            "T": (u + rng.normal(size=12)).tolist(),
            "z_usage": u.tolist(),
        }
    )


def test_h6_influence_primary_and_leave_one_out():
    g = _gap()
    df = dg.h6_influence(g)
    assert df.columns == dg.H6_COLUMNS
    assert df.height == 13
    prim = df.row(0, named=True)
    rho = stats.spearmanr(g["T"], g["z_usage"]).statistic
    assert math.isclose(prim["rho"], rho, rel_tol=1e-12) and prim["n"] == 12
    assert math.isclose(prim["p_nominal"], dg.spearman_p_nominal(rho, 12))
    assert prim["p_method"] == dg.P_METHOD
    loo = df.slice(1)
    assert loo["dropped"].to_list() == sorted(g["ff49_short"].to_list())
    assert loo["p_nominal"].null_count() == 12 and set(loo["n"]) == {11}
    keep = g.filter(pl.col("ff49_short") != "I05")
    want = stats.spearmanr(keep["T"], keep["z_usage"]).statistic
    got = loo.filter(pl.col("dropped") == "I05")["rho"][0]
    assert math.isclose(got, want, rel_tol=1e-12)


# --- documents and CLI ---------------------------------------------------------------------


def _docs() -> list[str]:
    all4 = ("r2", "r3", "r4", "r5")
    bal = _h2_frame({"a": all4}, {"a": 1.0})
    unb = _h2_frame({"a": all4, "c": ("r2", "r3")}, {"a": 1.0, "c": 1.0})
    return [
        dg.h1_md(dg.h1_influence(_task_rows(), estimate=_stub_h1)),
        dg.h2_md(dg.h2_influence(bal, unb, estimate=_stub_h2)),
        dg.h6_md(dg.h6_influence(_gap())),
    ]


@pytest.mark.parametrize("i", [0, 1, 2])
def test_docs_are_labelled_and_never_decide(i):
    text = _docs()[i]
    first = text.splitlines()[0]
    assert first.startswith("# ") and "post-result diagnostic (PAP §11 D-3)" in first
    assert dg.LABEL in text and "exploratory; not a decision" in text
    assert text.rstrip("\n").splitlines()[-1] == upstream.WORDING
    check_text(text)  # no forbidden phrase, no starred cell
    low = text.replace(upstream.WORDING, "").lower()
    for word in ("significan", "rejected", "supported", "contradict"):
        assert word not in low, word


def test_cli_diagnostics_flag(monkeypatch, capsys, tmp_path):
    p = tmp_path / "x.md"
    monkeypatch.setattr(dg, "write_all", lambda: [p])
    cli.main(["--diagnostics"])
    assert capsys.readouterr().out.strip() == str(p)
