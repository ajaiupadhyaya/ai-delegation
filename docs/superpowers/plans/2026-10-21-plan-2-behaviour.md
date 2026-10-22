# Plan 2 — Behaviour and Bridge: RQ1 Confirmatory Tests, RQ1/RQ2 Descriptives, Figure System

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the frozen RQ1 tests H1–H4 exactly as PAP §4–§5 specify, test them on synthetic and permuted outcomes, run them once on real outcomes under protocol P-RQ1, then produce the RQ1 descriptive anatomy, the H4 shift-share maps and the RQ2 "could vs does" descriptives, all through one shared figure system and generated results documents.

**Architecture:** Three new packages.
- `aideleg.rq1` holds the confirmatory estimators. Sample builders and estimators are separate functions, and every estimator takes its outcome column as an argument.
- `aideleg.describe` holds the descriptives. It calls `rq1` builders but never edits them.
- `aideleg.results` writes the generated markdown/CSV under `docs/results/rq1|rq2/`.

`aideleg.figures` is the shared visual system that Plans 3 and 4 also use. The RQ1 runner `aideleg.rq1.confirm` is write-once:
- it creates an attempt marker before any outcome is read;
- it records the git blobs of the code it is bound to;
- after its single logged commit, a test fails if any bound file changes.

**Tech Stack:** Python 3.12, uv, Polars, NumPy, SciPy, statsmodels 0.15.0 (as locked), matplotlib, geopandas (+ pyogrio, shapely), pytest, ruff, Make.

**Spec:**
- Authority: `docs/pap/pre-analysis-plan.md`, frozen at tag `pap-v1` ("the PAP"). Read §0.2, §0.3, §0.5, §2.1, §4, §5, §8.2 and §9.4 first.
- Then `docs/superpowers/specs/2026-10-21-ai-delegation-design.md` §5.2–§5.3 ("the spec"), as corrected by PAP §10.
- Facts: `.superpowers/sdd/2026-10-21-plan-1-foundations/progress.md` (Plan 1 ledger).

**Scope:**
- In scope: PAP §4 (H1–H4, D13–D17, D22) and §5 (D2); spec §5.2's descriptive anatomy; the H4 shift-share decomposition and its choropleths; spec §5.3's RQ2 descriptives (PAP §2.0 RQ2 row; D3, D8).
- Not in scope:
  - every PAP §8.2 robustness row (Plan 4);
  - every market analysis (Plan 3).
- Plan 2 builds the parameters that Plan 4's RQ1 rows need into the frozen builders, so that Plan 4 changes no bound code (table "Hand-off to Plan 4" at the end).

## Global Constraints

Copied verbatim from Plan 1:
- Repo root: `/Users/ajaiupadhyaya/Documents/ai-delegation`. Package: `src/aideleg/`. Tests: `tests/`.
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Wording rule (spec §6):** in code comments, docs and output labels, AEI data is "conversations matched to X tasks". Never infer job risk, displacement or reassurance. Say "labour market".
- **Market seal:** no code path may read French returns or factors dated ≥ `2022-11-30` unless the git tag `pap-v1` exists. Nothing in this plan is allowed to need them.
- Raw data are never committed. `data/raw/MANIFEST.json` (URL, retrieval UTC timestamp, bytes, SHA-256) is committed.
- HTTP User-Agent for `bls.gov` and `sec.gov`: `"Ajai Upadhyaya research ajaiupad@gmail.com"`. SEC requests must be ≤ 10/s.
- Randomness is seeded through `aideleg.config.SEED = 20261021`.
- Release IDs: `r1`=2025-02-10, `r2`=2025-03-27, `r3`=2025-09-15, `r4`=2026-01-15, `r5`=2026-03-24, `r6`=2026-06-26.
- Collaboration buckets (AEI definition):
  - automation = `directive` + `feedback_loop`
  - augmentation = `task_iteration` + `validation` + `learning`
  - Shares are normalised over classified conversations (excluding `filtered`, `none` and `not_classified`), in percent 0–100.

Plan 2 additions:
- **Branch:** `plan-2-behaviour`, cut from `plan-1-foundations` at `pap-v1` (6a16b1a). Plan 2 may change `src/`, `pyproject.toml` and `uv.lock` on its branch. `confirm_h5` runs from a worktree at `pap-v1` (Plan 3 Task 1), so these changes cannot block it. Plan 2 never runs `confirm_h5`.
- **The PAP is binding.**
  - No step may change a hypothesis, sample, estimator, inference or decision rule of PAP §4–§5.
  - If a step finds the PAP unimplementable as written, it STOPs. It drafts a §11 deviation entry with its reason. Ajai approves it in chat before work continues.
- **P-RQ1 (PAP §0.5):**
  - No real H1–H4 outcome enters an estimator before Task 11.
  - Task 11 is the single logged first run, and its output is committed unedited.
  - After Task 11, any change to a file in `aideleg.rq1.confirm.BOUND_FILES` is a deviation: a §11 entry with Ajai's approval, and the demotion rule applies. `tests/rq1/test_frozen.py` enforces this.
  - "Outcome" here means the panel metrics in `aideleg.rq1.confirm.OUTCOME_METRICS`.
- **Ordering for integrity:** every descriptive that relates a delegation measure to wage, education, occupation group, error cost, country or state runs only after Task 11 (Tasks 13–15). Results-dependent steps are reporting steps only. No specification is chosen after seeing a result.
- **Reporting (PAP §0.2):**
  - every estimate is reported with its point value, 95% CI and p-value;
  - no stars;
  - all tests are two-sided;
  - a significant estimate of the wrong sign is reported as "contradicts the hypothesis";
  - a non-rejection is never worded "no effect";
  - nulls get the same prominence (same table, same font) as rejections.
- **Generated documents:** every number in `docs/results/**` and every figure is computed by code from `data/` and the committed confirmatory JSON. Nothing is typed by hand. Each generated markdown file starts with the line `Generated by \`<module>\`. Do not edit by hand.`
- **RQ1 α split (D22):** H2 at α = 0.0125, alone. {H1, H3, H4} by Holm at family-wise α = 0.0375. Every RQ1 results document states the split.
- **Data additions (D20):** each newly acquired file is added to the source registry and `MANIFEST.json`, and logged in PAP §11 as an *addition* in the single §11 format of Task 2 (`aideleg.paplog`). An addition is not a deviation.
- **One §11 entry format (all plans).** `### A-<n>` per acquired key (bulk keys `sec_fts/*` and `sec_docs_index` take the set-digest form: one entry with a count and a digest), `### C-<n>` per pre-result clarification, `### D-<n>` per deviation. Task 2 defines it in `aideleg.paplog`; Plans 3 and 4 reuse it and never write §11 by hand.
- **Pre-result clarifications.** Every default this plan fixes where the PAP is silent is logged as a `C-<n>` entry under §11 "Clarifications (pre-result)" and committed before Task 11 reads any real outcome (Task 10 Step 8). The plan files themselves are committed in Task 1, which timestamps every default.
- **Dependency lock.** After any `uv add`, numpy, scipy, pandas, polars and statsmodels must keep their `pap-v1` versions in `uv.lock` (`tests/test_lock_pins.py`). If any would move, pin them with `[tool.uv] constraint-dependencies` at the `pap-v1` versions and STOP for the controller.

## Review Focus

1. **One month unpublished in r6.** A task, country or GWA with a value in April but not May (or the reverse) must be averaged over the month that has it (D13), never treated as 0. Its weight is the mean of the two months' `pct`, with unpublished = 0. Test: `test_two_month_mean_skips_unpublished_month` (Task 3).
2. **OEWS wage codes.** `#` (top-coded) must become $239,200 and `*`/`**` must drop the row, with the dropped share reported. Neither may become 0 or null-and-kept. `load_national` already nulls `#`, so H1 must not use it for wages. Test: `test_wages_topcode_and_suppression` (Task 3).
3. **Non-PSD two-way covariance.** A two-way block with a negative eigenvalue must be clipped, and every use reported. A zero variance after clipping falls back to the larger one-way SE, never to SE = 0 or p = NaN. Test: `test_resolve_tested_cov_clips_and_falls_back` (Task 5).
4. **Accidental second run.** Rerunning `aideleg.rq1.confirm` after the marker or any output exists, or with a dirty `src/`, must refuse **before** any outcome is loaded. Tests: `test_refuses_when_marker_exists_before_loading`, `test_refuses_dirty_tree` (Task 10).
5. **Geography identifiers.** Namibia's ISO-2 code `NA` is read as null by default CSV parsing. Kosovo and others differ between AEI ISO-3, the GDP file and Natural Earth. Joins must be on ISO-3 strings read without null coercion, and unmatched geographies must be listed, not dropped silently. Tests: `test_country_join_keeps_namibia` (Task 8), `test_choropleth_reports_unmatched_ids` (Task 2).

---

## File map

```
docs/superpowers/plans/                 the three plan files, plans-2-4-brief.md, plans-2-4-review-rulings.md (committed in Task 1)
pyproject.toml, uv.lock                 + matplotlib, geopandas (Task 1)
tests/test_confirm_h5.py                one stale test replaced (Task 1; tests only, outside DIFF_PATHS)
tests/test_lock_pins.py                 core numeric versions equal pap-v1's (Task 1)
src/aideleg/paplog.py                   the single §11 entry format and its CLI (Task 2)
tests/test_pap_frozen.py                PAP unchanged above §11; every addition logged (Task 2)
Makefile                                + figures-check, rq1-dry-run, rq1-confirm, describe, results (Tasks 10, 16)
src/aideleg/figures/__init__.py         re-exports apply_style, save_figure, PALETTE, FIGSIZE, choropleth
src/aideleg/figures/style.py            palette, colormaps, fonts, sizes, apply_style()
src/aideleg/figures/save.py             FIGURES_DIR, save_figure()
src/aideleg/figures/maps.py             load_countries(), load_us_states(), choropleth()
src/aideleg/acquire/sources.py          + ne_admin0_50m, census_states_20m (Task 2)
src/aideleg/bls/oews.py                 + A_MEDIAN_TOPCODE, load_national_wages() (Task 3)
src/aideleg/rq1/__init__.py
src/aideleg/rq1/result.py               Coef, HypothesisResult
src/aideleg/rq1/inputs.py               two_month_mean(), task_families(), error_cost_indicator(), log_wage_table()
src/aideleg/rq1/rows.py                 TaskRows, build_task_rows()         (H1/H3 unit)
src/aideleg/rq1/twoway.py               psd_clip(), resolve_tested_cov(), twoway_wls()
src/aideleg/rq1/h1h3.py                 attenuation_factor(), estimate_h1(), estimate_h3()
src/aideleg/rq1/h2.py                   release_times(), build_h2_panel(), clustered_within(), wild_bootstrap_p(), release_label_p(), release_effects(), estimate_h2()
src/aideleg/rq1/h4.py                   GeoSample, build_geo_sample(), estimate_h4(), shift_share()
src/aideleg/rq1/family.py               holm(), Decision, decide()
src/aideleg/rq1/confirm.py              BOUND_FILES, OUTCOME_METRICS, Inputs, load_inputs(), check_clean(), scramble_outcomes(), run(), main()
src/aideleg/describe/__init__.py
src/aideleg/describe/anatomy.py         composition tables, concentration, Lorenz
src/aideleg/describe/geography.py       country/state tables and maps
src/aideleg/describe/rq2.py             spearman_bootstrap(), top_bottom(), rank_gaps(), bound_widths()
src/aideleg/results/__init__.py
src/aideleg/results/common.py           write_result_doc(), write_csv(), fmt_coef(), FORBIDDEN_PHRASES
src/aideleg/results/rq1.py              docs/results/rq1/* from the confirmatory JSON + describe
src/aideleg/results/rq2.py              docs/results/rq2/*
docs/results/rq1/confirmatory_rq1.{attempt,json,md,log}   written once by Task 11
docs/results/rq1/*.md|csv, docs/results/rq2/*.md|csv, docs/paper/figures/*.pdf|png   generated
docs/pap/pre-analysis-plan.md           §11 only: the three subsections and A-/C- entries (Tasks 2, 10)
tests/figures/, tests/rq1/, tests/describe/, tests/results/   (+ tests/rq1/synth.py synthetic inputs)
```

---

### Task 1: Branch, dependencies and the shared figure system

**Files:**
- Add (docs only): `docs/superpowers/plans/2026-10-21-plan-2-behaviour.md`, `2026-10-21-plan-3-markets.md`, `2026-10-21-plan-4-paper.md`, `plans-2-4-brief.md` (copy of `.superpowers/plans-2-4-brief.md`), `plans-2-4-review-rulings.md` (copy of `.superpowers/plans-2-4-review-rulings.md`)
- Modify: `tests/test_confirm_h5.py` (replace one test; tests only, outside `confirm_h5.DIFF_PATHS`)
- Modify: `pyproject.toml`, `uv.lock` (`uv add matplotlib geopandas`; `pyogrio` and `shapely` come in as geopandas dependencies)
- Create: `src/aideleg/figures/__init__.py`, `src/aideleg/figures/style.py`, `src/aideleg/figures/save.py`, `tests/test_lock_pins.py`
- Test: `tests/figures/test_style.py`, `tests/figures/test_save.py`, `tests/test_lock_pins.py`

**Interfaces:**
- Produces (used by Plans 3 and 4; do not rename):
  - `style.PALETTE: tuple[str, ...]`, the Okabe–Ito colour-blind-safe set in this order: `("#000000", "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7")`
  - `style.SEQUENTIAL_CMAP = "viridis"`, `style.DIVERGING_CMAP = "PuOr"`, `style.MISSING_COLOR = "#D9D9D9"`
  - `style.FIGSIZE: dict[str, tuple[float, float]] = {"single": (3.5, 2.6), "double": (7.0, 4.2), "map": (7.0, 3.8), "tall": (7.0, 8.0)}` (inches)
  - `style.FONT_FAMILY = "DejaVu Sans"` (it ships with matplotlib, so renders are deterministic); `style.BASE_FONTSIZE = 8`
  - `style.apply_style() -> None`. It sets the rcParams below, and calling it twice is harmless:
    - `font.family`, `font.size`;
    - `axes.prop_cycle` from PALETTE;
    - `axes.spines.top/right = False`;
    - `savefig.dpi = 300`;
    - `pdf.fonttype = 42`, `ps.fonttype = 42`;
    - `svg.hashsalt = "aideleg"`;
    - `figure.dpi = 100`.
  - `save.FIGURES_DIR = ROOT / "docs/paper/figures"`
  - `save.save_figure(fig: matplotlib.figure.Figure, name: str, *, out_dir: Path = FIGURES_DIR) -> tuple[Path, Path]`. It writes `<name>.pdf` and `<name>.png` with `metadata={"CreationDate": None, "Creator": "aideleg"}` (PDF) and `metadata={"Software": "aideleg"}` (PNG), then closes the figure. It raises `ValueError` if `name` is not `^[a-z0-9][a-z0-9_]*$`.
  - `figures/__init__.py` re-exports `apply_style, save_figure, PALETTE, FIGSIZE, SEQUENTIAL_CMAP, DIVERGING_CMAP, MISSING_COLOR`. It also re-exports `choropleth` once Task 2 exists.
  - `tests/test_lock_pins.py::CORE = ("numpy", "scipy", "pandas", "polars", "statsmodels")` and `locked_versions(text: str) -> dict[str, str]` (the `[[package]]` `name`/`version` pairs of a `uv.lock`, parsed with `tomllib`). Plan 4 reruns this test after its own `uv add`.

