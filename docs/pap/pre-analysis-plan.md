# Pre-analysis plan: *Delegating to the Machine*

**Status: DRAFT for Ajai's review. Not signed, not frozen.** The plan is frozen only when Ajai signs §0.1
and the git tag `pap-v1` is created (plan 1, Task 15, Step 4). Until then every **[PROPOSED — Ajai to
confirm]** block is a recommendation, not a decision.

- Draft date: 2026-10-21. Branch `plan-1-foundations`.
- Code the plan refers to: commit `81cfae2af7d97eac277f6208647a389b9fde6d5d` (§9.2).
- Design: [`docs/superpowers/specs/2026-10-21-ai-delegation-design.md`](../superpowers/specs/2026-10-21-ai-delegation-design.md) ("the spec").
- Evidence the decisions rest on: [`docs/audit/data-audit.md`](../audit/data-audit.md) ("the audit", with
  its tables in `docs/audit/tables/`) and [`docs/pap/power.md`](power.md) ("the power analysis").

AEI data are conversations matched to O\*NET tasks. Throughout this plan, an occupation's or an
industry's AEI value describes conversations matched to that occupation's tasks (or to the tasks of the
occupations an industry employs). Nothing in this plan, and nothing estimated under it, is a statement
about job risk, displacement or reassurance about the labour market.

---

## 0. Status, conventions, decision register, disclosures

### 0.1 Signature

Signature: *pending (added at freeze, Task 15 Step 4).*

### 0.2 Conventions

- **Confirmatory** means: the specification, sample, inference and decision rule are fixed here; the
  result is reported whatever it is, with the same prominence for a null as for a rejection (spec §2).
  **Secondary** means a pre-specified alternative inference for a confirmatory estimate.
  **Robustness** means a pre-specified variant (§8), always reported in full. **Exploratory** means
  pre-specified where stated, but no claim of error-rate control, and labelled "exploratory" wherever it
  appears.
- Every estimate is reported with its point value, a 95% confidence interval and its p-value. Stars are
  not used.
- All tests are two-sided. Where a hypothesis states a direction (H1, H2, H3), the decision rule
  (§2) requires both significance and the stated sign; a significant estimate of the opposite sign is
  reported as "contradicts the hypothesis".
- Randomness: `aideleg.config.SEED = 20261021`, through `numpy.random.default_rng(SEED)`; the order
  in which draws are consumed is fixed in the section that uses them.
- Releases: `r1` = 2025-02-10, `r2` = 2025-03-27, `r3` = 2025-09-15, `r4` = 2026-01-15, `r5` = 2026-03-24,
  `r6` = 2026-06-26 (publication dates). Windows as in the audit [REL]; the r1/r2 windows are defaults
  (the READMEs state none).
- Sources: `claude_ai` (Claude.ai / Claude chat and Cowork) and `1p_api` (r3 onward). Geography is
  `global` unless stated.
- Collaboration buckets (AEI definition): automation = `directive` + `feedback_loop`; augmentation =
  `task_iteration` + `validation` + `learning`. Shares are renormalised over classified conversations
  (excluding `filtered`, `none`, `not_classified`), in percent 0–100.
- Units for the market tests: annualised alpha in percentage points (pp) per 1 SD of exposure.
- "The panel" is `data/derived/aei_panel.parquet` (`make panel`); "the exposure tables" are
  `data/derived/exposure_occupation.parquet` and `exposure_ff49.parquet` (`make exposure`); the
  benchmarks are `data/derived/benchmark_ff49.parquet` (`make benchmarks`), all at the commit in §9.2.

### 0.3 Decision register

Each decision below is set out in a **[PROPOSED — Ajai to confirm]** block in the section named. Each
block gives the recommended choice, its rationale, and the alternatives; every alternative becomes a
pre-registered robustness check (§8) unless the block says otherwise. When Ajai signs, the recommended
choice is adopted unless he writes a different one into the block.

| ID | Decision | Recommended | Section |
|---|---|---|---|
| D1 | Primary delegation measure | renormalised `automation_pct`; R7 bounds as robustness | §2.1 |
| D2 | H2 definition-stable metrics and series | `automation_pct`, r2–r5 `claude_ai`, balanced panel, linear trend | §5 |
| D3 | Occupations with no AEI match | zero usage (assumption); `drop` as robustness | §2.1 |
| D4 | Task-to-occupation allocation | equal split; employment-weighted split as robustness | §2.1 |
| D5 | Rank-based robustness for the skew | standardised ranks, and dropping Softw | §2.1 |
| D6 | AIOE vintage crosswalk | O\*NET-detail union (as built); BLS SOC 2010→2018 as robustness | §2.1 |
| D7 | NAICS 5511 | excluded; pro-rata redistribution as robustness | §2.1 |
| D8 | Eloundou rating | human β headline, GPT-4 β beside it (descriptive only) | §2.1 |
| D9 | r6 occupation basis | published SOC; task-allocated as robustness | §2.1 |
| D10 | Confirmatory inference for H5/H5b | normal test on the historical pre-seal null sd of the slope; RI (H5) and Freedman–Lane RI (H5b) secondary | §3.3 |
| D11 | 5 pp plausibility rule | rule fires (MDE 7.00–8.74 pp): RQ3 reported as "what the market evidence can and cannot yet say" | §7 |
| D12 | H6 AI-term dictionary | the list and matching rules in §6 | §6 |
| D13 | RQ1 cross-sectional sample (H1, H3) | r6 `claude_ai`, both months averaged | §4.1 |
| D14 | Task family fixed effects | O\*NET IWA via Tasks-to-DWAs (data to acquire before the tag) | §4.1 |
| D15 | H3 error-cost indicator | SOC-code list (legal, health practitioners, regulated finance) | §4.3 |
| D16 | H4 specification | r6 country cross-section; log AUI, log GDP per working-age person, task-mix control | §4.4 |
| D17 | One p-value per multi-coefficient hypothesis | H1 intersection–union; H4 joint Wald | §4.0 |
| D18 | H6 status and talk index | exploratory; firm share of 10-Ks with a term, 2024 filings | §6 |
| D19 | Exploratory market parameters | event dates and windows listed in §8.3 | §8.3 |
| D20 | Data acquired before and after the freeze | Tasks-to-DWAs and DWA Reference before the tag; others after, pre-specified | §9.4 |

### 0.4 Disclosures

What was seen before this plan was frozen:

1. **Task 3 incident.** While inspecting the French file layout, the Task 3 implementer subagent
   displayed aggregate monthly FF5 factor rows for 2026-05..2026-08 and the momentum row for 2026-08.
   These are aggregate factors, not industry returns. They were not used or recorded, and they carry no
   information about the cross-sectional slope of industry alphas on exposure (H5/H5b). The controller
   ruled it not contamination (ledger, Task 3); it is disclosed here as required.
2. **Retracted figure.** The Task 6 finding that renormalising task automation over published patterns
   inflates it by "7–9 points" (r3 57.8 vs 51.1) is **retracted**. It came from an uncommitted scratch
   script. Re-derived on the committed panel, the gap is 51.20 vs 51.07 (0.13–0.35 points for
   `claude_ai`, 1.11–1.86 for `1p_api`) [audit §4]. No decision in this plan relies on the retracted
   figure.
3. **Exposure descriptives seen before the freeze.** The researchers saw: the top and bottom FF49
   industries by Design B `z_delegation` (top Softw 4.739, next 1.977; bottom Meals, Rtail, Cnstr); its
   skewness (2.571); the within-group dispersion of U in SOC 15-125x; the Spearman correlations of
   the "could" benchmarks with `z_delegation` and `z_usage` across FF49 (AIOE 0.763 / 0.809, Eloundou
   human β 0.716 / 0.768, GPT-4 β 0.815 / 0.843); Pearson(`z_aioe`, `z_delegation`) = 0.671; the
   correlations of `z_delegation` with its R7 bounds (≥ 0.9997); the allocated-vs-published r6 SOC
   correlations [audit §5, §8, §9]. These are RQ2 descriptives. No delegation measure has been related
   to wage, education, error-cost or country variables (H1–H4), and no industry return dated on or after
   2022-11-30 has been read by code.
4. **Pre-seal market history.** The power analysis estimated FF5+UMD alphas and cross-sectional slopes
   on 1990–2022 windows (returns read to 2022-11-29). Only the dispersion of the slopes and RI rejection
   rates were printed; the level and sign of the historical slopes were computed in memory but never
   reported. While drafting this plan, the power module was rerun unchanged at commit `81cfae2` to read
   its full-precision slope sds (§3.3); the generated block was byte-identical to the committed one.
5. **General knowledge of the sealed period.** The seal stops code from reading post-2022-11-29 returns.
   It cannot remove what the researchers (or the language model assisting them) know from public
   commentary about broad market moves in 2023–2026, for example the AI-related rally in large
   technology stocks. This is why Design A is exploratory and why the confirmatory test (§3) is fixed
   here, together with its exposure vector (§9.3), before any post-seal return is read.

