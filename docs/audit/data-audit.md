# Data audit memo (Stage 0)

Date: 2026-10-21. Branch `plan-1-foundations`. This memo covers coverage, missingness,
schema differences and measurement regimes only. Every number here comes from a generated
table in [`tables/`](tables/) (`make audit`, code `src/aideleg/audit.py`). The table is
named in brackets after each number. Nothing here tests a hypothesis. No delegation
measure is related to wage, education, error-cost or country variables, and no market
returns are read. AEI data are conversations matched to O\*NET tasks. They say nothing
about job risk or displacement in the labour market.

Table keys:
- **[REL]** [releases](tables/releases.md)
- **[MET]** [metric_availability](tables/metric_availability.md)
- **[TM]** [task_matching](tables/task_matching.md)
- **[SUP]** [suppression](tables/suppression.md)
- **[R6]** [r6_checks](tables/r6_checks.md)
- **[OEWS]** [oews_coverage](tables/oews_coverage.md)
- **[XW]** [crosswalk_coverage](tables/crosswalk_coverage.md)
- **[EXP]** [exposure_coverage](tables/exposure_coverage.md)
- **[BEN]** [benchmark_coverage](tables/benchmark_coverage.md)
- **[PQ]** [panel_quality](tables/panel_quality.md) (from `make panel`; its
  `r6_bucket_consistency` and `unmatched_tasks` checks agree with [R6] and [TM])

## 1. Sources

| Source | Role | Vintage used |
|---|---|---|
| AEI r1–r6 (Hugging Face) | Conversations matched to O\*NET tasks; collaboration patterns | six releases, three file layouts, harmonised into `aei_panel.parquet` |
| O\*NET 29.3 task statements + r2-era statements + O\*NET 2010→2019 crosswalk | Task text → Task ID → occupation | O\*NET-SOC 2019 (= SOC 2018 in the first 7 characters) |
| BLS OEWS May 2024 (national, nat4d) | Employment weights | SOC 2018, NAICS 2022 |
| Census SIC 1987 → NAICS 2022 concordances + Siccodes49 | Industry crosswalk to FF49 | six links, equal splits |
| AIOE (Felten, Raj & Seamans 2021); GPTs-are-GPTs `occ_level.csv` (Eloundou et al.) | "Could" benchmarks, descriptive (RQ2) | SOC 2010 (AIOE); O\*NET-SOC 2019 (Eloundou) |
| Ken French library | Market tests (Task 14 onward) | sealed; not read by the audit |

Omitted on purpose: [MET] lists metric availability but leaves out the AEI education
metrics (`human_education_years_mean`, `ai_education_years_mean`). Education is an H1
covariate, and the integrity scan keeps every mention of it out of `audit.py`. Both
metrics are in the panel (r4–r6, task level and above).

## 2. Measurement regimes per release

The release calendar and windows are in [REL]:
- r1: 2024-12-01→2025-01-01. r2: 2025-02-24→2025-03-04. Both are marked
  **DEFAULT**: the r1/r2 Hugging Face READMEs state no window, so these come from the
  release reports.
- r3–r5: one-week windows, as published.
- r6: two calendar months, April and May 2026 (end dates exclusive).

Regime changes [REL §Measurement regimes]:
- **Platform scope.**
  - Claude.ai Free and Pro (r1–r4).
  - Free, Pro and Max (r5).
  - Claude chat *and Cowork*, Free/Pro/Max (r6).
  - The 1P API from r3. r6's API scope explicitly excludes Claude Code.
  - The r1/r2 scopes come from the release reports. Their files state none.
- **Classifier model.** No release file names the classifier model, in any release.
  Changes in the classifier are therefore unobservable and confounded with behavioural
  change.
- **Collaboration taxonomy.** r1 is `collab_v1` and publishes only an overall split
  [MET]. r2–r6 use `collab_v2`, the same five pattern labels.
- **Units and denominators** [MET §Task-level]:
  - r2 publishes a per-task `filtered` share.
  - r3–r5 publish `none` and `not_classified`. AEI folds intersection cells under 15
    conversations into `not_classified`.
  - **r6 has no `not_classified_pct`.** Its cells below the thresholds are simply absent.
  - So the r1–r5 sentinel rows absorb the suppressed task mass (0.48–12.16% of task
    `pct` [TM]). In r6 the global task `pct` instead sums short of 100: 5.68–18.87% is
    unpublished [SUP §global].
  - r6 patterns are published as shares of all conversations and are renormalised here.
