"""H6 talk index, AI-washing gap, Spearman CI and gap-return association (PAP §6, D18).

Synthetic data only: no market data, no derived files.
"""

import re
from datetime import date

import numpy as np
import polars as pl
import pytest
from scipy import stats as _st

from aideleg.h6 import talk
from aideleg.rq3 import data, inference

NAMES = pl.DataFrame({"ff49": [1, 2, 3], "ff49_short": ["Agric", "Food", "Soda"]})


def _grid(year: int, n_talk: list, n_filers: list) -> tuple[pl.DataFrame, pl.DataFrame]:
    ff = [1, 2, 3, None]
    num = pl.DataFrame(
        {"year": [year] * 4, "ff49": ff, "n_talk": n_talk, "n_exhibit_only": [0] * 4},
        schema={"year": pl.Int64, "ff49": pl.Int64, "n_talk": pl.Int64, "n_exhibit_only": pl.Int64},
    )
    den = pl.DataFrame(
        {"year": [year] * 4, "ff49": ff, "n_filers": n_filers},
        schema={"year": pl.Int64, "ff49": pl.Int64, "n_filers": pl.Int64},
    )
    return num, den


def test_talk_share_is_numerator_over_denominator():
    num, den = _grid(2024, [3, 0, 0, 1], [10, 4, 0, 5])
    t = talk.talk_table(num, den, names=NAMES)
    assert t.columns == ["year", "ff49", "ff49_short", "n_talk", "n_filers", "talk"]
    by = {r["ff49"]: r for r in t.iter_rows(named=True)}
    assert by[1]["talk"] == 0.3
    assert by[2]["talk"] == 0.0
    assert by[3]["talk"] is None
    assert by[None]["talk"] == 0.2 and by[None]["ff49_short"] is None
    assert talk.null_talk(t).to_dicts() == [{"year": 2024, "ff49_short": "Soda"}]


def test_talk_table_refuses_mismatched_grids():
    num, den = _grid(2024, [3, 0, 0, 1], [10, 4, 0, 5])
    with pytest.raises(ValueError):
        talk.talk_table(num.filter(pl.col("ff49") != 2), den, names=NAMES)
    with pytest.raises(ValueError):
        talk.talk_table(num.with_columns(pl.lit(11, pl.Int64).alias("n_talk")), den, names=NAMES)


def test_pooled_counts_every_filer_including_unmapped():
    num, den = _grid(2024, [3, 0, 0, 1], [10, 4, 0, 5])
    p = talk.pooled(talk.talk_table(num, den, names=NAMES))
    r = p.row(0, named=True)
    assert r["n_talk"] == 4 and r["n_filers"] == 19
    assert r["talk"] == 4 / 19
    assert r["talk_mapped"] == 3 / 14
    assert r["unmapped_share"] == 5 / 19


def _expo(n: int, seed: int = 3) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(n)
    return pl.DataFrame({"ff49_short": [f"I{i}" for i in range(n)], "z_usage": z})


def _T(n: int, seed: int = 4, null: tuple[int, ...] = ()) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    t = rng.uniform(0.0, 0.6, n).tolist()
    for i in null:
        t[i] = None
    return pl.DataFrame(
        {"ff49_short": [f"I{i}" for i in range(n)], "T": t},
        schema={"ff49_short": pl.String, "T": pl.Float64},
    )


def test_gap_is_standardised_residual():
    g = talk.gap(_T(20), _expo(20))
    assert g.columns == ["ff49_short", "T", "zT", "z_usage", "resid", "gap"]
    gap = g["gap"].to_numpy()
    assert abs(gap.mean()) < 1e-12
    assert abs(gap.std(ddof=0) - 1.0) < 1e-12
    assert abs(np.corrcoef(gap, g["z_usage"].to_numpy())[0, 1]) < 1e-12
    zT = g["zT"].to_numpy()
    assert abs(zT.mean()) < 1e-12 and abs(zT.std(ddof=0) - 1.0) < 1e-12
    assert g["gap"].to_list() == sorted(g["gap"].to_list(), reverse=True)


def test_gap_drops_null_T_and_refuses_missing_usage():
    g = talk.gap(_T(20, null=(2, 5)), _expo(20))
    assert g.height == 18 and not {"I2", "I5"} & set(g["ff49_short"].to_list())
    assert abs(g["gap"].to_numpy().std(ddof=0) - 1.0) < 1e-12
    with pytest.raises(ValueError):
        talk.gap(_T(20), _expo(19))


