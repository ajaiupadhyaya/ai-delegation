"""RQ2 descriptives: could vs does. Synthetic inputs only; no test, no decision."""

import numpy as np
import polars as pl

from aideleg.audit import design_zero_assigned
from aideleg.config import SEED
from aideleg.describe import rq2
from aideleg.results import rq2 as rq2_report


def _frame(n=30, seed=1):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    return pl.DataFrame({"z_delegation": x, "z_aioe": x + rng.normal(size=n),
                         "z_eloundou": rng.normal(size=n)})


def test_spearman_point_matches_polars():
    df = _frame()
    idx = rq2.bootstrap_indices(df.height, designs=("B",), draws=200)["B"]
    pairs = [("z_delegation", "z_aioe"), ("z_delegation", "z_eloundou")]
    out = rq2.spearman_bootstrap(df, pairs, idx)
    assert out.columns == ["aei", "benchmark", "n", "spearman", "ci_low", "ci_high",
                           "n_draws_used"]
    for aei, bench, rho in zip(out["aei"], out["benchmark"], out["spearman"], strict=True):
        ref = df.select(pl.corr(aei, bench, method="spearman")).item()
        assert abs(rho - ref) < 1e-12
    assert out["n"].to_list() == [30, 30]
    assert (out["ci_low"] < out["spearman"]).all() or (out["ci_low"] <= out["spearman"]).all()
    assert (out["n_draws_used"] == 200).all()


def test_bootstrap_indices_deterministic_and_ordered():
    a = rq2.bootstrap_indices(20, draws=50)
    b = rq2.bootstrap_indices(20, draws=50)
    assert list(a) == ["B", "A_pooled"]
    for k in a:
        assert np.array_equal(a[k], b[k])
    rng = np.random.default_rng(SEED)
    rng.integers(0, 20, size=(50, 20))
    assert np.array_equal(a["A_pooled"], rng.integers(0, 20, size=(50, 20)))


def test_constant_draw_excluded():
    df = _frame(10)
    idx = rq2.bootstrap_indices(10, designs=("B",), draws=20)["B"].copy()
    idx[3, :] = 4  # one draw resamples a single industry: constant vectors
    out = rq2.spearman_bootstrap(df, [("z_delegation", "z_aioe")], idx)
    assert out["n_draws_used"].item() == 19


def _ex(names, vals, lb=None, ub=None):
    d = {"ff49": list(range(len(names))), "ff49_short": names, "z_delegation": vals,
         "E_delegation": vals, "emp_covered_share": [0.9] * len(names)}
    d["E_delegation_lb"] = lb or vals
    d["E_delegation_ub"] = ub or vals
    return pl.DataFrame(d)


def test_rank_gap_hand_case():
    ex = _ex(["a", "b", "c"], [3.0, 2.0, 1.0])
    bench = pl.DataFrame({"ff49": [0, 1, 2], "z_aioe": [1.0, 2.0, 3.0],
                          "z_eloundou": [0.0] * 3, "z_eloundou_gpt4": [0.0] * 3})
    g = rq2.rank_gaps(ex, bench, k=3)
    assert g.columns == ["ff49_short", "rank_does", "rank_could", "gap"]
    assert g["gap"].to_list() == [2, 0, -2]
    assert g["ff49_short"].to_list() == ["c", "b", "a"]  # lowest on does, highest on could
    assert g["rank_does"].to_list() == [3, 2, 1]


def test_bound_width_hand_case():
    ex = _ex(["a"], [1.2], lb=[1.0], ub=[1.5])
    occ = pl.DataFrame({"usage_share": [1.0, 1.0, 2.0], "automation_share_all_lb": [0.0, 0.0, 0.0],
                        "automation_share_all_ub": [0.1, 0.2, 0.3],
                        "D_lb": [1.0] * 3, "D_ub": [1.5, 2.0, 2.5]})
    f, s = rq2.bound_widths(ex, occ)
    assert abs(f["width"].item() - 0.5) < 1e-12
    assert abs(f["width_pct_of_E"].item() - 100 * 0.5 / 1.2) < 1e-9
    assert s.height == 2 and "p50" in s.columns and "p25" in s.columns and "p75" in s.columns


def test_docs_state_zero_assigned_share(tmp_path):
    rng = np.random.default_rng(3)
    n = 12
    names = [f"i{i}" for i in range(n)]
    ex_rows, occ_rows = [], []
    for design in ("B", "A_pooled", "A_r2"):
        z = rng.normal(size=n)
        ex_rows.append(_ex(names, z.tolist(), lb=(z - 0.1).tolist(), ub=(z + 0.1).tolist())
                       .with_columns(design=pl.lit(design), z_usage=pl.col("z_delegation"),
                                     z_augmentation=pl.col("z_delegation")))
        has = rng.random(40) > 0.3
        occ_rows.append(pl.DataFrame({
            "design": design, "tot_emp": rng.integers(10, 1000, 40), "has_usage": has,
            "usage_share": np.where(has, rng.random(40), 0.0),
            "automation_share_all_lb": 0.0, "automation_share_all_ub": rng.random(40),
            "D_lb": 1.0, "D_ub": 1.0 + rng.random(40)}))
    ex, occ = pl.concat(ex_rows), pl.concat(occ_rows)
    bench = pl.DataFrame({"ff49": list(range(n)), "z_aioe": rng.normal(size=n),
                          "z_eloundou": rng.normal(size=n), "z_eloundou_gpt4": rng.normal(size=n)})
    paths = rq2_report.report(tmp_path / "docs", tmp_path / "figs", exposure=ex, occ=occ,
                              bench=bench, draws=100)
    zero = design_zero_assigned(occ)
    share_b = zero.filter(pl.col("design") == "B")["no_usage_emp_pct"].item()
    text = (tmp_path / "docs" / "could_vs_does.md").read_text()
    assert f"{share_b:.2f}" in text
    assert "descriptive" in text and "exploratory; contains look-ahead (PAP §10, S3)" in text
    assert (tmp_path / "figs" / "fig_rq2_could_vs_does.png").exists()
    assert (tmp_path / "figs" / "fig_rq2_bound_widths.png").exists()
    csv = pl.read_csv(tmp_path / "docs" / "could_vs_does.csv")
    assert csv.columns[0] == "design" and csv.height == 2 * 3 * 3
    assert paths
