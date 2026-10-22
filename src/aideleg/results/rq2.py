"""RQ2 reporting: could vs does, top/bottom industries, rank gaps and bound widths.

RQ2 is descriptive. There is no hypothesis test and no decision. Writes under `docs/results/rq2/`
(`could_vs_does`, `top_bottom`, `rank_gaps`, `bounds` as .md and .csv, plus `README.md`) and two
figures, `fig_rq2_could_vs_does` and `fig_rq2_bound_widths`. Floats in CSVs are rounded to 10
significant digits so that regeneration is bit-stable.
"""

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from aideleg.audit import design_zero_assigned
from aideleg.config import DERIVED, ROOT
from aideleg.describe import rq2
from aideleg.figures import FIGSIZE, PALETTE, apply_style, save_figure
from aideleg.figures.save import FIGURES_DIR
from aideleg.results.common import generated_line, write_result_doc
from aideleg.results.common import write_csv as _write_csv

GENERATOR = "aideleg.results.rq2"
OUT_DIR = ROOT / "docs/results/rq2"
DESIGNS = ("B", "A_pooled")
EXPLORATORY = "exploratory; contains look-ahead (PAP §10, S3)"
FIG_COULD, FIG_WIDTHS = "fig_rq2_could_vs_does", "fig_rq2_bound_widths"
DESCRIPTIVE = ("RQ2 is descriptive. Nothing in this document is a hypothesis test or a decision; "
               "the Spearman intervals are industry-bootstrap percentile intervals "
               "(2.5th and 97.5th percentiles) that describe spread.")
HEADLINE = ("`z_eloundou` (Eloundou et al. human beta) is the headline benchmark; "
            "`z_eloundou_gpt4` (GPT-4 beta) is shown beside it. `z_aioe` is the AIOE benchmark.")
RANK_NOTE = ("Rank 1 is the highest value. `gap = rank_does - rank_could`: a positive gap means "
             "the industry ranks lower on the AEI measure than on the benchmark.")


def _round10(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        pl.col(c).map_elements(lambda v: float(f"{v:.10g}"), return_dtype=pl.Float64)
        for c, t in df.schema.items() if t == pl.Float64)


def write_csv(df: pl.DataFrame, path: Path) -> Path:
    return _write_csv(_round10(df), path)


def _cell(v, digits: int) -> str:
    if v is None:
        return "—"
    return f"{v:.{digits}f}" if isinstance(v, float) else str(v)


def md_table(df: pl.DataFrame, digits: int = 3) -> str:
    out = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * df.width]
    out += ["| " + " | ".join(_cell(v, digits) for v in row) + " |" for row in df.iter_rows()]
    return "\n".join(out)


def zero_assigned_note(occ: pl.DataFrame, designs=DESIGNS) -> str:
    """The zero-assigned employment share per design (D3), computed by `audit`."""
    z = design_zero_assigned(occ)
    lines = []
    for d in designs:
        r = z.filter(pl.col("design") == d)
        if r.height:
            r = r.row(0, named=True)
            lines.append(f"- Design {d}: {r['no_usage_emp_pct']:.2f}% of OEWS employment is in "
                         f"{r['no_usage']} of {r['occupations']} occupations with no AEI usage, "
                         "and is assigned an exposure of zero.")
    return ("Zero-assigned employment share (D3): every exposure index below is built with the "
            "default of zero for occupations with no matched conversations.\n\n"
            + "\n".join(lines))


def _preamble(occ: pl.DataFrame, designs=DESIGNS) -> list[tuple[str, str]]:
    return [("Scope", DESCRIPTIVE + "\n\n" + HEADLINE),
            ("Zero-assigned employment share", zero_assigned_note(occ, designs))]


def could_vs_does(exposure: pl.DataFrame, bench: pl.DataFrame, draws: int) -> pl.DataFrame:
    idx = rq2.bootstrap_indices(bench.height, DESIGNS, draws)
    pairs = [(a, b) for a in rq2.AEI_COLS for b in rq2.BENCH_COLS]
    parts = []
    for d in DESIGNS:
        df = exposure.filter(pl.col("design") == d).join(
            bench.select("ff49", *rq2.BENCH_COLS), on="ff49", how="inner")
        parts.append(rq2.spearman_bootstrap(df, pairs, idx[d]).with_columns(
            design=pl.lit(d)).select("design", *rq2.SPEARMAN_COLUMNS))
    return pl.concat(parts)


def fig_could_vs_does(exposure_b: pl.DataFrame, bench: pl.DataFrame):
    apply_style()
    d = exposure_b.join(bench, on="ff49")
    fig, axes = plt.subplots(1, 3, figsize=(FIGSIZE["double"][0] * 1.6, FIGSIZE["double"][1]),
                             sharey=True)
    for ax, b in zip(axes, rq2.BENCH_COLS, strict=True):
        ax.scatter(d[b], d["z_delegation"], s=8, color=PALETTE[5])
        for x, y, lab in zip(d[b], d["z_delegation"], d["ff49_short"], strict=True):
            ax.annotate(lab, (x, y), fontsize=4, xytext=(2, 2), textcoords="offset points")
        ax.set_xlabel(f"{b} (could)")
    axes[0].set_ylabel("z_delegation (does; conversations matched to O*NET tasks)")
    fig.suptitle("Benchmark exposure against delegation-weighted AEI exposure, 49 industries "
                 "(Design B)", fontsize=8)
    fig.tight_layout()
    return fig