- [ ] **Step 1: Branch and commit the plans (docs only).**
  - `git switch -c plan-2-behaviour pap-v1` (the untracked plan files come along in the working tree).
  - `cp .superpowers/plans-2-4-brief.md docs/superpowers/plans/plans-2-4-brief.md && cp .superpowers/plans-2-4-review-rulings.md docs/superpowers/plans/plans-2-4-review-rulings.md`.
  - `git add` the five files listed under **Add**. `git diff --cached --name-only` must print exactly those five paths.
  - Commit `docs(plans): Plans 2-4, the shared brief and the review rulings (timestamps every pre-result default)`. Record the hash in the ledger: it is the timestamp the §11 clarifications cite.
- [ ] **Step 2: Replace the stale binding test.** In `tests/test_confirm_h5.py`, delete `test_binding_refuses_in_this_repo_before_the_tag` (it asserts `not seal.pap_frozen()`, false since the tag exists) and add:

  ```python
  def test_binding_refuses_in_this_repo_when_src_differs():
      # on a branch whose src/pyproject.toml/uv.lock differ from pap-v1, check_binding refuses
      rc = subprocess.run(["git", "-C", str(ch.ROOT), "diff", "--quiet", "pap-v1", "--",
                           *ch.DIFF_PATHS]).returncode
      if rc == 0:
          pytest.skip("this checkout equals pap-v1 under DIFF_PATHS")
      with pytest.raises(ch.BindingError, match="differ from"):
          ch.check_binding()
  ```

  (Add `import subprocess` to the test module if it is absent.) Run `uv run pytest tests/test_confirm_h5.py -q`. Expected: PASS (the new test skips until Step 3 changes `pyproject.toml`). Commit `test(confirm_h5): the in-repo binding test checks refusal when src differs from pap-v1` (tests only; outside `DIFF_PATHS`).
- [ ] **Step 3: Dependencies under the lock rule.**
  - Write `tests/test_lock_pins.py::test_core_numeric_versions_unchanged_since_pap_v1`: `locked_versions(Path("uv.lock").read_text())[p] == locked_versions(git show pap-v1:uv.lock)[p]` for every `p` in `CORE` (expected at the tag: numpy 2.5.4, scipy 1.18.1, pandas 3.0.6, polars 2.0.0, statsmodels 0.15.0).
  - `uv add matplotlib geopandas`, then `uv run pytest -q`. Expected: the whole suite passes, including `test_core_numeric_versions_unchanged_since_pap_v1` and `test_binding_refuses_in_this_repo_when_src_differs` (no longer skipped).
  - If the lock test fails: `git checkout -- pyproject.toml uv.lock`, add `[tool.uv] constraint-dependencies = ["numpy==2.5.4", "scipy==1.18.1", "pandas==3.0.6", "polars==2.0.0", "statsmodels==0.15.0"]` to `pyproject.toml`, rerun `uv add matplotlib geopandas`, and STOP: report the resolution to the controller before any further step.
- [ ] **Step 4: Write failing tests.**
  - `test_palette_is_okabe_ito`: `PALETTE` equals the tuple above.
  - `test_apply_style_sets_rcparams`: after `apply_style()`, `rcParams["pdf.fonttype"] == 42`, `rcParams["font.family"] == ["DejaVu Sans"]`, and the first prop-cycle colour is `"#000000"`.
  - `test_save_writes_pdf_and_png(tmp_path)`: both files exist, and the PNG's pixel width equals `round(3.5*300)` for a `"single"` figure.
  - `test_save_is_byte_reproducible(tmp_path)`: saving the same plot twice gives identical PDF bytes.
  - `test_save_rejects_bad_names`: `"a/b"`, `"Fig 1"` and `"x.pdf"` raise `ValueError`.
- [ ] **Step 5: Run** `uv run pytest tests/figures -v`. Expected: FAIL (module missing).
- [ ] **Step 6: Implement** `style.py`, `save.py` and `__init__.py`. Use the `Agg` backend (`matplotlib.use("Agg")` in `save.py`).
- [ ] **Step 7: Run** `uv run pytest -q && uv run ruff check`. Expected: PASS.
- [ ] **Step 8: Commit** `feat(figures): shared colour-blind-safe style and save_figure (PDF+PNG); lock-pin test`.

### Task 2: The §11 entry format, map geometries (data addition) and the choropleth helper

PAP §9.4 lists nothing that Plan 2 needs. Every §9.4 item is a robustness input (Plan 4) or a market or H6 input (Plan 3). The choropleths need boundary files, which §9.4 does not list. They are descriptive inputs and are logged as §11 additions marked "outside §9.4; descriptive".

**Files:**
- Modify: `src/aideleg/acquire/sources.py`, `data/raw/MANIFEST.json`, `docs/pap/pre-analysis-plan.md` (§11 only), `tests/acquire/test_sources.py` (its required-key set)
- Create: `src/aideleg/paplog.py`, `src/aideleg/figures/maps.py`, `tests/test_pap_frozen.py`
- Test: `tests/test_paplog.py`, `tests/test_pap_frozen.py`, `tests/figures/test_maps.py`

**Interfaces:**
- Consumes: `fetch.Source`, `fetch.fetch`, the `apply_style`/`save_figure` from Task 1.
- Produces (the §11 format; Plans 3 and 4 use these names):
  - `paplog.PAP = ROOT / "docs/pap/pre-analysis-plan.md"`; `paplog.SECTION_11 = "## 11. Deviations"`.
  - `paplog.SUBSECTIONS = {"A": "### Additions (D20)", "C": "### Clarifications (pre-result)", "D": "### Deviations after the freeze"}`, created once, in this order, at the end of §11 (after the frozen paragraph, which stays verbatim).
  - `paplog.ENTRY_RE = r"^### ([ACD])-(\d+)\. (Addition|Addition \(set\)|Clarification|Deviation): (.+) \((\d{4}-\d{2}-\d{2})\)$"`. Subsection headings do not match it.
  - `paplog.entries(pap: Path = PAP) -> list[dict]`: one dict per matching heading, `kind, n, form, title, date, body` (the lines up to the next `### `).
  - `paplog.next_number(kind: Literal["A", "C", "D"], pap: Path = PAP) -> int`: 1 + the largest `n` of that kind.
  - `paplog.set_digest(pairs: Iterable[tuple[str, str]]) -> str`: SHA-256 of the sorted `f"{key} {sha256}\n"` lines.
  - Entry builders, each returning the exact markdown block:
    - `addition(key: str, rec: dict, *, scope: str, used_by: str, date: str) -> str`:
      ```
      ### A-<n>. Addition: `<key>` (<date>)
      - Type: addition under D20 (<scope>; not a deviation)
      - Used by: <used_by>
      - URL: <url>
      - Retrieved (UTC): <retrieved_utc>; bytes: <bytes>; SHA-256: `<sha256>`
      ```
      `scope` is `"pre-specified in §9.4"` or `"outside §9.4; <reason>"`.
    - `set_addition(source: str, *, count: int, digest: str, first_utc: str, last_utc: str, scope: str, used_by: str, date: str) -> str` (bulk keys: a `sec_fts/` prefix, or `sec_docs_index`):
      ```
      ### A-<n>. Addition (set): `<source>` (<date>)
      - Type: addition under D20 (<scope>; not a deviation)
      - Used by: <used_by>
      - Records: <count>; retrieved (UTC) from <first_utc> to <last_utc>
      - Set digest: `<digest>`
      ```
      For a prefix, the records are the MANIFEST keys with that prefix retrieved in [first_utc, last_utc] and the digest is `set_digest` of their (key, sha256). For `sec_docs_index`, the records are the lines of `data/raw/sec/docs/INDEX.jsonl` and the digest is that file's SHA-256 (its MANIFEST value).
    - `clarification(title: str, *, rule: str, plan: str, date: str) -> str`:
      ```
      ### C-<n>. Clarification: <title> (<date>)
      - Type: clarification (pre-result); the PAP is silent or ambiguous here and no PAP rule changes
      - Fixed by: <plan>
      - Results seen: no
      - Rule: <rule>
      ```
      `plan` names the plan, the task and the commit of Task 1 Step 1, e.g. `"Plan 2 Task 4 (plans committed at <hash>)"`.
    - `deviation(title: str, *, reason: str, before: str, after: str, results_seen: bool, approved: str, date: str) -> str`:
      ```
      ### D-<n>. Deviation: <title> (<date>)
      - Type: deviation (needs Ajai's approval; demotion rule of §0.5 if a confirmatory result was seen)
      - Reason: <reason>
      - Before: <before>
      - After: <after>
      - Results seen: yes|no
      - Approved by Ajai: <approved>
      ```
  - `paplog.append(entry: str, pap: Path = PAP) -> None`: creates the three subsections if absent and inserts `entry` at the end of its kind's subsection. It raises `ValueError` if the entry's number is not `next_number(kind)`, and never touches text above `SECTION_11`.
  - CLI `python -m aideleg.paplog`:
    - `addition --keys K [K ...] --scope S --used-by U` (skips a key already logged);
    - `set-addition --source P --scope S --used-by U` (logs the not-yet-covered records of a prefix, or `sec_docs_index`);
    - `clarification --title T --rule R --plan P`;
    - `deviation --title T --reason R --before B --after A --results-seen yes|no --approved X`.
- Produces (maps):
  - registry keys `ne_admin0_50m` (`https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip`, dest `geo/ne_50m_admin_0_countries.zip`, `unzip=True`) and `census_states_20m` (`https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_state_20m.zip`, dest `geo/cb_2023_us_state_20m.zip`, `unzip=True`);
  - `maps.load_countries() -> geopandas.GeoDataFrame` with columns `iso3, name, geometry`. `iso3` = `ISO_A3_EH`, or `ADM0_A3` where that is `-99`. Antarctica (`iso3 == "ATA"`) is removed. CRS EPSG:4326, drawn in Equal Earth (`"EPSG:8857"`);
  - `maps.load_us_states() -> geopandas.GeoDataFrame` with columns `geo_id` (`"US-" + STUSPS`), `name`, `geometry`, the 50 states + DC only;
  - `maps.choropleth(gdf, values: pl.DataFrame, *, id_col: str, value_col: str, title: str, cmap: str, center: float | None = None, label: str) -> tuple[Figure, list[str]]`:
    - it joins `values` on `id_col` and draws missing areas in `MISSING_COLOR` with the legend entry "not published";
    - `center` gives a `TwoSlopeNorm` around it;
    - US-state frames are drawn in EPSG:5070 with Alaska and Hawaii on inset axes;
    - it returns the figure and the sorted list of `values[id_col]` that matched no geometry.

- [ ] **Step 1: Write failing tests:**
  - `tests/test_paplog.py` (on a tmp copy of a fixture PAP whose last section is `## 11. Deviations` + the frozen paragraph):
    - `test_append_creates_subsections_in_order`: appending one C entry to a fresh §11 leaves the three `SUBSECTIONS` headings in A, C, D order, the entry under the C heading, and the text above `SECTION_11` byte-identical.
    - `test_entry_formats_exact`: `addition("k", {"url": "u", "retrieved_utc": "t", "bytes": 3, "sha256": "s"}, scope="outside §9.4; descriptive", used_by="x", date="2026-10-22")` equals the five-line block above with `n = 1`; `clarification`, `deviation` and `set_addition` likewise match their blocks line for line; every heading matches `ENTRY_RE`.
    - `test_numbering_per_kind`: after A-1, A-2 and C-1, `next_number("A") == 3`, `next_number("C") == 2`, `next_number("D") == 1`; appending an entry numbered A-5 raises `ValueError`.
    - `test_set_digest_order_free`: `set_digest([("b","2"),("a","1")]) == hashlib.sha256(b"a 1\nb 2\n").hexdigest()`.
    - `test_cli_addition_idempotent`: running `addition --keys k` twice leaves one `A-` entry for `k`.
  - `tests/test_pap_frozen.py`:
    - `test_pap_unchanged_outside_section_11`: `git show pap-v1:docs/pap/pre-analysis-plan.md` is a byte prefix of the current file (it ends with the frozen §11 paragraph), and whatever follows it starts with a `SUBSECTIONS` heading.
    - `test_every_addition_logged`: every MANIFEST key absent from `git show pap-v1:data/raw/MANIFEST.json` is covered exactly once: by an `A-` single entry whose SHA-256 equals the MANIFEST value, or (for `sec_fts/*` and `sec_docs_index`) by one set entry whose recomputed count and digest equal the logged ones.
    - `test_section_11_entries_well_formed`: every `### ` heading in §11 is a `SUBSECTIONS` value or matches `ENTRY_RE`, and numbers within a kind run 1, 2, … without gaps.
  - `test_choropleth_reports_unmatched_ids`: a two-square synthetic GeoDataFrame (`iso3` ∈ {AAA, BBB}) with values for AAA and ZZZ returns `["ZZZ"]`, and BBB is filled with `MISSING_COLOR`. Check the face colour of the patch collection.
  - `test_choropleth_center_uses_two_slope_norm`: values {AAA: −2.0, BBB: 6.0} with `center=0.0` give a collection whose `norm` is a `matplotlib.colors.TwoSlopeNorm` with `vcenter == 0.0`, `vmin == -2.0` and `vmax == 6.0`; the same call with `center=None` gives a norm that is not a `TwoSlopeNorm`.
  - `test_new_geo_keys_registered`: both keys are in `SOURCES` with `unzip=True`. Also extend `test_required_keys_present`.