- **Occupation basis.** r1–r5 occupations are derived from task usage. r6 uses AEI's
  published SOC rows [REL]. 43 r6 occupations (claude_ai) appear in no r2–r5
  task-derived table, carrying **1.77%** of r6 published SOC usage (25-3031 alone 1.36%)
  [REL §basis change]. The two bases agree closely on r6 itself (§5).
- **Suppression regime.** In r3–r5 only 3.70–9.10% of tasks publish all five patterns.
  In r6, 99.71–99.96% do. The suppressed share falls from 7.10–17.77% (r3–r5) to
  2.28–3.76% (r6) [SUP §Task x collaboration]. Task-level pattern completeness is not
  comparable across r3–r5 and r6.

## 3. Task matching and the O\*NET-SOC 2019 harmonisation

[TM]:
- **Match rate.** 100.00% of non-sentinel global task nodes match an O\*NET Task ID in
  r1–r5, 99.96% (1p_api) and 99.93% (claude_ai) in r6. The r6 unmatched mass is 0.07%
  or less.
- **Multi-candidate statements.** Under the harmonised index, 300–503 statements per
  release carry more than one Task ID. Under the r2-era file alone the count is 38–93
  (Task 4 measured 84 for r1 and 86 for r2). The growth comes from the union of 29.3 and
  legacy wordings. Allocation uses the union of the candidates' occupations (ruling R6),
  so this changes the allocation weights, not the coverage.
- **Vintage provenance.** 18,796 Task IDs resolve via O\*NET 29.3 and 3,796 via the
  2010→2019 crosswalk; 0 are unresolved. Every occupation code is O\*NET-SOC 2019, the
  vintage of OEWS 2024 and AEI r6.

## 4. Suppression

Unpublished mass is 0.00 in every r1–r5 group [SUP §global], because suppressed mass
sits in sentinel rows. In r6:
- Global groups are short of 100 by 1.22–20.02 points, depending on taxonomy, source and
  month.
- Country and subregion task groups are short by far more: mean 59.33 (country) and
  76.40 (subregion) [SUP §country and subregion].
- Geographic task-level analysis on r6 therefore rests on a small published fraction.

**Task × collaboration suppression** [SUP §Task x collaboration]:
- **Retracted: the Task 6 "7–9 points" figure** (r3 57.8 vs 51.1). It came from an
  uncommitted script. The Task 13 reviewer re-derived it on the panel at commit 45bde80
  (the Task 6 code) and got 51.20 vs 51.07, the same as the current panel.
- The aggregate suppression bias of renormalised task automation is small. The
  pct-weighted task automation is 51.20 vs 51.07 overall for r3 claude_ai. The gaps are
  0.13–0.35 points (claude_ai) and 1.11–1.86 points (1p_api).
- Tasks publishing only some patterns carry 27–41% of the weight in r3–r5. Their
  automation differs from that of fully published tasks by up to 9.3 points (r4
  claude_ai: 40.55 partial vs 49.87 complete). The sign varies by source.
- The bias of renormalising over published patterns is therefore composition-dependent.
  It is not a uniform upward shift.
- The real suppression uncertainty is the occupation-level R7 bound width, below.

**R7 bounds** [SUP §Occupation automation]:
- The width between "suppressed = non-automation" (lb) and "suppressed = automation" (ub)
  is large on the task-derived releases. The median occupation width is 10.54–18.18
  points in r2–r5 and 1.18–2.64 in r6. Usage-weighted means for r2 claude_ai are 40.57
  (lb) and 46.57 (ub), around 42.75 (renormalised).
- Across FF49, however, the standardised index is almost unchanged. For Design B,
  corr(z_delegation, z_delegation_lb) = 0.99990 and corr(z_delegation, z_delegation_ub)
  = 0.99969 (Pearson); Spearman is 0.99949 and 0.99888 [SUP §Delegation vs its bounds].
  A_pooled carries no bounds.
- So suppression matters for occupation-level (RQ1) measures and hardly at all for the
  FF49 indices (RQ3).

## 5. r6 internal consistency

[R6]:
- **Bucket consistency.** Published automation equals renormalised directive +
  feedback_loop within a maximum gap of 0.132 points (mean 0.0035) over 31,374 nodes,
  with 0 nodes above 1 point. The published value is kept.
- **Allocated vs published SOC.** Spearman ρ of occupation usage between the
  task-allocated and published bases:
  - 0.931 (Apr, 1p_api)
  - 0.948 (Apr, claude_ai)
  - 0.952 (May, 1p_api)
  - 0.958 (May, claude_ai)

  The Pearson correlations are 0.996–0.999. Between 43 and 61 codes appear only on the
  published side.

