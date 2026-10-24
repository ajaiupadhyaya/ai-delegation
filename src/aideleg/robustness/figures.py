"""Forest plots of the robustness rows (Plan 4 Task 15): `fig_robustness_market` (H5, H5b)
and `fig_robustness_rq1` (the RQ1 coefficients).

One point per row and part with its interval, and the primary's interval as a band with its
estimate as a line. No significance marker and no count (PAP §8.1). Market intervals are the
c_0.05 intervals of the row files; RQ1 intervals are the 95% intervals of the row files.
"""

import math
from pathlib import Path

import polars as pl
from matplotlib.figure import Figure

from aideleg.figures.save import FIGURES_DIR, save_figure
from aideleg.figures.style import FIGSIZE, PALETTE, apply_style
from aideleg.robustness import appendix, registry, report

NAMES = ("fig_robustness_market", "fig_robustness_rq1")
_RQ1 = ("H1", "H2", "H3", "H4")


def _panel_key(df: pl.DataFrame) -> pl.DataFrame:
    return df if "panel" in df.columns else df.with_columns(pl.col("applies_to").alias("panel"))


def forest(
    records: pl.DataFrame, primary: dict[str, tuple[float, float, float]], title: str
) -> Figure:
    """One panel per key of `primary` (in its order); in each, one point per (row, part) of the
    records whose `panel` (default: `applies_to`) is that key, with its interval, and the
    primary's interval as a shaded band and its estimate as a vertical line."""
    apply_style()
    df = _panel_key(records)
    keys = list(primary)
    ncols = 1 if len(keys) == 1 else 2
    nrows = math.ceil(len(keys) / ncols)
    sizes = [df.filter(pl.col("panel") == k).height for k in keys]
    per_row = max(sizes or [1])
    width = FIGSIZE["double"][0] if ncols == 2 else FIGSIZE["single"][0] * 1.4
    fig = Figure(figsize=(width, nrows * (0.15 * per_row + 1.0) + 0.4))
    axes = fig.subplots(nrows, ncols, squeeze=False).ravel()
    for ax, key in zip(axes, keys, strict=False):
        sub = df.filter(pl.col("panel") == key)
        est, lo, hi = primary[key]
        ax.axvspan(lo, hi, color=PALETTE[2], alpha=0.25, lw=0, label="primary interval")
        ax.axvline(est, color=PALETTE[5], lw=0.8, label="primary estimate")
        labels, ys = [], []
        for i, r in enumerate(sub.iter_rows(named=True)):
            labels.append(f"{registry.output_stem(r['row_id'])} {r['part']}")
            ys.append(i)
            x, a, b = r["estimate"], r["ci_lo"], r["ci_hi"]
            if a is not None and b is not None:
                ax.errorbar(
                    x, i, xerr=[[x - a], [b - x]], fmt="o", ms=2.5, lw=0.8, color=PALETTE[0]
                )
            else:
                ax.plot(x, i, "o", ms=2.5, color=PALETTE[0])
        ax.set_yticks(ys, labels, fontsize=6)
        ax.invert_yaxis()
        ax.set_title(key, fontsize=8)
        units = sorted({u for u in sub["unit"].to_list() if u})
        ax.set_xlabel("; ".join(units), fontsize=7)
    for ax in axes[len(keys) :]:
        ax.set_visible(False)
    fig.suptitle(title, fontsize=9)
    fig.tight_layout()
    return fig


def market_inputs() -> tuple[pl.DataFrame, dict[str, tuple[float, float, float]]]:
    """The H5/H5b records of the Plan 4 rows, and the primary b with its c_0.05 interval from
    `confirmatory_h5.md` (printed precision)."""
    recs = appendix.load_records().filter(
        pl.col("unit") == report.MARKET_UNIT, pl.col("applies_to").is_in(["H5", "H5b"])
    )
    h5 = appendix.h5_record()
    prim = {h: tuple(float(v) for v in h5[h]) for h in ("H5", "H5b")}
    return recs, prim


def rq1_inputs() -> tuple[pl.DataFrame, dict[str, tuple[float, float, float]]]:
    """The RQ1 records that stand beside a primary coefficient in the same units (as in
    `summary.md`), one panel per hypothesis and coefficient, with the primary's 95% interval
    from `confirmatory_rq1.json`."""
    recs = appendix.load_records().filter(
        pl.col("applies_to").is_in(list(_RQ1)), pl.col("estimate").is_not_null()
    )
    keep, panels = [], []
    prim: dict[str, tuple[float, float, float]] = {}
    for r in recs.iter_rows(named=True):
        p = appendix.primary_for(r)
        if p is None:
            continue
        name = appendix._RQ1_ALIAS.get((r["applies_to"], r["estimand"]), r["estimand"])
        key = f"{r['applies_to']}: {name}"
        prim.setdefault(key, (p.est, p.lo, p.hi))
        keep.append(r)
        panels.append(key)
    df = pl.DataFrame(keep, infer_schema_length=None).with_columns(pl.Series("panel", panels))
    order = sorted(prim, key=lambda k: (k.split(":")[0], list(prim).index(k)))
    return df, {k: prim[k] for k in order}


def write_figures(out_dir: Path = FIGURES_DIR) -> list[Path]:
    """Write the two forest figures (PDF and PNG) through `save_figure`."""
    out: list[Path] = []
    recs, prim = market_inputs()
    out += save_figure(
        forest(recs, prim, "Market robustness rows: slope and c_0.05 interval"),
        NAMES[0],
        out_dir=out_dir,
    )
    recs, prim = rq1_inputs()
    out += save_figure(
        forest(recs, prim, "RQ1 robustness rows: coefficient and 95% interval"),
        NAMES[1],
        out_dir=out_dir,
    )
    return out