---

## 1. Hypotheses (verbatim from the spec, approved by Ajai on 2026-10-21)

### RQ1 — Behaviour: who delegates, for what, and is it changing?
- **H1 (stakes / algorithm aversion).** Within task families, delegation (automation share, mean AI autonomy) is lower for tasks requiring more human education and in higher-wage occupations. *Lit:* Dietvorst, Simmons & Massey (2015); Logg, Minson & Moore (2019); Parasuraman & Riley (1997).
- **H2 (trust accumulation).** Within the same O\*NET task, delegation rises across releases (Dec 2024 → May 2026). *Lit:* Lee & See (2004) trust calibration; AEI v5 "learning curves".
- **H3 (calibrated checking).** The *validation* collaboration pattern is more prevalent in occupations with high error costs (regulated finance, health, legal) after conditioning on task type.
- **H4 (geography).** Country-level delegation share relates to AI adoption intensity (Anthropic Usage Index) and income, conditional on task mix. Direction left open (two-sided).

### RQ2 — Bridge: industry exposure
- Construct three industry indices — **usage exposure**, **delegation exposure**, **augmentation exposure** — and benchmark them against theoretical exposure scores. Descriptive question: how far apart are "could" and "does"?

### RQ3 — Markets
- **H5 (pricing of exposure).** Industries with higher pre-period AI exposure earned different risk-adjusted returns after 30 Nov 2022; and **H5b**: delegation exposure carries information beyond theoretical exposure. Two-sided.
- **H6 (talk vs use).** Industry-level 10-K AI discussion ("talk") diverges from observed usage; the residual ("AI-washing gap") is tested for association with returns. Two-sided, exploratory unless Ajai promotes it to confirmatory.

A null on RQ3 is a complete, publishable result and will be reported with the same prominence as a positive.

---

## 2. Per-hypothesis specification

### 2.0 Summary

| | Outcome | Predictor / exposure | Sample | Estimator | SEs / inference | Family | Decision rule | Status |
|---|---|---|---|---|---|---|---|---|
| **H1** | task `automation_pct` | `human_education_years_mean` (task); log OEWS median wage (occupation) | r6 `claude_ai` global, task × occupation rows, IWA FE (D13, D14) | WLS, weights = allocated usage | two-way clustered (occupation, task); p = max of the two p-values (D17) | {H1–H4}, Holm 0.05 | Holm rejects and both coefficients < 0 | confirmatory |
| **H2** | task `automation_pct` | months since r2 (linear trend) | r2–r5 `claude_ai` global, tasks published in all four (D2) | WLS with task FE, fixed weights | clustered by task | {H1–H4} | Holm rejects and β > 0 | confirmatory |
| **H3** | task `validation_pct` | occupation error-cost indicator (D15) | as H1 | WLS with IWA FE | as H1 | {H1–H4} | Holm rejects and γ > 0 | confirmatory |
| **H4** | country `automation_pct` (overall) | log AUI; log GDP per working-age person; task-mix control | r6 `claude_ai` countries (D16) | OLS | HC3; joint Wald of the two coefficients (D17) | {H1–H4} | Holm rejects (two-sided) | confirmatory |
| RQ2 | — | `z_usage`, `z_delegation`, `z_augmentation` vs AIOE, Eloundou | FF49, Design B and A_pooled | Spearman ρ | industry bootstrap CI | none | descriptive | descriptive |
| **H5** | FF49 FF5+UMD alpha, 2025-04-01 → 2026-08-31 | Design B `z_delegation` | 49 FF49 industries, daily VW | cross-sectional OLS | historical-null normal test (D10); RI secondary | {H5, H5b}, Holm 0.05 | Holm rejects (two-sided) | confirmatory |
| **H5b** | as H5 | `z_delegation`, controlling for `z_aioe` | as H5 | cross-sectional OLS | as H5; Freedman–Lane RI secondary | {H5, H5b} | Holm rejects (two-sided) | confirmatory |
| **H6** | industry 10-K talk index; alpha | `z_usage`; AI-washing gap | FF49; 10-Ks filed 2019–2025 | OLS residual; cross-sectional OLS | as H5 (nominal) | none | reported, no rejection claim | exploratory (D18) |

H1–H4 are specified in §4, H5/H5b in §3, H6 in §6.

### 2.1 Measurement decisions shared by several hypotheses

Exposure construction follows spec §5.3 as implemented in `aideleg.exposure` and `aideleg.benchmarks`
at the commit in §9.2:
- U_o = AEI usage share of occupation o ÷ o's share of US employment (OEWS May 2024, national).
- D_o = U_o × automation share of o; A_o = U_o × augmentation share of o.
- E_j = Σ_o w_oj X_o over occupations with a value, w_oj = o's share of industry j employment (OEWS
  May 2024, NAICS 4-digit), NAICS 2022 → SIC 1987 → FF49 by the Census concordances with equal splits
  (`naics_to_ff49("split", 4, "exclude")`).
- z = (E − mean) / population SD across the FF49 industries present.
- Design B = release r2 only (`claude_ai`, the only r2 source). A_r2 = the same numbers, labelled
  exploratory. A_pooled = r2–r6 `claude_ai`, equal release weights (exploratory).

> **[PROPOSED — Ajai to confirm] D1. Primary delegation measure.**
> *Recommended:* the renormalised automation share `automation_pct` (automation as a percent of
> classified conversations), at task, occupation and industry level, in every hypothesis.
> *Rationale:* it is the only delegation measure defined identically in every release r2–r6 (the
> five classified patterns, renormalised) [MET], it is the spec's primary measure (§5.4.1), and its
> aggregate suppression bias is small: pct-weighted task automation is 51.20 vs 51.07 for r3
> `claude_ai`, gaps 0.13–0.35 points (`claude_ai`) and 1.11–1.86 (`1p_api`) [audit §4]. The R7
> bounds depend on each release's suppression construct (r2 `filtered`; r3–r5 `not_classified` +
> `none`; r6 `none`), so they are not definition-stable across releases. They are wide at occupation
> level on r2–r5 (median width 10.54–18.18 points) but narrow on r6 (1.18–2.64) [SUP], and at FF49
> level they barely move the index (Pearson 0.99969–0.99990 with `z_delegation`) [audit §4].
> *Alternatives (robustness R10):* `automation_share_all_lb` (suppressed conversations counted as
> non-automation) and `automation_share_all_ub` (counted as automation), substituted for
> `automation_pct` in H1, H3, H5, H5b and the Design B indices. Not applicable to H2 or A_pooled,
> where the bounds are not comparable across releases. Mean AI autonomy (`ai_autonomy_mean`, r4–r6) is
> the secondary RQ1 measure the spec names (§5.4.1); it is reported for H1 and H2 as robustness R23.

> **[PROPOSED — Ajai to confirm] D3. Occupations with no AEI match.**
> *Recommended:* `unmatched="zero"`: an OEWS occupation with no AEI usage is assigned U = D = A = 0.
> **This is an assumption.** AEI leaves these cells unpublished; it does not measure them as zero.
> *Rationale:* it is the spec's default (§4). The occupations concerned are mostly hands-on trades
> (construction laborers, maids, industrial truck operators, welders) [audit §6]. Dropping them would
> treat their unpublished usage as equal to their industry's mean usage, which overstates exposure in
> the industries that employ them most. Size of the assumption: 232 occupations and 12.14% of May
> 2024 employment are zero-assigned under Design B; 144 and 6.34% under A_pooled [OEWS]. Every report
> of an index states this.
> *Alternative (R3):* `unmatched="drop"`; the occupations leave the industry sums like a null measure.

> **[PROPOSED — Ajai to confirm] D4. Task-to-occupation allocation.**
> *Recommended:* equal split. A task statement shared by k occupations gives 1/k of its usage to
> each (the union of occupations over all candidate Task IDs, ruling R6).
> *Rationale:* the split conserves usage and uses no employment information, so U_o's numerator
> stays independent of its denominator. Its cost is documented: within SOC broad group 15-125x, U
> ranges from 5.020 (Software Developers) to 107.254 (Computer Programmers) because shared tasks are
> split equally regardless of employment [audit §8].
> *Alternative (R11):* split in proportion to the candidate occupations' May 2024 OEWS national
> employment. Note that this makes U equal across the occupations sharing a task, by construction,
> so it removes rather than tests the within-group dispersion.

