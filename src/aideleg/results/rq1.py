"""RQ1 confirmatory tables, decisions and figures, generated from the committed P-RQ1 JSON only.

AEI data are conversations matched to O*NET tasks. This module reads
`docs/results/rq1/confirmatory_rq1.json` and nothing else: it never loads the panel and never
re-runs an estimator. Every number it writes is copied or formatted from that JSON.

Reporting (PAP §0.2): every coefficient appears in the same table and in the same figure style
whether or not its hypothesis is rejected; no stars; a non-rejection names its null.

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
import polars as pl

from aideleg.figures import FIGSIZE, PALETTE, apply_style, save_figure
from aideleg.figures.save import FIGURES_DIR
from aideleg.results.common import write_csv, write_result_doc
from aideleg.rq1.confirm import JSON_NAME, OUT_DIR

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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog=GENERATOR, description=(
        "RQ1 reporting from the committed P-RQ1 JSON (no estimator is run)."))
    ap.add_argument("--confirmatory", action="store_true",
                    help="write the confirmatory table, decisions and figures")
    a = ap.parse_args(argv)
    if not a.confirmatory:
        ap.print_help()
        return 2
    for p in report_confirmatory():
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