- [ ] **Step 2: Run** `uv run pytest tests/test_paplog.py tests/test_pap_frozen.py tests/figures/test_maps.py tests/acquire -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `paplog.py`, the two `Source` entries and `maps.py`. Read the zips with `geopandas.read_file(<extracted .shp>)`.
- [ ] **Step 4: Real download.** Run `uv run python -m aideleg.acquire --only ne_admin0_50m census_states_20m`. Expected: both fetched and recorded in the MANIFEST.
  - If the Census GENZ2023 URL returns 404, use the newest `GENZ20YY/shp/cb_20YY_us_state_20m.zip` listed under `https://www2.census.gov/geo/tiger/`. Update the key's URL and dest, and note it in the commit body.
- [ ] **Step 5: Data check** (`@pytest.mark.data`):
  - `test_real_geometries_load`: `load_countries()` has ≥ 230 rows, holds `"NAM"` and `"SGP"`, and has unique `iso3`;
  - `load_us_states()` has 51 rows.
- [ ] **Step 6: Log the additions.** `uv run python -m aideleg.paplog addition --keys ne_admin0_50m census_states_20m --scope "outside §9.4; descriptive" --used-by "descriptive choropleths (spec §5.2); no confirmatory or robustness input"`. Expected: §11 gains the three subsection headings and entries A-1 and A-2. No other part of the PAP changes.
- [ ] **Step 7: Run** `uv run pytest -q && uv run ruff check`, then **commit** `feat: single PAP §11 entry format (paplog); choropleth helper; Natural Earth 50m and Census 20m boundaries (§11 A-1, A-2)`.

### Task 3: RQ1 shared inputs — D13 averaging, wages with top-code, D14 task families, D15 error cost

**Files:**
- Modify: `src/aideleg/bls/oews.py` (adds a function; `load_national` and `load_industry_matrix` are unchanged)
- Create: `src/aideleg/rq1/__init__.py`, `src/aideleg/rq1/inputs.py`, `src/aideleg/rq1/result.py`
- Test: `tests/rq1/test_inputs.py`, `tests/bls/test_oews.py` (append)

**Interfaces:**
- Consumes: `occupations.SUPPRESSION`, `oews_code_for`, `sources.by_key`.
- Produces:
  - `oews.A_MEDIAN_TOPCODE: dict[int, float] = {2024: 239_200.0}` [PAP §4.1; facts §2].
  - `oews.load_national_wages(year: int = 2024, *, path: Path | None = None) -> pl.DataFrame`. Columns: `soc6, tot_emp (Int64), a_median (Float64), a_median_status`, where status ∈ {`"published"`, `"topcoded"`, `"suppressed"`}.
    - It reads the raw `A_MEDIAN` strings itself, not through `_read`'s null mapping.
    - `#` gives `A_MEDIAN_TOPCODE[year]` (KeyError for a year without a top-code).
    - `*`, `**` or empty gives null with `"suppressed"`.
    - Detailed occupations only.
  - `inputs.two_month_mean(wide: pl.DataFrame, value_cols: list[str], *, key: list[str], n_periods: int) -> pl.DataFrame`. `wide` has one row per (key…, `period_start`), with `pct` and the value columns. It returns one row per key:
    - `weight` = Σ `pct.fill_null(0)` / `n_periods`;
    - each value = Σ pct·v / Σ pct over the periods where both `pct` and `v` are non-null; null if there are none.
    - This is D13, used for every r6 two-month average. With `n_periods = 1` it returns the single period.
  - `inputs.task_families(level: Literal["iwa", "gwa", "dwa"] = "iwa", *, tasks_to_dwas: Path | None = None, dwa_reference: Path | None = None) -> pl.DataFrame`. Columns `task_id (Int64), family (str)`, unique pairs.
    - `iwa` = `IWA ID`; `gwa` = `Element ID`; `dwa` = `DWA ID`.
    - The defaults are the registry keys `onet_29_3_tasks_to_dwas` and `onet_29_3_dwa_reference`. Both are tab-separated; the columns are verified as `O*NET-SOC Code, Task ID, DWA ID, Date, Domain Source` and `Element ID, IWA ID, DWA ID, DWA Title`.
  - `inputs.ERROR_COST_MAJOR = ("23", "29")`, `ERROR_COST_MINOR = ("13-2",)`, `ERROR_COST_CODES = ("11-3031", "41-3031")`.
  - `inputs.error_cost_indicator(soc6: pl.Series) -> pl.Series`: Int8, 1 if `soc6[:2]` ∈ MAJOR or `soc6[:4]` ∈ MINOR or `soc6` ∈ CODES (D15).
  - `inputs.log_wage_table(wages: pl.DataFrame) -> pl.DataFrame`: `soc6, log_wage, wage_status`, with `log_wage = ln(a_median)`, null when suppressed.
  - `result.Coef` (frozen dataclass): `name: str, estimate: float, se: float, ci_low: float, ci_high: float, p: float, df: int | None`. `df` None means normal reference.
  - `result.HypothesisResult` (dataclass) with:
    - `hypothesis: str`, `outcome: str`;
    - `coefs: dict[str, Coef]`;
    - `p_family: float`, the one p-value per hypothesis (D17);
    - `sample: dict[str, int | float]`, `drops: dict[str, float]` (percent of total usage by reason);
    - `diagnostics: dict[str, object]`, `notes: list[str]`;
    - `to_dict() -> dict`, JSON-safe (floats, ints, str, lists, dicts only).

- [ ] **Step 1: Write failing tests:**
  - `test_two_month_mean_skips_unpublished_month`:
    - one task with April (pct 3, automation 60) and May (pct 1, automation 20) gives automation 50.0 and weight 2.0;
    - with May automation null, automation 60.0 and weight 2.0;
    - with May pct null, automation 60.0 and weight 1.5.
  - `test_two_month_mean_single_period`: `n_periods=1` returns the values and pct unchanged.
  - `test_task_families_split_and_levels` (fixture files written in the test):
    - task 1 → DWAs `A.I01.D01`, `A.I02.D01`, `A.I01.D02` gives IWAs {`A.I01`, `A.I02`} (2 rows), GWA {`A`} (1 row) and 3 DWA rows;
    - a task with no DWA row is absent.
  - `test_error_cost_indicator`: `23-1011`, `29-1141`, `13-2011`, `11-3031`, `41-3031` → 1; `13-1111`, `11-3021`, `41-2031`, `15-1252` → 0.
  - `test_wages_topcode_and_suppression` (xlsx built in-test like `tests/bls/test_oews.py`): `A_MEDIAN` values `"50000"`, `"#"`, `"*"`, `"**"` give a_median `50000.0, 239200.0, null, null` and status `published, topcoded, suppressed, suppressed`.
  - `test_load_national_unchanged`: `load_national` on the same fixture still returns null for `#`, because the exposure inputs must not move.
  - `test_hypothesis_result_to_dict_is_json_safe`: `json.dumps(r.to_dict())` succeeds and round-trips `p_family`.
- [ ] **Step 2: Run** `uv run pytest tests/rq1/test_inputs.py tests/bls -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Read the O\*NET files with `quote_char=None` and tab separator, as `aei/tasks._read_tasks` does.
- [ ] **Step 4: Data check** (`@pytest.mark.data`):
  - `test_real_families_cover_r6_tasks`: the share of r6 `claude_ai` global matched-task D13 weight whose Task ID (or any candidate ID) has an IWA is printed and is ≥ 0.9. This is coverage only.
  - `test_real_topcoded_count`: the number of `topcoded` 2024 occupations is printed and is ≥ 1.
- [ ] **Step 5: Run tests and ruff, then commit** `feat(rq1): D13 two-month averaging, top-coded OEWS wages, D14 task families, D15 error cost`.

### Task 4: H1/H3 unit — the (task, occupation, family) rows

**Files:**
- Create: `src/aideleg/rq1/rows.py`
- Test: `tests/rq1/test_rows.py`

**Interfaces:**
- Consumes: `two_month_mean`, `task_families`, `log_wage_table`, `error_cost_indicator` (Task 3); `TaskIndex.task_ids_for`, `occupations_for_text`, `occupations_for`; `oews_code_for`; `occupations.SUPPRESSION`.
- Produces:
  - `rows.OUTCOME_COLUMNS = ("automation_pct", "augmentation_pct", "directive_pct", "feedback_loop_pct", "task_iteration_pct", "validation_pct", "learning_pct", "ai_autonomy_mean", "automation_share_all_lb", "automation_share_all_ub")`
  - `rows.ROW_COLUMNS = ["task_node", "task_code", "soc6", "oews_code", "occ_code", "family", "weight", "n_occ", "n_family", *OUTCOME_COLUMNS, "human_education_years_mean", "log_wage", "wage_status", "error_cost"]`
  - `rows.TaskRows` (frozen dataclass):
    - `rows: pl.DataFrame`;
    - `total_weight: float`, the D13 weight summed over **every** global `onet_task` node of the release and source, including `unmatched:*`;
    - `structural_drops: dict[str, float]`, percent of `total_weight` by reason;
    - `release: str`, `source: str`, `family_level: str`.
  - `rows.build_task_rows(panel, index, families, wages, oews_codes: set[str], soc_structure, *, release: str = "r6", source: str = "claude_ai", family_level: str = "iwa") -> TaskRows`.

Rules (PAP §4.1 H1 table, D4, D13, D14). Write them into the module docstring:
- **Task values.** Global `onet_task` rows of `release`/`source`, pivoted per period.
  - `automation_share_all_lb/_ub` are computed **per period** with the components in `occupations.SUPPRESSION[release]` and the formula of `occupations._wide`, then averaged.
  - Every value column is averaged by `two_month_mean` with `n_periods` = the number of distinct `period_start` values of the release and source.
- **Occupations.** A task's candidate Task IDs are `index.task_ids_for(node_name)` ∪ {`int(node_id)`}. Its occupations are the sorted set of `soc6 = code[:7]` over `occupations_for_text(node_name)` ∪ `occupations_for(int(node_id))`, the same union as `occupations._task_occupations` (ruling R6). `n_occ` = the number of distinct soc6.
- **Families.** Families are the union over the candidate Task IDs. `n_family` = their number.
- **Rows.** One row per (task, soc6, family). `weight` = task weight / (`n_occ` × `n_family`), so usage is conserved.
- **OEWS code and wage.** `oews_code` = `oews_code_for(soc6, oews_codes, soc_structure)`, which may be null. `log_wage` and `wage_status` come from the OEWS code: status `"no_oews_code"` if it is null, else the wage table's status.
- **Error cost.** `error_cost` = `error_cost_indicator(soc6)`.
- **Cluster codes.** `task_code` = dense integer code of `task_node` (= panel `node_id`). `occ_code` = dense integer code of `soc6`. The occupation cluster is the soc6 code as the PAP states. Two soc6 codes that share an OEWS code are separate rows and clusters, with the same wage.
- **Structural drops,** in this order, each node counted once under its first reason:
  - `unmatched_task` (`node_id` starts with `unmatched:`);
  - `no_occupation`;
  - `no_family`;
  - `zero_weight` (weight 0; these rows carry no usage).
- **Variable-level drops** (missing outcome, predictor or OEWS code) are not applied here. Each estimator applies them to its own variables (Task 6).

- [ ] **Step 1: Write failing tests** on a hand-built panel fixture: two r6 months, global `onet_task` rows, an `index` from `TaskIndex.from_onet` on a fixture file, two families, and a 4-occupation wage table.
  - `test_weights_conserve_usage`: a task with weight 6, occupations {A, B, C} and families {f1, f2} gives 6 rows of weight 1.0 each, `n_occ == 3`, `n_family == 2`.
  - `test_structural_drop_shares`: total weight 10:
    - an `unmatched:none` node (2) → `structural_drops["unmatched_task"] == 20.0`;
    - a matched node with no family (1) → `no_family == 10.0`.
  - `test_wage_status_no_oews_code_kept_as_row`: a soc6 with no OEWS code keeps its row, with `wage_status == "no_oews_code"` and null `log_wage`.
  - `test_topcoded_wage_log`: a top-coded occupation has `log_wage == math.log(239200.0)`.
  - `test_bounds_computed_per_period_then_averaged`:
    - April: automation 60, none_pct 10, pct 1;
    - May: automation 40, none_pct 30, pct 1;
    - lb = mean(54, 28) = 41.0 (weights equal), not 50·0.8 = 40.
  - `test_union_of_candidate_ids`: a statement with two Task IDs in two occupations gets both occupations.
  - `test_columns_and_codes`: `rows.columns == ROW_COLUMNS`; `occ_code` and `task_code` are 0-based dense ints.
- [ ] **Step 2: Run** `uv run pytest tests/rq1/test_rows.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `build_task_rows`. Reuse `occupations.SUPPRESSION`. Do not import private helpers; re-derive the two-line union in `rows.py`.
- [ ] **Step 4: Data check (coverage only)** (`@pytest.mark.data`):
  - `test_real_rows_coverage` builds r6 `claude_ai` rows. It prints `total_weight`, `structural_drops`, the row count, and the numbers of tasks, soc6 and families.
  - It asserts `sum(structural_drops.values()) < 15.0`, and STOPs and reports to the controller if that fails.
  - It must not print or summarise any outcome column.
- [ ] **Step 5: Run tests and ruff, then commit** `feat(rq1): H1/H3 task-occupation-IWA rows with usage-conserving weights and drop accounting`.

### Task 5: The two-way cluster estimator (PAP §4 top block)

**Files:**
- Create: `src/aideleg/rq1/twoway.py`
- Test: `tests/rq1/test_twoway.py`

**Interfaces:**
- Consumes: `Coef` (Task 3).
- Produces:
  - `twoway.psd_clip(v: np.ndarray) -> tuple[np.ndarray, float]`. It returns `U·max(Λ,0)·Uᵀ` (via `numpy.linalg.eigh`) and the smallest eigenvalue.
  - `twoway.resolve_tested_cov(v_two: np.ndarray, v_occ: np.ndarray, v_task: np.ndarray, idx: list[int]) -> tuple[np.ndarray, bool, float, list[int]]`:
    - it takes the block `idx` of `v_two`, clips it if its smallest eigenvalue is < 0, and returns (block, clipped, min_eig, fallback_positions);
    - a tested variance that is ≤ `1e-12 · max(v_occ[i,i], v_task[i,i])` after clipping is replaced by `max(v_occ[i,i], v_task[i,i])`. The variance is replaced, so the SE is the larger one-way SE. Its off-diagonals are left as they are.
  - `twoway.TwoWayFit` (dataclass) with:
    - `coefs: dict[str, Coef]` (tested only);
    - `df_inference: int`, `n_obs: int`, `g_occ: int`, `g_task: int`;
    - `psd_clipped: bool`, `min_eigenvalue: float`, `zero_variance_fallback: list[str]`;
    - `se_oneway_occ: dict[str, float]`, `se_oneway_task: dict[str, float]`, `p_oneway_occ: dict[str, float]`.
  - `twoway.twoway_wls(y, X, w, occ_id, task_id, *, names: list[str], tested: list[str]) -> TwoWayFit`.

