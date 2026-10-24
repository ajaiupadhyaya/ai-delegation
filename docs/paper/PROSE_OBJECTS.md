# Prose objects: the keys and ids the paper sections cite

The writers' reference for Plan 4 Stage E (Tasks 22–31). Every number in a section is a
`{{< var key >}}` from `docs/paper/_variables.yml` (built from `variables_map.csv`) or sits
inside a generated include (`@tbl-<id>`, `@fig-<id>`, from `tables.csv` / `figures.csv`).
Nothing here is new data: each key reads a committed generated file, `config`, the frozen
power values or the PAP. Section writers do not edit `variables_map.csv`, `tables.csv` or
`figures.csv`; a claim with no object listed here is cut or worded without its number (see
"Not available" at the end).

Conventions:

- Units follow the Global Constraints. RQ1 coefficients: pp of the outcome share per unit of the
  regressor (log regressors per unit of the log, = 100 log points; W-17). Market slopes: pp of
  annualised alpha per 1 SD of exposure. Correlations: no unit. p: two-sided, `< 0.001` form.
- Values read from printed markdown (`confirmatory_h5.md`, `.md` regex rows) keep their printed
  precision. For prose use the `_pp2` forms of the H5/H5b estimate and intervals, and the
  `decision_text` keys, never a raw `decision` or `co_condition` (they print `False`).
- An include is placed with `{{< include _generated/tables/<id>.md >}}` (or `figures/`) and
  cited as `@tbl-<id>` / `@fig-<id>`.
- Section labels: `@sec-introduction`, `@sec-literature`, `@sec-data`, `@sec-methods`, `@sec-rq1`,
  `@sec-rq2`, `@sec-markets`, `@sec-robustness`, `@sec-limitations`, `@sec-conclusion`;
  appendices `@sec-app-pap` (A), `@sec-app-deviations` (B), `@sec-app-disclosures` (C),
  `@sec-app-robustness-tables` (D, with the implementation-choices table),
  `@sec-app-replication` (E).
- The plan's informal ids map to: `@tbl-confirmatory-h5` → `@tbl-rq3-confirmatory`;
  `@tbl-rq1-holm` → `@tbl-rq1-confirmatory-table` (the table with family p, Holm level and
  decision). `@tbl-releases` exists under that id.

## Shared across sections

| key | meaning | unit |
|---|---|---|
| `meta.wording` | Plan 2's `WORDING`, verbatim (use once in §3 and once in the brief) | text |
| `pap.tag`, `pap.commit`, `pap.date` | the pre-registration tag, its commit, its date | text / date |
| `design.release.r1` … `design.release.r6` | AEI release publication dates | date |
| `design.formation` | Design B formation date (= `design.release.r2`) | date |
| `design.window.start`, `design.window.end` | Design B return window | date |
| `design.window.months` | length of the confirmatory window | months |
| `design.seal_date` | market seal date (ChatGPT launch) | date |
| `design.n_industries` | FF49 industry count | count |
| `design.seed` | the project seed | integer |
| `design.alpha.rq1_total` | RQ1 family-wise α before the split | level |
| `design.alpha.rq1_h2` | α at which H2 is tested alone | level |
| `design.alpha.rq1_family` | Holm family-wise α for {H1, H3, H4} | level |
| `design.alpha.h5_first`, `design.alpha.h5_second` | Holm step levels over {H5, H5b} | level |
| `rq1.holm.h1`, `rq1.holm.h2`, `rq1.holm.h3`, `rq1.holm.h4` | the level each RQ1 hypothesis was tested at, exact (W-1; `rq1.h1.holm_level` is the 3-dp form) | level |
| `design.plausibility_pp` | D11 plausibility threshold for the H5 MDE | pp per 1 SD |
| `d11.primary_mde` | the primary (H5) MDE the D11 rule compares (= `power.mde.h5`) | pp per 1 SD |
| `vintage.oews.primary` | OEWS weight vintage of the primary (Design B) | text |
| `vintage.oews.r1` | OEWS vintage of R1 (look-ahead) | text |
| `vintage.oews.r32` | OEWS vintage of R32 (strict real-time) | text |
| `vintage.onet.primary`, `vintage.onet.r32` | O*NET task-file versions of the primary and of R32 | text |
| `vintage.onet_soc` | the O*NET-SOC taxonomy year | text |
| `design.s1.oews_release` | release date of the primary's OEWS weights (S1; read from the PAP) | date |