def fig_bound_widths(ff: pl.DataFrame):
    apply_style()
    d = ff.sort("E_delegation")
    y = np.arange(d.height)
    fig, ax = plt.subplots(figsize=FIGSIZE["tall"])
    ax.hlines(y, d["E_delegation_lb"], d["E_delegation_ub"], color=PALETTE[5])
    ax.scatter(d["E_delegation"], y, s=6, color=PALETTE[0], zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(d["ff49_short"], fontsize=5)
    ax.set_xlabel("E_delegation with its bounds (Design B)")
    fig.tight_layout()
    return fig


def report(out: Path = OUT_DIR, fig_dir: Path = FIGURES_DIR, *, exposure=None, occ=None,
           bench=None, draws: int = 10_000, k: int = 10) -> list[Path]:
    if exposure is None:
        exposure = pl.read_parquet(DERIVED / "exposure_ff49.parquet")
        occ = pl.read_parquet(DERIVED / "exposure_occupation.parquet")
        bench = pl.read_parquet(DERIVED / "benchmark_ff49.parquet")
    out, fig_dir = Path(out), Path(fig_dir)
    ex_b = exposure.filter(pl.col("design") == "B")
    occ_b = occ.filter(pl.col("design") == "B")
    paths: list[Path] = []

    cvd = could_vs_does(exposure, bench, draws)
    paths.append(write_csv(cvd, out / "could_vs_does.csv"))
    secs = _preamble(occ)
    for d in DESIGNS:
        label = "Design B (primary)" if d == "B" else f"Design A_pooled ({EXPLORATORY})"
        body = md_table(cvd.filter(pl.col("design") == d).drop("design"))
        secs.append((f"Spearman correlation across industries, {label}",
                     f"{bench.height} industries; {draws} industry-bootstrap draws "
                     f"(same seed, drawn in the order B then A_pooled).\n\n{body}"))
    paths.append(write_result_doc(out / "could_vs_does.md", "RQ2: could against does", GENERATOR,
                                  secs))

    blocks = [top_bottom_block(ex_b, bench, c, k) for c in rq2.AEI_COLS]
    paths.append(write_csv(pl.concat(b.with_columns(aei=pl.lit(c)).select(
        "aei", pl.all().exclude("aei")).rename({c: "value"}) for b, c in
        zip(blocks, rq2.AEI_COLS, strict=True)), out / "top_bottom.csv"))
    secs = _preamble(occ, ("B",)) + [
        (f"Top and bottom {k} industries by {c} (Design B)", md_table(b))
        for b, c in zip(blocks, rq2.AEI_COLS, strict=True)]
    paths.append(write_result_doc(out / "top_bottom.md", "RQ2: top and bottom industries",
                                  GENERATOR, secs))

    gaps = rq2.rank_gaps(ex_b, bench, k=k)
    paths.append(write_csv(gaps, out / "rank_gaps.csv"))
    paths.append(write_result_doc(
        out / "rank_gaps.md", "RQ2: rank gaps between does and could", GENERATOR,
        _preamble(occ, ("B",)) + [("Rank gaps, `z_delegation` against `z_aioe` (Design B)",
                                   RANK_NOTE + "\n\n" + md_table(gaps))]))

    ff, summ = rq2.bound_widths(ex_b, occ_b)
    paths.append(write_csv(ff, out / "bounds.csv"))
    paths.append(write_csv(summ, out / "bounds_occupation.csv"))
    paths.append(write_result_doc(
        out / "bounds.md", "RQ2: widths of the R7 bounds", GENERATOR,
        _preamble(occ, ("B",)) + [
            ("Industries (Design B)", "`width = E_delegation_ub - E_delegation_lb`.\n\n"
             + md_table(ff.sort("width_pct_of_E", descending=True))),
            ("Occupations (Design B)", "Usage-weighted quantiles of the bound widths across "
             "occupations (weights are `usage_share`; occupations with no usage carry no "
             "weight).\n\n" + md_table(summ, 4))]))

    readme = [generated_line(GENERATOR), "", "# RQ2 results", "", DESCRIPTIVE, "",
              "- `could_vs_does.md` / `.csv`: Spearman correlations, Design B and "
              f"Design A_pooled ({EXPLORATORY})",
              "- `top_bottom.md` / `.csv`: top and bottom industries per AEI column",
              "- `rank_gaps.md` / `.csv`: rank on does minus rank on could",
              "- `bounds.md` / `.csv` / `bounds_occupation.csv`: widths of the R7 bounds",
              f"- figures `{FIG_COULD}` and `{FIG_WIDTHS}` in `docs/paper/figures/`", ""]
    (out / "README.md").write_text("\n".join(readme), encoding="utf-8")
    paths.append(out / "README.md")

    paths += save_figure(fig_could_vs_does(ex_b, bench), FIG_COULD, out_dir=fig_dir)
    paths += save_figure(fig_bound_widths(ff), FIG_WIDTHS, out_dir=fig_dir)
    return paths


def top_bottom_block(ex_b: pl.DataFrame, bench: pl.DataFrame, col: str, k: int) -> pl.DataFrame:
    return rq2.top_bottom(ex_b, bench, col, k)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog=GENERATOR, description="RQ2 descriptives (no test).")
    ap.add_argument("--draws", type=int, default=10_000)
    a = ap.parse_args(argv)
    for p in report(draws=a.draws):
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