def test_spearman_ci_reproducible():
    rng = np.random.default_rng(1)
    x = rng.standard_normal(30)
    y = 0.5 * x + rng.standard_normal(30)
    a = talk.spearman_ci(x, y, n_draws=500)
    b = talk.spearman_ci(x, y, n_draws=500)
    assert a == b
    assert abs(a["rho"] - _st.spearmanr(x, y).statistic) < 1e-12
    lo, hi = a["ci95"]
    assert lo < a["rho"] < hi
    m = talk.spearman_ci(np.arange(10.0), np.arange(10.0) ** 3, n_draws=200)
    assert m["rho"] == 1.0
    assert m["ci95"] == (1.0, 1.0)


def test_spearman_ci_counts_undefined_draws():
    r = talk.spearman_ci(np.array([0.0, 0.0, 1.0]), np.array([1.0, 2.0, 3.0]), n_draws=400)
    assert r["n_nan"] > 0
    assert np.isfinite(r["ci95"][0]) and np.isfinite(r["ci95"][1])


def _gap_df(names: list[str]) -> pl.DataFrame:
    rng = np.random.default_rng(9)
    g = rng.standard_normal(len(names))
    return pl.DataFrame({"ff49_short": names, "gap": g}).sort("gap", descending=True)


def _fake_vector_test(record):
    def spy(alphas, z, names, control=None, hist=None):
        record.update(
            alphas=np.asarray(alphas),
            z=np.asarray(z),
            names=list(names),
            control=control,
            hist=hist,
        )
        return {
            "b": 0.01,
            "s": 0.02,
            "bbar": 0.005,
            "q_0.975": 2.0,
            "crit_0.05": 2.1,
            "T_bbar": 0.25,
            "p_bbar": 0.8,
            "T_zero": 0.5,
            "p_zero": 0.6,
            "ci_0.05": (-0.032, 0.052),
            "n": len(names),
            "dropped": [],
        }

    return spy


def test_gap_return_test_uses_vector_test(monkeypatch):
    cols = ["I3", "I0", "I2", "I1", "I4"]  # return-column order
    alphas = np.array([0.03, 0.00, 0.02, 0.01, 0.04])
    monkeypatch.setattr(talk, "_window_alphas", lambda: (alphas, cols))
    rec: dict = {}
    monkeypatch.setattr(inference, "vector_test", _fake_vector_test(rec))
    g = _gap_df(["I0", "I1", "I2", "I3"])  # I4 has no gap (no T)
    res = talk.gap_returns(g)
    by = dict(zip(g["ff49_short"].to_list(), g["gap"].to_list(), strict=True))
    assert rec["names"] == ["I3", "I0", "I2", "I1"]
    assert rec["z"].tolist() == [by[n] for n in rec["names"]]
    assert rec["alphas"].tolist() == [0.03, 0.00, 0.02, 0.01]
    assert rec["control"] is None and rec["hist"] is None
    assert res["no_gap"] == ["I4"]
    assert res["b"] == 0.01


def test_gap_return_refuses_gap_industry_without_return(monkeypatch):
    monkeypatch.setattr(talk, "_window_alphas", lambda: (np.zeros(2), ["I0", "I1"]))
    with pytest.raises(ValueError):
        talk.gap_returns(_gap_df(["I0", "I1", "I9"]))


def _filers_hits(n_ind: int = 12):
    """Synthetic filers (years 2019-2025, FF49 1..n_ind plus unmapped) and FTS hits."""
    rng = np.random.default_rng(5)
    rows, hits = [], []
    cik = 1
    for y in range(2019, 2026):
        for ff in [*range(1, n_ind + 1), None]:
            for _ in range(int(rng.integers(3, 8))):
                rows.append(
                    {
                        "year": y,
                        "cik": cik,
                        "adsh": f"a{cik}",
                        "form": "10-K",
                        "date_filed": date(y, 3, 1),
                        "sic": None if ff is None else 100,
                        "ff49": ff,
                    }
                )
                if rng.random() < 0.2 + 0.05 * (y - 2019):
                    hits.append(
                        {
                            "phrase": "machine learning",
                            "cik": cik,
                            "adsh": f"a{cik}",
                            "form": "10-K",
                            "file_type": "10-K",
                            "file_date": date(y, 3, 1),
                        }
                    )
                cik += 1
    filers = pl.DataFrame(
        rows,
        schema={
            "year": pl.Int64,
            "cik": pl.Int64,
            "adsh": pl.String,
            "form": pl.String,
            "date_filed": pl.Date,
            "sic": pl.Int64,
            "ff49": pl.Int64,
        },
    )
    hits = pl.DataFrame(
        hits,
        schema={
            "phrase": pl.String,
            "cik": pl.Int64,
            "adsh": pl.String,
            "form": pl.String,
            "file_type": pl.String,
            "file_date": pl.Date,
        },
    )
    return filers, hits