## Abstract (Task 31)

- Decisions: `rq1.h1.decision_text`, `rq1.h2.decision_text`, `rq1.h3.decision_text`,
  `rq1.h4.decision_text`, `rq3.h5.decision_text`, `rq3.h5b.decision_text`.
- D11: `d11.primary_mde`, `design.plausibility_pp`.
- RQ2 headline: `rq2.b.z_delegation.z_eloundou.rho` with `.ci.lo` / `.ci.hi` (human β).
- No exploratory number is presented as a finding; robustness in words, pointing to @sec-robustness.

## §1 Introduction (Task 22)

- Pre-registration: `pap.tag`, `pap.date`; α split `design.alpha.rq1_total`,
  `design.alpha.rq1_h2`, `design.alpha.rq1_family`, `design.alpha.h5_first`,
  `design.alpha.h5_second`.
- D11: `d11.primary_mde` (pp per 1 SD), `design.plausibility_pp` (pp per 1 SD); pointer @sec-markets.
- One decision variable per RQ: as in the abstract (`rq1.h*.decision_text`; RQ2 is descriptive:
  `rq2.b.z_delegation.z_eloundou.rho`; `rq3.h5.decision_text`, `rq3.h5b.decision_text`).

## §2 Related literature (Task 23)

No result numbers. Citations only.

## §3 Data and measurement (Task 24)

| object | meaning | unit |
|---|---|---|
| `@tbl-releases` | the AEI releases: publication date, source, data window, geography, taxonomies | table |
| `@tbl-regimes` | the measurement regimes: platform scope, classifier (unstated), collab_v1/v2, suppression, occupation basis | table |
| `@tbl-audit-exposure-coverage` | FF49 coverage and the z-score distribution by design | table |
| `design.release.r1` … `r6` | release publication dates | date |
| `audit.employment_covered_pct` | OEWS employment covered by the crosswalk (exact + rollup + hybrid) | % |
| `audit.oews_without_aei_emp_pct` | OEWS employment in occupations without AEI usage | % |
| `audit.unmatched_usage_pct` | AEI usage share with no matched occupation | % |
| `audit.zero_assigned_pct.b`, `.a_r2`, `.a_pooled` (= `d3.zero_assigned_pct` for B) | the D3 zero-assigned employment share, by design (W-8: unpublished, assigned zero by assumption) | % |
| `vintage.onet.primary`, `vintage.onet_soc` | O*NET task file and O*NET-SOC year | text |
| `vintage.oews.primary`, `design.s1.oews_release`, `design.formation` | S1 timing: weights vintage, its release date, the formation date | text / date |
| `rq2.n_draws` | industry-bootstrap draws | count |
| `meta.wording` | the disclaimer, once | text |

Exposure-index equations: symbols only; no constant needs a variable beyond `design.n_industries`.

## §4 Pre-registration and methods (Task 25)