Exact call (PAP §4; do not substitute):
```
fit = statsmodels.api.WLS(y, X, weights=w).fit(
    cov_type="cluster",
    cov_kwds={"groups": numpy.column_stack([occ_id, task_id]), "use_correction": True},
    use_t=True)
```
Then:
- `df_inference = fit.df_resid_inference`, which is min(G_occ, G_task) − 1.
- One-way covariances come from `fit.get_robustcov_results`, or from refitting with `groups=occ_id` / `groups=task_id`, same `use_correction`.
- After `resolve_tested_cov`, SE = √diag, t = β/SE, two-sided p = `2·scipy.stats.t.sf(|t|, df_inference)`, 95% CI = β ± `t.ppf(0.975, df_inference)`·SE.
- `p_oneway_occ` uses the occupation one-way SE with df = G_occ − 1. It feeds R38 in Plan 4 and is not used in any decision.
- The function never drops rows: callers pass complete arrays.

- [ ] **Step 1: Write failing tests:**
  - `test_matches_manual_cgm`: on seeded synthetic data (n = 200, 15 occupation and 20 task clusters, random weights), the SEs equal a manual Cameron–Gelbach–Miller computation, `rtol=1e-10`. The manual computation is written in the test: scores = `wexog·wresid`, bread = `(X'WX)⁻¹`, each term scaled by `G/(G−1)·(n−1)/(n−k)`, V = V_occ + V_task − V_occ∩task.
  - `test_df_is_min_clusters_minus_one`: `df_inference == 14` for G = (15, 20).
  - `test_psd_clip_known_matrix`: `psd_clip([[1,2],[2,1]])` returns `[[1.5,1.5],[1.5,1.5]]` and −1.0.
  - `test_resolve_tested_cov_clips_and_falls_back`: `v_two=[[-0.5]]`, `v_occ=[[0.04]]`, `v_task=[[0.09]]` gives variance 0.09 (SE 0.3), clipped True and fallback `[0]`.
  - `test_fallback_reported_in_fit`: a `twoway_wls` on data built so the tested block is negative. Use 2 occupations × 2 tasks with perfectly crossed residuals, or monkeypatch the statsmodels covariance. The test asserts that `psd_clipped` and `zero_variance_fallback` name the coefficient.
  - `test_p_and_ci_use_df_inference`: p equals `2*t.sf(|β/se|, df)` and the CI half-width equals `t.ppf(.975, df)*se`.
- [ ] **Step 2: Run** `uv run pytest tests/rq1/test_twoway.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run tests and ruff, then commit** `feat(rq1): two-way clustered WLS exactly as PAP §4 with the non-PSD rule`.

### Task 6: H1 and H3 estimators (PAP §4.1, §4.3, D17, P13)

**Files:**
- Create: `src/aideleg/rq1/h1h3.py`, `tests/rq1/synth.py` (synthetic `TaskRows` generator shared by later tests)
- Test: `tests/rq1/test_h1h3.py`

**Interfaces:**
- Consumes: `TaskRows`, `ROW_COLUMNS` (Task 4); `twoway_wls` (Task 5); `HypothesisResult`, `Coef`.
- Produces:
  - `synth.task_rows(seed: int, *, n_occ=40, n_task=400, n_family=20, beta_educ=0.0, beta_wage=0.0, gamma=0.0, pure_error_cost_tasks=False) -> TaskRows`. Each task gets 1–3 occupations and 1–2 families, the outcome is constant within a task, and noise sd is 5.
  - `h1h3.attenuation_factor(x: np.ndarray, w: np.ndarray, family: np.ndarray, task: np.ndarray) -> float`:
    - r = x minus its w-weighted mean within family;
    - r̄ = the w-weighted mean of r within (task, family);
    - returns Σ w·r̄² / Σ w·r².
  - `h1h3.estimate_h1(tr: TaskRows, outcome: str = "automation_pct", predictors: tuple[str, str] = ("human_education_years_mean", "log_wage")) -> HypothesisResult`.
  - `h1h3.estimate_h3(tr: TaskRows, outcome: str = "validation_pct", indicator: str = "error_cost", covariates: tuple[str, ...] = ()) -> HypothesisResult`.

Rules:
- **Variable-level drops** apply only to the estimator's own variables (outcome, predictors/indicator, covariates), in that order. Reasons are `missing_<col>`. For `log_wage` the reason is `no_oews_code` or `wage_suppressed`, by `wage_status`. They are reported in percent of `tr.total_weight`, merged with `tr.structural_drops`. Weights are not renormalised.
  - H3 with no covariates requires no OEWS code, wage or education, because the PAP says it "applies the same rule to its own variables". This is an interpretation fixed now; the module docstring states it.
- **Design.** Regressors first, then one dummy per family present in the sample, with no constant. The family dummies are the IWA fixed effects.
- **H1.**
  - `coefs` = {`human_education_years_mean`, `log_wage`} under their column names.
  - `p_family = max(p_educ, p_wage)` (D17 intersection–union).
  - `diagnostics["attenuation_log_wage"] = attenuation_factor(log_wage, …)`.
- **H3.**
  - `coefs` = {indicator, *covariates}; `p_family = p[indicator]`.
  - `diagnostics["attenuation_error_cost"]`.
- **Both.**
  - `diagnostics` also carries every `TwoWayFit` field except `coefs`.
  - `sample` = {`n_rows`, `n_tasks`, `n_occ`, `n_family`, `g_occ`, `g_task`, `df_inference`}.
  - `notes` lists each use of the non-PSD rule in the words "non-PSD rule applied to <coef block>: smallest eigenvalue <x>; <fallback>".

- [ ] **Step 1: Write failing tests** (all synthetic):
  - `test_h1_recovers_planted_education`: `synth.task_rows(SEED, beta_educ=-2)` gives β_e within ±0.3 of −2 and `p_family < 0.01`.
  - `test_h1_wage_coefficient_is_attenuated_as_p13_states`: with `beta_wage=-3` (outcome built on the task's allocation-weighted mean log wage), `β_w / attenuation_log_wage` is within ±0.4 of −3.
  - `test_attenuation_factor_hand_case`: one family, two tasks with two rows each, weights 1, x = (0, 2, 2, 4) gives 0.5.
  - `test_h1_p_family_is_max`: `p_family == max(p_educ, p_wage)`.
  - `test_h1_size_under_permuted_outcome`:
    - 200 permutations of the outcome **across tasks** (the task's value moves with its rows; `numpy.random.default_rng(SEED)`) on a `beta_educ=0` dataset;
    - the rejection rate of `p_family ≤ 0.05` is ≤ 0.08;
    - the rejection rate of p_educ ≤ 0.05 is in [0.01, 0.10].
  - `test_h3_recovers_gamma_and_attenuation_one`: `synth.task_rows(SEED, gamma=5, pure_error_cost_tasks=True)` gives γ within ±0.5 of 5 and `attenuation_error_cost == pytest.approx(1.0)`.
  - `test_h3_ignores_wage_missingness`: H3 keeps rows with `wage_status == "no_oews_code"`, while H1 drops them, and H1's `drops["no_oews_code"]` equals their weight share.
  - `test_outcome_is_an_argument`: `estimate_h1(tr, outcome="ai_autonomy_mean")` uses that column (a planted effect on it is recovered); `estimate_h3(tr, covariates=("human_education_years_mean","log_wage"))` returns three coefs.
- [ ] **Step 2: Run** `uv run pytest tests/rq1/test_h1h3.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run tests and ruff, then commit** `feat(rq1): H1 (intersection-union p) and H3 estimators with P13 attenuation factors`.

### Task 7: H2 — panel, task-clustered trend, release-level wild bootstrap, release-label RI, release effects (PAP §4.2, §5, D2, D22)

**Files:**
- Create: `src/aideleg/rq1/h2.py`
- Test: `tests/rq1/test_h2.py`

**Interfaces:**
- Consumes: `two_month_mean` (Task 3), `HypothesisResult`, `Coef`; the panel's `period_start`/`period_end`; `config.RELEASES`.
- Produces:
  - `h2.H2_RELEASES = ("r2", "r3", "r4", "r5")`
  - `h2.WEBB = (-math.sqrt(1.5), -1.0, -math.sqrt(0.5), math.sqrt(0.5), 1.0, math.sqrt(1.5))`
  - `h2.release_times(panel, releases, basis: Literal["midpoint", "publication"] = "midpoint") -> dict[str, float]`:
    - midpoint basis: t_r = (mid_r − mid_r2) days / 365.25, where mid = `min(period_start)` + (`max(period_end)` − `min(period_start)`)/2 over the release's `claude_ai` periods;
    - publication basis: (`RELEASES[r]` − `RELEASES["r2"]`) days / 365.25 (R36);
    - the reference is always r2.
  - `h2.build_h2_panel(panel, *, releases=H2_RELEASES, source="claude_ai", outcome="automation_pct", balanced=True, time_basis="midpoint") -> pl.DataFrame`. Columns `task_node, release, t, <outcome>, weight`.
    - Global `onet_task` rows, `unmatched:*` excluded.
    - A release with several periods (r6) is first averaged by `two_month_mean`.
    - `balanced=True` keeps tasks with a non-null outcome in **every** listed release.
    - `balanced=False` keeps every (task, release) row with a non-null outcome, for tasks that have such rows in **at least two** of the listed releases (a one-release task has no within-task variation). This is the one unbalanced-panel rule of the study **[default]**: the confirmatory H2 never uses it; Plan 4's R22 uses it through this builder and logs it as a §11 `C-` entry before R22 runs.
    - `weight` = the task's mean D13 pct over the listed releases, unpublished = 0, constant across the task's rows.
  - `h2.clustered_within(y, X, w, task, tested: int) -> tuple[np.ndarray, np.ndarray]`. It returns (β, cov) for the columns of `X` after weighted within-task demeaning.
    - The cov is the task-clustered CRV1 with `use_correction` scaling `G/(G−1)·(n−1)/(n−k)`, where k = number of tasks + number of columns of X.
    - It equals the statsmodels dummy-variable fit. Task 7's tests prove this; it is the fast path for the 1,296 + 24 refits.
  - `h2.estimate_h2(df, outcome: str = "automation_pct", *, r6_indicator: bool = False) -> HypothesisResult`.
  - `h2.wild_bootstrap_p(df, outcome, *, r6_indicator=False) -> tuple[float, int]` returns (p, number of draws).
  - `h2.release_label_p(df, outcome) -> float`.
  - `h2.release_effects(df, outcome, base="r2") -> dict[str, Coef]`.

Exact primary call (PAP §4.2): `statsmodels.api.WLS(y, [t, task dummies (+ r6 dummy)], weights=w).fit(cov_type="cluster", cov_kwds={"groups": task_code}, use_t=True)`, with no constant and all task dummies. `coefs["trend"]` comes from it: two-sided p and 95% CI with `df_resid_inference` = G_task − 1.

Wild bootstrap (D22 item 3):
- Clusters = releases.
- Restricted model = task FE (+ r6 dummy), giving fitted ŷ⁰ and residuals ũ.
- For every one of the 6^R weight vectors v ∈ WEBB^R (`itertools.product`, R = number of releases, 1,296 for R = 4): y* = ŷ⁰ + v[release]·ũ. Refit with `clustered_within` and take t* = β*/se* of the trend.
- p = #{|t*| ≥ |t|} / 6^R.
- `diagnostics` gets `p_wild`, `n_wild_draws`.

Release-label RI (D22 item 4): every permutation of the R time values over the R releases (24 for R = 4, identity included), each scored by the task-clustered |t| of the trend. p = #{|t_perm| ≥ |t|} / R!. It is reported in `diagnostics["p_release_label"]` with the note "descriptive only; smallest attainable p = 1/24".

Release effects: the same WLS with release dummies (base r2) in place of t, task-clustered, 95% CIs, in `diagnostics["release_effects"]` as `{release: Coef dict}`. These feed the event-style plot (Task 12).

`p_family` = the task-clustered p of the trend. `sample` = {`n_tasks`, `n_rows`, `releases`, `times`}. `notes` always includes:
- the D22 disclosure: "With four clusters the release-level co-condition is demanding and may be conservative";
- the wording: "measured within-task automation", "includes any change in the classifier and in platform scope".

- [ ] **Step 1: Write failing tests:**
  - `test_release_times_midpoints`: with the real r2–r5 windows (in a fixture panel), the times equal `{r2: 0.0, r3: 0.4394250513347023, r4: 0.7159479808350445, r5: 0.945927446954141}` (abs 1e-12).
  - `test_release_times_publication`: `{r2: 0.0, r3: 0.47091033538672145, r4: 0.8049281314168378, r5: 0.9911019849418207}`. With r6 windows 2026-04-01→2026-06-01, the midpoint t_r6 = 1.1704312114989732.
  - `test_balanced_panel_drops_tasks_missing_a_release`: a fixture with r2–r5 rows for T1 (all four published), T2 (r4 outcome null), T3 (no r5 row) and T4 (r2 only):
    - `balanced=True` gives `task_node` set {T1} and 4 rows;
    - `balanced=False` gives {T1, T2, T3} with 4, 3 and 3 rows; T4 is dropped (one release);
    - T2's `weight` under `balanced=False` is the mean of its four `pct` values with the r4 `pct` kept (the outcome was null, not the usage), unpublished = 0.
  - `test_weights_fixed_per_task`: pct (1, 2, 3, 4) over r2–r5 gives weight 2.5 on all four rows.
  - `test_within_matches_statsmodels_dummy_fit`: on random balanced and unbalanced panels (30 tasks), `clustered_within`'s β and t equal the exact statsmodels call (`rtol=1e-10`).
  - `test_webb_enumeration`: `WEBB` values as above; for 4 releases, `n_wild_draws == 1296` and the draws are all distinct.
  - `test_h2_recovers_planted_trend`: y = α_task + 3·t + N(0, 0.5), 500 tasks, gives β within ±0.3 of 3 and a task-clustered p < 1e-6.
  - `test_wild_bootstrap_controls_release_shocks`:
    - 100 datasets, dataset i drawn with `numpy.random.default_rng(SEED + i)`, i = 0…99;
    - each has 200 tasks × the four releases r2–r5 at the midpoint times of `test_release_times_midpoints`, balanced, every `pct` = 1 (so every weight is 1.0);
    - y = α_task + s_release + ε, with α_task ~ N(0, 1) (200 draws), s_release ~ N(0, 2²) (4 draws, one per release), ε ~ N(0, 1) (800 draws), drawn in that order; no trend;
    - the share with `p_wild ≤ 0.0125` is ≤ 0.05;
    - the share with task-clustered p ≤ 0.0125 is ≥ 0.30 (this documents why D22 exists);
    - every dataset reports `n_wild_draws == 1296`.
  - `test_release_label_p_floor`: y = α_task + 3·t + N(0, 0.01) gives `p_release_label == pytest.approx(1/24)`.
  - `test_release_effects_base_r2`: y = α_task + δ_r, δ = (0, 1, 2, 4) + N(0, 0.01), gives effects r3, r4, r5 ≈ 1, 2, 4 (abs 0.05).
  - `test_outcome_and_knobs`: `build_h2_panel(..., outcome="validation_pct", balanced=False, releases=("r2","r3","r4","r5","r6"))` runs on the fixture; `estimate_h2(df, "validation_pct", r6_indicator=True)` has a `coefs["trend"]` and 6^5 wild draws.
