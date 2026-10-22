# Cross-plan review of Plans 2–4: findings and controller rulings (2026-10-22)

Apply every item below to the three plan files. The findings are referenced by number from the review; the line numbers are the reviewer's.

## Critical
1. **Design A test (Plan 4, Tasks 2 and 10).** Delete `design_a_test`.
   - R8 = Plan 3 `run_terciles(months=<month-ends excluding 2023>)` plus the FM equivalent through `fm_panel(expo, months)`.
   - The Design A parts of R4 and R16 = terciles, FM and event slopes on the variant exposure.
   - Plan 3 adds `expo: pl.DataFrame | None = None` to `run_terciles`, `run_fm` and `run_events`.
   - Ruling: no new Design A cross-sectional test is added. The 33-month-null default is removed, which keeps the analysis inside the PAP.

## Important
2. **Broken test.** Plan 2 Task 1 replaces `test_binding_refuses_in_this_repo_before_the_tag` with `test_binding_refuses_in_this_repo_when_src_differs`: on a branch where `src` differs from pap-v1, `check_binding()` raises `BindingError`. This is tests-only, outside DIFF_PATHS. Plan 3 Task 14 (L660) then expects every test to pass, and Plan 2's and Plan 4's green-suite steps stand.
3. **Plan 4's RQ1 guard.**
   - The commit is `git log -1 --format=%H -- docs/results/rq1/confirmatory_rq1.json`.
   - All four `confirmatory_rq1.*` files must be tracked and unmodified, with `meta.scrambled == false`.
   - `protected_files()` = the keys of `meta.blobs`.
4. **Plan 4's upstream contract uses Plan 2's real names:**
   - `confirmatory_rq1.json` and `confirmatory_table.csv`;
   - `confirmatory_rq1.log`;
   - the Make targets `results-rq1`, `results-rq2` and `rq1-confirm`.
   Plan 2 Task 13 adds `basis: Literal["published","tasks"]="published"` to `anatomy.by_wage_decile`. Plan 4 Task 33's `make all` excludes `rq1-confirm`, `h6-data` and any network target. Add `test_make_all_never_runs_rq1_confirm`.
5. **Plan 4 routes R10, R22, R23, R24, R26, R28, R31, R36 and R38 through Plan 2's builders** (`build_task_rows`, `estimate_h1`/`estimate_h3`, `build_h2_panel`/`estimate_h2`, `build_geo_sample`/`estimate_h4`) via the adapter. New code is written only for the Consequence-of-Error column, the validation bounds and the r4/r5 H4 construction.
   - Exactly one unbalanced-panel rule, matching Plan 2's handling and tagged [default].
   - Fix Plan 2 L926 (`build_geo_sample(release="r4")`): either Plan 2 supports r4/r5 through a Plan 4-supplied AUI/mix, or the hand-off note says that r4/r5 go through Plan 4's construction. Pick the one consistent with Plan 4.