| key | meaning | unit |
|---|---|---|
| `pap.tag`, `pap.commit`, `pap.date` | the protocol | text / date |
| `design.alpha.*`, `rq1.holm.*` | the α split and the Holm levels (see shared table) | level |
| `rq1.h1.n_rows`, `rq1.h1.n_tasks`, `rq1.h1.n_occ` | H1 sample: rows, task clusters, occupation clusters | count |
| `rq1.h3.n_rows`, `rq1.h3.n_tasks`, `rq1.h3.n_occ` | H3 sample | count |
| `rq1.h2.n_tasks`, `rq1.h2.n_rows` | H2 balanced panel | count |
| `rq1.h2.n_wild_draws` | enumerated release-level wild-bootstrap vectors (D22) | count |
| `rq1.h2.n_release_orderings` | release-label orderings (descriptive check) | count |
| `rq1.h4.n` | H4 countries | count |
| `rq1.h1.attenuation`, `rq1.h3.attenuation` | P13 attenuation factors | ratio |
| `rq2.n_draws` | RQ2 industry-bootstrap draws | count |
| `power.n_windows` | historical windows for the null scale (D10) | count |
| `design.null_years` | span of the historical windows | text |
| `power.t_df` | t degrees of freedom | df |
| `power.crit_0025`, `power.crit_005` | t₂₁ criticals at the two Holm steps | t |
| `power.s.h5`, `power.s.h5b` (also `_r12`, `_r13`) | frozen null scale s | pp per 1 SD |
| `power.bbar.h5`, `power.bbar.h5b` (also `_r12`, `_r13`) | D21 null b̄ | pp per 1 SD |
| `power.mde.h5`, `power.mde.h5b`, `power.mde.h5_r13`, `power.mde.h5b_r13` | MDEs at 80 % power, first Holm step | pp per 1 SD |
| `power.power_pct` | power for the MDE | % |
| `design.plausibility_pp` | D11 threshold | pp per 1 SD |
| `rq3.secondary.size_pct.ri_h5`, `.ri_h5b`, `.fl_pivotal_h5b`, `.fl_coef_h5b` | documented size of the RI secondaries at nominal `design.alpha.h5_first` (§3.2: why RI is not primary) | % |
| `rq3.secondary.n_permutations` | permutations per RI test | count (text) |
| `audit.exposure.b.z_del_max`, `.z_del_max_industry`, `.z_del_skewness` | why R12 (ranks) and R13 (drop Softw) are co-primary | SD / text / skewness |

## §5 RQ1 results (Task 26)

Anatomy: `@tbl-rq1-major`, `@tbl-rq1-wage-decile`, `@tbl-rq1-education`,
`@tbl-rq1-concentration`, `@tbl-rq1-concentration-harmonised`; `@fig-rq1-composition-major`,
`@fig-rq1-composition-wage-decile`, `@fig-rq1-composition-education`, `@fig-rq1-lorenz`;
values `rq1.anatomy.*` (major groups, deciles, education, `rq1.anatomy.concentration.<source>.<release>.{gini,top1_share,top10_share,n_tasks,n_tasks_50pct}`).
Confirmatory: `@tbl-rq1-confirmatory-table` (Holm table), `@fig-rq1-coefficients`.