- [ ] **Step 2: Run** `uv run pytest tests/rq1/test_h2.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Vectorise the 1,296 refits; the within-transformed X is fixed across draws.
- [ ] **Step 4: Run tests and ruff, then commit** `feat(rq1): H2 trend with task-clustered SEs, release-level Webb wild bootstrap, release-label RI and release effects`.

### Task 8: H4 — country sample, task-mix control, HC3 joint Wald, shift-share (PAP §4.4, D16, D17)

**Files:**
- Create: `src/aideleg/rq1/h4.py`
- Test: `tests/rq1/test_h4.py`

**Interfaces:**
- Consumes: `two_month_mean`, `HypothesisResult`, `Coef`; registry keys `aei_geo_gdp_country`, `aei_geo_wap_country`, `aei_geo_gdp_us_state`, `aei_geo_wap_us_state`.
- Produces:
  - `h4.GeoSample` (frozen dataclass):
    - `frame: pl.DataFrame`, with columns `geo_id, automation_pct, aui, log_aui, income, log_income, mix, usage_pct`;
    - `excluded: dict[str, list[str]]`, reason → geo_ids;
    - `global_automation: float`, the global overall `automation_pct`, two-month mean;
    - `m_global: float`, the same mix formula applied to the global GWA shares.
  - `h4.build_geo_sample(panel, *, release="r6", source="claude_ai", geo: Literal["country", "us_state"] = "country", mix_level: Literal["gwa", "iwa"] = "gwa", require_income: bool = True, gdp: pl.DataFrame | None = None, wap: pl.DataFrame | None = None) -> GeoSample`.
  - `h4.estimate_h4(frame, outcome: str = "automation_pct", predictors: tuple[str, str] = ("log_aui", "log_income"), control: str = "mix", weights: str | None = None) -> HypothesisResult`.
  - `h4.shift_share(frame: pl.DataFrame, global_automation: float) -> pl.DataFrame`, with columns `geo_id, gap, mix_part, within_part`:
    - `gap = automation_pct − global_automation`;
    - `mix_part = mix − global_automation`;
    - `within_part = automation_pct − mix`.

Rules (D16):
- **Geographies.** `geo="country"` uses `geo_level == "country"` with ISO-3 `geo_id`. `geo="us_state"` uses `geo_level == "subregion"` with `geo_id` starting `US-`, as R28 needs.
- **Releases.** The builder needs the release's geography `usage_per_capita_index` and `onet_gwa`/`onet_iwa` rows. If either is absent for `release`/`geo` it raises `ValueError` naming the missing metric or node type. r4 and r5 publish neither for countries, so R28's r4/r5 country parts are built by Plan 4's own construction (Plan 4 Task 13), which then calls `estimate_h4` here.
- **Variables.** `automation_pct`, `aui` (`usage_per_capita_index`) and `usage_pct` come from the `overall` taxonomy. Each is the **equal-weighted mean of the two published monthly values**.
- **Sample.** A geography needs both months of `automation_pct` and `usage_per_capita_index` for its inclusion; otherwise its reason is `missing_month`. The log is taken of the two-month mean: `log_aui = ln(mean)`.
- **Income.** `income` = GDP 2024 / working-age population 2024:
  - countries join on `iso_alpha_3`;
  - states join on `"US-" + state_code`;
  - the CSVs are read with `infer_schema_length=0` (all strings, so `NA` stays `"NA"`), then cast;
  - a missing value gives reason `missing_income` when `require_income`;
  - with `require_income=False`, income stays null and the geography is kept. Descriptive maps use this.
- **Task-mix control.** M_c = Σ_g s̄_cg·ā_g.
  - s_cg = the geography's `pct` over `onet_gwa` (or `onet_iwa`) nodes, renormalised over the nodes published in that month. An unpublished node is 0.
  - s̄ = the mean over the two months.
  - ā_g = the global `onet_gwa`/`onet_iwa` `automation_pct` averaged by `two_month_mean` (weights = its global `pct`).
  - The sum runs over g with a non-null ā_g, and s̄ is renormalised over them.
  - A geography with no published node gets reason `missing_mix`.
- **Estimator.** `statsmodels.api.OLS(y, [1, log_aui, log_income, mix]).fit(cov_type="HC3")`, or `WLS(..., weights=frame[weights])` when `weights` is given (R28).
  - `p_family` = `fit.wald_test(R, use_f=True, scalar=True).pvalue`, with R selecting the two predictors.
  - `diagnostics` holds `F`, `df_num` (= 2) and `df_denom` (= n − 4).
  - `coefs` holds the two predictors and `mix`, with `fit.conf_int()` 95% intervals, `df=None` (normal, as the fit's default) and individual HC3 p-values (feeding R25 in Plan 4).

- [ ] **Step 1: Write failing tests:**
  - `test_mix_control_hand_case`:
    - month 1 GWA pct {g1: 30, g2: 10}, month 2 {g1: 20, g2: 20}, ā = {g1: 40, g2: 80} gives M = 55.0;
    - with ā_g2 unpublished, M = 40.0.
  - `test_logs_of_two_month_means`: AUI 1 and 3 gives `log_aui == math.log(2)`, not the mean of logs.
  - `test_country_join_keeps_namibia`: fixture WAP/GDP CSVs where Namibia has `country_code` `NA` keep `"NAM"` in the frame with a non-null income.
  - `test_missing_month_excluded_and_listed`: a country with only April automation appears in `excluded["missing_month"]`.
  - `test_h4_recovers_planted_coefficients_and_df`: 60 synthetic countries, y = 50 + 2·log_aui − 1·log_income + 0.5·mix + N(0,1), give b₁, b₂ within ±0.3 of 2 and −1, `df_num == 2` and `df_denom == 56`.
  - `test_h4_p_is_joint_wald`: `p_family` equals `fit.wald_test(...).pvalue` recomputed in the test.
  - `test_shift_share_identity`: automation 60, mix 55, global 50 gives gap 10, mix_part 5, within_part 5. On random frames, `mix_part + within_part == gap` (abs 1e-12).
  - `test_us_state_geo`: a fixture with `US-CA` and `US-TX` subregion rows and state GDP/WAP builds two rows with `geo_id` `US-CA` and `US-TX`.
  - `test_outcome_is_an_argument`: `estimate_h4(frame, outcome="validation_pct")` runs on a frame carrying that column.
  - `test_release_without_country_aui_raises`: a fixture release with country `automation_pct` rows but no `usage_per_capita_index` raises `ValueError` matching `"usage_per_capita_index"`.
- [ ] **Step 2: Run** `uv run pytest tests/rq1/test_h4.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** For `outcome` ≠ `automation_pct`, `build_geo_sample` also carries `validation_pct` and `ai_autonomy_mean` (two-month means), so Plan 4 can vary the outcome.
- [ ] **Step 4: Run tests and ruff, then commit** `feat(rq1): H4 country sample with GWA task-mix control, HC3 joint Wald, shift-share split`.

### Task 9: The RQ1 family, decision rules and fixed wording (PAP §4, §4.0, D17, D22, §0.2)

**Files:**
- Create: `src/aideleg/rq1/family.py`
- Test: `tests/rq1/test_family.py`

**Interfaces:**
- Consumes: `HypothesisResult`.
- Produces:
  - `family.RQ1_FAMILY = ("H1", "H3", "H4")`, `FAMILY_ALPHA = 0.0375`, `H2_ALPHA = 0.0125`
  - `family.HolmStep` (frozen dataclass): `rank: int, level: float, rejected: bool`
  - `family.holm(p: dict[str, float], alpha: float) -> dict[str, HolmStep]`:
    - sort ascending, with ties broken by name;
    - the k-th (1-based) of m is compared with α/(m−k+1);
    - stop at the first non-rejection; every later one is not rejected.
  - `family.Decision` (frozen dataclass): `hypothesis: str, status: Literal["supported", "contradicts", "rejected_mixed_sign", "not_rejected"], rejected: bool, level: float, text: str`
  - `family.decide(results: dict[str, HypothesisResult]) -> dict[str, Decision]`
  - `family.SPLIT_STATEMENT = "RQ1's α = 0.05 is split (D22): H2 is tested on its own at α = 0.0125, and {H1, H3, H4} by Holm at family-wise α = 0.0375, so the RQ1 family-wise error is at most 0.05."`

Decision rules (copy exactly):
- **H1.** Holm-rejected at `p_family`:
  - both coefficients < 0 → `supported`;
  - both > 0 → `contradicts`;
  - otherwise → `rejected_mixed_sign`.
- **H3.** Holm-rejected: γ > 0 → `supported`; γ < 0 → `contradicts`.
- **H4.** Holm-rejected → `supported`. There is no sign condition.
- **H2.** Let `p_c` = task-clustered p and `p_w` = `diagnostics["p_wild"]`.
  - `p_c ≤ 0.0125` and `p_w ≤ 0.0125` and β > 0 → `supported`;
  - the same p conditions with β < 0 → `contradicts`;
  - else `not_rejected`, with each failed condition named: "task-clustered p = {p_c:.4f} > 0.0125", "release-level wild bootstrap p = {p_w:.4f} > 0.0125".
- **Text templates.** Exact strings, with `{…}` filled:
  - supported: `"{H} is supported: {rule}. {coef_lines}"`;
  - contradicts: `"{H}: the null is rejected, and the estimate contradicts the hypothesis ({coef_lines})."`;
  - not rejected: `"{H} is not rejected (H0: {null}). {coef_lines}"`;
  - nulls: H1 `"β_e = 0 or β_w = 0"`, H2 `"β = 0"`, H3 `"γ = 0"`, H4 `"b₁ = b₂ = 0"`;
  - `coef_lines`: one `"{name} = {est:.3f} (95% CI [{lo:.3f}, {hi:.3f}], p = {p:.4f})"` per coefficient, joined with `"; "`;
  - `rule` for H1/H3/H4: `"Holm over {H1, H3, H4} at family-wise 0.0375 rejects at step {rank} (level {level:.5f}, p = {p:.4f})"`; for H2: `"task-clustered p = {p_c:.4f} and release-level wild bootstrap p = {p_w:.4f}, both ≤ 0.0125, and β > 0"`.

- [ ] **Step 1: Write failing tests:**
  - `test_holm_stops_at_first_failure`: {H1: 0.01, H3: 0.02, H4: 0.03} at 0.0375 gives levels (0.0125, 0.01875, 0.0375) and rejections (True, False, False).
  - `test_holm_all_reject`: {0.012, 0.018, 0.037} gives all True.
  - `test_holm_ties_by_name`: {H4: 0.01, H1: 0.01, H3: 0.5} at 0.0375 gives H1 rank 1 (level 0.0125, rejected), H4 rank 2 (level 0.01875, rejected) and H3 rank 3 (level 0.0375, not rejected).
  - `test_h1_statuses`: supported / contradicts / rejected_mixed_sign / not_rejected, each from a constructed `HypothesisResult`.
  - `test_h2_requires_all_three`: `p_c = 0.001`, `p_w = 0.02`, β > 0 gives `not_rejected`, and the text contains `"release-level wild bootstrap p = 0.0200 > 0.0125"`.
  - `test_h4_two_sided`: a rejected H4 with negative coefficients is `supported`.
  - `test_wording_never_says_no_effect`: across every constructed decision, `"no effect"` is not in `text.lower()`.