## 6. OEWS coverage

[OEWS]:
- **Coverage.** AEI r6 published occupations reach OEWS codes holding **92.61%** of May
  2024 detailed employment (90.72% with exact matching and rollup alone). No AEI usage is
  left unmatched (0.66% before the hybrid step).
- **Hybrid codes.** Ten AEI codes reach OEWS only through the hybrid step, all
  O\*NET-SOC 2019 splits that OEWS merges:
  - 21-1011/21-1014 → 21-1018
  - 25-2055/25-2056 → 25-2052
  - 25-9042/25-9043 → 25-9045
  - 51-2022 → 51-2028
  - 53-1042/53-1043/53-1044 → 53-1047
- **Occupations with no AEI r6 occupation.** **202 OEWS codes, 7.39% of employment**:
  construction laborers, maids, industrial truck operators, welders and others. They are
  *unpublished* in AEI, not measured as zero.
- **The zero-assignment assumption.** Under the default `unmatched="zero"` they are
  **assigned zero usage. This is an assumption.** Per design [OEWS §Zero-assigned]:
  - Design B (r2): 232 occupations, 12.14% of employment, are zero-assigned.
  - A_pooled: 144 occupations, 6.34%.

## 7. Crosswalk coverage (NAICS → SIC → FF49)

[XW], OEWS May 2024, 4-digit, split weights:
- **Mapped and unmapped.** 99.72% of private employment maps to an FF49 industry, and
  **0.28%** is unmapped. Legal Services (541100) is the largest unmapped item, through
  the source-less 541120.
- **Excluded buckets.** Two buckets sit outside the private denominator:
  - `management_of_companies` (NAICS 5511): 2,809,200 employed, 1.84% of total.
  - government (99xxxx plus USPS 491100): 10,685,940 employed, 7.00%.
- **5511 alternatives.** `hq="redistribute"` moves 5511 into FF49 pro rata. Without the
  exclusion, 5511 would go to Fin through SIC 6712/6719.
- **Other = #49, Fin = #48** (Siccodes49) [XW §FF49 numbering]. The Task 10 brief's "#48"
  was wrong.
- **Equal-split artifacts.** 230 of 1,009 six-digit NAICS 2022 codes split over two or
  more targets. The weights are structural, not employment-based. For example, 488111 Air
  Traffic Control is 0.3333 Trans and 0.6667 unmapped, purely because SIC 4581 is split
  over three NAICS codes.
- **Source-less codes.** Four codes have no SIC 1987 source (112130, 481219, 541120,
  551114).

## 8. Exposure coverage per FF49

[EXP]:
- **Covered share.** `emp_covered_share`, the employment share with a non-null
  delegation value, ranges 0.680–0.988 (Design B, median 0.890) and 0.555–1.000
  (A_pooled).
- **Right skew.** Design B `z_delegation` peaks at **4.739 (Softw)**, with the next
  industry at 1.977. The skewness of the 49 z-scores is 2.571 (z_usage 2.284).
- **Within-group dispersion.** U varies widely inside SOC broad group 15-125x because
  shared tasks are split equally across their occupations regardless of employment:
  - Computer Programmers 107.254
  - Software QA 55.141
  - Software Developers 5.020

## 9. Benchmarks ("could" vs "does", RQ2, descriptive)

[BEN]:
- **AIOE coverage.** AIOE has 774 SOC 2010 codes, 88 of them not SOC 2018 detailed
  codes. Coverage of OEWS employment is 82.5% before vintage mapping and 98.9% after.
- **Eloundou coverage.** 98.6%, already on O\*NET-SOC 2019.
- **FF49 coverage.** 0.976–1.000 (AIOE) and 0.949–0.998 (Eloundou).
- **Union-crosswalk caveat.** The AIOE mapping goes through the O\*NET 2010→2019
  crosswalk, and 49 SOC 2010 codes take the union of several successors. 15-1199
  (Computer Occupations, All Other) is copied to seven codes, including 13-1082, 13-1161
  and 15-2051, and 11-9199 to seven.
- **Eloundou rating.** In `occ_level.csv`, `dv_rating_*` is the GPT-4 rating and
  `human_rating_*` the annotators'. The GPTs-are-GPTs README (github.com/openai/GPTs-are-GPTs,
  read 2026-10-21) states "dv_rating is the GPT-4 rating and human is from the
  annotators". It is not in `data/raw`.