def _patch_run(monkeypatch, n_ind: int = 12):
    names = pl.DataFrame(
        {"ff49": list(range(1, 50)), "ff49_short": [f"I{i}" for i in range(1, 50)]}
    )
    monkeypatch.setattr(talk, "_ff49_names", lambda: names)
    rng = np.random.default_rng(8)
    expo = pl.DataFrame(
        {
            "design": ["B"] * 49,
            "ff49": list(range(1, 50)),
            "ff49_short": [f"I{i}" for i in range(1, 50)],
            "z_delegation": rng.standard_normal(49),
            "z_usage": rng.standard_normal(49),
            "z_aioe": rng.standard_normal(49),
        }
    )
    alphas = rng.normal(0, 0.05, 49)
    monkeypatch.setattr(data, "exposures", lambda: expo)
    monkeypatch.setattr(
        data,
        "zero_assigned",
        lambda: pl.DataFrame(
            {"design": ["B", "A_r2", "A_pooled"], "no_usage_emp_pct": [1.25, 2.0, 3.0]}
        ),
    )
    monkeypatch.setattr(talk, "_window_alphas", lambda: (alphas, [f"I{i}" for i in range(1, 50)]))
    rec: dict = {}
    monkeypatch.setattr(inference, "vector_test", _fake_vector_test(rec))
    return _filers_hits(n_ind), rec


def test_h6_docs_labelled(monkeypatch, tmp_path):
    (filers, hits), _ = _patch_run(monkeypatch)
    talk.run_talk(tmp_path, filers=filers, hits=hits, n_draws=200)
    for name in ("talk_index.md", "gap.md", "gap_returns.md"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "exploratory (PAP §6, D18)" in text.splitlines()[0], name
        assert text.count(talk.WORDING) == 1, name
    gap_md = (tmp_path / "gap.md").read_text(encoding="utf-8")
    assert "Zero-assigned employment share, Design B: 1.25% (D3)" in gap_md
    assert "Zero-assigned employment share, Design B: 1.25% (D3)" in (
        tmp_path / "gap_returns.md"
    ).read_text(encoding="utf-8")
    t = pl.read_csv(tmp_path / "talk_index.csv")
    assert t.columns == ["year", "ff49", "ff49_short", "n_talk", "n_filers", "talk"]
    assert sorted(set(t["year"].to_list())) == list(range(2019, 2026))
    g = pl.read_csv(tmp_path / "gap.csv")
    assert g.columns == ["ff49_short", "T", "zT", "z_usage", "resid", "gap"]
    assert g.height == 12  # industries 13..49 have no 2024 filer: T null, listed, not in gap
    assert "| talk filers 2024 | filers 2024 |" in gap_md
    assert "I13" in gap_md and "unmapped" in (tmp_path / "talk_index.md").read_text()


def test_figures_go_to_fig_dir_only(monkeypatch, tmp_path):
    (filers, hits), _ = _patch_run(monkeypatch)
    out, figs = tmp_path / "out", tmp_path / "figs"
    talk.run_talk(out, filers=filers, hits=hits, n_draws=200)
    assert not figs.exists()
    talk.run_talk(out, filers=filers, hits=hits, n_draws=200, fig_dir=figs)
    assert {p.name for p in figs.iterdir()} == {
        f"{n}.{e}" for n in (talk.FIG_BY_YEAR, talk.FIG_VS_USAGE) for e in ("pdf", "png")
    }


def test_rerun_is_byte_identical(monkeypatch, tmp_path):
    (filers, hits), _ = _patch_run(monkeypatch)
    talk.run_talk(tmp_path / "a", filers=filers, hits=hits, n_draws=200)
    talk.run_talk(tmp_path / "b", filers=filers, hits=hits, n_draws=200)
    for p in (tmp_path / "a").iterdir():
        assert p.read_bytes() == (tmp_path / "b" / p.name).read_bytes(), p.name


def test_summary_heading_and_links_without_estimates(monkeypatch, tmp_path):
    (filers, hits), _ = _patch_run(monkeypatch)
    talk.run_talk(tmp_path, filers=filers, hits=hits, n_draws=200)
    path = talk.write_summary(tmp_path)
    text = path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "# H6: talk vs use (exploratory, PAP §6, D18)"
    for name in ("talk_index.md", "gap.md", "gap_returns.md"):
        assert f"]({name})" in text
    assert re.search(r"\d\.\d|\d%", text.replace(talk.WORDING, "").replace("§3.1", "")) is None