- [ ] **Step 2: Run** `uv run pytest tests/rq1/test_family.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run tests and ruff, then commit** `feat(rq1): Holm family {H1,H3,H4} at 0.0375, H2 co-conditions at 0.0125, fixed decision wording`.

### Task 10: The write-once RQ1 runner, its dry run, and the frozen-code guard (P-RQ1)

**Files:**
- Create: `src/aideleg/rq1/confirm.py`, `tests/rq1/test_frozen.py`
- Modify: `Makefile` (targets `rq1-dry-run`, `rq1-confirm`), `tests/rq1/synth.py` (add `synthetic_inputs()`)
- Test: `tests/rq1/test_confirm.py`

**Interfaces:**
- Consumes: everything in Tasks 3–9; `seal.pap_frozen`; `default_index`; `load_national`; `load_national_wages`.
- Produces:
  - `confirm.OUT_DIR = ROOT / "docs/results/rq1"`; file names `confirmatory_rq1.attempt`, `confirmatory_rq1.json`, `confirmatory_rq1.md`, `confirmatory_rq1.log`.
  - `confirm.BOUND_FILES: tuple[str, ...]`: `src/aideleg/rq1/{__init__,result,inputs,rows,twoway,h1h3,h2,h4,family,confirm}.py`, `src/aideleg/bls/oews.py`, `src/aideleg/occupations.py`, `src/aideleg/aei/tasks.py`.
    - `pyproject.toml` and `uv.lock` are not bound by blob, so that Plans 3–4 can add unrelated dependencies. Instead, the guard binds the installed versions of numpy, scipy, polars and statsmodels recorded in `meta.versions`.
    - Plans 3–4 put new code in new modules and never edit a bound file.
  - `confirm.OUTCOME_METRICS = frozenset({"automation_pct", "augmentation_pct", "directive_pct", "feedback_loop_pct", "task_iteration_pct", "validation_pct", "learning_pct", "ai_autonomy_mean", "none_pct", "not_classified_pct", "filtered_pct"})`
  - `confirm.Inputs` (dataclass): `panel, index, families, wages, oews_codes, soc_structure, gdp_country, wap_country`. Also `confirm.load_inputs() -> Inputs`, the study defaults.
  - `confirm.check_clean(repo: Path = ROOT) -> str`. It returns HEAD and raises `RefusedError` unless:
    - `pap-v1` is an annotated tag;
    - `git merge-base --is-ancestor pap-v1 HEAD` succeeds;
    - `git status --porcelain --untracked-files=all -- src tests pyproject.toml uv.lock` is empty.
  - `confirm.RefusedError(RuntimeError)`
  - `confirm.scramble_outcomes(panel: pl.DataFrame, seed: int) -> pl.DataFrame`. It replaces the non-null `value` of every row whose metric is in OUTCOME_METRICS with `rng.uniform(0, 100)` (`ai_autonomy_mean`: `rng.uniform(1, 5)`). It adds and removes no rows, so the samples and their drops match the real run.
  - `confirm.run(out_dir: Path = OUT_DIR, *, scramble_seed: int | None = None, inputs: Inputs | None = None, repo: Path = ROOT) -> dict`
  - `confirm.main(argv: list[str] | None = None) -> int`, with CLI `python -m aideleg.rq1.confirm [--dry-run DIR]`.

`run` order (each step completes before the next):
1. `head = check_clean(repo)`.
2. Refuse (`RefusedError`) if the marker or any of the three outputs exists in `out_dir`.
3. With a dry run (`scramble_seed` set), refuse if `out_dir` resolves inside `ROOT/"docs/results"`.
4. Create the marker with `open(..., "x")` and write UTC time and HEAD into it. **Only now** load `inputs` (`load_inputs()` if None).
5. Wrap everything after the marker in `try`. On any exception, write the traceback to `confirmatory_rq1.md` (mode `"x"`) and re-raise.
6. If dry run, `scramble_outcomes(panel, scramble_seed)`.
7. Fit, in this order:
   - H1: `build_task_rows` → `estimate_h1`;
   - H3: `estimate_h3`;
   - H2: `build_h2_panel` → `estimate_h2`;
   - H4: `build_geo_sample` → `estimate_h4`;
   - then `decide`.
8. Write the JSON, mode `"x"`: `{"meta": {...}, "alpha": {"H2": 0.0125, "family": 0.0375, "members": ["H1","H3","H4"], "statement": SPLIT_STATEMENT}, "results": {H: r.to_dict()}, "decisions": {H: asdict(d)}}`. `meta` holds:
   - `utc`, `head`, `pap_v1_commit`;
   - `blobs` (`git rev-parse HEAD:<path>` for each BOUND_FILES path);
   - versions of python, numpy, scipy, polars and statsmodels;
   - `seed` (`SEED`), `scrambled` (bool);
   - the `input_sha256` of `data/derived/aei_panel.parquet` and `data/raw/MANIFEST.json`;
   - `panel_sha256_equals_pap` (compared with §9.3's `15ba38ec…bb370`; informational).
9. Write `confirmatory_rq1.md` (mode `"x"`):
   - the split statement;
   - the four decision texts;
   - one coefficient table: hypothesis | coefficient | estimate | 95% CI | p | df;
   - the sample and drop shares;
   - H2's wild and release-label p-values with their notes;
   - H4's F and df;
   - the non-PSD notes;
   - the wording header ("AEI data are conversations matched to O\*NET tasks…").
10. Write `confirmatory_rq1.log` (mode `"x"`): every line the run printed, collected with a logger, including timings.

`tests/rq1/test_frozen.py::test_bound_code_unchanged_since_first_run`:
- skipped while `docs/results/rq1/confirmatory_rq1.json` does not exist or has `meta.scrambled == true`;
- otherwise, for each path in `meta.blobs`, `git hash-object <path>` equals the recorded blob, and `importlib.metadata.version(pkg)` equals `meta.versions[pkg]` for numpy, scipy, polars and statsmodels. On failure the message reads "bound RQ1 code changed after the P-RQ1 first run: record a §11 deviation (PAP §0.5)".

- [ ] **Step 1: Write failing tests** (`tests/rq1/test_confirm.py`; `synth.synthetic_inputs()` builds a small panel with r2–r6 global tasks, r6 country overall/GWA rows, families, wages and GDP/WAP frames):
  - `test_refuses_when_marker_exists_before_loading`: monkeypatch `load_inputs` to raise `AssertionError("loaded")`. With a marker present, `run(tmp)` raises `RefusedError`, not `AssertionError`. Monkeypatch `check_clean` to return `"abc"`.
  - `test_refuses_when_output_exists`: the same, for each of the three outputs.
  - `test_refuses_dirty_tree`: a tmp git repo with an annotated `pap-v1` and an untracked `src/x.py` makes `check_clean(tmp)` raise. A lightweight tag also raises.
  - `test_dry_run_refuses_docs_results`.
  - `test_scramble_changes_only_outcomes`: on a fixture panel, every OUTCOME_METRICS row's value changes; `pct`, `human_education_years_mean`, `usage_per_capita_index` and `usage_pct` rows are byte-identical; the row count is unchanged.
  - `test_failure_after_marker_writes_traceback`: monkeypatch `estimate_h2` to raise. `run` re-raises, the marker exists, and `confirmatory_rq1.md` contains `"Traceback"`.
  - `test_run_on_synthetic_inputs_writes_schema`:
    - `run(tmp, scramble_seed=1, inputs=synthetic_inputs())` writes the JSON with keys `meta, alpha, results, decisions`;
    - `results` has keys `H1, H2, H3, H4`;
    - `alpha["family"] == 0.0375`;
    - each decision status is one of the four literals.
  - `test_bound_files_exist`: every BOUND_FILES path exists.
- [ ] **Step 2: Run** `uv run pytest tests/rq1/test_confirm.py tests/rq1/test_frozen.py -v`. Expected: FAIL (test_frozen skips).
- [ ] **Step 3: Implement** `confirm.py` and the Makefile targets:
  - `rq1-dry-run`: `uv run python -m aideleg.rq1.confirm --dry-run $${TMPDIR:-/tmp}/aideleg-rq1-dry`;
  - `rq1-confirm`: `uv run python -m aideleg.rq1.confirm`, with a comment that it is single-run and write-once.
- [ ] **Step 4: Run** `uv run pytest -q && uv run ruff check`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(rq1): write-once confirmatory runner with attempt marker, outcome-scrambled dry run, frozen-code guard`.
- [ ] **Step 6: Real-data dry run.**
  - Command: `rm -rf "$TMPDIR/aideleg-rq1-dry" && make rq1-dry-run`. Expected: it completes.
  - The implementer reports **only** the `sample` and `drops` blocks of each hypothesis and the run time. These are coverage, and equal to the real run's by construction. They do not open the scrambled coefficients.
  - If a drop share for H1 or H3 exceeds 15% of r6 task usage, or H4 has fewer than 30 countries, STOP and report to the controller. A sample rule may be unimplementable, which would be a deviation candidate.
- [ ] **Step 7: Whole-RQ1 review gate.** The reviewer checks Tasks 3–10 against PAP §4/§5 line by line with the requirement map at the end of this plan:
  - the exact library calls;
  - the D13, D14, D15, D16 and D22 rules;
  - the α split;
  - the wording.
  
  The reviewer confirms the review in the ledger. No code changes are allowed after this gate except fixes it requests, which are re-reviewed.
- [ ] **Step 8: Log Plan 2's pre-result clarifications (before Task 11).** One `uv run python -m aideleg.paplog clarification --title … --rule … --plan "Plan 2 Task <k> (plans committed at <Task 1 Step 1 hash>)"` per row, in this order (each **Rule** is the text below, copied):

  | Title | Task | Rule |
  |---|---|---|
  | H1/H3 occupation cluster | 4 | The occupation cluster is the soc6 code; two soc6 codes sharing an OEWS code are separate rows and clusters with the same wage. |
  | Variable-level drops | 6 | Each estimator drops rows missing its own variables only (outcome, then predictors or indicator, then covariates), reported as percent of total task usage without renormalising; H3 with no covariates needs no OEWS code, wage or education. |
  | Zero variance after PSD clipping | 5 | A tested variance ≤ 1e-12 × the larger one-way variance after clipping is replaced by the larger one-way variance. |
  | R7 bounds in H1/H3 rows | 4 | `automation_share_all_lb/_ub` are computed per period with that release's suppression components, then D13-averaged. |
  | Wage deciles (descriptive) | 13 | Employment-weighted deciles of `a_median` (top-coded at $239,200; suppressed excluded): decile = clip(ceil(10·(cum_emp − tot_emp/2)/total_emp), 1, 10), occupations sorted ascending. |
  | Education bins (descriptive) | 13 | Bins <12, 12–14, 14–16, 16–18, ≥18 years, left-closed; tasks without an education value reported as "not published". |
  | Concentration shares (descriptive) | 13 | The top-x% share is the usage share of the ⌈x%·n⌉ largest tasks. |
  | RQ2 bootstrap draws (descriptive) | 15 | Spearman ρ by average-tie ranks then Pearson; a draw with a constant vector is excluded and counted; percentile 95% CI; one `default_rng(SEED)` drawn in design order B, A_pooled. |

  Then `uv run pytest tests/test_pap_frozen.py tests/test_paplog.py -q` (PASS) and commit `docs(pap): §11 C-1…C-8 pre-result clarifications for Plan 2 (before the P-RQ1 run)`. The commit touches only the PAP.

### Task 11: P-RQ1 — the single logged first run of H1–H4 on real outcomes

**Files:**
- Create (by the script only): `docs/results/rq1/confirmatory_rq1.{attempt,json,md,log}`

**Interfaces:**
- Consumes: `make rq1-confirm` (Task 10).
- Produces: the committed confirmatory output, which Tasks 12, 16 and Plan 4 read. **Nothing in this task edits code or output.**

- [ ] **Step 1: Preconditions** (the controller verifies and records them in the ledger):
  - Task 10 review gate passed;
  - Task 10 Step 8's `C-` entries are committed (`git log -1 --format=%H -- docs/pap/pre-analysis-plan.md` is an ancestor of HEAD);
  - `uv run pytest -q` passes and `uv run ruff check` is clean;
  - `git status --porcelain --untracked-files=all -- src tests pyproject.toml uv.lock` is empty;
  - `docs/results/rq1/` holds no `confirmatory_rq1.*` file;
  - `git rev-parse HEAD` is recorded.
- [ ] **Step 2: Run once.** `make rq1-confirm`. Do not rerun it under any circumstances.
- [ ] **Step 3: Commit the output unedited.**
  - Run `git add docs/results/rq1/confirmatory_rq1.attempt docs/results/rq1/confirmatory_rq1.json docs/results/rq1/confirmatory_rq1.md docs/results/rq1/confirmatory_rq1.log` and commit `results(rq1): P-RQ1 single logged first run of H1-H4 (output unedited)`.
  - The commit contains only those four files. Its body states HEAD at the run and "first run of the H1–H4 estimators on real outcomes (PAP §0.5 P-RQ1)".