6. **Timestamped pre-result defaults.**
   - Plan 2 Task 1 Step 1 commits all three plan files (docs only), plus this rulings file and the brief copied to `docs/superpowers/plans/` (docs only).
   - Add a PAP §11 subsection "Clarifications (pre-result)", in the single §11 format of item 8. Each plan adds its defaults before its first real-outcome or post-seal read:
     - Plan 2 before Task 11;
     - Plan 3 before Plan 3 Task 1 (include the event-study HC3 inference, the tercile ties, the French firm-size timing once verified, the exhibit-only CIK rule and the H6 `all` definition);
     - Plan 4 before its first robustness read (the R28 construction, R10-for-H3, the unbalanced rule, R9's scope, the R29 denominator).
   - Plan 3 L146 must expect the plan files to be committed.
   - Also record the organisational note: R6, R32 and R35 move from "plan 3" to Plan 4, with no specification change.
7. **The wording test is scoped per plan.**
   - Plan 2's `test_generated_docs_wording` scans only `docs/results/rq1|rq2/**`.
   - Use one shared `WORDING` constant and `FORBIDDEN_PHRASES` from `aideleg.results.common` (Plan 2). Plans 3 and 4 import it, and each tests its own docs.
   - Each plan's required disclaimer is the shared WORDING. Drop the separate disclaimers.
8. **One §11 entry format**, defined in Plan 2 Task 2 and reused by Plans 3 and 4:
   - `### A-<n>` per acquired key (additions);
   - `### C-<n>` per clarification;
   - `### D-<n>` per deviation;
   - a set-digest form for bulk keys (`sec_fts/*`, `sec_docs_index`): one entry with a count and a digest.
   Plan 4's test accepts all of these. `data_appendix` collapses the bulk keys.
9. **H6 must rebuild from a fresh clone.**
   - Plan 3 defines `aideleg.h6 all` = talk + secondary + summary, with no acquire. Acquisition is a separate `h6-data` target.
   - Plan 4's `--from-dir` restores `data/raw/sec/docs`, verified against the `INDEX.jsonl` hashes.
10. **The dependency lock.**
    - After any `uv add`, assert that numpy, scipy, pandas, polars and statsmodels are unchanged in `uv.lock`, with a test. If any would move, pin them with `[tool.uv] constraint-dependencies` and STOP.
    - Applies to Plan 2 Task 1 and Plan 4 (pypdf).
11. **Red-team fixes.** Every change to Plan 3/4 analysis code made after any result is seen is logged as a §11 `D-<n>` entry, with the date and both values. No silent "bug fixed".
12. **FF3. Ruling:**
    - Acquire the canonical `F-F_Research_Data_Factors_CSV.zip` (monthly) and the daily variant if any analysis is daily, under keys `ff3_monthly`/`ff3_daily`.
    - Log it as a §11 `A-` addition outside §9.4, with the reason "the PAP names FF3; FF5 2×3 SMB is not FF3 SMB".
    - Do not build FF3 from FF5 columns.
    - This is acquisition before any post-seal read, so it changes no specification. Report it to Ajai.

## Minor (apply)
13. Plan 4 is cut with `git switch -c plan-4-paper plan-3-markets`.
14. In Plan 3 Task 1 Step 5, require an empty status under `-- src pyproject.toml uv.lock` only; record any other diff instead of stopping.
15. Plan 3 verifies French's "Average Firm Size" definition (from the README in the zip, or French's site) before Task 1, and uses the row whose date is the prior month-end ME, as the PAP says.
16. Give the listed tests concrete assertions:
    - Plan 2: `test_choropleth_center_uses_two_slope_norm`, `test_balanced_panel_drops_tasks_missing_a_release`, `test_holm_ties_by_name`, `test_write_result_doc_rejects_forbidden_and_stars`, `test_decision_texts_copied_verbatim`, and `test_wild_bootstrap_controls_release_shocks` (task count, weights, seeds);
    - Plan 4: `test_r21_label_no_error_control`, `test_r7_drops_three`, `test_robustness_section_no_counts`;
    - fix the Plan 4 L911 path to `tests/test_confirm_h5.py`.
17. Plan 3 states that exhibit-only CIKs count in `n_talk`, with a test case.
18. Plan 4:
    - R29: the denominator is also cut at 2025-03-26;
    - R9 is tagged [default];
    - R10's H3 bounds are computed per period, then the D13 average;
    - an R38 parity check against Plan 2's `p_oneway_occ`;
    - `load_return_set` reuses `rq3.guard` and rejects attempt-only records.
19. Every report of an exposure index (the rq3 docs and Plan 4's exposure rows) states the zero-assigned share (D3).
20. Figure names are `fig_<area>_…` in all plans (rq3, h6, robustness).
21. Plan 2's boundary files and Plan 4's SEC public-float frame are logged as `A-` additions marked "outside §9.4; descriptive" or "R29 cap proxy".