- **Spearman correlations.** Across FF49, against Design B (descriptive only):

  | Benchmark | z_delegation | z_usage |
  |---|---|---|
  | AIOE | 0.763 | 0.809 |
  | Eloundou human β | 0.716 | 0.768 |
  | Eloundou GPT-4 β | 0.815 | 0.843 |

  This collinearity lowers the power of H5b, which the Task 14 power analysis must
  reflect.

## 10. Integrity disclosures and open data risks

**Task 3 incident.** While inspecting the file layout, the Task 3 implementer subagent
displayed aggregate monthly FF5 factor rows for 2026-05..2026-08 and the Mom 2026-08 row.
- They were aggregate factors, not industry returns.
- Nothing was used or recorded.
- They carry no information about the cross-sectional exposure slope (H5/H5b).

The controller ruled this not contamination. It is to be disclosed in the PAP.

**Open data risks**
1. **Classifier drift.** No release states the classifier model, so classifier drift
   cannot be separated from behavioural change in H2.
2. **Default windows.** The r1/r2 windows are defaults, not documented windows.
3. **Suppression uncertainty at occupation level (closed item: Task 6 figure).** The
   Task 6 "7–9 points" figure is retracted (§4). The remaining risk is the R7 bound
   width: median 10.54–18.18 points per occupation on r2–r5.
4. **Sparse geographic task data in r6.** The r6 country and subregion task groups are
   mostly unpublished (§4).
5. **Equal allocation.** Equal allocation of shared tasks drives within-group U dispersion
   (§8). The equal-split concordance drives structural crosswalk weights (§7).
6. **Zero assignment.** Zero assignment of unpublished occupations covers 6.34–12.14% of
   employment (§6).

## Decisions the audit forces (for the pre-analysis plan)

1. **Primary delegation measure.** Choose among:
   - renormalised `automation_pct` (the current default);
   - the R7 bounds `automation_share_all_lb` / `_ub`.

   This stays open, on the following grounds:
   - The aggregate bias of renormalising is small: 0.13–0.35 points (claude_ai) and
     1.11–1.86 (1p_api).
   - The R7 bounds are wide at occupation level: median 10.54–18.18 points on r2–r5.
   - They barely move the FF49 z-scores (Pearson 0.99969–0.99990) (§4).

   Decide which is primary, and whether the other is a pre-registered robustness check.
   The choice matters mainly for occupation- and task-level RQ1 measures.
2. **Definition-stable metric list for H2.**
   - Candidates published at task level in r2–r6 under `collab_v2`: `automation_pct`,
     `augmentation_pct` and the five pattern shares [MET].
   - `ai_autonomy_mean` is r4–r6 only.
   - Exclude `filtered_pct`, `not_classified_pct` and `none_pct`: their denominators
     differ by release.
   - Exclude r1, which has no task-level collaboration.
   - Decide whether the r3–r5 → r6 suppression-regime change (§2) excludes r6 from the
     "definition-stable" series, or enters it as a regime dummy.
   - Decide whether platform-scope changes (Max in r5, Cowork in r6) need release-level
     controls.
3. **Unmatched-occupation treatment.** Zero assignment (default, an assumption) versus
   dropping the occupations: 12.14% of employment is zero-assigned under Design B (§6).
   Pre-register `unmatched="drop"` as robustness.
4. **Employment-weighted allocation.** Shared task usage is currently split equally
   across occupations. Pre-register an employment-weighted split as a robustness check
   (§8).
5. **Rank-based robustness.** z_delegation is right-skewed (Softw 4.739 SD, skewness
   2.571). Pre-register a rank-based specification, and consider dropping Softw.
6. **AIOE crosswalk.** Choose between:
   - the O\*NET-detail union (current; 49 codes split, 15-1199 to seven successors);
   - the BLS SOC 2010→2018 crosswalk for the confirmatory H5b control.

   Choose before the freeze.
7. **NAICS 5511.** Keep it excluded (default; 2.81M employed), or redistribute pro rata
   (robustness). State this in the PAP.
8. **Eloundou rating.** Choose the human β (current headline `z_eloundou`) or the GPT-4 β
   (`dv_rating_beta`). It is descriptive only either way.
9. **Occupation basis for r6.** Published SOC (default) or task-allocated. The two agree
   at ρ 0.931–0.958. 43 r6-only occupations enter A_pooled through r6 alone.
10. **H5b collinearity in the power analysis.** Across FF49, Spearman(z_aioe,
    z_delegation) = 0.763 [BEN]. The Task 14 minimum detectable effect for H5b must use
    this collinearity (variance inflation of the delegation slope once AIOE is
    controlled), not the H5 power alone.