- [ ] **Step 4: Record.** In the ledger, record the commit hash, HEAD at the run, and each decision status as printed. In this task, do not interpret, summarise beyond the statuses, or plot.
- [ ] **Step 5: Verify the guard.** `uv run pytest tests/rq1/test_frozen.py -v`. Expected: PASS (not skipped).
- [ ] **STOP rule.** If the script refuses **before** the marker, nothing was read. Fix the cause, and log the fix in §11 only if it changes bound code (with Ajai's approval). If it fails **after** the marker:
  - commit the marker and the traceback `.md` as they are (same commit rule);
  - STOP and report to Ajai.
  
  A rerun needs a §11 deviation with Ajai's approval. The attempt stays committed, and the hypothesis is reported with that history.

### Task 12: RQ1 confirmatory reporting (tables and figures from the committed JSON only)

**Files:**
- Create: `src/aideleg/results/__init__.py`, `src/aideleg/results/common.py`, `src/aideleg/results/rq1.py`
- Test: `tests/results/test_common.py`, `tests/results/test_rq1_report.py`

**Interfaces:**
- Consumes: `docs/results/rq1/confirmatory_rq1.json`; `figures.apply_style`, `save_figure`, `PALETTE`, `FIGSIZE`.
- Produces (also used by Plans 3 and 4):
  - `common.WORDING = "AEI data are conversations matched to O*NET tasks. Nothing here says anything about job risk, displacement or reassurance about the labour market."`
  - `common.FORBIDDEN_PHRASES = ("job risk", "displacement", "job market", "reassur", "no effect", "accountants use", "workers use")`. These are case-insensitive. `WORDING` itself is exempt: it is checked by exact match and stripped before the scan.
  - `common.write_result_doc(path: Path, title: str, generator: str, sections: list[tuple[str, str]]) -> Path`. It writes the generated-by line, `WORDING`, then the sections. It raises `ValueError` if any forbidden phrase appears outside `WORDING`, or if a table cell matches `r"\d\*+"` (no stars).
  - `common.write_csv(df: pl.DataFrame, path: Path) -> Path`, with floats at full precision.
  - `common.fmt_coef(c: dict) -> str`, in the `family.py` `coef_lines` format.
  - `rq1.report_confirmatory(json_path: Path = OUT_DIR/"confirmatory_rq1.json", out: Path = OUT_DIR) -> list[Path]`. It writes:
    - `docs/results/rq1/confirmatory_table.csv` and `.md`: one row per coefficient (hypothesis, coefficient, estimate, se, ci_low, ci_high, p, df, family p, Holm level, decision status);
    - `docs/results/rq1/decisions.md`: the split statement, the four decision texts verbatim from the JSON, and the H2 disclosure notes;
    - `fig_rq1_coefficients`: a dot-and-CI panel per hypothesis, every coefficient drawn alike whether rejected or not;
    - `fig_rq1_h2_release_effects`: the event-style plot, release effects vs r2 with 95% CIs, x = release time t_r.

  `rq1.README` is written in Task 16.

- [ ] **Step 1: Write failing tests:**
  - `test_write_result_doc_rejects_forbidden_and_stars` (tmp paths):
    - a section `"there is no effect here"` raises `ValueError` matching `"no effect"`;
    - `"Job Risk rises"` raises (the scan is case-insensitive);
    - a table cell `"| 0.12** |"` raises `ValueError` matching `"star"`;
    - a doc whose only forbidden phrases sit inside `WORDING` is written; its line 1 is exactly ``Generated by `aideleg.results.x`. Do not edit by hand.`` and it contains `WORDING` exactly once.
  - `test_table_numbers_equal_json`: on a JSON produced by `run(tmp, scramble_seed=1, inputs=synthetic_inputs())`, every estimate, CI and p in `confirmatory_table.csv` equals the JSON value exactly.
  - `test_decision_texts_copied_verbatim`: on the same JSON, for each H in H1–H4, `json["decisions"][H]["text"]` occurs in `decisions.md` exactly once as a substring, and `SPLIT_STATEMENT` occurs once.
  - `test_report_reads_no_panel`: monkeypatch `polars.read_parquet` to raise; the report still builds. It reads the JSON only.
  - `test_figures_written`: both figure names exist as PDF and PNG in a tmp `out_dir`.
- [ ] **Step 2: Run** `uv run pytest tests/results -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Generate** `uv run python -m aideleg.results.rq1 --confirmatory`. Expected: the files above exist, and `git diff --stat` shows only new files under `docs/results/rq1/` and `docs/paper/figures/`.
- [ ] **Step 5: Run tests and ruff, then commit** `docs(results): RQ1 confirmatory tables, decisions and figures generated from the P-RQ1 output`.

### Task 13: RQ1 descriptive anatomy — collaboration composition and usage concentration (spec §5.2)

**Files:**
- Create: `src/aideleg/describe/__init__.py`, `src/aideleg/describe/anatomy.py`
- Modify: `src/aideleg/results/rq1.py` (adds `report_anatomy`)
- Test: `tests/describe/test_anatomy.py`

**Interfaces:**
- Consumes: `two_month_mean`, `load_national_wages`, `log_wage_table` (Task 3); `occupation_table` (published basis for r6, D9); `exposure.oews_usage`; `load_national`; the panel.
- Produces:
  - `anatomy.PATTERN_COLS = ["directive_pct", "feedback_loop_pct", "task_iteration_pct", "validation_pct", "learning_pct", "automation_pct", "augmentation_pct"]`
  - `anatomy.by_major_group(panel, *, release="r6", source="claude_ai") -> pl.DataFrame`, with columns `major, name, usage_share, *PATTERN_COLS`:
    - global `soc_major` rows (published), `two_month_mean` for each pattern;
    - `usage_share` = D13 weight renormalised to 100 over the published groups.
  - `anatomy.wage_deciles(occ: pl.DataFrame, wages: pl.DataFrame) -> pl.DataFrame`. Columns `soc6, decile`, from employment-weighted deciles of `a_median` (top-coded set; suppressed excluded). Occupations are sorted ascending, and each takes decile `clip(ceil(10·(cum_emp − tot_emp/2)/total_emp), 1, 10)`.
  - `anatomy.by_wage_decile(panel, index, wages, national, soc_structure, *, release="r6", source="claude_ai", basis: Literal["published", "tasks"] = "published") -> pl.DataFrame`. Columns `decile, emp_share, usage_share, n_occ, *PATTERN_COLS`.
    - It takes `occupation_table(..., basis=basis)` per period, then `oews_usage` per period, then `two_month_mean` with weight `usage_share`.
    - `basis="published"` is the D9 primary. `basis="tasks"` is the r6 task-allocated basis that Plan 4's R16 calls; the report never uses it.
    - Within a decile, each pattern is the usage-weighted mean.
    - The usage share of occupations with a suppressed wage is reported in a final row `decile = null`.
  - `anatomy.EDU_EDGES = (12.0, 14.0, 16.0, 18.0)` with labels `("<12", "12–14", "14–16", "16–18", "≥18")`, left-closed.
  - `anatomy.by_education(panel, *, release="r6", source="claude_ai") -> pl.DataFrame`. Columns `bin, usage_share, n_tasks, *PATTERN_COLS`, from global matched `onet_task` rows, D13-averaged, binned on `human_education_years_mean`. Tasks with no education value are reported as `bin = "not published"`.
  - `anatomy.gini(shares: np.ndarray) -> float` = (2 Σ i·x₍ᵢ₎)/(n Σ x) − (n+1)/n, with x ascending and i 1-based.
  - `anatomy.lorenz_points(shares) -> tuple[np.ndarray, np.ndarray]`, both starting at 0.
  - `anatomy.concentration(panel) -> pl.DataFrame`. One row per release × source over global matched `onet_task` `pct`: r1–r6 for `claude_ai`, r3–r6 for `1p_api`; r6 combined by `two_month_mean`; renormalised to 100 over the published matched tasks. Columns `release, source, n_tasks, gini, top1_share, top5_share, top10_share, n_tasks_50pct`, where top-x share = the usage share of the ⌈x%·n⌉ largest tasks.
  - `rq1.report_anatomy(out: Path = OUT_DIR) -> list[Path]` writes:
    - `docs/results/rq1/anatomy.md` + one CSV per table;
    - figures `fig_rq1_composition_major`, `fig_rq1_composition_wage_decile`, `fig_rq1_composition_education` (stacked bars of the five patterns, automation patterns in the two warm palette colours);
    - `fig_rq1_lorenz` (claude_ai r2–r6).
  
  The md states:
  - that composition is computed over published cells only;
  - that the occupation basis is AEI's published SOC rows (D9);
  - that cross-release concentration mixes suppression regimes (PAP §5);
  - that these are descriptive, with no test attached.

- [ ] **Step 1: Write failing tests:**
  - `test_gini_hand_cases`: `gini([0,0,0,1]) == 0.75`; `gini([1,1,1,1]) == 0.0`.
  - `test_lorenz_endpoints`: (0,0) and (1,1).
  - `test_top_shares`: shares (40, 30, 20, 10) give top10_share = 40.0 (⌈0.4⌉ = 1 task) and n_tasks_50pct = 2.
  - `test_wage_deciles_equal_employment`: 10 occupations with equal employment and wages 1..10 get deciles 1..10.
  - `test_topcoded_occupation_lands_in_top_decile`: of 10 equal-employment occupations with wages 1..9 and one `#`, the top-coded one has decile 10.
  - `test_wage_decile_basis_passed_to_occupation_table`: a spy on `occupation_table` sees `basis="published"` by default and `basis="tasks"` when passed.
  - `test_education_bins_left_closed`: 12.0 → "12–14"; 11.99 → "<12"; 18.0 → "≥18".
  - `test_major_group_two_month_mean`: uses D13 (a fixture with one month unpublished).
- [ ] **Step 2: Run** `uv run pytest tests/describe/test_anatomy.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Generate** `uv run python -m aideleg.results.rq1 --anatomy`. Expected: `anatomy.md`, its CSVs and four figures.
- [ ] **Step 5: Run tests and ruff, then commit** `feat(describe): RQ1 collaboration composition by major group, wage decile and education; usage concentration`.

### Task 14: Geography — H4 shift-share decomposition and choropleths (countries, US states)

**Files:**
- Create: `src/aideleg/describe/geography.py`
- Modify: `src/aideleg/results/rq1.py` (adds `report_geography`)
- Test: `tests/describe/test_geography.py`

**Interfaces:**
- Consumes: `build_geo_sample` (with `require_income=False`), `shift_share` (Task 8, called, never edited); `maps.load_countries`, `load_us_states`, `choropleth` (Task 2); `save_figure`.
- Produces:
  - `geography.geo_table(panel, geo: Literal["country", "us_state"]) -> tuple[pl.DataFrame, float, float]`. It returns the table and the two globals `global_automation` and `m_global`. Columns: `geo_id, name, automation_pct, aui, mix, gap, mix_part, within_part, in_h4_sample`.
    - For countries, `name` comes from `iso_country_codes.csv` (read as strings); for states, from `gdp_2024_us_state.csv`.
    - `in_h4_sample` is True iff the geography is in the confirmatory H4 frame (`require_income=True`).
  - `geography.MAPS`: the four variables per geography, (`automation_pct`, sequential), (`aui`, sequential, log colour scale), (`mix_part`, diverging, center 0) and (`within_part`, diverging, center 0). The figure names are `fig_rq1_map_{country|state}_{automation|aui|mix|within}`.
  - `rq1.report_geography(out: Path = OUT_DIR) -> list[Path]` writes `docs/results/rq1/geography.md`, `geography_country.csv`, `geography_state.csv` and the 8 maps. The md states:
    - the identity gap = mix_part + within_part;
    - that the mix part includes the common offset `m_global − global_automation` (printed);
    - the unmatched geography IDs per map, as returned by `choropleth`;
    - that the US-state H4 regression is robustness R28 (Plan 4), and that this section is descriptive;
    - AUI as "Anthropic Usage Index: a geography's share of Claude usage divided by its share of working-age population".

- [ ] **Step 1: Write failing tests:**
  - `test_geo_table_identity`: on `synthetic_inputs().panel`, `mix_part + within_part == gap` (abs 1e-12).
  - `test_in_h4_sample_flag`: a country without GDP has `in_h4_sample == False` and is still in the table.
  - `test_map_specs_cover_both_geographies`: 8 figure names, all matching the `save_figure` name rule.
  - `test_state_ids_prefixed`: every state `geo_id` starts with `"US-"`.
- [ ] **Step 2: Run** `uv run pytest tests/describe/test_geography.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Generate** `uv run python -m aideleg.results.rq1 --geography`. Expected: 8 maps, 2 CSVs and `geography.md`, with unmatched IDs listed (Kosovo may appear; it must be listed, not dropped silently).
- [ ] **Step 5: Run tests and ruff, then commit** `feat(describe): H4 shift-share decomposition and country/US-state choropleths`.

### Task 15: RQ2 descriptives — could vs does, top/bottom industries, rank gaps, bound widths (spec §5.3; PAP §2.0 RQ2, D3, D8)

**Files:**
- Create: `src/aideleg/describe/rq2.py`, `src/aideleg/results/rq2.py`
- Test: `tests/describe/test_rq2.py`

**Interfaces:**
- Consumes: `data/derived/exposure_ff49.parquet`, `exposure_occupation.parquet`, `benchmark_ff49.parquet` (Plan 1, unchanged); `audit.design_zero_assigned`; `figures`.
- Produces:
  - `rq2.AEI_COLS = ("z_usage", "z_delegation", "z_augmentation")`, `rq2.BENCH_COLS = ("z_aioe", "z_eloundou", "z_eloundou_gpt4")`. `z_eloundou` is the human β headline; `z_eloundou_gpt4` is shown beside it in every table (D8).
  - `rq2.spearman_bootstrap(df: pl.DataFrame, pairs: list[tuple[str, str]], idx: np.ndarray) -> pl.DataFrame`. Columns `aei, benchmark, n, spearman, ci_low, ci_high, n_draws_used`.
    - `idx` is a (B, n) resample index matrix.
    - Each draw's ρ is computed with `scipy.stats.rankdata` (average ties) followed by Pearson.
    - A draw with a constant vector is excluded and counted.
    - The CI is the 2.5/97.5 percentile.
  - `rq2.bootstrap_indices(n: int, designs: tuple[str, ...] = ("B", "A_pooled"), draws: int = 10_000) -> dict[str, np.ndarray]`. It uses one `numpy.random.default_rng(SEED)`, drawing `rng.integers(0, n, size=(draws, n))` once per design in the listed order.
  - `rq2.top_bottom(exposure, bench, col: str, k: int = 10) -> pl.DataFrame`. Columns `rank, side, ff49_short, <col>, z_aioe, z_eloundou, z_eloundou_gpt4, emp_covered_share`.
  - `rq2.rank_gaps(exposure, bench, aei: str = "z_delegation", bench_col: str = "z_aioe", k: int = 10) -> pl.DataFrame`. Columns `ff49_short, rank_does, rank_could, gap = rank_does − rank_could`; the top k and bottom k gaps.
  - `rq2.bound_widths(exposure, occ_exposure) -> tuple[pl.DataFrame, pl.DataFrame]`, Design B:
    - the FF49 table `ff49_short, E_delegation, E_delegation_lb, E_delegation_ub, width = ub − lb, width_pct_of_E`;
    - the occupation summary: usage-weighted median, p25 and p75 of `automation_share_all_ub − automation_share_all_lb`, and of `D_ub − D_lb`.
  - `results.rq2.main() -> int`. It writes:
    - `docs/results/rq2/could_vs_does.{md,csv}` (B and A_pooled; A_pooled labelled "exploratory; contains look-ahead (PAP §10, S3)"); the CSV is `design` followed by the `spearman_bootstrap` columns, one row per (design, aei, benchmark);
    - `top_bottom.{md,csv}` (Design B; one block per AEI column);
    - `rank_gaps.{md,csv}`;
    - `bounds.{md,csv}`;
    - `docs/results/rq2/README.md` (index);
    - figures `fig_rq2_could_vs_does` (3 panels, `z_aioe`, `z_eloundou`, `z_eloundou_gpt4` against `z_delegation`, each point labelled with `ff49_short`) and `fig_rq2_bound_widths`.
    
    Every RQ2 md states the zero-assigned employment share per design (D3), computed by `audit.design_zero_assigned` and never typed. It also states that RQ2 is descriptive, with no test.

- [ ] **Step 1: Write failing tests:**
  - `test_spearman_point_matches_polars`: the `spearman` column equals `pl.corr(..., method="spearman")`.
  - `test_bootstrap_indices_deterministic_and_ordered`: two calls are equal; the `"A_pooled"` matrix equals the second draw of a fresh `default_rng(SEED)`.
  - `test_constant_draw_excluded`: an `idx` row of identical indices is dropped and counted.
  - `test_rank_gap_hand_case`: 3 industries, does (3, 2, 1) and could (1, 2, 3), give gaps (2, 0, −2) with rank 1 = highest.
  - `test_bound_width_hand_case`: lb 1.0 and ub 1.5 give width 0.5.
  - `test_docs_state_zero_assigned_share`: the generated `could_vs_does.md` (tmp out) contains the share from `design_zero_assigned` formatted to 2 decimals for B.
- [ ] **Step 2: Run** `uv run pytest tests/describe/test_rq2.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Generate** `uv run python -m aideleg.results.rq2`. Expected: the files above.
- [ ] **Step 5: Run tests and ruff, then commit** `feat(describe): RQ2 could-vs-does with industry bootstrap CIs, top/bottom and rank gaps, R7 bound widths`.

### Task 16: Results indexes, Make targets, regeneration and wording checks; branch wrap-up

**Files:**
- Modify: `Makefile`, `src/aideleg/results/rq1.py` (`main()` runs all three reports and writes `README.md`)
- Create: `tests/results/test_generated.py`

**Interfaces:**
- Consumes: Tasks 12–15.
- Produces:
  - `make results-rq1` (`uv run python -m aideleg.results.rq1`, all sections, never the runner);
  - `make results-rq2`;
  - `make results` (both);
  - `make figures-check` (lists `docs/paper/figures/*.pdf` with no PNG twin, or the reverse, and fails if any exist);
  - `docs/results/rq1/README.md`:
    - an index of every generated file;
    - the P-RQ1 commit, read with `git log -1 --format=%H -- docs/results/rq1/confirmatory_rq1.json`;
    - the split statement;
    - the hand-off note "RQ1 robustness rows R10, R22–R28, R31, R36–R38 are reported in Plan 4, through these builders and estimators; R28's r4/r5 country parts use Plan 4's own construction, because r4 and r5 publish no country usage index or GWA rows".

- [ ] **Step 1: Write failing tests** (`@pytest.mark.data`):
  - `test_results_docs_up_to_date`: regenerating rq1 (`--anatomy --geography --confirmatory`) and rq2 into a tmp dir gives markdown and CSV byte-identical to the committed `docs/results/rq1|rq2/`, except the confirmatory_rq1.* files, which are never regenerated.
  - `test_generated_docs_wording`: every `docs/results/rq1/**/*.md` and `docs/results/rq2/**/*.md` except `confirmatory_rq1.md` has the generated-by line, contains `WORDING`, and has no `FORBIDDEN_PHRASES` outside it. It scans only Plan 2's two directories; Plans 3 and 4 test their own docs with the same constants.
  - `test_every_figure_has_pdf_and_png`.
  - `test_confirmatory_output_untouched`: `git diff --quiet <P-RQ1 commit> -- docs/results/rq1/confirmatory_rq1.json docs/results/rq1/confirmatory_rq1.md docs/results/rq1/confirmatory_rq1.log docs/results/rq1/confirmatory_rq1.attempt`.
- [ ] **Step 2: Run** them. Expected: FAIL until the README and Make targets exist.
- [ ] **Step 3: Implement**, then run `make results && make figures-check`.
- [ ] **Step 4: Full check.** `uv run pytest -q && uv run ruff check`. Expected: all pass, including `test_bound_code_unchanged_since_first_run`.
- [ ] **Step 5: Coverage check against the PAP.** The reviewer ticks every row of the requirement map below against a task and a test or output. Any row without one is added as a task before the branch closes.
- [ ] **Step 6: Commit** `docs(results): RQ1/RQ2 indexes, make results, regeneration and wording checks`.
- [ ] **Step 7: STOP — hand-off.** Report to the controller:
  - the P-RQ1 commit;
  - the figure list;
  - the results paths.
  
  Do not push and do not merge. Plan 3 starts from this branch's tip as `plan-3-markets`.

---

## Requirement map (PAP → task)

| PAP item | Requirement | Task(s) |
|---|---|---|
| §0.2 | point, 95% CI, p; no stars; two-sided; wrong sign = "contradicts the hypothesis"; null wording | 9, 12, 16 |
| §0.2 | `SEED` via `default_rng`, draw order fixed | 9 (none drawn), 10 (scramble), 15 (bootstrap order) |
| §0.5 P-RQ1 | estimators written and tested before any real outcome; single logged first run; output unedited; later code change = deviation | 3–10, 11, 10 (`test_frozen`) |
| §0.5 demotion rule | a deviation after a seen result demotes the hypothesis | 11 STOP rule; Global Constraints |
| §2.1 D1 | `automation_pct` primary; lb/ub carried for R10 | 4 (`OUTCOME_COLUMNS`), 6 |
| §2.1 D3 | every index report states the zero-assigned share | 15 |
| §2.1 D4 | equal split of task usage across occupations | 4 |
| §2.1 D8 | human β headline, GPT-4 β beside it in every RQ2 table | 15 |
| §2.1 D9 | r6 occupation descriptives on the published SOC basis | 13 |
| §2.0 RQ2 row | Spearman ρ of z_usage/z_delegation/z_augmentation vs AIOE/Eloundou, B and A_pooled, industry bootstrap CI | 15 |
| §4 top | the exact two-way `WLS(...).fit(cov_type="cluster", ...)` call; CGM V; t with min(G)−1 df; non-PSD rule and its reporting; one-way SEs exposed for R38 | 5, 6 |
| §4.0 D17 | H1 intersection–union p = max; H4 joint HC3 Wald | 6, 8 |
| §4.1 D13 | r6 `claude_ai` global `onet_task`; usage-weighted two-month mean; weights = mean pct, unpublished = 0 | 3, 4 |
| §4.1 D14 | IWA via Tasks-to-DWAs + DWA Reference; equal split across IWAs; tasks with no DWA dropped and reported | 3, 4 |
| §4.1 H1 table | unit; outcome; education + log `a_median`; `#` → $239,200, `*`/`**` drop; IWA FE; weights ÷ (n_occ × n_iwa); drop-by-reason without renormalising; WLS; decision with Holm 0.0375 and both β < 0 | 3, 4, 6, 9 |
| §4.1 "two measures" | `ai_autonomy_mean` beside the decision (R23) | builder knob in 6; reported in Plan 4 |
| §4.1 P13 | attenuation factors for β_w and γ reported | 6, 12 |
| §4.2 D22 (1) | wording "measured within-task automation rises" | 7 (notes), 9 |
| §4.2 D22 (2) | H2 outside the family at 0.0125; {H1, H3, H4} Holm at 0.0375; split stated | 9, 10, 12, 16 |
| §4.2 D22 (3) | restricted wild cluster bootstrap, clusters = releases, Webb 6-point, all 1,296 vectors, task-clustered t, p = share \|t\*\| ≥ \|t\| | 7 |
| §4.2 D22 (4) | release-label randomisation, 24 orderings, descriptive | 7, 12 |
| §4.2 H2 table | unit, r2–r5, balanced, `automation_pct`, t_r from window midpoints ÷ 365.25, WLS task FE, fixed weights = mean pct, task-clustered `use_t`, decision | 7, 9 |
| §4.2 "also reported" | event-style plot (release FE, r2 base, 95% CI) | 7, 12 |
| §4.3 D15 | SOC list: 23, 29, 13-2xxx, 11-3031, 41-3031 | 3 |
| §4.3 H3 table | `validation_pct`; error_cost; IWA FE; two-way; Holm and γ > 0 | 6, 9 |
| §4.4 D16 | r6 `claude_ai` countries; both months; two-month means then logs; log AUI; log GDP/WAP; GWA mix control M_c as specified; OLS HC3; `wald_test(R, use_f=True, scalar=True)` F(2, n−4); Holm | 8, 9 |
| §4.4 "also reported" | shift-share split with maps | 8, 14 |
| §5 D2 | definition-stable list (outcome knob); exclusions; r2–r5 primary; no platform controls; balanced | 7 |
| §9.4 D20 | Plan 2 needs no §9.4 item; geometry additions logged in §11 as `A-` entries "outside §9.4; descriptive"; the single §11 format | 2 |
| §11 | pre-result clarifications `C-1`…`C-8` committed before the P-RQ1 run | 10 (Step 8), 1 (plans committed) |
| spec §5.2 | composition by major group, wage decile, education; Lorenz/concentration across tasks | 13 |
| spec §5.3 | scatter of could vs does; top/bottom tables | 15 |
| spec §3 goals | one visual system including maps | 1, 2 |

Not in Plan 2 (exactly once elsewhere): every §8.2 row. The RQ1 ones are R10 (H1/H3 part), R22, R23, R24, R25, R26, R27, R28, R31, R36, R37 and R38, in Plan 4. The RQ2 parts of R1, R2, R3, R11, R14, R15, R16, R17, R20 and R33 are in Plan 4. D11's paper framing is in Plan 4.

## Hand-off to Plan 4 (knobs built into frozen code, so no bound file changes)

Plan 4 calls these through its adapter (`aideleg.robustness.upstream`) with the inputs of `confirm.load_inputs()`. Plan 4 writes new code only for the Consequence-of-Error column, the validation bounds and the r4/r5 H4 frames.

| Row | Call |
|---|---|
| R10 | `estimate_h1(tr, outcome="automation_share_all_lb")` / `_ub`. For H3, Plan 4 adds `validation_share_all_lb/_ub` columns (per period, then D13, its own code) to `tr.rows` and calls `estimate_h3(tr, outcome=…)` |
| R16 | `anatomy.by_wage_decile(..., basis="tasks")` beside `basis="published"` |
| R22 | `build_h2_panel(releases=("r2",…,"r6"), balanced=True|False, outcome=<metric>, source=…)`; `estimate_h2(df, outcome, r6_indicator=…)`. `balanced=False` is the single unbalanced rule (Task 7) |
| R23 | `estimate_h1(tr, outcome="ai_autonomy_mean")`; `build_h2_panel(releases=("r4","r5","r6"), outcome="ai_autonomy_mean")` → `estimate_h2` |
| R24 | `build_task_rows(..., release="r4"/"r5")`, and `source="1p_api"` at r6 → `estimate_h1`, `estimate_h3` |
| R25 | `HypothesisResult.coefs[*].p` for H1 and H4 (individual p-values) from the committed JSON, then `family.holm` at 0.0375 over five members |
| R26 | `task_families("gwa")` / `("dwa")` → `build_task_rows(..., families=…, family_level=…)` |
| R27 | `build_task_rows` output with a `coe` column added (Plan 4's code: the standardised Consequence-of-Error value), then `estimate_h3(tr, indicator="coe")`; rows without `coe` are dropped and reported by the estimator's own drop rule as `missing_coe` |
| R28 | `build_geo_sample(geo="us_state")` → `estimate_h4`; `estimate_h4(frame, weights="usage_pct")`; `build_geo_sample(mix_level="iwa")`. The r4/r5 country frames are Plan 4's construction (this builder raises for them, Task 8), passed to `estimate_h4` |
| R31 | `estimate_h3(tr, covariates=("human_education_years_mean", "log_wage"))` |
| R36 | `build_h2_panel(time_basis="publication")` → `estimate_h2` |
| R37 | a new Plan 4 module on the panel, which does not touch bound files |
| R38 | `diagnostics["se_oneway_occ"]` and `diagnostics["p_oneway_occ"]` of `estimate_h1`/`estimate_h3` |

## Interfaces for Plans 3 and 4

- Figures:
  - `from aideleg.figures import apply_style, save_figure, PALETTE, FIGSIZE, SEQUENTIAL_CMAP, DIVERGING_CMAP, MISSING_COLOR, choropleth`;
  - `save_figure(fig, name, *, out_dir=FIGURES_DIR) -> (pdf, png)` into `docs/paper/figures/`;
  - names match `^[a-z0-9][a-z0-9_]*$` and are prefixed `fig_<area>_`.
- Results helpers: `aideleg.results.common.write_result_doc`, `write_csv`, `fmt_coef`, `WORDING`, `FORBIDDEN_PHRASES`. `WORDING` is the study's one required disclaimer: Plans 3 and 4 import it (and `FORBIDDEN_PHRASES`) and define no disclaimer of their own; each tests its own docs.
- PAP §11: `aideleg.paplog` (`addition`, `set_addition`, `clarification`, `deviation`, `append`, `set_digest`, `entries`, `ENTRY_RE`, `SUBSECTIONS`) and its CLI; `tests/test_pap_frozen.py` checks every plan's additions.
- Lock: `tests/test_lock_pins.py::test_core_numeric_versions_unchanged_since_pap_v1`, rerun after any `uv add`.
- RQ1 runner: `confirm.load_inputs() -> Inputs`, `confirm.OUT_DIR`; the committed output `docs/results/rq1/confirmatory_rq1.{json,md,log,attempt}` (`meta.blobs`, `meta.scrambled`); its commit is `git log -1 --format=%H -- docs/results/rq1/confirmatory_rq1.json`.
- Make targets: `rq1-dry-run`, `rq1-confirm` (single-run; never part of `make all`), `results-rq1`, `results-rq2`, `results`, `figures-check`.
- Results paths:
  - `docs/results/rq1/`: `confirmatory_rq1.{json,md,log,attempt}`, which are write-once, plus `confirmatory_table.{csv,md}`, `decisions.md`, `anatomy.md`, `geography.md`, `README.md` and the CSVs;
  - `docs/results/rq2/`: `could_vs_does`, `top_bottom`, `rank_gaps`, `bounds` (`.md` and `.csv`), plus `README.md`;
  - Plan 3 writes `docs/results/rq3/` and `docs/results/h6/` with the same helpers.

## Self-review (writing-plans checklist, run 2026-10-22)

1. **Spec coverage.** Every PAP §4/§5 requirement and every D13–D17 and D22 element maps to a task in the requirement map. Spec §5.2 and §5.3's descriptive items map to Tasks 13–15. The scope and integrity items from §0.2 and §0.5 map to Tasks 9–12 and 16. No gaps were found. Three PAP ambiguities are resolved by fixed defaults, written down before any outcome is read:
   - the occupation cluster is the soc6 code, and soc6 codes that share an OEWS code stay separate rows (Task 4);
   - H3 does not require an OEWS code or wage (Task 6);
   - the zero-variance tolerance is 1e-12 × the one-way variance (Task 5).
   
   None changes a PAP rule. These and the descriptive defaults are logged as §11 `C-1`…`C-8` before Task 11 (Task 10 Step 8), and the plan files are committed in Task 1 Step 1.
   
   Review rulings of 2026-10-22 applied here: the stale binding test replaced (Task 1); the lock-pin test (Task 1); the single §11 format in `paplog` (Task 2); the boundary files as "outside §9.4; descriptive" additions (Task 2); the one unbalanced rule (Task 7); `build_geo_sample` refusing r4/r5 countries, which go through Plan 4 (Task 8); `by_wage_decile(basis=)` (Task 13); the wording test scoped to rq1/rq2 (Task 16); concrete assertions for the six listed tests.
2. **Step scan.** No TBDs. Every code step names its file, signature and pinned values. Bodies appear only for the fixed library calls and the run order. The "handle edge cases" lines were replaced by named drop reasons.
3. **Type consistency.**
   - `TaskRows`, `HypothesisResult`, `Coef`, `TwoWayFit`, `GeoSample` and `Decision` are defined once (Tasks 3–9) and used with the same field names in Tasks 10–16.
   - `two_month_mean(..., n_periods=)` is used the same way in Tasks 4, 7, 8 and 13.
   - `build_geo_sample(require_income=)` is introduced in Task 8 for its use in Task 14.
   - Cross-plan: every name in "Hand-off to Plan 4" and "Interfaces for Plans 3 and 4" is defined in a Produces block here, and Plan 3 (`WORDING`, `paplog`, `save_figure`) and Plan 4 (its adapter, `confirmatory_rq1.json`, `confirmatory_table.csv`, the Make targets) use the same spellings.
4. **Review Focus.** There are five items, each with a named test in its owning task (Tasks 2, 3, 5, 8, 10).
5. **Proportion.** The plan carries signatures, rules, test names and assertions. Code blocks are limited to the two exact statsmodels calls the PAP fixes.