| key | meaning | unit |
|---|---|---|
| `rq1.h1.beta_e`; `rq1.h1.human_education_years_mean.{ci_low,ci_high,p,se}` | β_e | pp of automation per year of education |
| `rq1.h1.beta_w`; `rq1.h1.log_wage.{ci_low,ci_high,p,se}` | β_w (W-2: opposite in sign to H1, nominal p only) | pp per unit of log wage |
| `rq1.h1.p`, `rq1.holm.h1`, `rq1.h1.decision_text`, `rq1.h1.attenuation` | p_H1, its level, decision, P13 factor | p / level / text / ratio |
| `rob.r24.r5.p_h1.p`, `rob.r24.r5.human_education_years_mean.estimate`, `rob.r24.r5.log_wage.estimate` | W-15: R24 r5 | p / coef |
| `rq1.h2.beta`, `rq1.h2.trend.{ci_low,ci_high}`, `rq1.h2.p_cluster`, `rq1.h2.p_wild`, `rq1.holm.h2`, `rq1.h2.decision_text` | H2 | pp per year |
| `rq1.h2.release_effect.{r3,r4,r5}.{estimate,ci_low,ci_high,p}` | release effects relative to r2 (W-3: one r2→r3 step, then a fall) | pp |
| `rq1.h2.p_release_label` | release-label randomisation p, descriptive | p |
| `@fig-rq1-h2-release-effects` | the event-style plot | figure |
| `diag.h2.leave_out_release_r2.{beta,p_cluster,p_wild}` | W-3: leaving out r2 reverses β (D-3 diagnostic) | pp per year |
| `diag.h2.balancing_removed.n_tasks`, `diag.h2.balancing_removed.usage_share_pct` | W-4: the D2 balanced-panel drop, descriptive | count / % |
| `rob.r22.api_r3_r5.estimate` (+ `ci_lo`, `ci_hi`, `p`), `rob.r23.h2.estimate` (+ …) | W-3: rows that run the other way | pp per year |
| `rq1.h3.gamma`; `rq1.h3.error_cost.{ci_low,ci_high,p,se}`, `rq1.holm.h3`, `rq1.h3.decision_text`, `rq1.h3.attenuation` | H3 | pp of validation share |
| `rq1.h4.b1`; `rq1.h4.log_aui.{ci_low,ci_high,p,se}` | b₁ | pp per unit of log AUI |
| `rq1.h4.b2`; `rq1.h4.log_income.{ci_low,ci_high,p,se}` | b₂ | pp per unit of log GDP per working-age person |
| `rq1.h4.p_wald`, `rq1.holm.h4`, `rq1.h4.decision_text`, `rq1.h4.mix.*` | joint Wald p, level, decision; mix term (not tested) | p / text / pp per pp |
| `@fig-rq1-map-country-{automation,aui,mix,within}`, `@fig-rq1-map-state-{automation,aui,mix,within}`, `@tbl-rq1-countries`, `@tbl-rq1-states` | H4 shift-share maps | figure / table |
| `diag.h1.leave_out_soc_major_15.{beta_e,beta_w,p_h1,dropped_weight_pct,dropped}` | W-5: SOC major group leave-out (`dropped` prints the group code) | coef / p / % / text |
| `diag.h1.leave_out_top_1.{…,dropped}`, `diag.h1.leave_out_top_3.{…,dropped}` | W-5: top occupation(s) left out (`dropped` prints the SOC codes) | coef / p / % / text |
| `@tbl-diag-h1-influence`, `@tbl-diag-h2-influence` | the D-3 tables | table |
| `rob.r26.{gwa,dwa}.*`, `rob.r24.{r4,r5,r6_1p_api}.*`, `rob.r10.h1_ub.*` | W-5: the rows that move H1 most | coef / p |

R23 for H1: `rob.r23.{human_education_years_mean,log_wage,p_h1}.*` exist (in R23.md). W-14: no
correlation number exists; word without one.

## §6 RQ2 results (Task 27)

`@tbl-rq2-could-vs-does-b` (Spearman table; human β column `z_eloundou` is the headline, GPT-4 β
`z_eloundou_gpt4` beside it), `@fig-rq2-could-vs-does` (scatter), `@tbl-rq2-top-bottom-usage`,
`@tbl-rq2-top-bottom-delegation`, `@tbl-rq2-top-bottom-augmentation`, `@tbl-rq2-rank-gaps-eloundou`,
`@tbl-rq2-rank-gaps-eloundou-gpt4`, `@tbl-rq2-rank-gaps-aioe`, `@tbl-rq2-bounds-industries`,
`@fig-rq2-bound-widths`; Design `A_pooled` (look-ahead) `@tbl-rq2-could-vs-does-a-pooled`.