> **[PROPOSED — Ajai to confirm] D5. Rank-based robustness for the skew.**
> *Recommended:* keep the standardised index `z_delegation` in the primary H5/H5b specification (the
> spec's wording and the basis of the power analysis), and pre-register two variants: (a) standardised
> ranks: rank E_delegation across the 49 industries (average ranks for ties), then z-score the ranks
> with population SD; (b) the primary specification with Softw dropped (48 industries, z not
> re-standardised).
> *Rationale:* Design B `z_delegation` is heavily right-skewed: Softw is at 4.739 SD, the next industry
> at 1.977, skewness 2.571 [EXP]. In the H5 regression Softw's leverage is 1/49 + 4.739²/49 ≈ 0.48, so
> the primary slope is driven to a large degree by Softw against the rest. Ajai should know this before
> signing. Making ranks primary would change the hypothesis's metric from "per SD of exposure" and would
> require the power analysis to be rerun before the tag; the recommendation keeps the spec and reports
> both variants with the same inference (§3.3, null sd recomputed for each vector).
> *Alternatives (R12, R13):* (a) and (b) above. If Ajai prefers ranks as primary, the power analysis
> is rerun with the rank vector before the tag and §3.3, §7 and §9.3 are regenerated.

> **[PROPOSED — Ajai to confirm] D6. AIOE vintage crosswalk.**
> *Recommended:* keep the O\*NET-detail union as built (`map_soc2010_to_2018`): a SOC 2010 code takes
> the successors of all its O\*NET-SOC 2010 children in the O\*NET 2010→2019 crosswalk; a split copies
> the value, a merge takes the simple mean.
> *Rationale:* it is the `z_aioe` that the power analysis used (Pearson 0.671 with `z_delegation`, VIF
> 1.82), it raises AIOE's coverage of OEWS employment from 82.5% to 98.9% and its FF49 coverage is
> 0.976–1.000 [BEN]. Its weakness is real: 49 SOC 2010 codes take the union of several successors, and
> 15-1199 (Computer Occupations, All Other) is copied to seven codes including 13-1082, 13-1161 and
> 15-2051 [audit §9]. The BLS SOC 2010→2018 crosswalk is the standard published mapping, but it is not
> in `data/raw`; adopting it as primary means acquiring it, writing and testing the mapping, and rerunning
> the power analysis, all before the tag. It is not established that it would be materially cleaner at
> SOC 6-digit level, since it is also many-to-many.
> *Alternative (R14):* the BLS SOC 2010→2018 crosswalk (acquired after the freeze, §9.4), with the same
> copy/simple-mean rule. If Ajai prefers it as primary, it is acquired before the tag, the power analysis
> is rerun, and §3.3 and §9 are regenerated.

> **[PROPOSED — Ajai to confirm] D7. NAICS 5511 (Management of Companies).**
> *Recommended:* excluded from FF49 as its own bucket (`hq="exclude"`), the current default.
> *Rationale:* 5511 holds 2.81M employed (1.84% of total). Through SIC 6712/6719 it would map to Fin,
> where it would make up about 71% of Fin's weight, so the head-office staff of non-financial firms
> would set Fin's occupation mix [ledger Task 10; audit §7].
> *Alternative (R15):* `hq="redistribute"`, 5511 spread over FF49 industries in proportion to their
> mapped private employment.

> **[PROPOSED — Ajai to confirm] D8. Eloundou rating.**
> *Recommended:* the human-annotator β (`human_rating_beta`) is the headline `z_eloundou`; the GPT-4 β
> (`dv_rating_beta`) is reported beside it in every RQ2 table.
> *Rationale:* the human rating does not depend on a language model's assessment of language-model
> exposure. The column meanings were confirmed from the GPTs-are-GPTs README ("dv_rating is the GPT-4
> rating and human is from the annotators", read 2026-10-21) [audit §9]. Eloundou is descriptive only
> (spec §5.4.1), so this choice cannot affect a confirmatory test.
> *Alternative (R17):* GPT-4 β as headline. Both are always shown, so this is a labelling choice.

> **[PROPOSED — Ajai to confirm] D9. r6 occupation basis.**
> *Recommended:* AEI's published SOC rows (`soc_detailed`) for r6 occupation tables, as built.
> *Rationale:* it is what AEI publishes for r6; it agrees closely with the task-allocated basis
> (Spearman 0.931–0.958, Pearson 0.996–0.999) [R6]. Its cost: 43 occupations appear only in r6
> (`claude_ai`), carrying 1.77% of r6 published SOC usage (25-3031 alone 1.36%), and they enter
> A_pooled through r6 alone [REL]. Design B (r2) is unaffected. H1 and H3 use task-level rows (§4.1)
> and are unaffected.
> *Alternative (R16):* the task-allocated r6 basis (`basis="tasks"`), which applies to A_pooled and
> to r6 occupation-level descriptives.

---

## 3. RQ3 confirmatory family {H5, H5b}

### 3.1 Primary specification (spec §5.4.1)

- **Exposure (formation).** Design B, release r2 only (published 2025-03-27): `z_delegation` from
  `build_exposure("B")` with the decisions of §2.1; `z_aioe` from `benchmark_ff49()`. Both are
  population-SD z-scores across the 49 FF49 industries. The exact vector is frozen by hash in §9.3.
  Nothing published after 2025-03-27 informs it.
- **Returns.** Ken French 49-industry **daily value-weighted** returns and the FF5 (2×3) daily factors
  plus daily momentum (UMD), the frozen files in §9.1 (`ff49_daily`, `ff5_daily`, `mom_daily`), in
  percent as published; −99.99 and −999 are missing.
- **Window.** 2025-04-01 to 2026-08-31 inclusive, every trading day present in both the industry and
  the factor file.
- **Alpha.** For each industry j: daily OLS of (r_jt − rf_t) on [1, Mkt-RF, SMB, HML, RMW, CMA, UMD],
  all in decimal; α̂_j = 252 × intercept (annualised, decimal). Implemented by
  `aideleg.power.window_alphas` at the commit in §9.2, the same code the power analysis used. An
  industry with any missing return in the window gets no alpha and is dropped; z values are **not**
  re-standardised; the dropped industries are reported and the null sd (§3.3) is recomputed on the
  remaining industries with the same procedure.
- **H5 regression.** α̂_j = a + b·z_delegation_j + e_j, OLS, unweighted. Estimand: b, in pp of
  annualised alpha per 1 SD of delegation exposure.
- **H5b regression.** α̂_j = a + b·z_delegation_j + c·z_aioe_j + e_j, OLS, unweighted. Estimand: b.
- **Theoretical-exposure control.** Felten, Raj & Seamans (2021) AIOE (D6). Webb (2020) is the spec's
  fallback, used only if AIOE became unusable, which would be a logged deviation.

### 3.2 Why the spec's inference cannot be primary

The spec names randomisation inference: shuffle exposure across industries, ≥ 10,000 draws. The power
analysis tested that procedure, exactly as specified (10,000 permutations, seed `SEED`), on 378
overlapping pre-seal 17-month windows, where exposure measured in 2025 can have no causal relation to
alphas. At a nominal 0.025 it rejects in **13.8%** of windows for H5 and **14.8%** for H5b with `z_aioe`
held in place; the Freedman–Lane scheme for H5b rejects in **6.1%** [power, size table]. The cause is
documented there: industries with similar exposure co-move, so the alpha noise is correlated along z,
and permutation, which treats industries as exchangeable, has a null spread (median within-window OLS SE
1.65 pp for H5) well below the across-window sd of the slope (2.27 pp). A confirmatory test with five
times its nominal size is not acceptable, so this plan replaces it as primary and keeps it as secondary.

### 3.3 Confirmatory inference

> **[PROPOSED — Ajai to confirm] D10. Confirmatory inference for H5 and H5b.**
> *Recommended:* a normal test whose scale is the historical null standard deviation of the same slope,
> estimated on pre-seal windows with the confirmatory exposure vector held fixed.
>
> - **Statistic.** T_H5 = b̂_H5 / s_H5 and T_H5b = b̂_H5b / s_H5b, with b̂ from §3.1.
> - **Null distribution source.** s is the sample standard deviation (ddof = 1) of the slope b
>   estimated, with the same code and the same frozen z vector(s), on the **378 overlapping 17-month
>   windows** stepped monthly from 1990-01-01 (first 1990-01-01 → 1991-05-31, last 2021-06-01 →
>   2022-10-31), using returns read through the sealed loaders with end = 2022-11-29. These are
>   `run_power()["sd_h5_overlap"]` and `run_power()["sd_h5b_overlap"]` at the commit in §9.2:
>   - **s_H5 = 0.022709785806829905** (2.271 pp)
>   - **s_H5b = 0.02560409470770698** (2.560 pp)
>
>   They are frozen at these values. They were reproduced while drafting this plan (§0.4 item 4).
> - **Null hypothesis and p-value.** H0: b = 0 in the Design B window. Under H0, T ~ N(0, 1).
>   p = 2·(1 − Φ(|T|)).
> - **Windows.** One confirmatory window, 2025-04-01 → 2026-08-31.
> - **Seed.** The primary test uses no random draws. The secondary RI tests use `SEED` (below).
> - **Decision rule (Holm over {H5, H5b}, family-wise α = 0.05).** Order the two p-values. If the
>   smaller is ≤ 0.025, reject its hypothesis, and then reject the other if its p-value is ≤ 0.05;
>   otherwise reject neither. Equivalent critical values for |b̂|: at the 0.025 step 2.2414·s =
>   **5.090 pp (H5), 5.739 pp (H5b)**; at the 0.05 step 1.9600·s = **4.451 pp (H5), 5.018 pp
>   (H5b)**. Rejection is two-sided; the sign is reported, not required.
> - **Interval.** 95% CI: b̂ ± 1.9600·s.
>
> *Rationale:* s is the empirical spread of the slope when the documented cross-industry correlation is
> present and there is no relation between this exposure vector and alphas, so a test scaled by s has
> close to nominal size under that correlation, which RI does not [§3.2]. It is also exactly the
> quantity behind the power analysis's MDEs (MDE = 3.0830·s = 7.00 pp for H5, 7.89 pp for H5b), so the
> test and the reported power describe the same procedure. The overlapping estimate (n = 378) is used
> rather than the non-overlapping one (n = 23) because it averages over start months; the
> non-overlapping sd ranges 1.78–2.82 pp across the 17 start offsets [power]. A normal approximation
> is used rather than the empirical tail quantile because 378 overlapping windows hold only about 22
> independent windows, and a 1.25% tail quantile would rest on about five of them. The test is centred
> at zero, the null of the hypothesis; s is the spread around the historical mean slope, whose level is
> not used (and has not been reported).
>
> *Secondary inference (reported beside the primary, never used for the decision):*
> 1. **RI as the spec names it, for H5:** permute `z_delegation` across industries, 10,000 permutations,
>    two-sided p = (1 + #{|b_perm| ≥ |b_obs|}) / 10,001 (`aideleg.power.ri_pvalues`,
>    `scheme="exposure"`).
> 2. **Freedman–Lane RI for H5b:** residuals of α̂ on [1, z_aioe] permuted, 10,000 permutations
>    (`scheme="freedman_lane"`). Permuting `z_delegation` with `z_aioe` held in place is also reported,
>    labelled as oversized even under exchangeability.
>
>    Draws: one `numpy.random.default_rng(SEED)` generator, consumed in the order H5 (exposure),
>    H5b (exposure), H5b (Freedman–Lane), as in `run_power`. Each secondary p-value is printed with the
>    size documented for its procedure in §3.2 (13.8%, 14.8%, 6.1% at nominal 0.025).
> 3. **Conventional OLS with HC3 standard errors**, for reference.
>
> *Alternatives (robustness R18, R19):* (a) s from non-overlapping windows, taking the largest of the 17
> start offsets (H5 2.82 pp, H5b 3.22 pp): the most conservative calibration; (b) s replaced by the
> root mean square of the 378 historical slopes around zero rather than their sd around their mean.
> This treats any persistent historical association between this exposure vector and alphas as noise,
> and is at least as conservative as the primary. (A cluster-robust or Driscoll–Kraay SE is not
> proposed: there is one cross-section of 49 time-aggregated alphas and no defensible cluster
> structure.)
> *Interpretive check (reported):* b̂ minus the mean historical slope, scaled by s. This asks whether
> the 2025–26 slope differs from what 1990–2022 history shows for the same exposure vector. It is not
> part of the decision rule.

If any decision in §2.1 changes the Design B `z_delegation` or `z_aioe` vector before the tag, the
power analysis is rerun at the new commit, and s, the critical values, §7 and §9.3 are regenerated
before signing.

### 3.4 What the Holm family covers

The family is {H5, H5b} only. Every other market analysis (robustness variants of §8, tercile
portfolios, Fama–MacBeth, event studies, Design A, H6) is outside it and carries no family-wise error
control. The spec allows Romano–Wolf or Holm across "pre-registered exposure variants"; this plan
assigns those variants to robustness (§8), reported in full, rather than to a second testing family.

---

## 4. RQ1 confirmatory family {H1, H2, H3, H4}

Holm correction across the four p-values at family-wise α = 0.05. The primary delegation measure is
`automation_pct` (D1). No H1–H4 relationship has been estimated before this plan.

### 4.0 One p-value per hypothesis

> **[PROPOSED — Ajai to confirm] D17. Hypotheses with two coefficients.**
> *Recommended:* H1 states two conjunctive claims (lower delegation for more education **and** in
> higher-wage occupations), so its family p-value is the intersection–union p-value
> p_H1 = max(p_educ, p_wage), each two-sided; H1 is supported only if Holm rejects at p_H1 and both
> coefficients are negative. H4 states that the delegation share "relates to" AUI and income, with no
> direction, so its p-value is the joint HC3 Wald test of both coefficients equal to zero.
> *Rationale:* both keep the family at four members as the spec defines it. The intersection–union
> test is valid at level α without a further correction, and it matches H1's conjunctive wording; the
> joint test matches H4's non-directional "relates to" and copes with the correlation between AUI and
> income.
> *Alternative:* splitting H1 into H1a (education) and H1b (wage) and H4 into H4a/H4b gives a
> six-member Holm family; these four p-values are reported as robustness (R25).

### 4.1 H1 (stakes / algorithm aversion)

> **[PROPOSED — Ajai to confirm] D13. RQ1 cross-sectional sample (H1, H3).**
> *Recommended:* release r6, source `claude_ai`, global geography, `onet_task` rows; each task's value
> is the usage-weighted mean of its April and May 2026 values (a month in which the value is unpublished
> is left out); weights are the mean of the two months' `pct` (unpublished = 0).
> *Rationale:* r6 is the only release with near-complete task × collaboration publication (99.71–99.96%
> of tasks publish all five patterns, against 3.70–9.10% in r3–r5) [SUP], so its task automation is the
> least affected by renormalising over partially published patterns, and the R7 bound width is
> 1.18–2.64 points rather than 10.54–18.18 [SUP]. `human_education_years_mean` is published at task
> level only in r4–r6.
> *Alternatives (R24):* r4 and r5 `claude_ai` separately, and r6 `1p_api`.

> **[PROPOSED — Ajai to confirm] D14. Task family fixed effects.**
> *Recommended:* task family = O\*NET Intermediate Work Activity (IWA), linked through the O\*NET 29.3
> "Tasks to DWAs" file (Task ID → DWA ID) and "DWA Reference" file (DWA ID → IWA ID). A task linked to
> several IWAs is split equally across them (rows duplicated, weights divided by their number). Tasks
> whose Task IDs have no DWA link (for example r2-era IDs reached only through the 2010→2019
> crosswalk) are dropped, and their usage share is reported.
> *Rationale:* the spec asks for "O\*NET task family fixed effects" (§5.2); the IWA is O\*NET's own
> grouping of similar work activities across occupations (about 330 categories), fine enough to compare
> like tasks and coarse enough to leave within-family variation in wage and education. r6 publishes
> the DWA/IWA/GWA hierarchy, so the grouping is native to AEI too.
> **These two files are not in `data/raw`.** They must be acquired, added to the MANIFEST and §9
> regenerated before the tag (D20). The linkage code is written in plan 2 and tested against this
> rule.
> *Alternatives (R26):* GWA (41 categories) fixed effects; DWA fixed effects.

| | H1 primary specification |
|---|---|
| Unit | (task statement, occupation) pair. A task's occupations are the union over its candidate Task IDs (ruling R6), as O\*NET-SOC 2019 `soc6` codes, mapped to OEWS codes with `oews_code_for`. Further split by IWA (D14). |
| Outcome | the task's `automation_pct` (D13), the same value on every row of the task. |
| Predictors | `human_education_years_mean` of the task (years, D13 averaging); log of the OEWS May 2024 national annual median wage (`a_median`) of the occupation. A top-coded median (`#`) is set to the top-code value printed in the OEWS May 2024 documentation; a suppressed median (`*`, `**`) drops the row. |
| Fixed effects | IWA (D14). |
| Weights | the task's weight (D13) ÷ (number of its occupations × number of its IWAs). Usage is conserved. |
| Missing values | a row missing the outcome, either predictor, the IWA or an OEWS code is dropped; weights are not renormalised; the dropped share of r6 task usage is reported by reason. `unmatched:*` nodes are never included. H3 applies the same rule to its own variables. |
| Estimator | WLS: automation = β_e·education + β_w·log wage + IWA FE + ε. |
| Inference | two-way cluster-robust SEs by occupation (`soc6`) and task statement (Cameron, Gelbach & Miller 2011), with the library's default small-sample correction. p_educ, p_wage two-sided; p_H1 = max (D17). |
| Decision | supported if Holm rejects at p_H1 and β_e < 0 and β_w < 0. Each coefficient is reported with its CI in pp of automation per year of education and per log point of wage. |
| Secondary | `ai_autonomy_mean` as outcome (R23). |
| Status | confirmatory. |

### 4.2 H2 (trust accumulation)

Specified in §5 (the definition-stable list) together with D2.

| | H2 primary specification |
|---|---|
| Unit | (task, release), `claude_ai`, global, `onet_task` rows; task identity = the panel's matched task node. |
| Releases | r2, r3, r4, r5 (D2). |
| Sample | tasks with a published `automation_pct` in all four releases (balanced). |
| Outcome | `automation_pct`. |
| Time | t_r = (midpoint of r's window − midpoint of r2's window) in days ÷ 365.25, with midpoint = `period_start` + (`period_end` − `period_start`)/2 from the panel. β is therefore in pp per year. |
| Estimator | WLS with task fixed effects: automation_tr = α_t + β·t_r + ε_tr. |
| Weights | fixed per task: the mean of its `pct` over the four releases, so weights do not move with release. |
| Inference | SEs clustered by task; two-sided p. |
| Decision | supported if Holm rejects and β > 0. β is reported as "the change in measured delegation within task", which includes any change in the unstated classifier and in platform scope (§5). |
| Also reported | the event-style plot: release fixed effects instead of the trend, r2 as base, with 95% CIs. |
| Status | confirmatory. |

### 4.3 H3 (calibrated checking)

> **[PROPOSED — Ajai to confirm] D15. H3 error-cost indicator.**
> *Recommended:* error_cost_o = 1 if the occupation's SOC 2018 code is in: major group 23 (Legal
> occupations); major group 29 (Healthcare practitioners and technical occupations); minor group 13-2000
> (Financial specialists); or 11-3031 (Financial managers) or 41-3031 (Securities, commodities and
> financial services sales agents). Otherwise 0.
> *Rationale:* H3 names the three domains ("regulated finance, health, legal"); a fixed SOC code list is
> transparent, needs no new data and matches the hypothesis's own wording.
> *Alternative (R27):* the continuous O\*NET 29.3 Work Context element "Consequence of Error"
> (occupation mean on the context scale), standardised; acquired after the freeze (§9.4).

| | H3 primary specification |
|---|---|
| Unit, sample, weights, FE | as H1 (D13, D14). |
| Outcome | the task's `validation_pct` (renormalised over the five classified patterns). |
| Predictor | error_cost_o (D15). |
| Estimator | WLS: validation = γ·error_cost + IWA FE + ε. |
| Inference | two-way clustered as H1; two-sided p. |
| Decision | supported if Holm rejects and γ > 0. γ is reported in pp of validation share. |
| Status | confirmatory. |

### 4.4 H4 (geography)

> **[PROPOSED — Ajai to confirm] D16. H4 specification.**
> *Recommended:*
> - **Sample.** r6 `claude_ai`, `geo_level = country`. Countries with a published overall
>   `automation_pct` and `usage_per_capita_index` in both months, and with 2024 GDP and working-age
>   population in the AEI r3 inputs. Each variable is the mean of the two months.
> - **Outcome.** The country's overall `automation_pct` (renormalised).
> - **Predictors.** log of the Anthropic Usage Index (`usage_per_capita_index`); log of 2024 GDP per
>   working-age (15–64) person (`aei_geo_gdp_country` ÷ `aei_geo_wap_country`).
> - **Task-mix control.** M_c = Σ_g s_cg · a_g, where s_cg is country c's `pct` over GWA nodes
>   (`onet` hierarchy level 3, renormalised over published GWAs) and a_g is the global r6 `claude_ai`
>   `automation_pct` of GWA g.
> - **Estimator.** OLS: automation_c = a + b₁·log AUI_c + b₂·log income_c + b₃·M_c + e_c, unweighted.
> - **Inference.** HC3; p_H4 = joint Wald test of b₁ = b₂ = 0 (D17).
> - **Decision.** Supported if Holm rejects; b₁ and b₂ are reported with CIs, two-sided.
> - **Also reported (descriptive).** The shift-share split of each country's gap from the global
>   delegation share into a task-mix part (M_c − global) and a within-task part, with maps.
>
> *Rationale:* r6 publishes all metrics at country × GWA level, which makes the mix adjustment
> possible on the latest and least suppressed release; finer country × task cells are mostly
> unpublished (mean 59.33 points short of 100) [audit §4], so a task-level mix would rest on a small
> published fraction. GDP and working-age population come from the AEI release inputs, which keeps the
> income measure consistent with AEI's own usage index.
> *Alternatives (R28):* US states (AUI and state GDP per working-age person); r5 and r4 country
> samples; weights = country `usage_pct`; IWA-level mix control where published.

---

## 5. H2 definition-stable metric list

> **[PROPOSED — Ajai to confirm] D2. Definition-stable metrics and series for H2.**
> *Recommended:*
> - **Definition-stable metrics.** Published at task level in r2–r6 under `collab_v2`, each renormalised
>   over the five classified patterns [MET]:
>   - `automation_pct` (**the H2 primary**);
>   - `augmentation_pct`;
>   - `directive_pct`, `feedback_loop_pct`, `task_iteration_pct`, `validation_pct`, `learning_pct`.
> - **Excluded.** `filtered_pct` (r2 only), `not_classified_pct` (r3–r5) and `none_pct` (r3–r6), whose
>   denominators differ by release. Release r1, which has no task-level collaboration [MET].
>   `ai_autonomy_mean` is definition-stable only over r4–r6, so it is a secondary series (R23), not
>   part of the primary.
> - **Primary series: r2–r5.** r6 is excluded from the definition-stable series. In r3–r5 only
>   3.70–9.10% of tasks publish all five patterns; in r6, 99.71–99.96% do [SUP]. Task automation in
>   r3–r5 is renormalised over partially published patterns, and the partial tasks' automation
>   differs from the complete tasks' by up to 9.3 points with a sign that varies by source [audit §4].
>   So a level shift at r6 would mix behaviour with the change in suppression regime. A regime dummy for
>   r6 would absorb r6 entirely under a linear trend, so it is equivalent to excluding r6, and exclusion
>   is the plainer statement.
> - **No platform-scope controls in the primary.** Max joins in r5 and Cowork in r6. With one source
>   and one scope per release, a release-level control is collinear with the time trend, so it cannot
>   be included. The primary β is therefore described as the change in **measured** delegation within
>   task, including any change in scope and in the classifier (unobservable: no release names it)
>   [audit §2, open risk 1].
> - **Balanced panel.** Tasks published in all four releases, so that the set of tasks does not change
>   with the suppression regime.
>
> *Rationale:* above. The spec asks for a "definition-stable" and an "all-releases" series, with the
> definition-stable one primary (§5.1, §5.2).
>
> *Note on H2's wording.* The approved text says "Dec 2024 → May 2026". The primary series spans the
> r2–r5 windows (late February 2025 → mid-February 2026). r1 (December 2024) has no task-level
> collaboration, and r6 (April–May 2026) is in the all-releases series.
>
> *Alternatives (R22):*
> - the all-releases series r2–r6, with and without an r6 indicator (the latter reported as
>   confounded with the regime change);
> - the unbalanced panel;
> - each of the other definition-stable metrics as outcome;
> - `1p_api` over r3–r5.

---

## 6. H6: talk vs use (exploratory)

> **[PROPOSED — Ajai to confirm] D18. H6 status and talk index.**
> *Recommended:* H6 stays **exploratory**, as the spec allows.
> - **Filings.** 10-Ks (form types `10-K`, `10-K405`, `10-KT`; amendments excluded) filed in calendar
>   years 2019–2025, from SEC EDGAR.
> - **Firm to industry.** Each filer's SIC from the EDGAR submissions API, mapped to FF49 by the
>   `Siccodes49` ranges; a SIC outside every range is unmapped and reported.
> - **Talk, primary.** For FF49 industry j and filing year y, the share of filers whose 10-K contains
>   at least one primary dictionary term (§6.1), firms equally weighted. Measured by EDGAR full-text
>   search at the filing level, all documents of the filing.
> - **Talk index for the gap.** T_j = talk in filings dated 2024-01-01 → 2024-12-31. These were all
>   public before Design B's formation date, 2025-03-27.
> - **Gap.** OLS across FF49 of z(T_j) on Design B `z_usage`. gap_j = the residual, standardised.
> - **"Diverges".** Spearman(T_j, z_usage) with a 95% industry-bootstrap CI (10,000 draws, `SEED`);
>   the ranking of gap_j; the talk series by year.
> - **Return association.** The §3.1 regression with gap_j in place of z_delegation, its inference
>   computed as in §3.3 (null sd recomputed for the gap vector on the same pre-seal windows). Reported
>   with nominal p-values; it is in no testing family.
> - **Secondary talk measure.** Dictionary occurrences (primary and acronym terms, §6.1) per 10,000
>   words of the primary 10-K document text, firm-level, then the industry mean.
>
> *Rationale:* the 10-K pipeline does not exist yet; promoting H6 to confirmatory before its measurement
> has been audited would fix a specification no one has seen work. Filing-level binary presence is what
> EDGAR full-text search returns directly, so it needs the fewest processing choices.
> *Alternatives (R29):* talk from 2025 filings dated before 2025-03-27; the change in talk from 2019 to
> 2024; filers weighted by market capitalisation where SEC data allow.

### 6.1 AI term dictionary (D12)

> **[PROPOSED — Ajai to confirm] D12. H6 AI-term dictionary.**
> *Recommended terms.*
>
> **Primary terms.** Phrases; case-insensitive; matched as whole words; a single space in a term
> matches any run of whitespace or a hyphen; the plural is the listed form plus "s".
> 1. artificial intelligence
> 2. machine learning
> 3. deep learning
> 4. neural network(s)
> 5. generative AI
> 6. generative artificial intelligence
> 7. large language model(s)
> 8. natural language processing
> 9. computer vision
> 10. reinforcement learning
> 11. foundation model(s)
> 12. ChatGPT
>
> **Acronym terms.** Used only in the secondary count measure; case-sensitive; whole-token match,
> bounded by a non-letter and non-digit on each side:
> - `AI`, `A.I.`, `GenAI`, `LLM`, `LLMs`.
> - They count only in a filing that also contains "artificial intelligence" or "generative AI" at
>   least once. This excludes filings where "AI" abbreviates something else, such as avian influenza
>   in food producers' filings.
>
> **Matching rules.**
> - Text is Unicode-NFKC-normalised.
> - HTML tags are stripped before matching (secondary measure).
> - Overlapping matches count once, at the longest match: "generative artificial intelligence" counts
>   once, not also as "artificial intelligence".
> - No stemming beyond the listed plurals. No other terms.
>
> *Rationale:* the primary list is the core vocabulary of AI technology, written so that each phrase
> almost never has a non-AI meaning in a 10-K. Bare acronyms do have other meanings, so they are kept
> out of the binary full-text-search measure, which cannot match case-sensitively. Product and company
> names other than "ChatGPT" are left out: they date-stamp the index to particular launches, and
> several (for example "Copilot", "Gemini", "Claude") have common non-AI meanings.
> *Alternatives (R30):*
> - the primary list without items 9–11 (computer vision, reinforcement learning, foundation models),
>   which are narrower technical terms;
> - adding "automation" and "robotics", which measure a broader construct than AI talk.

---

## 7. Power results and the plausibility rule

From the power analysis [power], at α = 0.025 (Holm's first step) and power 0.80, MDE = 3.0830 × the
null sd of the slope. Units: pp of annualised alpha per 1 SD of exposure.

| | overlapping windows (n = 378) | non-overlapping windows (n = 23) |
|---|---|---|
| H5: null sd / MDE | 2.27 / **7.00** | 2.63 / **8.10** |
| H5b: null sd / MDE | 2.56 / **7.89** | 2.83 / **8.74** |

- Non-overlapping sd across the 17 start offsets: H5 1.78–2.82 pp (MDE 5.5–8.7), H5b 2.17–3.22 pp.
- Collinearity: Pearson(`z_aioe`, `z_delegation`) = 0.671, VIF 1.82.
- The MDEs describe the D10 test exactly: its scale is the same s.

> **[PROPOSED — Ajai to confirm] D11. The plausibility rule.**
> *Rule as pre-registered (spec §5.4; the threshold is Ajai's call):* if the H5 MDE exceeds **5
> percentage points of annualised alpha per 1 SD of exposure**, RQ3 is reported as "what the market
> evidence can and cannot yet say", and the paper is led by RQ1–RQ2.
> *What the rule gives now:* the H5 MDE is 7.00 pp (overlapping) or 8.10 pp (non-overlapping). H5b's
> is 7.89 or 8.74 pp. Every one exceeds 5 pp. **Under the rule as written, RQ3 is reported as "what
> the market evidence can and cannot yet say", and the paper is led by RQ1–RQ2.**
>
> The Design B test (§3) is still run and reported in full, with its MDE beside it, as the spec
> requires. A non-rejection is described as "no effect larger than about 7 pp per SD is supported";
> it is not described as "no effect".
> *For Ajai to confirm or change before signing:* the 5 pp threshold itself. The rule is evaluated on
> the overlapping H5 MDE (7.00 pp). Any threshold below 7.00 pp gives the same outcome; a threshold above
> 7.00 pp would flip it.

---

## 8. Robustness (spec §5.6, plus the audit's forced items)

### 8.1 Reporting rules

- Every variant below is run and reported in an appendix table, whatever its result.
- A variant never changes a confirmatory decision.
- Results are not summarised by counting how many variants are significant.
- Market variants use the §3.3 inference with s recomputed, for the variant's exposure vector or
  sample, by the same pre-seal procedure.
- RQ1 variants use the inference of the hypothesis they vary.

### 8.2 The list

| ID | Variant | Applies to | Source |
|---|---|---|---|
| R1 | OEWS May 2025 employment weights (`oesm25in4`; national shares from its cross-industry rows, or `oesm25nat` acquired after the freeze if absent) | H5, H5b, RQ2 | spec §5.6 |
| R2 | wage-bill weights (OEWS employment × mean wage) in place of employment weights | H5, H5b, RQ2 | spec §5.6 |
| R3 | `unmatched="drop"` | H5, H5b, RQ2 | D3 |
| R4 | `1p_api` instead of `claude_ai` (r3 onward; Design B has no API source) | H1–H3, A_pooled | spec §5.6 |
| R5 | equal-weighted FF49 returns in place of value-weighted | H5, H5b | spec §5.6 |
| R6 | FF30 and FF48 industry granularity (Siccodes and return files acquired after the freeze) | H5, H5b | spec §5.6 |
| R7 | drop technology industries {Hardw, Softw, Chips} | H5, H5b | spec §5.6 |
| R8 | exclude calendar 2023 (the 2023 AI large-cap rally months) | Design A only (Design B starts 2025-04) | spec §5.6 |
| R9 | placebo event dates: the same month-day as each §8.3 event in 2017, 2018, 2019 and 2021 | event studies | spec §5.6 |
| R10 | R7 bounds `_lb` / `_ub` in place of `automation_pct` | H1, H3, H5, H5b | D1 |
| R11 | employment-weighted task allocation | H5, H5b, RQ2 | D4 |
| R12 | standardised-rank exposure | H5, H5b | D5 |
| R13 | drop Softw | H5, H5b | D5 |
| R14 | AIOE through the BLS SOC 2010→2018 crosswalk | H5b, RQ2 | D6 |
| R15 | NAICS 5511 redistributed (`hq="redistribute"`) | H5, H5b, RQ2 | D7 |
| R16 | r6 task-allocated occupation basis | A_pooled, r6 descriptives | D9 |
| R17 | Eloundou GPT-4 β as headline | RQ2 | D8 |
| R18 | null sd from non-overlapping windows, largest of the 17 offsets | H5, H5b | D10 |
| R19 | null scale = RMS of the historical slopes around zero | H5, H5b | D10 |
| R20 | crosswalk `majority` mode instead of `split` | H5, H5b, RQ2 | Task 10 ruling |
| R21 | `z_usage` and `z_augmentation` in place of `z_delegation` | H5, H5b | spec §5.4.1 |
| R22 | H2 all-releases series, unbalanced panel, other definition-stable metrics, `1p_api` | H2 | D2 |
| R23 | `ai_autonomy_mean` as delegation measure (r4–r6) | H1, H2 | spec §5.4.1 |
| R24 | r4, r5 `claude_ai`; r6 `1p_api` | H1, H3 | D13 |
| R25 | H1 and H4 coefficients tested separately (six-member Holm family) | H1, H4 | D17 |
| R26 | GWA and DWA fixed effects | H1, H3 | D14 |
| R27 | O\*NET "Consequence of Error" (continuous) | H3 | D15 |
| R28 | US states; r4, r5 countries; usage-weighted; IWA-level mix | H4 | D16 |
| R29 | 2025 pre-formation filings; change 2019→2024; cap-weighted filers | H6 | D18 |
| R30 | narrower and broader dictionaries | H6 | D12 |

### 8.3 Exploratory market analyses (labelled exploratory wherever they appear)

> **[PROPOSED — Ajai to confirm] D19. Exploratory market parameters.**
> *Recommended:*
> - **Design A exposure.** A_r2 (formed from the earliest task-level release) and A_pooled. Returns
>   from 2022-12-01 → 2026-08-31.
> - **Event studies.** Day 0 is the announcement date; if that date is not a trading day, day 0 is the
>   next trading day.
>   - Abnormal return = industry excess return minus its FF5+UMD fit, estimated over trading days
>     [−250, −21].
>   - CARs over [0, +5] and [0, +20], and [0, +9] for the Eisfeldt, Schubert & Zhang (2023)
>     comparison.
>   - Each industry CAR is regressed on exposure across industries.
> - **Event dates** (public announcement dates, to be checked against the primary announcements
>   before the tag):
>   - ChatGPT, 2022-11-30;
>   - GPT-4, 2023-03-14;
>   - Claude 3, 2024-03-04;
>   - GPT-4o, 2024-05-13;
>   - DeepSeek-R1, 2025-01-20.
>
>   Only model-release dates are used, never dates chosen from market reactions.
> - **Tercile portfolios.** FF49 sorted on exposure: top 16 minus bottom 16, value-weighted by prior
>   month-end industry market capitalisation (average firm size × number of firms, from the frozen
>   `ff49_monthly` file), rebalanced never (static exposure), monthly.
>   - Alphas vs CAPM, FF3 and FF5+UMD.
>   - Newey–West SEs with lag floor(4·(T/100)^(2/9)).
>   - Sharpe with PSR.
>   - Stationary-bootstrap CIs, mean block length 3 months, 10,000 draws, `SEED`.
>   - Cost sensitivity at 0/5/15/30 bps one-way on formation turnover.
>   - DSR across the variants tested.
>
>   Run for Design B (secondary) and for Design A (exploratory).
> - **Fama–MacBeth.** Monthly industry returns on exposure plus log size, log BE/ME (from the frozen
>   `ff49_monthly` file) and 12-2-month momentum; Newey–West SEs.
> - **Eisfeldt et al. replication.** The sign of the CAR–`z_aioe` slope over [0, +9] around
>   2022-11-30, before `z_delegation` is added.
>
> *Rationale:* fixing these now removes the main degrees of freedom left in exploratory work: windows,
> dates and portfolio rules.
> *Alternatives:* none pre-registered. Further exploratory analyses may be added later only as labelled
> additions in the deviations log (§10).

---

## 9. Data freeze

### 9.1 Raw data: `data/raw/MANIFEST.json`

Generated from `data/raw/MANIFEST.json` by script, not typed. SHA-256 of `MANIFEST.json` itself:
`a2b0cdd48d5844e692e9c763aef06987ad9fa04147820b23050b055bf9d4ebb7`. 47 keys.

<!-- BEGIN GENERATED: MANIFEST table -->
| key | dest (under `data/raw/`) | bytes | retrieved (UTC) | SHA-256 |
|---|---|---|---|---|
| `aei_geo_gdp_country` | `aei/r3/gdp_2024_country.csv` | 4115 | 2026-10-21T21:13:17Z | `e0618d6ba634a612b97b1c82f521ab38a387216069818a86f50c9aaf8e2bda6c` |
| `aei_geo_gdp_us_state` | `aei/r3/gdp_2024_us_state.csv` | 2179 | 2026-10-21T21:13:18Z | `cb1573e8143bd407c2ea7c43f5a6822852568c596dbde843fc5d8692c9e967ec` |
| `aei_geo_iso` | `aei/r3/iso_country_codes.csv` | 4564 | 2026-10-21T21:13:18Z | `eee318d4ab2c2c30f5a7da11f2bc7e0e36c246f6be5bb9b323fdb12b8e4809e0` |
| `aei_geo_wap_country` | `aei/r3/working_age_pop_2024_country.csv` | 6321 | 2026-10-21T21:13:17Z | `3a9e0edc0453702e8efb63d7cab57e5b1a689bc09e070626bbf513e37edd5dd3` |
| `aei_geo_wap_us_state` | `aei/r3/working_age_pop_2024_us_state.csv` | 1079 | 2026-10-21T21:13:17Z | `e2d0fb7239934f4f6d0ae3444ab12ad8ff1dd323b71ccfc4295d074b537f17ec` |
| `aei_job_exposure` | `aei/labor_market_impacts/job_exposure.csv` | 37176 | 2026-10-21T21:13:16Z | `4f0a3adf5feeb2ec5f5d02ab18cc5e851a2a4b8470bde84c0c9335017be12d68` |
| `aei_onet_tasks` | `aei/r2/onet_task_statements.csv` | 3592256 | 2026-10-21T21:12:42Z | `82e4c418dc08475ef1263ad1e8c66ffa3357291370cd35ee1065ecea590597ec` |
| `aei_r1_collab` | `aei/r1/automation_vs_augmentation.csv` | 197 | 2026-10-21T21:12:41Z | `d1e264882b17618db4f4a00b6f87f48134222bc5c15eefb3d46aae9519e89d11` |
| `aei_r1_task_pct` | `aei/r1/onet_task_mappings.csv` | 461306 | 2026-10-21T21:12:41Z | `8de89c99f762146c9e46b2202c3501e2a14f11c5b44c61c8007021127b6c676e` |
| `aei_r1_wage` | `aei/r1/wage_data.csv` | 128047 | 2026-10-21T21:12:41Z | `4453fc56402c94306e4749ad62b6f7c313f63d884ca99bab767a52e7d627b15f` |
| `aei_r2_collab_by_task` | `aei/r2/automation_vs_augmentation_by_task.csv` | 561368 | 2026-10-21T21:12:42Z | `f6570714a9af31ae783fd91bd7ee3b2e9cfabcbf522a30ba1aa9b1f230665e79` |
| `aei_r2_task_pct` | `aei/r2/task_pct_v2.csv` | 435372 | 2026-10-21T21:12:42Z | `0c20f184cd4a1e3d8ef3d77f500b32b62431ce61a3c2f133c3af7fa8429f97db` |
| `aei_r2_thinking` | `aei/r2/task_thinking_fractions.csv` | 372332 | 2026-10-21T21:12:42Z | `35a78bc803b610e4dcc654391e87e33e124021115fce2ffa4b6488230e2be357` |
| `aei_r3_api` | `aei/r3/aei_raw_1p_api_2025-08-04_to_2025-08-11.csv` | 7027019 | 2026-10-21T21:12:44Z | `c0fc061ea7d4feb71a7bd88c528d54e2d3a11e2045574f1e1fb2d594eebffd0f` |
| `aei_r3_claude_ai` | `aei/r3/aei_raw_claude_ai_2025-08-04_to_2025-08-11.csv` | 18894517 | 2026-10-21T21:12:43Z | `c8ef9c5eee0c42febc73e358ecc7d2358e0a0ce3b50122c0c15ae8ec569aceff` |
| `aei_r3_docs` | `aei/r3/data_documentation.md` | 20133 | 2026-10-21T21:12:44Z | `d7e23aa0888628fdeb27f49a14e151c41ea99d47bd5dd65e84383b203c23464a` |
| `aei_r4_api` | `aei/r4/aei_raw_1p_api_2025-11-13_to_2025-11-20.csv` | 41518256 | 2026-10-21T21:12:52Z | `432f8d14348ba384dd9c659fa7fdc85754cbae3b5a480c14a344ac4823d0e861` |
| `aei_r4_claude_ai` | `aei/r4/aei_raw_claude_ai_2025-11-13_to_2025-11-20.csv` | 94086309 | 2026-10-21T21:12:49Z | `70dc16780061b84d3f34ddf7fe5c978d65c99a5ef58afd78f9315f886a6a5873` |
| `aei_r4_docs` | `aei/r4/data_documentation.md` | 18721 | 2026-10-21T21:12:52Z | `50f117f8f995606004680749fc43012d2bd83c5fc9dab6044a935f601643ef6f` |
| `aei_r5_api` | `aei/r5/aei_raw_1p_api_2026-02-05_to_2026-02-12.csv` | 43957174 | 2026-10-21T21:13:00Z | `b3bcd68e7f6d820ffbb50a3c53d71ec2a122556fc2a38226cd86951a054bd4c8` |
| `aei_r5_claude_ai` | `aei/r5/aei_raw_claude_ai_2026-02-05_to_2026-02-12.csv` | 103287181 | 2026-10-21T21:12:58Z | `69ebf6f9afc1e3be45caab172a84ae09e78bf41b97e1c310100d81c8a35a7433` |
| `aei_r5_docs` | `aei/r5/data_documentation.md` | 17739 | 2026-10-21T21:13:01Z | `0a194ff1e317567e8b5d68d581fa2e5f8a1d3112f71aa209d2caa408ee12a779` |
| `aei_r6_api` | `aei/r6/aei_1p_api_2026-06-26.csv` | 77282477 | 2026-10-21T21:13:16Z | `62197f003e001945ad130c2f26f5e07f3fda45ff41644df91444b04fd524a19f` |
| `aei_r6_claude_ai` | `aei/r6/aei_claude_ai_2026-06-26.csv` | 219174671 | 2026-10-21T21:13:12Z | `f974b358bce0e5a8417510c61da4342234cd0de9d9d0b62acf4c6dbcf8ec7b68` |
| `aei_r6_docs` | `aei/r6/data_documentation.md` | 7397 | 2026-10-21T21:13:16Z | `1a01eeb7d34250b192aa9c906098bea1db971644e6bdb04497d87b7a4ed141a5` |
| `aei_soc_structure` | `aei/r1/SOC_Structure.csv` | 77176 | 2026-10-21T21:12:41Z | `05eb5e689fb471b7a66962b57bba6666dee2c3e6a6854f0f84faf423af68dd17` |
| `aioe` | `benchmarks/AIOE_DataAppendix.xlsx` | 170359 | 2026-10-21T21:13:24Z | `c123b4c64840aff3568ae6c97256678719b88a74d45b6362dbefb5af34667b95` |
| `census_naics02_07` | `census/2002_to_2007_NAICS.xls` | 161280 | 2026-10-21T21:13:24Z | `a4b00b2195e318420962ba52b77f3c3122e83d893a9f804e820c151847ec85b1` |
| `census_naics07_12` | `census/2007_to_2012_NAICS.xls` | 171520 | 2026-10-21T21:13:25Z | `302b8abcd78881f1ea5aa4c6c9104811bf8fa10d57b48d492939de5cacc8cfc5` |
| `census_naics12_17` | `census/2012_to_2017_NAICS.xlsx` | 58543 | 2026-10-21T21:13:25Z | `17f463f7e8385df1cc762fadf0dd5c25910aa27034ca96275a906608399188f5` |
| `census_naics17_22` | `census/2017_to_2022_NAICS.xlsx` | 59656 | 2026-10-21T21:13:25Z | `4662cc7ed9e7f3fb8a968e9504a7d06e448f5b65a349996a5627439df193eb30` |
| `census_naics97_02` | `census/1997_NAICS_to_2002_NAICS.xls` | 1282560 | 2026-10-21T21:13:24Z | `c9940c1236a033026acc2c05f0bd75e6ae6d8b716ac6e3f8d3453488d1e74a10` |
| `census_sic87_naics97` | `census/1987_SIC_to_1997_NAICS.xls` | 367616 | 2026-10-21T21:13:24Z | `ba04e2332bbe5d56eec834908f7d0e253b377b59d906dbc3053088a0aa09701d` |
| `eloundou_occ` | `benchmarks/occ_level.csv` | 126022 | 2026-10-21T21:13:24Z | `40c74f53de40aec91c0017d80690cbba915f83a8bb414bcf2f884692f1749acb` |
| `ff49_daily` | `french/49_Industry_Portfolios_daily_CSV.zip` | 4173817 | 2026-10-21T21:13:23Z | `8f394fe34bea54d41b9aafed410425ee8f8e252ede3c71a7c1cd20bab83040de` |
| `ff49_monthly` | `french/49_Industry_Portfolios_CSV.zip` | 489433 | 2026-10-21T21:13:23Z | `16b3f20bf5bd1db8f5cd7a1b29f5cab1350eb0d5106c5309f77a6629590b1c0e` |
| `ff5_daily` | `french/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip` | 150292 | 2026-10-21T21:13:23Z | `7881223b51929ee0d6d23b8a28524aaec478a2c3d4eeca47224955cc845c5186` |
| `ff5_monthly` | `french/F-F_Research_Data_5_Factors_2x3_CSV.zip` | 11964 | 2026-10-21T21:13:23Z | `36756c5c2559648519ac4b22913d860c6afd865cfebce920e3e8927f8e2d10b7` |
| `ff_siccodes49` | `french/Siccodes49.zip` | 9587 | 2026-10-21T21:13:24Z | `36761b4009107e11cd15cff0eb75f8837ef49f024524b7378634629bf90905d5` |
| `mom_daily` | `french/F-F_Momentum_Factor_daily_CSV.zip` | 85269 | 2026-10-21T21:13:23Z | `ecf82b116e6ec56d2b79a2f27bd1d1598c217b5c6c25caa55b945bdd8a2c0b78` |
| `mom_monthly` | `french/F-F_Momentum_Factor_CSV.zip` | 5600 | 2026-10-21T21:13:24Z | `c06d1c2e9a5e4f6985879722f23c6bb585f46b34eaf3fcb681d4de887e353f3e` |
| `oews_2024_ind` | `bls/oesm24in4.zip` | 32425931 | 2026-10-21T21:13:20Z | `0d76287e92de226c0a142873e41f6fe84191e588f0c562d685e12e63ad3f4f72` |
| `oews_2024_nat` | `bls/oesm24nat.zip` | 282052 | 2026-10-21T21:13:18Z | `5fa368aa034ca784f0a4f67f0f1bac67072c5a07992ac3e3de92db10a2821043` |
| `oews_2025_ind` | `bls/oesm25in4.zip` | 31514940 | 2026-10-21T21:13:22Z | `3ef0e42fab1b42a7dac8a3a9b3e7024f5d7a07eff308bff5fc91808061ec08e1` |
| `onet_2010_2019_crosswalk` | `onet/2010_to_2019_Crosswalk.csv` | 108052 | 2026-10-21T21:54:31Z | `8f026a33134bfde5770308d1c6117cf70d9dd41c2b3467e6dd271d65bdeecc5a` |
| `onet_29_3_tasks` | `onet/db_29_3_task_statements.txt` | 2759559 | 2026-10-21T21:54:30Z | `fecdcda81a4b8a28e750a6c75ed8bf2d0a9b71186e5be37eec8dc6cef7985d1a` |
| `sec_tickers` | `sec/company_tickers_exchange.json` | 523851 | 2026-10-21T21:13:25Z | `6c29e2e3db973d4479875164603c2434f81ad22e14c9f1694999aca9cca246cb` |
<!-- END GENERATED -->

The market-data end date is frozen at **2026-08-31**: the last date of the frozen French daily files.
French revises its files retroactively; only the frozen files above are used. A later AEI release can
appear only in a clearly marked appendix (spec §5.4.1).

### 9.2 Code

- Code commit the plan refers to: **`81cfae2af7d97eac277f6208647a389b9fde6d5d`** ("fix(power): size of
  the specified RI test on pre-seal windows; caveat (3) rewritten").
- The exposure, benchmark and power modules at this commit define every constructed input of the
  confirmatory tests.
- Plan 2 and plan 3 code implements this plan; it does not change these modules' outputs for the
  primary specifications. A change that would is a deviation (§10).
- Environment: Python 3.12 via `uv` (lockfile at that commit), Polars 2.0.0.

### 9.3 Confirmatory inputs (hashes of derived data at the commit in §9.2)

| Object | SHA-256 |
|---|---|
| `data/derived/aei_panel.parquet` | `15ba38ec8b65c7311cace1823f713126cd3fccafca376cd6e63769c92ddbb370` |
| `data/derived/exposure_ff49.parquet` | `8d403a702b6a1007b426b510156f6c24e5e7c928e3036bacf247b45973a00c40` |
| `data/derived/benchmark_ff49.parquet` | `032003801622938c3e7e48d35969ec980cdc0dc02b5279c0874e98f39a289b1f` |
| Design B vector `(ff49, ff49_short, z_delegation, z_aioe)`, 49 rows, no nulls, CSV with 10-digit floats (command below) | `bddc49d49b9565bba8daa8bc6fdb709043a6007090b9e7faf7dda1001229ac36` |

The parquet hashes are informational (parquet bytes can differ across library versions). The binding
check is the vector hash:

```
uv run python -c "import hashlib; from aideleg.power import load_exposure; \
df = load_exposure().select('ff49','ff49_short','z_delegation','z_aioe'); \
print(hashlib.sha256(df.write_csv(float_precision=10).encode()).hexdigest())"
```

The frozen null scales of §3.3 (s_H5, s_H5b) are part of the confirmatory inputs.

### 9.4 Data still to be acquired

> **[PROPOSED — Ajai to confirm] D20. Data acquired before and after the freeze.**
> *Recommended:*
> - **Before the tag (blocking).** The O\*NET 29.3 "Tasks to DWAs" and "DWA Reference" files (D14),
>   from the O\*NET 29.3 text database on onetcenter.org (exact URLs verified at download), added to
>   `aideleg.acquire.sources`. §9.1 is then regenerated. H1 and H3 are confirmatory and cannot
>   depend on data acquired after the freeze.
> - **After the freeze, pre-specified here, used only in robustness or exploratory work:**
>   - the BLS SOC 2010→2018 crosswalk (R14);
>   - O\*NET 29.3 Work Context (R27);
>   - OEWS May 2025 national (R1, if needed);
>   - Ken French Siccodes30/48 and the 30- and 48-industry daily return files (R6);
>   - the SEC EDGAR submissions API and full-text search results, and 10-K documents (H6).
>
>   Each is recorded in the MANIFEST when acquired, and its SHA-256 is logged in §10 as an addition.
>   An addition is not a deviation.
>
> *Rationale:* every confirmatory input must be frozen before any post-seal return is read. Robustness
> and exploratory inputs can come later because their use is fixed here.
> *Alternative:* acquire everything before the tag. This is safer for the record, but it delays the
> freeze and adds nothing to the confirmatory tests.

---

## 10. Deviations

*None at freeze.*

Any change after `pap-v1` to a hypothesis, specification, sample, inference, decision rule or frozen input
is recorded here with its date, the reason, Ajai's approval, and whether results had been seen at the
time.
