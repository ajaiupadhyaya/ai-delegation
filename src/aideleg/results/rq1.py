"""RQ1 confirmatory tables, decisions and figures, plus the descriptive anatomy.

AEI data are conversations matched to O*NET tasks. `report_confirmatory` reads
`docs/results/rq1/confirmatory_rq1.json` and nothing else: it never loads the panel and never
re-runs an estimator. Every number it writes is copied or formatted from that JSON.
`report_anatomy` is different: it loads the AEI panel, the OEWS wages and national employment,
the O*NET task index and the AEI SOC structure, and computes descriptive tables (no test, no
p-value).

Reporting (PAP §0.2): every coefficient appears in the same table and in the same figure style
whether or not its hypothesis is rejected; no stars; a non-rejection names its null.

Outputs of `report_anatomy` are listed in its docstring.

Outputs (`report_confirmatory`):
- `confirmatory_table.csv` / `.md`: one row per coefficient;
- `decisions.md`: the α split, the four decision texts verbatim, the H2 disclosure notes, and
  samples with the structural drop node counts (C-30);
- `fig_rq1_coefficients`, `fig_rq1_h2_release_effects` (PDF + PNG) in `fig_dir`.
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from aideleg.describe import anatomy
from aideleg.figures import FIGSIZE, PALETTE, apply_style, save_figure
from aideleg.figures.save import FIGURES_DIR
from aideleg.results.common import write_csv, write_result_doc
from aideleg.rq1.confirm import JSON_NAME, OUT_DIR
from aideleg.rq1.family import SPLIT_STATEMENT

GENERATOR = "aideleg.results.rq1"
HYPOTHESES = ("H1", "H2", "H3", "H4")
TABLE_CSV, TABLE_MD = "confirmatory_table.csv", "confirmatory_table.md"
DECISIONS_MD = "decisions.md"
FIG_COEFS, FIG_H2 = "fig_rq1_coefficients", "fig_rq1_h2_release_effects"
H2_STATEMENT = "measured within-task automation rises across releases"
TABLE_COLUMNS = ("hypothesis", "coefficient", "tested", "estimate", "se", "ci_low", "ci_high",
                 "p", "df", "p_family", "holm_level", "status", "p13_attenuation")
# the coefficients the P13 attenuation factor sits beside (PAP §4.1)
_ATTENUATION_LABEL = {("H1", "log_wage"): "β_w", ("H3", "error_cost"): "γ"}


def _tested(res: dict, h: str) -> list[str]:
    return ["trend"] if h == "H2" else list(res["diagnostics"]["tested"])


def table_rows(data: dict) -> pl.DataFrame:
    """One row per coefficient, every value copied from the JSON."""
    rows = []
    for h in HYPOTHESES:
        res, dec = data["results"][h], data["decisions"][h]
        tested = _tested(res, h)
        for c in res["coefs"].values():
            rows.append({
                "hypothesis": h, "coefficient": c["name"], "tested": c["name"] in tested,
                "estimate": c["estimate"], "se": c["se"], "ci_low": c["ci_low"],
                "ci_high": c["ci_high"], "p": c["p"], "df": c["df"],
                "p_family": res["p_family"], "holm_level": dec["level"],
                "status": dec["status"],
                "p13_attenuation": res["diagnostics"].get(f"attenuation_{c['name']}"),
            })
    schema = {"hypothesis": pl.String, "coefficient": pl.String, "tested": pl.Boolean,
              "estimate": pl.Float64, "se": pl.Float64, "ci_low": pl.Float64,
              "ci_high": pl.Float64, "p": pl.Float64, "df": pl.Int64, "p_family": pl.Float64,
              "holm_level": pl.Float64, "status": pl.String, "p13_attenuation": pl.Float64}
    return pl.DataFrame(rows, schema=schema).select(TABLE_COLUMNS)


def _num(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x:.2e}" if x != 0 and abs(x) < 1e-4 else f"{x:.4f}"


def _level(x: float) -> str:
    return f"{x:g}"


def _table_md(df: pl.DataFrame) -> str:
    head = ("| hypothesis | coefficient | tested | estimate | SE | 95% CI | p | df | family p "
            "| level | status | P13 attenuation |")
    out = [head, "|" + "---|" * 12]
    for r in df.iter_rows(named=True):
        df_cell = "normal" if r["df"] is None else str(r["df"])
        out.append(
            f"| {r['hypothesis']} | {r['coefficient']} | {'yes' if r['tested'] else 'control'} "
            f"| {_num(r['estimate'])} | {_num(r['se'])} | [{_num(r['ci_low'])}, "
            f"{_num(r['ci_high'])}] | {_num(r['p'])} | {df_cell} | {_num(r['p_family'])} "
            f"| {_level(r['holm_level'])} | {r['status']} | {_num(r['p13_attenuation'])} |")
    return "\n".join(out)


def _table_doc(data: dict, df: pl.DataFrame, path: Path) -> Path:
    notes = "\n".join([
        "- One row per coefficient. Rejected and non-rejected hypotheses share this table and "
        "its format (PAP §0.2); there are no stars, and every test is two-sided.",
        "- `family p` is the hypothesis's single p-value (D17); `level` is the level that p was "
        "compared with: the Holm step level for H1, H3 and H4, and the stand-alone α for H2.",
        "- `status` is the decision of the hypothesis the row belongs to; `control` rows are "
        "not tested.",
        "- `df`: the t reference degrees of freedom; `normal` marks a normal reference.",
        "- P13 attenuation: the between-task share of the regressor's identifying "
        "(within-IWA, FWL-residualised) variation, beside β_w (H1, log_wage) and γ (H3, "
        "error_cost) (PAP §4.1).",
        f"- Full-precision values: `{TABLE_CSV}`.",
    ])
    return write_result_doc(path, "RQ1 confirmatory coefficients", GENERATOR, [
        ("α split", data["alpha"]["statement"]),
        ("Coefficients", _table_md(df)),
        ("Notes", notes),
    ])


def _kv(d: dict, fmt=str) -> str:
    return ", ".join(f"{k} = {fmt(v)}" for k, v in d.items())


def _decision_section(data: dict, h: str) -> str:
    res, dec = data["results"][h], data["decisions"][h]
    lines = [dec["text"], "",
             f"- Outcome: `{res['outcome']}`; tested: {', '.join(_tested(res, h))}.",
             f"- Status: `{dec['status']}`; its p was compared with level {_level(dec['level'])}."]
    for (hh, coef), label in _ATTENUATION_LABEL.items():
        if hh == h:
            att = res["diagnostics"][f"attenuation_{coef}"]
            c = res["coefs"][coef]
            lines.append(f"- {label} ({coef}) = {_num(c['estimate'])}, beside its P13 "
                         f"attenuation factor {_num(att)} (PAP §4.1).")
    if h == "H2":
        d = res["diagnostics"]
        lines += [
            f"- H2 is worded as \"{H2_STATEMENT}\" (D22); β is the change in measured "
            "within-task automation per year of release time, which includes any change in "
            "the classifier and in platform scope.",
            f"- Release-level wild bootstrap p = {_num(d['p_wild'])} over {d['n_wild_draws']} "
            "Webb vectors (D22 co-condition).",
            f"- Release-label randomisation p = {_num(d['p_release_label'])} over "
            f"{d['n_release_orderings']} orderings (descriptive only).",
            "", "H2 disclosure notes, as recorded by the run (including the wild-bootstrap "
            "granularity disclosure, C-15):", ""]
        lines += [f"- {n}" for n in res["notes"]]
    if h == "H4":
        d = res["diagnostics"]
        lines.append(f"- Joint {d['cov_type']} Wald F = {_num(d['F'])} with ({d['df_num']}, "
                     f"{d['df_denom']}) df; p = {_num(res['p_family'])}.")
    if h in ("H1", "H3"):
        lines += [f"- {n}" for n in res["notes"]]
    return "\n".join(lines)


def _samples_section(data: dict) -> str:
    lines = ["Drop shares are in percent of total r6 task usage (H1, H3). Structural drop "
             "nodes count the r6 task nodes removed at each structural step (C-30).", ""]
    for h in HYPOTHESES:
        r = data["results"][h]
        lines.append(f"- {h} sample: {_kv(r['sample'])}")
        nodes = r["diagnostics"].get("structural_drop_nodes")
        if nodes:
            lines.append(f"- {h} structural drop nodes (C-30): {_kv(nodes)}")
        if r["drops"]:
            lines.append(f"- {h} drops (%): {_kv(r['drops'], _num)}")
    return "\n".join(lines)


def _decisions_doc(data: dict, path: Path) -> Path:
    reading = ("Each decision text below is copied verbatim from the run's JSON. A hypothesis "
               "that is not rejected names its null: the data do not reject that null at its "
               "level, which is not evidence that the coefficient is zero. A significant "
               "estimate of the wrong sign is reported as contradicting the hypothesis.")
    sections = [("α split", data["alpha"]["statement"]), ("Reading the decisions", reading)]
    sections += [(h, _decision_section(data, h)) for h in HYPOTHESES]
    sections.append(("Samples and structural drops", _samples_section(data)))
    if data["meta"].get("scrambled"):
        sections.insert(0, ("DRY RUN", "**Every outcome was SCRAMBLED before estimation. These "
                                       "numbers are not results.**"))
    return write_result_doc(path, "RQ1 confirmatory decisions", GENERATOR, sections)


def _ci_panel(ax, coefs: list[dict], tested: list[str]) -> None:
    ys = list(range(len(coefs)))[::-1]
    for y, c in zip(ys, coefs, strict=True):
        ax.errorbar(c["estimate"], y, xerr=[[c["estimate"] - c["ci_low"]],
                                            [c["ci_high"] - c["estimate"]]],
                    fmt="o", color=PALETTE[5], ecolor=PALETTE[5], capsize=2, markersize=4,
                    linewidth=1)
    ax.axvline(0.0, color=PALETTE[0], linewidth=0.6, linestyle=":")
    ax.set_yticks(ys)
    ax.set_yticklabels([c["name"] if c["name"] in tested else f"{c['name']} (control)"
                        for c in coefs])
    ax.set_ylim(-0.6, len(coefs) - 0.4)


def fig_coefficients(data: dict):
    apply_style()
    fig, axes = plt.subplots(2, 2, figsize=FIGSIZE["double"], layout="constrained")
    for ax, h in zip(axes.flat, HYPOTHESES, strict=True):
        res = data["results"][h]
        _ci_panel(ax, list(res["coefs"].values()), _tested(res, h))
        ax.set_title(f"{h} ({data['decisions'][h]['status']})")
        ax.set_xlabel(f"{res['outcome']}: estimate with 95% CI")
    return fig


def fig_h2_release_effects(data: dict):
    res = data["results"]["H2"]
    times, effects = res["sample"]["times"], res["diagnostics"]["release_effects"]
    apply_style()
    fig, ax = plt.subplots(figsize=FIGSIZE["single"], layout="constrained")
    ref = [r for r in times if r not in effects]
    for r in ref:
        ax.plot(times[r], 0.0, "o", color=PALETTE[0], markersize=4, markerfacecolor="white")
    xs = [times[r] for r in effects]
    ys = [effects[r]["estimate"] for r in effects]
    lo = [effects[r]["estimate"] - effects[r]["ci_low"] for r in effects]
    hi = [effects[r]["ci_high"] - effects[r]["estimate"] for r in effects]
    ax.errorbar(xs, ys, yerr=[lo, hi], fmt="o", color=PALETTE[5], capsize=2, markersize=4,
                linewidth=1, label="release effect vs " + ", ".join(ref) + " (95% CI)")
    for r, t in times.items():
        y = effects[r]["ci_high"] if r in effects else 0.0
        ax.annotate(r, (t, y), textcoords="offset points", xytext=(0, 4), ha="center")
    ax.axhline(0.0, color=PALETTE[0], linewidth=0.6, linestyle=":")
    ax.set_xlabel("release time t_r (years since r2)")
    ax.set_ylabel(f"{res['outcome']} vs r2 (pp)")
    ax.legend(frameon=False, loc="lower right")
    return fig


def report_confirmatory(json_path: Path = OUT_DIR / JSON_NAME, out: Path = OUT_DIR, *,
                        fig_dir: Path = FIGURES_DIR) -> list[Path]:
    """Write the RQ1 confirmatory table, decisions and figures from the JSON alone."""
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    out = Path(out)
    df = table_rows(data)
    paths = [write_csv(df, out / TABLE_CSV), _table_doc(data, df, out / TABLE_MD),
             _decisions_doc(data, out / DECISIONS_MD)]
    paths += save_figure(fig_coefficients(data), FIG_COEFS, out_dir=fig_dir)
    paths += save_figure(fig_h2_release_effects(data), FIG_H2, out_dir=fig_dir)
    return paths


# --- RQ1 descriptive anatomy (spec §5.2) -----------------------------------------------------

ANATOMY_MD = "anatomy.md"
ANATOMY_CSVS = {"major": "anatomy_major_group.csv", "decile": "anatomy_wage_decile.csv",
                "education": "anatomy_education.csv", "concentration": "anatomy_concentration.csv",
                "harmonised": "anatomy_concentration_harmonised.csv"}
FIG_MAJOR, FIG_DECILE = "fig_rq1_composition_major", "fig_rq1_composition_wage_decile"
FIG_EDU, FIG_LORENZ = "fig_rq1_composition_education", "fig_rq1_lorenz"
# the two automation patterns take the two warm palette colours
PATTERN_STYLE = [("directive", PALETTE[6]), ("feedback loop", PALETTE[1]),
                 ("task iteration", PALETTE[2]), ("validation", PALETTE[3]),
                 ("learning", PALETTE[5])]
LORENZ_RELEASES = ("r2", "r3", "r4", "r5", "r6")


def _cell(x, digits: int) -> str:
    if x is None:
        return "—"
    return f"{x:.{digits}f}" if isinstance(x, float) else str(x)


def _md_table(df: pl.DataFrame, digits: int = 2) -> str:
    out = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * df.width]
    out += ["| " + " | ".join(_cell(v, digits) for v in row) + " |" for row in df.iter_rows()]
    return "\n".join(out)


def _stacked(ax, df: pl.DataFrame, labels: list[str], *, horizontal: bool) -> None:
    """Stacked bars of the five patterns (percent of classified conversations)."""
    base = np.zeros(df.height)
    pos = np.arange(df.height)
    for (name, color), col in zip(PATTERN_STYLE, anatomy.FIVE_PATTERNS, strict=True):
        vals = np.nan_to_num(df[col].to_numpy(allow_copy=True).astype(float))
        if horizontal:
            ax.barh(pos, vals, left=base, color=color, label=name, linewidth=0)
        else:
            ax.bar(pos, vals, bottom=base, color=color, label=name, linewidth=0)
        base += vals
    ticks = (ax.set_yticks, ax.set_yticklabels) if horizontal else (ax.set_xticks,
                                                                     ax.set_xticklabels)
    ticks[0](pos)
    ticks[1](labels)
    if horizontal:
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.set_xlabel("% of classified conversations")
    else:
        ax.set_ylim(0, 100)
        ax.set_ylabel("% of classified conversations")


def fig_composition(df: pl.DataFrame, labels: list[str], *, horizontal: bool, xlabel: str = "",
                    size: str = "double"):
    apply_style()
    fig, ax = plt.subplots(figsize=FIGSIZE[size], layout="constrained")
    _stacked(ax, df, labels, horizontal=horizontal)
    if xlabel:
        (ax.set_ylabel if horizontal else ax.set_xlabel)(xlabel)
    ax.legend(frameon=False, ncols=5, loc="upper center", bbox_to_anchor=(0.5, -0.12 if not
                                                                          horizontal else -0.05),
              fontsize=7)
    return fig


def fig_lorenz(panel: pl.DataFrame):
    apply_style()
    fig, ax = plt.subplots(figsize=FIGSIZE["single"], layout="constrained")
    ax.plot([0, 1], [0, 1], color=PALETTE[0], linewidth=0.6, linestyle=":", label="equality")
    colors = [PALETTE[2], PALETTE[3], PALETTE[1], PALETTE[7], PALETTE[6]]
    for r, color in zip(LORENZ_RELEASES, colors, strict=True):
        if panel.filter((pl.col("release") == r) & (pl.col("source") == "claude_ai")).is_empty():
            continue
        x, y = anatomy.lorenz_points(anatomy.harmonised_shares(panel, r, "claude_ai"))
        ax.plot(x, y, color=color, linewidth=1.0, label=r)
    ax.set_title("each release rounded to 2 dp, zero-usage tasks dropped", fontsize=6.5)
    ax.set_xlabel("cumulative share of tasks (smallest first)")
    ax.set_ylabel("cumulative share of usage")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, loc="upper left")
    return fig


def _zero_note(conc: pl.DataFrame, harm: pl.DataFrame, release: str) -> str:
    """Why the as-published concentration of `release` differs from earlier releases."""
    parts = []
    for r in conc.filter(pl.col("release") == release).iter_rows(named=True):
        h = harm.filter((pl.col("release") == release) & (pl.col("source") == r["source"]))
        parts.append(
            f"{r['source']}: {r['n_zero']} of {r['n_tasks']} published matched tasks carry 0.00; "
            f"Gini {r['gini']:.3f} as published, {r['gini_pos']:.3f} over positive-usage tasks, "
            f"{h['gini'].item():.3f} harmonised; top-10% share {r['top10_share']:.1f} as "
            f"published, {r['top10_share_pos']:.1f} positive-only")
    return (f"In {release}, usage is published to two decimals, and earlier releases publish "
            "finer values. Both drive the gap between the as-published rows of "
            f"{release} and r1-r5: the zero-usage tasks it keeps in its task count and Gini "
            "(zero inclusion), and its coarser rounding (which turns small shares into those "
            "zeros). The as-published Gini and top-K columns of different releases are "
            "therefore not comparable; use the `_pos` columns or the harmonised table. "
            + "; ".join(parts) + ".")


def _anatomy_doc(path: Path, tables: dict[str, pl.DataFrame], release: str, source: str,
                 zero_note: str, edu_note: str) -> Path:
    major, decile, edu, conc, harm = (tables[k] for k in (
        "major", "decile", "education", "concentration", "harmonised"))
    scope = "\n".join([
        "- Composition is computed over published cells only: what AEI leaves out is not "
        "imputed, and each table's usage shares are renormalised to 100 over the cells it "
        "covers.",
        "- The occupation basis is AEI's published SOC rows (D9). The task-allocated basis is "
        "not used here.",
        f"- The reference release is {release} ({source}); its two months are combined by D13: "
        "a value missing in one month is averaged over the month that has it, never treated "
        "as 0.",
        "- Cross-release concentration mixes suppression regimes (PAP §5), so differences "
        "between releases are not read as changes in the underlying conversations.",
        "- These tables are descriptive. No hypothesis test is attached to any of them, and "
        "they report no p-value.",
        "- Patterns are percentages of classified conversations. Automation = directive + "
        "feedback loop; augmentation = task iteration + validation + learning.",
    ])
    csvs = "\n".join(f"- `{v}`" for v in ANATOMY_CSVS.values())
    figs = "\n".join(f"- `{n}` (PDF and PNG)" for n in
                      (FIG_MAJOR, FIG_DECILE, FIG_EDU, FIG_LORENZ))
    sections = [
        ("α split", SPLIT_STATEMENT + " This document tests nothing; the split is stated "
                    "because every RQ1 results document states it."),
        ("Scope and reading", scope),
        (f"Composition by occupation major group ({release}, {source})",
         "`usage_share` is the percentage of published SOC-major usage.\n\n"
         + _md_table(major)),
        (f"Composition by wage decile ({release}, {source}, published basis)",
         "Deciles are employment-weighted deciles of the OEWS May 2024 annual median wage; a "
         "top-coded median takes the top-code and a suppressed median is excluded, and those "
         "occupations form the final row (`decile` empty). `emp_share` is the percentage of "
         "OEWS employment; `usage_share` is the percentage of conversations matched to OEWS "
         "occupations; `n_occ` counts OEWS occupations.\n\n" + _md_table(decile)),
        (f"Composition by education ({release}, {source})",
         "Matched tasks are binned on the mean education years of the person in the "
         "conversation (`human_education_years_mean`), left-closed bins. A task with no "
         "published value is `zero published usage`: " + edu_note + "\n\n" + _md_table(edu)),
        ("Usage concentration across tasks, as published",
         "One row per release and source over the published matched tasks, usage renormalised "
         "to 100. `topK_share` is the usage share of the largest ⌈K% · n⌉ tasks; "
         "`n_tasks_50pct` is the number of largest tasks that together hold half the usage. "
         "The columns ending `_pos` repeat the statistics over the tasks with positive usage "
         "only; `n_zero` counts the tasks published as 0.\n\n" + zero_note + "\n\n"
         + _md_table(conc, digits=4)),
        ("Usage concentration across tasks, harmonised",
         "Every release and source with each month's usage rounded to two decimals (r6's "
         "publication precision) and zero-usage tasks dropped, so the rows are like-for-like "
         "in rounding and zero handling. Suppression regimes still differ (PAP §5).\n\n"
         + _md_table(harm, digits=4)),
        ("Figures", figs),
        ("Tables as CSV", "Full-precision values:\n\n" + csvs),
    ]
    return write_result_doc(path, "RQ1 descriptive anatomy", GENERATOR, sections)


def _load_anatomy_inputs():
    from aideleg.acquire.sources import by_key
    from aideleg.aei.tasks import default_index
    from aideleg.bls.oews import load_national, load_national_wages
    from aideleg.config import RAW
    from aideleg.rq1.confirm import PANEL_PATH

    return (pl.read_parquet(PANEL_PATH), default_index(), load_national_wages(2024),
            load_national(2024), pl.read_csv(RAW / by_key("aei_soc_structure").dest))


def report_anatomy(out: Path = OUT_DIR, *, fig_dir: Path = FIGURES_DIR, panel=None, index=None,
                   wages=None, national=None, soc_structure=None, release: str = "r6",
                   source: str = "claude_ai") -> list[Path]:
    """Write `anatomy.md`, one CSV per table and four figures (descriptive; no test).

    Tables: composition by major group, wage decile (published basis) and education, and usage
    concentration. Figures: `fig_rq1_composition_major`, `fig_rq1_composition_wage_decile`,
    `fig_rq1_composition_education` (stacked bars of the five patterns) and `fig_rq1_lorenz`
    (claude_ai r2-r6). With `panel=None` the study inputs are loaded; the other inputs are
    for tests (`index` is unused on the published basis).
    """
    if panel is None:
        panel, index, wages, national, soc_structure = _load_anatomy_inputs()
    out = Path(out)
    tables = {
        "major": anatomy.by_major_group(panel, release=release, source=source),
        "decile": anatomy.by_wage_decile(panel, index, wages, national, soc_structure,
                                         release=release, source=source),
        "education": anatomy.by_education(panel, release=release, source=source),
        "concentration": anatomy.concentration(panel),
        "harmonised": anatomy.concentration_harmonised(panel),
    }
    zero_note = _zero_note(tables["concentration"], tables["harmonised"], release)
    miss = tables["education"].filter(pl.col("bin") == anatomy.EDU_MISSING)
    edu_note = (f"{miss['n_tasks'].item()} tasks holding {miss['usage_share'].item():.4f}% "
                "of usage; in the panel these are the tasks published with pct 0.00, which "
                "carry no education value or collaboration pattern."
                if miss.height else "none in this release.")
    paths = [write_csv(tables[k], out / ANATOMY_CSVS[k]) for k in ANATOMY_CSVS]
    paths.append(_anatomy_doc(out / ANATOMY_MD, tables, release, source, zero_note, edu_note))
    major, decile = tables["major"], tables["decile"]
    edu = tables["education"].filter(pl.col("bin") != anatomy.EDU_MISSING)  # no patterns to stack
    paths += save_figure(fig_composition(
        major, [f"{m} {n[:44]}" for m, n in zip(major["major"], major["name"], strict=True)],
        horizontal=True, size="tall"), FIG_MAJOR, out_dir=fig_dir)
    paths += save_figure(fig_composition(
        decile, [str(d) if d is not None else "no wage" for d in decile["decile"]],
        horizontal=False, xlabel="wage decile (employment-weighted)"),
        FIG_DECILE, out_dir=fig_dir)
    paths += save_figure(fig_composition(
        edu, edu["bin"].to_list(), horizontal=False,
        xlabel="education years (human, mean per task)"), FIG_EDU, out_dir=fig_dir)
    paths += save_figure(fig_lorenz(panel), FIG_LORENZ, out_dir=fig_dir)
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog=GENERATOR, description=(
        "RQ1 reporting from the committed P-RQ1 JSON (no estimator is run)."))
    ap.add_argument("--confirmatory", action="store_true",
                    help="write the confirmatory table, decisions and figures")
    ap.add_argument("--anatomy", action="store_true",
                    help="write the descriptive anatomy (composition, concentration)")
    a = ap.parse_args(argv)
    if not (a.confirmatory or a.anatomy):
        ap.print_help()
        return 2
    paths = (report_confirmatory() if a.confirmatory else []) + (
        report_anatomy() if a.anatomy else [])
    for p in paths:
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