| key | meaning | unit |
|---|---|---|
| `rq2.b.<aei>.<bench>.rho`, `.ci.lo`, `.ci.hi` (aei ∈ z_delegation, z_augmentation, z_usage; bench ∈ z_eloundou, z_eloundou_gpt4, z_aioe) | Design B Spearman with industry-bootstrap CI | ρ |
| `rq2.a_pooled.<aei>.<bench>.*` | the same, Design `A_pooled` (look-ahead) | ρ |
| `rq2.n_draws` | bootstrap draws | count |
| `audit.exposure.b.z_del_max`, `.z_del_max_industry`, `.z_del_2nd`, `.z_del_min`, `.z_del_skewness`, `.z_usage_skewness` | Softw's position and the skew of the 49 z-scores | SD / text / skewness |
| `rq2.bounds_occupation.{delegation,automation}.{p25,p50,p75,n}` | width of the suppression bounds across occupations | pp |
| `rob.r03.spearman_z_eloundou_vs_z_delegation.{estimate,ci_lo,ci_hi}` | W-7: R3 lowers ρ most | ρ |
| `rob.r01.spearman_*`, `rob.r02.*`, `rob.r11.*`, `rob.r14.*`, `rob.r15.*`, `rob.r17.*`, `rob.r20.*`, `rob.r33.*` | R1/R2/R11/R14/R15/R17/R20/R33 values (Appendix D) | ρ |
| `vintage.oews.primary`, `design.s1.oews_release`, `design.formation`, `vintage.onet.primary`, `vintage.onet.r32`, `vintage.oews.r32` | W-9 timing caveat beside every RQ2 Spearman | text / date |
| `rob.r32.*` | R32 strict real-time row (market values; R32 has no RQ2 Spearman key) | pp per 1 SD |

## §7 What the market evidence can and cannot yet say (Task 28)

1. D11: `d11.primary_mde`, `design.plausibility_pp`.
2. `@tbl-rq3-confirmatory`; co-primary `rq3.h5_r12.*`, `rq3.h5_r13.*`, `rq3.h5b_r12.*`,
   `rq3.h5b_r13.*` (`b`, `s`, `bbar`, `t_bbar`, `t_zero`, `p_primary`, `p_secondary`).
3. Fixed wording: `rq3.h5.wording`, `rq3.h5b.wording` (verbatim).
4. Intervals and MDEs:

| key | meaning | unit |
|---|---|---|
| `rq3.h5.b_pp2`, `rq3.h5.ci_005.{lo,hi}_pp2`, `rq3.h5.ci_0025.{lo,hi}_pp2` (raw: no `_pp2`) | b̂ and the two intervals | pp per 1 SD |
| `rq3.h5.t`, `rq3.h5.p`, `rq3.h5.s`, `rq3.h5.bbar`, `rq3.h5.decision_text` | primary statistic, p, s, b̄, decision | t / p / pp / text |
| `rq3.h5b.*` | the same for H5b | |
| `rq3.h5.mde`, `rq3.h5b.mde`, `rq3.h5.mde_r13`, `rq3.h5b.mde_r13` | MDE and R13 MDE | pp per 1 SD |
| `rq3.h5.b0.t`, `rq3.h5.b0.p`, `rq3.h5b.b0.t`, `rq3.h5b.b0.p` | W-11: the secondary b = 0 null, labelled secondary, MDE beside it | t / p |
| `rq3.secondary.ri_h5`, `rq3.secondary.ri_h5b`, `rq3.secondary.fl_h5b`, `rq3.secondary.fl_coef_h5b` | RI p-values (secondary) | p |
| `rq3.secondary.size_pct.*` | their documented size | % |
| `rq3.secondary.hc3_h5_b`, `_se`, `rq3.secondary.hc3_h5b_b`, `_se` | OLS HC3 b and SE | pp |
| `rq3.provenance.{n,n_days,dropped,commit}` | industries, factor days, drops, commit | count / text |
| `rq3.influence.softw.h5.{dfbetas,cooks_d,leverage}`, `rq3.influence.softw.h5b.*` | item 6: Softw influence (unitless) | — |
| `@tbl-rq3-influence-softw`, `@tbl-rq3-influence-top` | the influence tables | table |
| `rob.r07.h5.*`, `rob.r05.h5.*`, `rq3.h5_r12.b` | W-16: rows moving H5 most (R7, R5, R12) | pp per 1 SD |
| `rob.r07.h5b.*`, `rob.r06.h5b.ff30.*`, `rq3.h5b_r12.b` | W-16: rows moving H5b most (R7, R6 FF30, R12) | pp per 1 SD |
| `rob.r32.h5.*`, `rob.r32.h5b.*`, `rob.r01.h5.*` | W-9: R32 strict real-time; R1 look-ahead | pp per 1 SD |

7. Exploratory (each paragraph opens "Exploratory:"):
   - Design A / events: `@tbl-rq3-event-dates`, `@tbl-rq3-event-days`, `@tbl-rq3-event-slopes`,
     `@fig-rq3-event-slopes`; `rq3.event.<event>.<k>.<design>.<regressors>.<regressor>.{b,ci_lo,ci_hi,p}`.
   - Terciles: `@tbl-rq3-terciles-*`, `@tbl-rq3-terciles-dsr`, `@fig-rq3-tercile-cumulative`;
     `rq3.terciles.<design>.<cap|ew>.{psr,dsr}.estimate` and the alpha keys.
   - Fama–MacBeth: `@tbl-rq3-fama-macbeth-{b,a-r2,a-pooled}`; `rq3.fama_macbeth.<design>.<var>.{mean,ci_lo,ci_hi,p,n_months}`.
   - Eisfeldt et al.: `@tbl-rq3-eisfeldt-step1`, `@tbl-rq3-eisfeldt-step2`;
     `rq3.eisfeldt.step1.{b,ci_lo,ci_hi,p}` (pp of CAR per 1 SD of `z_aioe`, nominal p).
   - `audit.exposure.a_pooled.*` for the `A_pooled` z-distribution.
8. H6, exploratory:

| key | meaning | unit |
|---|---|---|
| `h6.talk.year`, `h6.talk.filed_start`, `h6.talk.filed_end` | filing year and dates of the talk index T | text / date |
| `h6.talk.pooled_all.{y2019,y2024,y2025}`, `h6.talk.pooled_mapped.{…}` | pooled talk share (all / mapped filers) | share |
| `h6.talk.unmapped_share_pct.{y2019,y2024,y2025}` | unmapped filers | % |
| `h6.spearman.rho`, `h6.spearman.ci.lo`, `h6.spearman.ci.hi` | divergence Spearman(T, z_usage) | ρ |
| `diag.h6.none.p` | W-6: its nominal p (t-approximation, n − 2 df) | p |
| `diag.h6.<industry>.{rho,ci_lo,ci_hi}` (e.g. `diag.h6.softw.*`) | W-5: leave-one-industry-out | ρ |
| `rob.r29.h6_divergence.{change_2019_2024,float_weighted,pre_formation_2025}.*` | W-5: R29 parts whose CIs cover 0 | ρ |
| `h6.gap_returns.{b,ci.lo,ci.hi,p_bbar,t_bbar,p_zero,t_zero,s,bbar,crit,n}` | gap–return association, nominal | pp per 1 SD of gap |
| `h6.vintage.submissions_retrieved_utc` | W-10: retrieval timestamp of the EDGAR submissions file (current SIC) | timestamp text |
| `@tbl-h6-divergence`, `@tbl-h6-gap-ranking`, `@tbl-h6-gap-returns`, `@tbl-h6-talk-by-year`, `@tbl-diag-h6-influence`, `@fig-h6-talk-by-year`, `@fig-h6-talk-vs-usage` | H6 tables and figures | |

9. A future window: `power.mde_over_s` (the MDE in units of s, the across-window spread of the
   historical slopes: MDE = `power.mde_over_s` × s), with `power.s.h5`, `power.s.h5b`,
   `rq3.h5.mde`, `rq3.h5b.mde`, `design.window.months`, `design.plausibility_pp`.

## §8 Robustness (Task 29)

`@fig-robustness-rq1`, `@fig-robustness-market`, `@tbl-rob-summary`; per-row tables
`@tbl-rob-r01` … `@tbl-rob-r38`; values `rob.rNN.*`. Pointer `@sec-app-robustness-tables`.
Rows that move each confirmatory estimate most (named, never counted):

| estimate | rows and keys |
|---|---|
| H1 (W-5, W-15) | R24 r5 `rob.r24.r5.*`; R24 r4 `rob.r24.r4.*`; R24 `rob.r24.r6_1p_api.*`; R26 `rob.r26.gwa.*`, `rob.r26.dwa.*`; R10 `rob.r10.h1_ub.*` |
| H2 (W-3) | R22 `rob.r22.api_r3_r5.*`, `rob.r22.all_r2_r6.*`, `rob.r22.unbalanced.*`; R23 `rob.r23.h2.*`; R36 `rob.r36.h2.*`; R37 `rob.r37.h2.*` |
| H3 | R10 `rob.r10.h3_ub.*`; R27 `rob.r27.h3.*`; R31 `rob.r31.error_cost.*`; R38 `rob.r38.h3.*` |
| H4 | R25 `rob.r25.h4a.*`, `rob.r25.h4b.*`; R28 `rob.r28.*` |
| H5 (W-16) | R7 `rob.r07.h5.*`; R12 `rq3.h5_r12.b`; R5 `rob.r05.h5.*` |
| H5b (W-16) | R12 `rq3.h5b_r12.b`; R7 `rob.r07.h5b.*`; R6 `rob.r06.h5b.ff30.*` |
| H6 (W-5) | R29 `rob.r29.h6_divergence.*`, `rob.r29.h6_gap_return.*`; R30 `rob.r30.*` |

Which rows move an estimate "most" for H3 and H4 is not stated by any generated file; name rows
only where W-5, W-15 or W-16 names them, otherwise report the row values without ranking.

## §9 Limitations (Task 30)

`audit.zero_assigned_pct.b` (D3), `@tbl-regimes` (unstated classifier, platform drift),
`rq2.bounds_occupation.*` (suppression), `diag.h2.leave_out_release_r2.beta`, `rq1.h2.n_tasks`
(H2's releases: four, in words), `design.n_industries`, `audit.exposure.b.z_del_max`,
`rq3.influence.softw.*`, `design.window.months`, `design.window.start`/`end`,
`design.s1.oews_release`, `design.formation`, `vintage.oews.*`, `rob.r32.*`,
`h6.vintage.submissions_retrieved_utc`.

## §10 Conclusion (Task 30)

One decision variable per RQ: `rq1.h1.decision_text` … `rq1.h4.decision_text`;
`rq2.b.z_delegation.z_eloundou.rho` (descriptive); `rq3.h5.decision_text`, `rq3.h5b.decision_text`,
`rq3.h5.mde`, `rq3.h5b.mde`, `power.mde_over_s`.

## Executive brief (Task 31)

`meta.wording` (once); decisions as in the abstract; uncertainty `rq1.h4.log_aui.{ci_low,ci_high}`,
`rq2.b.z_delegation.z_eloundou.ci.{lo,hi}`, `rq3.h5.ci_005.{lo,hi}_pp2`, `rq3.h5.mde`; one figure,
for example `@fig-rq1-coefficients` or `@fig-rq2-could-vs-does`.

## Not available (cut the claim, or word it without the number)

- **H6 gap–return MDE** (W-12): no generated file computes one. Write "no MDE computed
  (exploratory)".
- **Correlation of log AUI with log GDP per working-age person** (W-14): none generated; state
  the collinearity without a number.
- **SEC full-text-search retrieval date as one value** (W-10): the search pages were retrieved
  over a span (MANIFEST rows `sec_fts/*`); no single generated value. Say "on the retrieval
  date"; the year of retrieval can be taken from `h6.vintage.submissions_retrieved_utc`.
- **"Rows that move H3/H4 most"**: no file ranks them (see §8 note).
- **R32 RQ2 Spearman**: R32 is a market row only; no RQ2 value under strict real-time inputs.
- **RI size at nominal 0.05** and the non-overlapping-window sizes: printed only in
  `docs/pap/power.md` prose tables, not mapped; quote the 0.025 sizes (`rq3.secondary.size_pct.*`).
- **H1/H3 non-PSD clipping flag**: in `confirmatory_rq1.json` as a boolean only; not mapped,
  because prose must not print `False`. State the rule and that the variance matrix was used as
  estimated only if that is worded without a number (Appendix B/C for detail).
