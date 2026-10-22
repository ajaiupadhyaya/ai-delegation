# Pre-analysis plan: *Delegating to the Machine*

**Status: SIGNED and FROZEN on 2026-10-21 (revision 1).** The plan was signed in §0.1, and the annotated
git tag `pap-v1` marks the frozen state. Ajai accepted all 23 recommendations, so every
**[PROPOSED — Ajai to confirm]** block below is a decision, adopted as recommended. Any change from here
on is a deviation and goes in §11.

- Draft date: 2026-10-21. Revision 1: 2026-10-21. Branch `plan-1-foundations`.
- Code the plan binds to, and the git blob of the confirmatory script `src/aideleg/confirm_h5.py`:
  the generated block in §9.2 (regenerated at signing, never typed).
- Design: [`docs/superpowers/specs/2026-10-21-ai-delegation-design.md`](../superpowers/specs/2026-10-21-ai-delegation-design.md) ("the spec"). Where this plan corrects or departs from the spec, §10 says so.
- Evidence the decisions rest on: [`docs/audit/data-audit.md`](../audit/data-audit.md) ("the audit", with
  its tables in `docs/audit/tables/`), [`docs/pap/power.md`](power.md) ("the power analysis") and
  [`docs/pap/facts.md`](facts.md) ("the facts file": release dates, top-code, event dates, with sources).

AEI data are conversations matched to O\*NET tasks. Throughout this plan, an occupation's or an
industry's AEI value describes conversations matched to that occupation's tasks (or to the tasks of the
occupations an industry employs). Nothing in this plan, and nothing estimated under it, is a statement
about job risk, displacement or reassurance about the labour market.

---

## Decisions for Ajai

Read this first. These are the 23 **[PROPOSED — Ajai to confirm]** decisions. Each line gives the
recommendation, then the alternative. The full block is in the section named. At signing, the
recommendation is adopted unless Ajai writes a different choice into the block.

1. **D1 Primary delegation measure** (§2.1). Recommended: renormalised `automation_pct` everywhere. Alternative: the R7 suppression bounds `_lb`/`_ub` (kept as robustness R10).
2. **D2 H2 series** (§5). Recommended: r2–r5 `claude_ai`, balanced panel, linear trend, r6 excluded (suppression-regime change). Alternative: all releases r2–r6 as primary (R22).
3. **D3 Occupations with no AEI match** (§2.1). Recommended: assign zero usage, stated as an assumption (12.14% of employment, Design B). Alternative: drop them (R3).
4. **D4 Task-to-occupation allocation** (§2.1). Recommended: equal split. Alternative: employment-weighted split (R11).
5. **D5 Skewed exposure** (§2.1). Recommended: keep `z_delegation` primary; ranks (R12) and drop-Softw (R13) are reported co-primary, and R13 is a co-condition of the H5/H5b claim (D10). Alternative: ranks as primary (power rerun before the tag).
6. **D6 AIOE vintage crosswalk** (§2.1). Recommended: the O\*NET-detail union as built. Alternative: the BLS SOC 2010→2018 crosswalk (R14; primary would mean acquiring it and rerunning power before the tag).
7. **D7 NAICS 5511** (§2.1). Recommended: excluded. Alternative: redistributed pro rata (R15).
8. **D8 Eloundou rating** (§2.1). Recommended: human β headline, GPT-4 β beside it. Alternative: GPT-4 β headline (R17).
9. **D9 r6 occupation basis** (§2.1). Recommended: AEI's published SOC rows. Alternative: task-allocated basis (R16).
10. **D10 H5/H5b inference** (§3.3). Recommended: T = (b̂ − b₀)/s with s the historical pre-seal slope sd; critical max(t₂₁, empirical quantile), which equals t₂₁ with the frozen values; Holm over {H5, H5b}; the claim also needs the drop-Softw variant to reject. Alternative: the spec's randomisation inference as primary (documented size 13.8% at nominal 2.5%).
11. **D11 Plausibility threshold** (§7). Recommended: keep 5 pp per SD, so the rule fires (primary MDE 7.43 pp) and the paper is led by RQ1–RQ2. Alternative: any threshold above 7.43 pp, which would not fire.
12. **D12 H6 dictionary** (§6.1). Recommended: the 12 phrases and the acronym rules listed. Alternative: narrower or broader lists (R30).
13. **D13 RQ1 sample for H1/H3** (§4.1). Recommended: r6 `claude_ai`, April and May averaged. Alternative: r4 or r5 `claude_ai`, or r6 `1p_api` (R24).
14. **D14 Task family** (§4.1). Recommended: O\*NET IWA through the 29.3 DWA files (now acquired). Alternative: GWA or DWA fixed effects (R26).
15. **D15 H3 error-cost indicator** (§4.3). Recommended: the SOC code list (legal, health practitioners, regulated finance). Alternative: O\*NET "Consequence of Error" (R27).
16. **D16 H4 specification** (§4.4). Recommended: r6 country cross-section on log AUI, log GDP per working-age person and a GWA task-mix control. Alternative: US states, other releases, other weights (R28).
17. **D17 One p-value per hypothesis** (§4.0). Recommended: H1 intersection–union p, H4 joint Wald. Alternative: split H1 and H4 into separate coefficients (R25).
18. **D18 H6** (§6). Recommended: exploratory; talk = industry share of 2024 10-K filers with a primary term, by EDGAR full-text search, denominator from the EDGAR full index. Alternative: the primary measure computed on downloaded 10-K text; or promote H6 to confirmatory.
19. **D19 Exploratory market parameters** (§8.3). Recommended: the objective event rule (14 dates), the event windows, and terciles with monthly cap reweighting. Alternative: buy-and-hold terciles; a different named event source.
20. **D20 Data after the freeze** (§9.4). Recommended: the listed robustness-only inputs are acquired after the tag, pre-specified here. Alternative: acquire them all before the tag.
21. **D21 H5/H5b confirmatory null** (§3.3). Recommended: H0: b = b̄, meaning no departure from the frozen 1990–2022 pattern for this exposure vector (`PRIMARY_NULL = "bbar"`); b = 0 is reported as secondary. **This is a narrower claim than the approved H5 wording, so it needs your explicit approval.** Alternative: H0: b = 0 as approved, which rejects 7.1% (H5) and 3.2% (H5b) of historical windows at nominal 2.5%. It needs a one-line script change, after which the blob hash is re-recorded. **What each null rejects** (Holm's first step, c = 2.4138, frozen s and b̄): under b̄, H5 rejects iff b̂ > 7.13 or b̂ < −3.83 pp, and H5b iff b̂ > 7.40 or b̂ < −4.96 pp; under b = 0, iff |b̂| > 5.48 pp (H5) or 6.18 pp (H5b). The b̄ null makes a positive finding harder to reach and a negative one easier.
22. **D22 H2 inference and family** (§4.2). Recommended: remove H2 from the RQ1 Holm family, reword it as "measured within-task automation rises", require a release-level wild bootstrap as a co-condition, and **split RQ1's α = 0.05**: H2 at α = 0.0125, and {H1, H3, H4} by Holm at family-wise 0.0375, so the RQ1 family-wise error stays ≤ 0.05. Alternatives: H2 on its own at a separate 0.05 beside the {H1, H3, H4} Holm at 0.05, which raises the RQ1 family-wise error to about 0.10; or keep H2 in the {H1–H4} family with task-clustered SEs, as approved.
23. **D23 NAICS → SIC → FF49 crosswalk** (§2.1). Recommended: equal split as built, disclosed as a departure from the spec's "employment-weighted" crosswalk. Alternative: the employment-weighted crosswalk from OEWS `nat5d_6d` as primary (R33 otherwise), which needs the power analysis rerun before the tag.

---

## 0. Status, conventions, decision register, disclosures, protocols

### 0.1 Signature

Signed: Ajai Upadhyaya, 2026-10-21.

Ajai's statement at signing: "I accept all 23 recommendations in the pre-analysis plan, including D21
(the b = b̄ null) and D22 (the α split). Sign it, freeze it and tag pap-v1."

Adopted as recommended: D1–D23. That includes D11 (the 5 pp plausibility threshold, which fires), D21
(the H5/H5b confirmatory null is H0: b = b̄, with b = 0 secondary; Ajai explicitly approved this narrower
claim than the original H5 wording) and D22 (H2 leaves the RQ1 Holm family; α is split, with H2 at 0.0125
and {H1, H3, H4} by Holm at 0.0375).

### 0.2 Conventions

- **Confirmatory** means: the specification, sample, inference and decision rule are fixed here; the
  result is reported whatever it is, with the same prominence for a null as for a rejection (spec §2).
  **Secondary** means a pre-specified alternative inference for a confirmatory estimate.
  **Robustness** means a pre-specified variant (§8), always reported in full. **Exploratory** means
  pre-specified where stated, but no claim of error-rate control, and labelled "exploratory" wherever it
  appears.
- Every estimate is reported with its point value, a confidence interval and its p-value. Stars are
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

Each decision is set out in a **[PROPOSED — Ajai to confirm]** block in the section named. Each block
gives the recommended choice, its rationale, and the alternatives; every alternative becomes a
pre-registered robustness check (§8) unless the block says otherwise.

| ID | Decision | Recommended | Section |
|---|---|---|---|
| D1 | Primary delegation measure | renormalised `automation_pct`; R7 bounds as robustness | §2.1 |
| D2 | H2 definition-stable metrics and series | `automation_pct`, r2–r5 `claude_ai`, balanced panel, linear trend | §5 |
| D3 | Occupations with no AEI match | zero usage (assumption); `drop` as robustness | §2.1 |
| D4 | Task-to-occupation allocation | equal split; employment-weighted split as robustness | §2.1 |
| D5 | Rank-based robustness for the skew | standardised ranks (R12), drop Softw (R13), both co-primary in reporting | §2.1 |
| D6 | AIOE vintage crosswalk | O\*NET-detail union (as built); BLS SOC 2010→2018 as robustness | §2.1 |
| D7 | NAICS 5511 | excluded; pro-rata redistribution as robustness | §2.1 |
| D8 | Eloundou rating | human β headline, GPT-4 β beside it (descriptive only) | §2.1 |
| D9 | r6 occupation basis | published SOC; task-allocated as robustness | §2.1 |
| D10 | Confirmatory inference for H5/H5b | historical-null scale s, critical max(t₂₁, q), Holm, R13 co-condition; RI secondary | §3.3 |
| D11 | 5 pp plausibility rule | rule fires (primary MDE 7.43 pp) | §7 |
| D12 | H6 AI-term dictionary | the list and matching rules in §6.1 | §6.1 |
| D13 | RQ1 cross-sectional sample (H1, H3) | r6 `claude_ai`, both months averaged | §4.1 |
| D14 | Task family fixed effects | O\*NET IWA via Tasks-to-DWAs + DWA Reference (acquired) | §4.1 |
| D15 | H3 error-cost indicator | SOC-code list (legal, health practitioners, regulated finance) | §4.3 |
| D16 | H4 specification | r6 country cross-section; log AUI, log GDP per working-age person, task-mix control | §4.4 |
| D17 | One p-value per multi-coefficient hypothesis | H1 intersection–union; H4 joint Wald | §4.0 |
| D18 | H6 status and talk index | exploratory; EDGAR full-text search, 2024 filings, full-index denominator | §6 |
| D19 | Exploratory market parameters | objective event rule, windows, terciles with monthly cap reweighting | §8.3 |
| D20 | Data acquired after the freeze | robustness-only inputs listed, pre-specified | §9.4 |
| D21 | H5/H5b confirmatory null | b = b̄ (frozen 1990–2022 mean slope); b = 0 secondary | §3.3 |
| D22 | H2 inference and family | outside the RQ1 Holm family; release-level wild bootstrap co-condition; α split: H2 at 0.0125, {H1, H3, H4} Holm at 0.0375 | §4.2 |
| D23 | NAICS → SIC → FF49 crosswalk | equal split (departure from the spec); employment-weighted as robustness | §2.1 |

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
   correlations [audit §5, §8, §9]; the leverage and OLS weight of every industry in the H5/H5b
   regressions [power, leverage table]. These are RQ2 descriptives and design diagnostics. No delegation
   measure has been related to wage, education, error-cost or country variables (H1–H4), and no
   industry return dated on or after 2022-11-30 has been read by code.
4. **Pre-seal market history.** The power analysis estimated FF5+UMD alphas and cross-sectional slopes
   on 1990–2022 windows (returns read to 2022-11-29; in Task 15b also windows from 1963-07 and
   1969-07). Printed: slope dispersions, RI rejection rates, the D10 rule's in-sample rejection rates
   (centred and uncentred), empirical centred quantiles, kurtosis, leverage, and the **frozen mean
   slopes b̄** for H5, H5b and their R12/R13 variants. The referee ruled that freezing b̄ is harmless
   because it is pre-seal and the exposure vector is fixed (ruling on C3). The frozen values therefore
   show the level and sign of the mean historical slope. They are not interpreted anywhere in this
   plan. The recommendation in D21 (centre the null on b̄) was made **after** the uncentred in-sample
   rejection rates (7.1% for H5, 3.2% for H5b at nominal 2.5%) had been seen.
5. **General knowledge of the sealed period.** The seal stops code from reading post-2022-11-29 returns.
   It cannot remove what the researchers (or the language model assisting them) know from public
   commentary about broad market moves in 2023–2026, for example the AI-related rally in large
   technology stocks. This is why Design A is exploratory and why the confirmatory test (§3) is fixed
   here, together with its exposure vector, its frozen null values and the script that computes it
   (§9.3), before any post-seal return is read.
6. **D19's event-rule exceptions were chosen with the source list in view** (Gemma and Gemini Ultra
   excluded, ChatGPT added, GPT-4o absent from the source); see §8.3.
7. **The confirmatory script exists and has been tested on synthetic data only.**
   `aideleg.confirm_h5` was written before the tag. Its tests monkeypatch the seal and use synthetic
   returns. It has not been run on real data, and `docs/results/` does not exist.

### 0.5 Protocols for the first read of outcomes

These rules apply from the moment `pap-v1` exists.

- **P-H5 (single run of the confirmatory market test).**
  1. The first post-seal read of market data is `uv run python -m aideleg.confirm_h5`, at a commit
     whose `src/aideleg/confirm_h5.py` has the blob hash in §9.2. It runs once.
  2. **Before it loads anything**, the script enforces its own binding and refuses unless:
     (a) `pap-v1` is an annotated tag; (b) HEAD descends from `pap-v1`; (c) its own blob, and the
     working-tree blobs of `src/aideleg/power.py` and every `src/aideleg/market/*.py`, equal their
     blobs at `pap-v1`; (d) `git diff --quiet pap-v1 -- src pyproject.toml uv.lock` succeeds; (e)
     `git status --porcelain --untracked-files=all -- src pyproject.toml uv.lock` is empty, so no
     untracked file (for example a `src/aideleg/power/` package) can shadow bound code. It
     then checks each French zip's SHA-256 against `git show pap-v1:data/raw/MANIFEST.json` and each
     extracted member's CRC32 against the zip header (hashes only), and the Design B vector hash.
  3. **Attempt marker.** Immediately before the first post-seal read, the script creates
     `docs/results/confirmatory_h5.attempt` (exclusive creation; UTC time and HEAD). From then on,
     any failure writes its traceback to `docs/results/confirmatory_h5.md` and re-raises. While the
     marker exists the script refuses to run again.
  4. Its output (result or traceback) and the marker are committed **unedited**, in a commit that
     contains only those two files. The script writes with exclusive creation and refuses to
     overwrite.
  5. Every other post-seal read (robustness, secondary portfolios, Design A, event studies, H6
     returns) happens in later commits.
  6. If the script refuses **before** the marker (missing or lightweight tag, binding or data-hash
     mismatch, exposure hash), no market data has been read and no result exists; the fix is logged
     in §11 as a deviation, with its reason and Ajai's approval, before the script is run again. A
     refusal or failure **after** the marker (for example window coverage, or a crash) has read
     post-seal data: it is recorded as an **attempt, not a result**. Any rerun needs a §11 deviation
     with Ajai's approval, the attempt record stays committed, and the hypothesis is reported with
     that history.
- **P-RQ1 (single logged first run of the H1–H4 estimators).** The H1–H4 estimators are written in
  plan 2 (ruling R9), not before the tag. Their first run on real outcomes is a single logged commit
  whose output is committed unedited. Any code change after that commit is a deviation (§11). This is a
  **weaker guarantee than P-H5**: the H5 code and its hash are frozen before the tag, but the RQ1 code
  is frozen only at its first run. The specification it must implement is fixed here (§4).
- **Demotion rule.** A deviation adopted after a confirmatory result has been seen demotes that
  hypothesis to **exploratory**. The pre-registered specification is still reported as the primary
  result, beside the deviation.

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

The approved wording is kept above. Three proposed decisions change how two hypotheses are tested, and
Ajai must approve each one explicitly:
- **D21** tests H5/H5b against the historical pattern rather than against zero (§3.3).
- **D22** rewords H2 as "measured within-task automation rises", takes it out of the RQ1 Holm
  family and splits RQ1's α between them (H2 at 0.0125, {H1, H3, H4} at 0.0375) (§4.2).
- **D2** restricts H2's primary span to r2–r5 (§5).

---

## 2. Per-hypothesis specification

### 2.0 Summary

| | Outcome | Predictor / exposure | Sample | Estimator | SEs / inference | Family | Decision rule | Status |
|---|---|---|---|---|---|---|---|---|
| **H1** | task `automation_pct` | `human_education_years_mean` (task); log OEWS median wage (occupation) | r6 `claude_ai` global, task × occupation rows, IWA FE (D13, D14) | WLS, weights = allocated usage | two-way clustered (occupation, task), statsmodels; p = max of the two p-values (D17) | {H1, H3, H4}, Holm 0.0375 (D22) | Holm rejects and both coefficients < 0 | confirmatory |
| **H2** | task `automation_pct` | years since r2 (linear trend) | r2–r5 `claude_ai` global, tasks published in all four (D2) | WLS with task FE, fixed weights | clustered by task, **and** release-level wild bootstrap (D22) | none; own α = 0.0125 (D22) | both p ≤ 0.0125 and β > 0 | confirmatory, reworded (D22) |
| **H3** | task `validation_pct` | occupation error-cost indicator (D15) | as H1 | WLS with IWA FE | as H1 | {H1, H3, H4} | Holm rejects and γ > 0 | confirmatory |
| **H4** | country `automation_pct` (overall) | log AUI; log GDP per working-age person; task-mix control | r6 `claude_ai` countries (D16) | OLS | HC3; joint Wald of the two coefficients (D17) | {H1, H3, H4} | Holm rejects (two-sided) | confirmatory |
| RQ2 | — | `z_usage`, `z_delegation`, `z_augmentation` vs AIOE, Eloundou | FF49, Design B and A_pooled | Spearman ρ | industry bootstrap CI | none | descriptive | descriptive |
| **H5** | FF49 FF5+UMD alpha, 2025-04-01 → 2026-08-31 | Design B `z_delegation` | 49 FF49 industries, daily VW | cross-sectional OLS | T = (b̂ − b₀)/s, historical-null scale, critical max(t₂₁, q) (D10, D21); RI secondary | {H5, H5b}, Holm 0.05 | Holm rejects (two-sided) and R13 also rejects | confirmatory |
| **H5b** | as H5 | `z_delegation`, controlling for `z_aioe` | as H5 | cross-sectional OLS | as H5; Freedman–Lane RI secondary | {H5, H5b} | as H5 | confirmatory |
| **H6** | industry 10-K talk index; alpha | `z_usage`; AI-washing gap | FF49; 10-Ks filed 2019–2025 | OLS residual; cross-sectional OLS | as H5 (nominal) | none | reported, no rejection claim | exploratory (D18) |

H1–H4 are specified in §4, H5/H5b in §3, H6 in §6.

### 2.1 Measurement decisions shared by several hypotheses

Exposure construction follows spec §5.3 as implemented in `aideleg.exposure` and `aideleg.benchmarks`
at the commit in §9.2:
- U_o = AEI usage share of occupation o ÷ o's share of US employment (OEWS May 2024, national).
- D_o = U_o × automation share of o; A_o = U_o × augmentation share of o.
- E_j = Σ_o w_oj X_o over occupations with a value, w_oj = o's share of industry j employment (OEWS
  May 2024, NAICS 4-digit), NAICS 2022 → SIC 1987 → FF49 by the Census concordances with equal splits
  (`naics_to_ff49("split", 4, "exclude")`, D23).
- z = (E − mean) / population SD across the FF49 industries present.
- Design B = release r2 only (`claude_ai`, the only r2 source). A_r2 = the same numbers, labelled
  exploratory. A_pooled = r2–r6 `claude_ai`, equal release weights (exploratory). A_pooled uses
  releases published during and after the return window, so it contains look-ahead (§10, S3).

**Timing of the inputs (correction of the spec's real-time claim; §10, S1).** Design B's AEI input is
release r2 alone, published 2025-03-27. Two other inputs were published **after** that formation date:
- the OEWS May 2024 weights, released 2025-04-02 (USDL-25-0451), after the formation date and one
  trading day after the window starts;
- the O\*NET 29.3 task statements, used to link AEI tasks to occupations, released May 2025 (the
  exact day is not verified) [facts §1].

So Design B is out of sample in its AEI usage data, but **not strictly real-time** in its occupation
weights and task links. Both are slow-moving structural inputs that carry no return information. A
strict-real-time variant, with inputs public at 2025-03-27 (OEWS May 2023 weights; O\*NET ≤ 29.2 task
statements, 29.2 released February 2025), is pre-registered as R32. It is implemented in plan 3, with
the data acquired after the freeze (D20).

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
> where the bounds are not comparable across releases. Mean AI autonomy (`ai_autonomy_mean`,
> **r4–r6**; the spec's "from release 3" is corrected in §10, S2) is the secondary RQ1 measure the
> spec names (§5.4.1); it is reported for H1 and H2 as robustness R23.

> **[PROPOSED — Ajai to confirm] D3. Occupations with no AEI match.**
> *Recommended:* `unmatched="zero"`: an OEWS occupation with no AEI usage is assigned U = D = A = 0.
> **This is an assumption.** AEI leaves these cells unpublished; it does not measure them as zero.
> *Rationale:* it is the spec's default (§4). The occupations concerned are mostly hands-on trades
> (construction laborers, maids, industrial truck operators, welders) [audit §6]. Dropping them would
> treat their unpublished usage as equal to their industry's mean usage, which overstates exposure in
> the industries that employ them most.
> *Size of the assumption.* 232 occupations, 12.14% of May 2024 employment, are zero-assigned under
> Design B, and 144 occupations, 6.34%, under A_pooled [OEWS]. Every report of an index states this.
> The spec's "16.6%" and the audit's "7.39%" measure different things; they are reconciled in §10, S5.
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
> spec's wording and the basis of the power analysis), and pre-register two variants: (a) R12,
> standardised ranks: rank E_delegation across the 49 industries (average ranks for ties), then z-score
> the ranks with population SD, with `z_aioe` left unranked in H5b; (b) R13, the primary specification
> with Softw dropped (48 industries, z not re-standardised; in H5b Softw leaves both vectors). R12 and
> R13 are reported **co-primary**: in the same table as H5/H5b, with their own frozen s, b̄ and
> criticals (§3.3). R13 is also a co-condition of the H5/H5b claim (D10).
> *Rationale:* Design B `z_delegation` is heavily right-skewed: Softw is at 4.739 SD, the next industry
> at 1.977, skewness 2.571 [EXP]. Softw's leverage in the H5 regression is **0.479** (1/49 + 4.739²/49)
> and 0.518 in H5b. Its OLS weight is +0.0967 (H5) and +0.1225 (H5b), 14.2% and 15.1% of the sum of
> absolute weights. The next-highest leverage is Books at 0.100 [power, leverage table]. The primary
> slope is therefore to a large degree Softw against the rest. In alpha terms, the per-SD MDE implies a
> predicted alpha gap between Softw and an industry at z = 0 of 7.43 × 4.739 ≈ **35 pp** a year under
> the t₂₁ MDE (7.00 × 4.739 ≈ 33 pp under the normal MDE). Making ranks primary would change the
> hypothesis's metric from "per SD of exposure" and would require the power analysis to be rerun before
> the tag.
> *Alternatives:* ranks (R12) as primary. If Ajai prefers that, the power analysis and the frozen values
> are recomputed with ranks as primary, `confirm_h5.py` is updated (its hash changes), and §3.3, §7 and
> §9.3 are regenerated before the tag.

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

> **[PROPOSED — Ajai to confirm] D23. NAICS → SIC → FF49 crosswalk.**
> *Recommended:* the equal split as built: a NAICS code that maps to k SIC codes in the Census
> concordance chain gives 1/k of its employment to each (`naics_to_ff49("split", 4, "exclude")`).
> **This departs from the spec**, whose §5.3 says "employment-weighted crosswalk" (§10, D-3).
> *Rationale:* it is the vector the power analysis used and the one frozen in §9.3. The Census
> concordances carry no employment weights, so an employment-weighted split needs a further input.
> *Alternatives:*
> - **R33, the spec's variant:** an employment-weighted crosswalk. A NAICS 4-digit industry's
>   employment is split across SIC codes in proportion to the May 2024 employment of its NAICS 5- and
>   6-digit children, taken from `nat5d_6d_M2024_dl.xlsx` in the frozen `oesm24in4.zip`, that map to
>   each SIC. Children without published employment split equally. If Ajai prefers this as primary,
>   the exposure vector, the power analysis and the frozen values are rebuilt before the tag, and the
>   §9.3 hashes and the script constants are regenerated.
> - **R20 is not the spec's variant.** It is the `majority` many-to-one assignment, the spec's
>   "sensitivity to an alternative many-to-one assignment".

---

## 3. RQ3 confirmatory family {H5, H5b}

### 3.1 Primary specification (spec §5.4.1)

- **Exposure (formation).** Design B, release r2 only (published 2025-03-27): `z_delegation` from
  `build_exposure("B")` with the decisions of §2.1; `z_aioe` from `benchmark_ff49()`. Both are
  population-SD z-scores across the 49 FF49 industries. The exact vector is frozen by hash in §9.3. No
  AEI data published after 2025-03-27 inform it. The occupation weights and task links are vintages
  published shortly after that date (§2.1; R32).
- **Returns.** Ken French 49-industry **daily value-weighted** returns and the FF5 (2×3) daily factors
  plus daily momentum (UMD), the frozen files in §9.1 (`ff49_daily`, `ff5_daily`, `mom_daily`), in
  percent as published; −99.99 and −999 are missing.
- **Window.** 2025-04-01 to 2026-08-31 inclusive, every trading day present in both the industry and
  the factor file. The script refuses to run unless both files cover 2025-04-01 and 2026-08-31 and
  hold the same dates in the window. 2026-08-31 is a verified NYSE trading day. That 2025-04-01 was a
  trading day rests on calendar knowledge only; if it was not, the script fails safe and refuses
  [facts §4].
- **Alpha.** For each industry j: daily OLS of (r_jt − rf_t) on [1, Mkt-RF, SMB, HML, RMW, CMA, UMD],
  all in decimal; α̂_j = 252 × intercept (annualised, decimal). Implemented by
  `aideleg.power.window_alphas`, the same code the power analysis used. An industry with any missing
  return in the window gets no alpha and is dropped; z values are **not** re-standardised; the dropped
  industries are reported. Every frozen value (s, b̄, q, critical) is then recomputed on the kept
  industries from pre-seal history with the same code (`aideleg.power.null_scales`).
- **H5 regression.** α̂_j = a + b·z_delegation_j + e_j, OLS, unweighted. Estimand: b, in pp of
  annualised alpha per 1 SD of delegation exposure.
- **H5b regression.** α̂_j = a + b·z_delegation_j + c·z_aioe_j + e_j, OLS, unweighted. Estimand: b.
- **Co-primary variants.** R12 (standardised ranks) and R13 (drop Softw) as in D5, computed in the
  same run and reported in the same table.
- **Theoretical-exposure control.** Felten, Raj & Seamans (2021) AIOE (D6). Webb (2020) is the spec's
  fallback, used only if AIOE became unusable, which would be a logged deviation.
- **Implementation.** `aideleg.confirm_h5` (§0.5, §9.3) performs every step above and in §3.3, and
  writes `docs/results/confirmatory_h5.md`.

### 3.2 Why the spec's inference cannot be primary

The spec names randomisation inference: shuffle exposure across industries, ≥ 10,000 draws. The power
analysis tested that procedure, exactly as specified (10,000 permutations, seed `SEED`), on 378
overlapping pre-seal 17-month windows, where exposure measured in 2025 can have no causal relation to
alphas. At a nominal 0.025 it rejects in **13.8%** of windows for H5 and **14.8%** for H5b with `z_aioe`
held in place; the Freedman–Lane scheme for H5b, scored by the pivotal t of the coefficient on
`z_delegation` (Winkler et al. 2014), rejects in **5.6%** (6.1% when scored by the coefficient itself,
the statistic used before the final review) [power, size table].
- **The cause** is documented there. Industries with similar exposure co-move, so the alpha noise is
  correlated along z. Permutation treats industries as exchangeable, so its null spread (median
  within-window OLS SE 1.65 pp for H5) is well below the across-window sd of the slope (2.27 pp).
- **How large.** 13.8% is **5.5 times** the nominal 2.5% (5.9 times for H5b, 2.2 times for
  Freedman–Lane with the pivotal t, 2.4 times with the coefficient). These rates are an **upper bound** on the oversizing from clustering alone, because
  they also count windows in which high-exposure industries happened to earn persistently different
  alphas.

A confirmatory test with that size is not acceptable. This plan replaces it as primary and keeps it as
secondary.

**The wild-cluster bootstrap the spec lists (§5.4) is not used for H5/H5b.** There is one cross-section
of 49 time-aggregated alphas and no defensible cluster structure among the industries. A wild bootstrap
of the 49 residuals would address heteroskedasticity only, not the correlation along z, so it would
share the RI's understated null spread. The wild bootstrap is used where clusters exist: across
releases for H2 (D22).

### 3.3 Confirmatory inference

> **[PROPOSED — Ajai to confirm] D10. Confirmatory inference for H5 and H5b.**
> *Recommended:* a t-type test whose scale is the historical null standard deviation of the same slope,
> estimated on pre-seal windows with the confirmatory exposure vector held fixed. The critical value is
> the more conservative of a small-sample t critical and the empirical tail quantile.
>
> - **Scale (s_overlap).** s is the sample standard deviation (ddof = 1) of the slope b estimated,
>   with the same code and the same frozen z vector(s), on the **378 overlapping 17-month windows**
>   stepped monthly from 1990-01-01 (first 1990-01-01 → 1991-05-31, last 2021-06-01 → 2022-10-31),
>   using returns read through the sealed loaders with end = 2022-11-29.
>   - **s_H5 = 0.022709785806829905** (2.271 pp)
>   - **s_H5b = 0.02560409470770698** (2.560 pp)
>   - R12 and R13 have their own s on the same windows (§9.3).
> - **Statistic.** T_v = (b̂_v − b₀_v) / s_v for v ∈ {H5, H5b, H5-R12, H5b-R12, H5-R13, H5b-R13},
>   where b₀ is the null value fixed by D21: b̄_v under the recommended null, 0 under the alternative.
>   Both statistics are computed and printed for every v; the D21 choice decides which is primary.
> - **Reference distribution and p-value.** t with ν = 21 fixed. The 378 overlapping windows hold
>   about 22 independent 17-month windows, so the normal criticals would oversize by 25–45% (referee
>   C1). p = 2·(1 − F₂₁(|T|)).
> - **Primary critical (P1, stated exactly).** For variant v at Holm level L ∈ {0.025, 0.05}:
>   c_v,L = max(t₂₁,1−L/2 , q_v,1−L/2). Here q_v,0.9875 and q_v,0.975 are the empirical quantiles of
>   the symmetrised centred historical distribution ±(b − b̄_v)/s_v over the 378 windows, which are
>   the same as the 0.975 and 0.95 quantiles of |b − b̄_v|/s_v. With t₂₁,0.9875 = 2.4138 and
>   t₂₁,0.975 = 2.0796:
>   - H5: q = 2.080 / 1.896;
>   - H5b: 2.131 / 1.863;
>   - H5-R12: 1.996 / 1.811;
>   - H5-R13: 1.984 / 1.888;
>   - H5b-R12: 2.304 / 1.966;
>   - H5b-R13: 2.166 / 1.962.
>
>   Every q is below t₂₁, so **with the frozen values every c_v,L equals the t₂₁ critical**
>   (2.4138 at L = 0.025, 2.0796 at L = 0.05). The max rule matters only if industries drop out and
>   the frozen values are recomputed (§3.1).
> - **Critical values for |b̂ − b₀|** (c × s, pp):
>
>   | | s | at Holm 0.025 | at Holm 0.05 | MDE (c₀.₀₂₅ + t₂₁,0.80)·s |
>   |---|---|---|---|---|
>   | H5 | 2.271 | 5.482 | 4.723 | 7.43 |
>   | H5b | 2.560 | 6.180 | 5.325 | 8.38 |
>   | H5-R12 | 2.211 | 5.337 | 4.598 | 7.24 |
>   | H5-R13 | 3.195 | 7.713 | 6.645 | 10.46 |
>   | H5b-R12 | 2.982 | 7.197 | 6.201 | 9.76 |
>   | H5b-R13 | 3.713 | 8.963 | 7.722 | 12.15 |
>
>   t₂₁,0.80 = 0.8591, so MDE = 3.2729·s [power, t₂₁ and null-scale tables].
> - **Windows.** One confirmatory window, 2025-04-01 → 2026-08-31.
> - **Seed.** The primary test uses no random draws. The secondary RI tests use `SEED` (below).
> - **Decision rule (Holm over {H5, H5b}, family-wise α = 0.05).**
>   1. Order H5 and H5b by their primary t₂₁ p-values.
>   2. The first is rejected at Holm level 0.025 if |T| > c_v,0.025.
>   3. If it is rejected, the second is rejected at level 0.05 if |T| > c_v,0.05. Otherwise neither is
>      rejected (Holm stops at the first step).
>
>   Rejection is two-sided; the sign is reported, not required.
> - **Co-condition (P1).** The claim "delegation exposure is priced" (under D21's recommended null:
>   "priced in this window in excess of the 1990–2022 pattern for this exposure vector") requires the
>   hypothesis to be rejected **and** its R13 variant (Softw dropped) to reject under the same null, at
>   the same Holm level, with R13's own s and critical. If the hypothesis is rejected but R13 does not
>   reject, the fixed wording is: "**the result is not robust to dropping Softw (R13 not
>   rejected)**". It does not say the result is driven by Softw: R13 has its own, larger null scale,
>   and its non-rejection may be a power failure. The co-conditioned claim has 80% power only near
>   R13's MDE, **10.46 pp (H5) and 12.15 pp (H5b)** per 1 SD at Holm level 0.025 (§7), against
>   7.43 and 8.38 pp for the primaries; the script prints the R13 MDE beside each result.
> - **Historical-pattern check (P5; applies when the primary null is b = 0).** If H5 or H5b rejects
>   b = 0 but |b̂ − b̄|/s < c at its Holm level, the result is described as "**not distinguishable from
>   the 1990–2022 pattern for this exposure vector**". Under the recommended b̄ null this check is the
>   primary test itself, and the b = 0 result is reported as secondary.
> - **Intervals and non-rejection wording (P14).** Reported: b̂ ± c_v,0.05·s_v and b̂ ± c_v,0.025·s_v.
>   A non-rejection is worded exactly as the script prints it: "H is not rejected (H0: …). Interval
>   [lo, hi] pp per 1 SD; the test had 80% power only against a departure from H0 of at least MDE pp
>   per 1 SD (MDE at Holm level 0.025)." It is never described as "no effect".
> - **Influence diagnostics (P11).** For the confirmatory window, Softw's DFBETA for b and its Cook's
>   distance in the H5 and H5b OLS fits (statsmodels `OLSInfluence`: `dfbetas`, `cooks_distance`) are
>   reported beside the primary result. They are computed in a later commit, not by the single-run
>   script (§0.5), and they are not part of the decision.
>
> *Rationale.*
> - **Calibration.** s is the empirical spread of the slope when the documented cross-industry
>   correlation is present and there is no relation between this exposure vector and alphas. A test
>   scaled by s therefore has close to nominal size under that correlation, which RI does not [§3.2].
> - **Own size, checked in-sample (referee C2)** [power, own-size table]. On the 378 windows with t₂₁
>   criticals:
>   - centred on b̄, the rule rejects 0.3% (H5) and 1.3% (H5b) at nominal 2.5%, and 2.6% and 2.9% at
>     nominal 5%;
>   - uncentred, i.e. testing b = 0, it rejects 7.1% and 3.2% at 2.5%, and 12.4% and 7.4% at 5%;
>   - the excess kurtosis of the historical b is −0.43 (H5) and −0.36 (H5b): thin tails.
>
>   This is what D21 rests on.
> - **The max rule** guards against a fat empirical tail. With these values it does not bind.
> - **Power and test describe the same procedure.** The MDE uses the same s and the same critical as
>   the test.
> - **Overlapping windows.** The overlapping estimate (n = 378) is used because it averages over start
>   months. The non-overlapping sd ranges 1.78–2.82 pp across the 17 start offsets [power].
>
> *Secondary inference (reported beside the primary, never used for the decision):*
> 1. **RI as the spec names it, for H5:** permute `z_delegation` across industries, 10,000 permutations,
>    two-sided p = (1 + #{|b_perm| ≥ |b_obs|}) / 10,001 (`aideleg.power.ri_pvalues`,
>    `scheme="exposure"`).
> 2. **H5b, two schemes:**
>    - permuting `z_delegation` with `z_aioe` held in place, labelled as oversized even under
>      exchangeability;
>    - Freedman–Lane RI, permuting the residuals of α̂ on [1, z_aioe], 10,000 permutations, each
>      draw scored by the pivotal t of the coefficient on `z_delegation` in the refit on
>      [1, z_aioe, z_delegation] (Winkler et al. 2014; `scheme="freedman_lane"`). The
>      coefficient-scored p on the same draws (`scheme="freedman_lane_coef"`) is printed beside it.
>
>    Draws: one `numpy.random.default_rng(SEED)` generator, consumed in the order H5 (exposure),
>    H5b (exposure), H5b (Freedman–Lane, t); the coefficient version reuses the t version's draws.
>    Each secondary p-value is printed with the pre-seal size documented for its procedure in §3.2
>    (13.8%, 14.8%, 5.6% with the t and 6.1% with the coefficient, at nominal 0.025).
> 3. **Conventional OLS with HC3 standard errors**, for reference.
>
> *Alternatives (robustness):*
> - **R18:** s from non-overlapping windows, taking the largest of the 17 start offsets (H5 2.82 pp,
>   H5b 3.22 pp).
> - **R19:** s replaced by the root mean square of the 378 historical slopes around the null value.
> - **R34:** s from windows starting 1969-07 (the first month with all 49 industries) and from
>   1963-07 (§7).
> - **R35:** the studentised variant (§8.2).
> - **The spec's RI as primary.** Not recommended, because of its documented size.
>
> A cluster-robust or Driscoll–Kraay SE is not proposed: there is one cross-section of 49
> time-aggregated alphas and no defensible cluster structure.

> **[PROPOSED — Ajai to confirm] D21. The confirmatory null for H5 and H5b.**
> *Recommended:* **H0: b = b̄**, where b̄ is the frozen mean of the 378 historical slopes for the same
> exposure vector:
> - b̄_H5 = 0.01650391358632771;
> - b̄_H5b = 0.01216949247017634;
> - the R12/R13 values are in §9.3.
>
> The statistic is T = (b̂ − b̄)/s. This is `PRIMARY_NULL = "bbar"` in `confirm_h5.py`, its current
> value. The b = 0 statistic is computed in the same run and reported as **secondary**.
> *What the recommended null claims.* A rejection means that the post-2025 slope departs from the
> 1990–2022 pattern for this exposure vector. **This is a narrower claim than the approved H5 wording.**
> H5 says industries with higher exposure "earned different risk-adjusted returns", which is a test of
> b = 0. A b̄-null rejection says the 2025–26 slope differs from what this exposure vector historically
> showed. A b = 0 rejection with b̂ close to b̄ would say only that the historical pattern persisted.
> **Ajai must approve this reinterpretation explicitly.**
> *What each null rejects, in pp of annualised alpha per 1 SD (computed from the frozen s, b̄ and
> criticals of §9.3: bound = b₀ ± c_v,L·s_v).*
>
> | | null | Holm level 0.025 (first step) | Holm level 0.05 (second step) |
> |---|---|---|---|
> | H5 | b = b̄ (recommended) | b̂ > 7.13 or b̂ < −3.83 | b̂ > 6.37 or b̂ < −3.07 |
> | H5 | b = 0 | \|b̂\| > 5.48 | \|b̂\| > 4.72 |
> | H5b | b = b̄ (recommended) | b̂ > 7.40 or b̂ < −4.96 | b̂ > 6.54 or b̂ < −4.11 |
> | H5b | b = 0 | \|b̂\| > 6.18 | \|b̂\| > 5.32 |
>
> Because the frozen b̄ is not zero, the two nulls do not treat the two directions alike: **the b̄
> null makes a positive finding harder to reach and a negative one easier** than the b = 0 null
> does. This is a property of the test's geometry, stated so that a reader can weigh a result in
> either direction; it is not an interpretation of the sign of b̄.
> *Rationale:* the historical exposure–alpha slope is not centred at zero. Under the historical null,
> testing b = 0 with t₂₁ criticals rejects in 7.1% of windows (H5) and 3.2% (H5b) at a nominal 2.5%.
> Centred on b̄, the same rule rejects in 0.3% and 1.3% [power, own-size table]. For H5 the uncentred
> rule is oversized almost threefold. The defensible confirmatory question, given a persistent
> historical exposure–alpha pattern that cannot be caused by 2025 delegation, is whether the
> post-2025 slope departs from that pattern.
> *Alternative:* **H0: b = 0**, the literal approved wording, with P5's "not distinguishable from the
> 1990–2022 pattern" wording applied to rejections. Setting this means changing one line of
> `confirm_h5.py` (`PRIMARY_NULL = "zero"`). That changes the script's git blob hash, and the new hash
> is re-recorded in §9.3 (and the header) before the tag. The script and its tests already handle both
> settings.

If any decision in §2.1 changes the Design B `z_delegation` or `z_aioe` vector before the tag, the
power analysis is rerun at the new commit; s, b̄, q, the criticals, the `FROZEN` constants in
`confirm_h5.py` (and so its hash), §7 and §9 are regenerated before signing.

### 3.4 What the Holm family covers

The family is {H5, H5b} only. R12 and R13 are reported co-primary, and R13 enters the claim as a
co-condition (D10), but neither is a separate family member. Every other market analysis (robustness
variants of §8, tercile portfolios, Fama–MacBeth, event studies, Design A, H6) is outside the family and
carries no family-wise error control. The spec allows Romano–Wolf or Holm across "pre-registered
exposure variants"; this plan assigns those variants to robustness (§8), reported in full, rather than to
a second testing family.

---

## 4. RQ1 confirmatory hypotheses

**Testing family {H1, H3, H4}, Holm at family-wise α = 0.0375.** H2 is tested on its own at
α = 0.0125 (D22), so RQ1 as a whole keeps a family-wise error ≤ 0.05. The
primary delegation measure is `automation_pct` (D1). No H1–H4 relationship has been estimated before
this plan. The estimators are written in plan 2 under protocol P-RQ1 (§0.5).

**Two-way cluster estimator (H1, H3), stated exactly.**
- **Call.**
  ```
  statsmodels.api.WLS(y, X, weights=w).fit(
      cov_type="cluster",
      cov_kwds={"groups": numpy.column_stack([occ_id, task_id]), "use_correction": True},
      use_t=True)
  ```
  This uses statsmodels 0.15.0, in the lockfile at §9.2. X holds the regressors and the IWA dummies.
  occ_id and task_id are integer codes of `soc6` and the task statement.
- **What it computes.** A two-column `groups` makes statsmodels call
  `statsmodels.stats.sandwich_covariance.cov_cluster_2groups`. That gives
  V = V_occ + V_task − V_occ∩task (Cameron, Gelbach & Miller 2011), each term with the small-sample
  correction.
- **Inference.** t with min(G_occ, G_task) − 1 degrees of freedom (`df_resid_inference`).
- **Non-PSD rule.** Let V_k be the covariance block of the tested coefficients ([β_e, β_w] for H1,
  γ for H3).
  - If its smallest eigenvalue is negative, V_k is replaced by U·max(Λ, 0)·U′, where V_k = UΛU′
    (CGM 2011, §2.3).
  - If a tested coefficient's variance is then zero, its SE is the larger of its two one-way cluster
    SEs (by occupation, by task).
  - Each use of the rule is reported.
- **Departure from the spec.** The spec (§5.2) asks for SEs clustered by occupation only. Two-way
  clustering is intended to be conservative, because it also allows correlation within a task across
  occupations. The one-way occupation-clustered p-values are reported as R38.

### 4.0 One p-value per hypothesis

> **[PROPOSED — Ajai to confirm] D17. Hypotheses with two coefficients.**
> *Recommended:* H1 states two conjunctive claims (lower delegation for more education **and** in
> higher-wage occupations), so its family p-value is the intersection–union p-value
> p_H1 = max(p_educ, p_wage), each two-sided; H1 is supported only if Holm rejects at p_H1 and both
> coefficients are negative. H4 states that the delegation share "relates to" AUI and income, with no
> direction, so its p-value is the joint HC3 Wald test of both coefficients equal to zero.
> *Rationale:* both give one p-value per hypothesis. The intersection–union test is valid at level α
> without a further correction and matches H1's conjunctive wording. The joint test matches H4's
> non-directional "relates to" and copes with the correlation between AUI and income.
> *Alternative:* splitting H1 into H1a (education) and H1b (wage) and H4 into H4a/H4b gives a
> five-member Holm family {H1a, H1b, H3, H4a, H4b}; these p-values are reported as robustness (R25).

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
> *Rationale:* the spec asks for "O\*NET task family fixed effects" (§5.2). The IWA is O\*NET's own
> grouping of similar work activities across occupations (about 330 categories). It is fine enough to
> compare like tasks and coarse enough to leave within-family variation in wage and education. r6
> publishes the DWA/IWA/GWA hierarchy, so the grouping is native to AEI too.
> The two files were acquired in Task 15b and are in the MANIFEST: `onet_29_3_tasks_to_dwas` and
> `onet_29_3_dwa_reference` (§9.1) [facts §3]. The linkage code is written in plan 2 and tested
> against this rule.
> *Alternatives (R26):* GWA (41 categories) fixed effects; DWA fixed effects.

| | H1 primary specification |
|---|---|
| Unit | (task statement, occupation) pair. A task's occupations are the union over its candidate Task IDs (ruling R6), as O\*NET-SOC 2019 `soc6` codes, mapped to OEWS codes with `oews_code_for`. Further split by IWA (D14). |
| Outcome | the task's `automation_pct` (D13), the same value on every row of the task. |
| Predictors | `human_education_years_mean` of the task (years, D13 averaging); log of the OEWS May 2024 national annual median wage (`a_median`) of the occupation. A top-coded median (`#`) is set to **$239,200**, the annual top-code printed in the May 2024 field descriptions [facts §2]. A suppressed median (`*`, `**`) drops the row. |
| Fixed effects | IWA (D14). |
| Weights | the task's weight (D13) ÷ (number of its occupations × number of its IWAs). Usage is conserved. |
| Missing values | a row missing the outcome, either predictor, the IWA or an OEWS code is dropped; weights are not renormalised; the dropped share of r6 task usage is reported by reason. `unmatched:*` nodes are never included. H3 applies the same rule to its own variables. |
| Estimator | WLS: automation = β_e·education + β_w·log wage + IWA FE + ε. |
| Inference | two-way cluster-robust SEs by occupation (`soc6`) and task statement, exactly as stated at the top of §4. p_educ, p_wage two-sided; p_H1 = max (D17). |
| Decision | supported if Holm over {H1, H3, H4} at family-wise 0.0375 (D22) rejects at p_H1 and β_e < 0 and β_w < 0. Each coefficient is reported with its CI in pp of automation per year of education and per log point of wage. |
| Two measures, one decision | H1 names two delegation measures. The decision uses `automation_pct` only. `ai_autonomy_mean` (R23) is reported beside it. If its coefficients have the opposite sign and are significant at nominal 0.05, the report states "the two delegation measures named in H1 disagree", and the decision is unchanged. |
| Status | confirmatory. |

**Effective estimand of H1 and H3 (P13).** The outcome and education are constant within a task, and
only the wage varies across a task's occupation rows. So:
- **β_e** is the usage-weighted, within-IWA association between a task's automation share and its
  education requirement.
- **β_w** compares tasks whose occupations have different log median wages, weighting each occupation
  by its allocated share of the task's usage. Its effective regressor is the task's allocation-weighted
  mean log wage. The within-task spread of wages across occupations enters the denominator but not the
  numerator of the estimator, which attenuates β_w. The attenuation factor is the between-task share
  of the within-IWA (residualised) wage variance. It is reported beside β_w.
- **γ (H3)** is the within-IWA difference in the validation share between task rows of error-cost and
  other occupations, attenuated the same way. Its attenuation factor is the between-task share of the
  indicator's within-IWA variance.

H1 and H3 therefore measure how tasks differ, weighted by the occupations they are allocated to. They
do not compare workers.

### 4.2 H2 (trust accumulation)

Specified here and in §5 (the definition-stable list, D2).

> **[PROPOSED — Ajai to confirm] D22. H2 inference, wording and family.**
> *Problem (referee V5).* The H2 trend is identified from four release cross-sections. Under task fixed
> effects, the time regressor varies only across releases, so the effective time degrees of freedom are
> about 4 − 2 = 2. Task-clustered SEs treat each task as independent across releases. They ignore any
> shock common to all tasks in a release, such as a classifier or platform change (§5), so their
> p-value is not valid for a Holm family.
> *Recommended:*
> 1. **Wording.** H2 is tested as "**measured within-task automation rises across releases**". The
>    approved text says "delegation rises". The rewording makes explicit that the classifier and
>    platform scope are not held fixed.
> 2. **Family and α.** H2 is removed from the RQ1 Holm family. The family becomes {H1, H3, H4}.
>    RQ1's α = 0.05 is split (Bonferroni across the two parts): H2 is tested on its own at
>    **α = 0.0125**, and {H1, H3, H4} by Holm at family-wise **α = 0.0375**. The RQ1 family-wise
>    error is then at most 0.0125 + 0.0375 = 0.05. Testing H2 at a separate 0.05 beside a Holm family
>    at 0.05 would raise the RQ1 family-wise error to about 1 − 0.95² ≈ 0.10; that is the
>    alternative below, not the recommendation. The report states the split.
> 3. **Co-condition (release-level inference).** H2 is supported only if all three hold:
>    - the task-clustered p ≤ 0.0125;
>    - β > 0;
>    - a **wild cluster bootstrap with clusters = releases** gives p ≤ 0.0125.
>
>    The bootstrap is restricted (null β = 0 imposed) and uses Webb six-point weights. All 6⁴ = 1,296
>    weight vectors are enumerated, so no random draws are used. Its statistic is the task-clustered
>    t of β, and p = share of |t\*| ≥ |t|.
>
>    With four clusters this co-condition is demanding and may be conservative. H2 can be supported
>    only by a trend that is large relative to release-to-release variation. This is disclosed with
>    the result.
> 4. **Also reported:** randomisation over release labels. All 24 orderings of the four
>    cross-sections over the four time values are used. Its smallest attainable p-value is at least
>    1/24 ≈ 0.042, so it is reported as descriptive only.
>
> *Alternatives:*
> - H2 on its own at a separate α = 0.05, beside {H1, H3, H4} by Holm at 0.05 (the earlier
>   recommendation). The RQ1 family-wise error is then about 0.10, not 0.05;
> - keep H2 in the {H1–H4} Holm family with task-clustered SEs, as approved. Not recommended: that
>   p-value is not valid at the release level;
> - use release-label randomisation as the co-condition instead of the wild bootstrap.

| | H2 primary specification |
|---|---|
| Unit | (task, release), `claude_ai`, global, `onet_task` rows; task identity = the panel's matched task node. |
| Releases | r2, r3, r4, r5 (D2). |
| Sample | tasks with a published `automation_pct` in all four releases (balanced). |
| Outcome | `automation_pct`. |
| Time | t_r = (midpoint of r's window − midpoint of r2's window) in days ÷ 365.25, with midpoint = `period_start` + (`period_end` − `period_start`)/2 from the panel. β is therefore in pp per year. Robustness R36: t_r from publication dates. |
| Estimator | WLS with task fixed effects: automation_tr = α_t + β·t_r + ε_tr. |
| Weights | fixed per task: the mean of its `pct` over the four releases, so weights do not move with release. |
| Inference | SEs clustered by task (`cov_type="cluster"`, groups = task id, `use_t=True`), two-sided; and the release-level wild bootstrap (D22). |
| Decision | supported if both p ≤ 0.0125 and β > 0 (D22). β is reported as "the change in measured within-task automation", which includes any change in the unstated classifier and in platform scope (§5). |
| Also reported | the event-style plot: release fixed effects instead of the trend, r2 as base, with 95% CIs; the within-r6 April vs May check (R37). |
| Status | confirmatory, stand-alone (D22). |

### 4.3 H3 (calibrated checking)

> **[PROPOSED — Ajai to confirm] D15. H3 error-cost indicator.**
> *Recommended:* error_cost_o = 1 if the occupation's SOC 2018 code is in one of:
> - major group 23 (Legal occupations);
> - major group 29 (Healthcare practitioners and technical occupations);
> - minor group 13-2000 (Financial specialists);
> - 11-3031 (Financial managers) or 41-3031 (Securities, commodities and financial services sales
>   agents).
>
> Otherwise 0.
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
| Decision | supported if Holm over {H1, H3, H4} at family-wise 0.0375 (D22) rejects and γ > 0. γ is reported in pp of validation share. |
| Robustness | R31: H3 with H1's covariates (education, log wage) added. |
| Status | confirmatory. |

### 4.4 H4 (geography)

> **[PROPOSED — Ajai to confirm] D16. H4 specification.**
> *Recommended:*
> - **Sample.** r6 `claude_ai`, `geo_level = country`. Countries with a published overall
>   `automation_pct` and `usage_per_capita_index` in both months, and with 2024 GDP and working-age
>   population in the AEI r3 inputs.
> - **Months, then logs.** Each country-level variable is first averaged over April and May 2026 (the
>   two published values, equally weighted). The log is taken of the two-month mean, never the mean of
>   the logs.
> - **Outcome.** The country's overall `automation_pct` (renormalised), two-month mean.
> - **Predictors.**
>   - log of the two-month mean of the Anthropic Usage Index (`usage_per_capita_index`);
>   - log of 2024 GDP per working-age (15–64) person (`aei_geo_gdp_country` ÷ `aei_geo_wap_country`).
> - **Task-mix control.** M_c = Σ_g s̄_cg · ā_g.
>   - s_cg is country c's `pct` over GWA nodes (`onet` hierarchy level 3), renormalised over the GWAs
>     published in that month (an unpublished GWA is 0 in that month).
>   - s̄_cg is the mean of the two months' s_cg.
>   - ā_g is the global r6 `claude_ai` `automation_pct` of GWA g, as the usage-weighted mean of the
>     two months (weights: the GWA's global `pct` in each month; a month with an unpublished value is
>     left out), the same rule as D13.
>   - The sum runs over GWAs with a published ā_g; s̄ is renormalised over them.
> - **Estimator.** OLS: automation_c = a + b₁·log AUI_c + b₂·log income_c + b₃·M_c + e_c, unweighted,
>   `statsmodels.api.OLS(...).fit(cov_type="HC3")`.
> - **Inference.** p_H4 = the joint Wald test of b₁ = b₂ = 0 on the HC3 covariance
>   (`fit.wald_test(R, use_f=True, scalar=True)`, F with (2, n − 4) df) (D17).
> - **Decision.** Supported if Holm over {H1, H3, H4} at family-wise 0.0375 (D22) rejects; b₁ and b₂ are reported with CIs,
>   two-sided.
> - **Also reported (descriptive).** The shift-share split of each country's gap from the global
>   delegation share into a task-mix part (M_c − global) and a within-task part, with maps.
>
> *Rationale:* r6 publishes all metrics at country × GWA level, which makes the mix adjustment
> possible on the latest and least suppressed release. Finer country × task cells are mostly
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
> - **Excluded.**
>   - `filtered_pct` (r2 only), `not_classified_pct` (r3–r5) and `none_pct` (r3–r6), whose
>     denominators differ by release.
>   - Release r1, which has no task-level collaboration [MET].
>   - `ai_autonomy_mean`, which is definition-stable only over r4–r6. It is a secondary series (R23),
>     not part of the primary.
> - **Primary series: r2–r5.** r6 is excluded from the definition-stable series. In r3–r5 only
>   3.70–9.10% of tasks publish all five patterns; in r6, 99.71–99.96% do [SUP]. Task automation in
>   r3–r5 is renormalised over partially published patterns, and the partial tasks' automation
>   differs from the complete tasks' by up to 9.3 points with a sign that varies by source [audit §4].
>   So a level shift at r6 would mix behaviour with the change in suppression regime. A regime dummy for
>   r6 would absorb r6 entirely under a linear trend, so it is equivalent to excluding r6, and exclusion
>   is the plainer statement.
> - **No platform-scope controls in the primary.** Max joins in r5 and Cowork in r6. With one source
>   and one scope per release, a release-level control is collinear with the time trend, so it cannot
>   be included. The primary β is therefore the change in **measured** within-task automation,
>   including any change in scope and in the classifier, which is unobservable because no release names
>   it [audit §2, open risk 1].
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
> - **Talk, primary (one method, chosen: EDGAR full-text search).** For FF49 industry j and filing
>   year y, talk = numerator ÷ denominator.
>   - **Numerator.** The number of distinct CIKs whose 10-K is returned by EDGAR full-text search
>     (FTS) for at least one primary term (§6.1). Each term and its listed plural is queried as a
>     quoted phrase, restricted to the form types above and to filing dates in year y. **The matching
>     semantics are FTS phrase semantics as implemented by the SEC on the retrieval date.** The
>     case, whitespace and hyphen rules of §6.1 bind only the secondary measure, which runs on
>     downloaded text. The raw FTS responses are saved, and recorded in the MANIFEST with their
>     retrieval date and SHA-256.
>   - **Denominator.** The number of distinct CIKs filing one of those form types in year y, from the
>     EDGAR full index (`https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{1–4}/form.idx`),
>     mapped to FF49 the same way.
> - **Talk index for the gap.** T_j = talk in filings dated 2024-01-01 → 2024-12-31. These were all
>   public before Design B's formation date, 2025-03-27.
> - **Gap.** OLS across FF49 of z(T_j) on Design B `z_usage`. gap_j = the residual, standardised.
> - **"Diverges".** Spearman(T_j, z_usage) with a 95% industry-bootstrap CI (10,000 draws, `SEED`);
>   the ranking of gap_j; the talk series by year.
> - **Return association.** The §3.1 regression with gap_j in place of z_delegation. Its inference is
>   computed as in §3.3: s, b̄ and q recomputed for the gap vector on the same pre-seal windows, the same
>   null as D21. Reported with nominal p-values; it is in no testing family.
> - **Secondary talk measure.** Dictionary occurrences (primary and acronym terms, §6.1) per 10,000
>   words of the primary 10-K document text, downloaded from EDGAR, firm-level, then the industry
>   mean.
>
> *Rationale:* the 10-K pipeline does not exist yet. Promoting H6 to confirmatory before its measurement
> has been audited would fix a specification no one has seen work. Filing-level presence is what EDGAR
> full-text search returns directly, so it needs the fewest processing choices. The full index gives a
> denominator that does not depend on the search.
> *Alternatives:*
> - the primary talk measure computed on downloaded 10-K text with the §6.1 rules, in place of FTS;
> - promoting H6 to confirmatory;
> - **R29:** talk from 2025 filings dated before 2025-03-27; the change in talk from 2019 to 2024;
>   filers weighted by market capitalisation where SEC data allow.

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
> **Matching rules (downloaded text; the FTS primary uses the SEC's phrase semantics, D18).**
> - Text is Unicode-NFKC-normalised.
> - HTML tags are stripped before matching.
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

From the power analysis [power]. The primary MDE uses the D10 test as specified:
MDE = (c₀.₀₂₅ + t₂₁,0.80)·s = 3.2729·s, with c₀.₀₂₅ = t₂₁,0.9875 = 2.4138 (Holm's first step) and power
0.80. Units: pp of annualised alpha per 1 SD of exposure. The normal-critical MDE (3.0830·s) is shown for
comparison only.

| | windows | n | s | MDE t₂₁ (primary) | MDE normal |
|---|---|---|---|---|---|
| H5 | overlapping, from 1990-01 | 378 | 2.271 | **7.43** | 7.00 |
| H5 | non-overlapping, from 1990-01 | 23 | 2.626 | 8.59 | 8.10 |
| H5b | overlapping, from 1990-01 | 378 | 2.560 | **8.38** | 7.89 |
| H5b | non-overlapping, from 1990-01 | 23 | 2.834 | 9.27 | 8.74 |
| H5 | overlapping, from 1969-07 (all 49 industries) | 624 | 2.51 | 8.22 | 7.74 |
| H5b | overlapping, from 1969-07 | 624 | 3.00 | 9.80 | 9.24 |
| H5 | overlapping, from 1963-07 (first daily FF5 month) | 696 | 2.72 | 8.90 | 8.38 |
| H5b | overlapping, from 1963-07 | 696 | 3.53 | 11.56 | 10.89 |

- Non-overlapping sd across the 17 start offsets: H5 1.78–2.82 pp, H5b 2.17–3.22 pp.
- Collinearity: Pearson(`z_aioe`, `z_delegation`) = 0.671, VIF 1.82.
- The co-primary variants: MDE t₂₁ for H5-R12 7.24, H5-R13 10.46, H5b-R12 9.76, H5b-R13 12.15 pp
  (§3.3). The R13 co-condition can be met only by an effect that R13 itself can detect.
- **The 1990-01 start (P6).** The start date was fixed in plan 1 (commit `468feff`) before any slope
  was computed. **No reason for 1990-01 was recorded at the time.** The rationale that follows was
  supplied afterwards, once the referee asked: to keep the history within the last three decades of
  FF49 industry composition, when the software and semiconductor industries were populated. **It is the least
  conservative of the three starts.** The 1969-07 and 1963-07 starts give larger s, because Softw is
  missing until 1965-07 and Hlth until 1969-07, and because the earlier decades differ. They are
  pre-registered as robustness inference R34. The 1963-07 rows are not like-for-like: 113
  industry-window drops in 89 windows. The 1969-07 rows are the clean comparison: 17 Softw drops.

> **[PROPOSED — Ajai to confirm] D11. The plausibility rule.**
> *Rule as proposed:* if the H5 MDE exceeds **5 percentage points of annualised alpha per 1 SD of
> exposure**, RQ3 is reported as "what the market evidence can and cannot yet say", and the paper is led
> by RQ1–RQ2.
> *Where the 5 pp comes from (P9).*
> - The number is **not in the spec**. Spec §5.4 says only "implausibly large".
> - It comes from the plan file (plan 1, Task 15, Step 1, item 7), committed at `468feff`, before the
>   power analysis was first run (`53d6cf4`).
> - The plan marks it as Ajai's call, so it **becomes binding only when Ajai confirms it, and he does
>   so after the MDE is known**. A reader should treat it as a threshold confirmed with the MDE in view.
>
> *What the rule gives now:* the primary H5 MDE is **7.43 pp** (t₂₁, overlapping). Every H5 and H5b MDE
> in the table is between 7.00 and 11.56 pp, so all exceed 5 pp. **Under the rule, RQ3 is reported as
> "what the market evidence can and cannot yet say", and the paper is led by RQ1–RQ2.**
>
> The Design B test (§3) is still run and reported in full, with its MDE beside it, as the spec
> requires. A non-rejection uses the P14 wording (§3.3). It is never described as "no effect".
> *For Ajai to confirm or change before signing:* the 5 pp threshold. The rule is evaluated on the
> primary H5 MDE (7.43 pp). Any threshold below 7.43 pp gives the same outcome; a threshold above
> 7.43 pp would flip it.

---

## 8. Robustness (spec §5.6, plus the audit's and the referee's items)

### 8.1 Reporting rules

- Every variant below is run and reported in an appendix table, whatever its result.
- A variant never changes a confirmatory decision. The one exception is R13, which is a pre-registered
  co-condition of the H5/H5b claim (D10).
- Results are not summarised by counting how many variants are significant.
- No variant carries error control across variants. R21 in particular (other indices in place of
  `z_delegation`) has none and is labelled so.
- Market variants use the §3.3 inference with s, b̄ and q recomputed, for the variant's exposure vector
  or sample, by the same pre-seal procedure (same 378 windows, same t₂₁ rule, same D21 null).
- RQ1 variants use the inference of the hypothesis they vary.
- All market robustness reads happen after the single confirmatory run (§0.5). They are implemented in
  plan 3 unless stated.

### 8.2 The list

| ID | Variant | Applies to | Source |
|---|---|---|---|
| R1 | OEWS May 2025 employment weights (`oesm25in4`; national shares from its cross-industry rows, or `oesm25nat` acquired after the freeze if absent). **Labelled look-ahead for H5/H5b**: the May 2025 weights were published after the formation date and during the return window. | RQ2; H5, H5b (look-ahead) | spec §5.6; P16 |
| R2 | wage-bill weights (OEWS employment × mean wage) in place of employment weights | H5, H5b, RQ2 | spec §5.6 |
| R3 | `unmatched="drop"` | H5, H5b, RQ2 | D3 |
| R4 | `1p_api` instead of `claude_ai` for A_pooled (r3–r6). For RQ1, this variant is merged into R22 (H2) and R24 (H1, H3). Design B has no API source. | A_pooled | spec §5.6 |
| R5 | equal-weighted FF49 returns in place of value-weighted | H5, H5b | spec §5.6 |
| R6 | FF30 and FF48 industry granularity. Specification, frozen now: exposure rebuilt on the 30/48 industries with `Siccodes30`/`Siccodes48` and the same split crosswalk, z re-standardised across those industries; alphas from the 30/48-industry daily VW files; s, b̄, q recomputed on the same 378 windows with the same code; critical max(t₂₁, q); the D21 null. Files acquired after the freeze. | H5, H5b | spec §5.6; P10 |
| R7 | drop technology industries {Hardw, Softw, Chips} | H5, H5b | spec §5.6 |
| R8 | exclude calendar 2023 (the 2023 AI large-cap rally months). **Not applicable to Design B by design**: its window starts 2025-04. | Design A only | spec §5.6 |
| R9 | placebo event dates: the same month-day as each §8.3 event in 2017, 2018, 2019 and 2021. 2020 is skipped because the COVID-19 crash and recovery make 2020 abnormal returns unrepresentative of a no-event year. | event studies | spec §5.6 |
| R10 | R7 bounds `_lb` / `_ub` in place of `automation_pct` | H1, H3, H5, H5b | D1 |
| R11 | employment-weighted task allocation | H5, H5b, RQ2 | D4 |
| R12 | standardised-rank exposure (co-primary reporting) | H5, H5b | D5 |
| R13 | drop Softw (co-primary reporting; co-condition) | H5, H5b | D5 |
| R14 | AIOE through the BLS SOC 2010→2018 crosswalk | H5b, RQ2 | D6 |
| R15 | NAICS 5511 redistributed (`hq="redistribute"`) | H5, H5b, RQ2 | D7 |
| R16 | r6 task-allocated occupation basis | A_pooled, r6 descriptives | D9 |
| R17 | Eloundou GPT-4 β as headline | RQ2 | D8 |
| R18 | null sd from non-overlapping windows, largest of the 17 offsets | H5, H5b | D10 |
| R19 | null scale = RMS of the historical slopes around the null value | H5, H5b | D10 |
| R20 | crosswalk `majority` mode instead of `split` (the spec's alternative many-to-one assignment) | H5, H5b, RQ2 | Task 10 ruling |
| R21 | `z_usage` and `z_augmentation` in place of `z_delegation`. No error control. | H5, H5b | spec §5.4.1 |
| R22 | H2 all-releases series, unbalanced panel, other definition-stable metrics, `1p_api` (r3–r5) | H2 | D2 |
| R23 | `ai_autonomy_mean` as delegation measure (r4–r6). For H2 this series includes r6, against D2's regime caveat, so it is labelled "confounded with the r6 suppression-regime change", like R22's all-releases series. | H1, H2 | spec §5.4.1 |
| R24 | r4, r5 `claude_ai`; r6 `1p_api` | H1, H3 | D13 |
| R25 | H1 and H4 coefficients tested separately (five-member Holm family {H1a, H1b, H3, H4a, H4b}, family-wise 0.0375) | H1, H4 | D17 |
| R26 | GWA and DWA fixed effects | H1, H3 | D14 |
| R27 | O\*NET "Consequence of Error" (continuous) | H3 | D15 |
| R28 | US states; r4, r5 countries; usage-weighted; IWA-level mix | H4 | D16 |
| R29 | 2025 pre-formation filings; change 2019→2024; cap-weighted filers | H6 | D18 |
| R30 | narrower and broader dictionaries | H6 | D12 |
| R31 | H3 with H1's covariates (education, log wage) added | H3 | P13 |
| R32 | **strict real-time Design B**: OEWS May 2023 weights (`oesm23in4`, `oesm23nat`) and O\*NET task statements ≤ 29.2, i.e. inputs public at 2025-03-27; s, b̄, q recomputed. Data acquired after the freeze. | H5, H5b | P15 |
| R33 | employment-weighted NAICS → SIC crosswalk from OEWS `nat5d_6d` (D23), the spec's variant | H5, H5b, RQ2 | D23; P17 |
| R34 | null scale and criticals from windows starting 1969-07 and 1963-07 | H5, H5b | P6 |
| R35 | **studentised statistic** (below) | H5, H5b | P10 |
| R36 | H2 time t_r from publication dates instead of window midpoints | H2 | P19 |
| R37 | within-r6 April vs May: the within-task change in `automation_pct` between the two r6 months, a check on short-run seasonality and noise. Descriptive. | H2 | P19 |
| R38 | H1/H3 SEs clustered by occupation only (spec §5.2) | H1, H3 | P18 |

**R35, the studentised variant (P10; frozen now, implemented in plan 3).** For each historical window w
of the 378:
- Fit the daily FF5+UMD regression of each industry, as `window_alphas` does.
- Σ_w is the 49 × 49 covariance of the daily residuals across industries (denominator T_w − 7).
- c_w = [(X_w′X_w)⁻¹]₁₁ is the intercept element of the common factor design.
- ω is the OLS weight vector with b = ω′α (`power.ols_weights` of [1, z] for H5, [1, z, z_aioe] for
  H5b).
- SE_Σ,w = 252·√(c_w·ω′Σ_wω).
- κ = sd_w(b_w) / median_w(SE_Σ,w), the same sd as s.

In the confirmatory window, SE_Σ,2025–26 is computed the same way. The statistic is
T_stud = (b̂ − b₀)/(κ·SE_Σ,2025–26), with b₀ the D21 null value and the t₂₁ criticals of §3.3.

### 8.3 Exploratory market analyses (labelled exploratory wherever they appear)

> **[PROPOSED — Ajai to confirm] D19. Exploratory market parameters.**
> *Recommended:*
> - **Design A exposure.** A_r2 and A_pooled. Returns from 2022-12-01 → 2026-08-31.
>   - A_r2 is formed from r2, the earliest release with task-level collaboration. It is numerically
>     identical to Design B.
>   - A_pooled is labelled look-ahead, because r3–r6 were published during and after the return
>     window (§10, S3).
> - **Event rule (P7, objective).** The events are:
>   - ChatGPT (2022-11-30), which the spec names (§5.4);
>   - every flagship model announcement by OpenAI, Anthropic or Google's AI labs (listed as "Google"
>     or "Google DeepMind") in a named source between 2022-11-30 and 2025-03-31.
>
>   The rule's terms:
>   - **Named source.** Wikipedia, "List of large language models", revision 1381207107 [facts §4].
>   - **Flagship.** Every row of that source from those developers, except open-weights small models
>     (Gemma) and a tier of a model family already listed (Gemini Ultra, a tier of Gemini 1.0).
>   - **Day.** The source's date where it gives a day. Otherwise the developer's own announcement
>     date in the source's month, verified in the facts file. Where the developer's page and the
>     developer's own model identifier disagree on the day, the earlier date is used, so that the
>     [0, +k] window contains the announcement either way. This applies only to Claude 3.5: the page
>     shows 2024-06-21 and the identifier `claude-3-5-sonnet-20240620` gives 2024-06-20.
>   - **Trading days.** Day 0 is the announcement date; if that is not a trading day, day 0 is the
>     next trading day. Whether any date is an NYSE holiday is unverified for 2022–2025 [facts §4].
>     It is checked mechanically after the tag against the dates in the frozen files.
>
>   Only model-release dates are used, never dates chosen from market reactions.
> - **Event dates under the rule (14).**
>   - 2022-11-30 ChatGPT
>   - 2023-03-14 GPT-4
>   - 2023-05-10 PaLM 2
>   - 2023-07-11 Claude 2
>   - 2023-11-21 Claude 2.1
>   - 2023-12-06 Gemini 1.0
>   - 2024-02-15 Gemini 1.5
>   - 2024-03-04 Claude 3
>   - 2024-06-20 Claude 3.5
>   - 2024-09-12 OpenAI o1
>   - 2025-02-05 Gemini 2.0 (the source's date; the first 2.0 Flash Experimental announcement,
>     2024-12-11, is not used)
>   - 2025-02-24 Claude 3.7
>   - 2025-02-27 GPT-4.5
>   - 2025-03-25 Gemini 2.5
>
>   **Excluded by the rule:**
>   - GPT-4o (2024-05-13) and o3-mini (2025-01-31), which are not in the source's table;
>   - DeepSeek-R1, whose developer is not one of the three named;
>   - Gemma and Gemini Ultra.
>
>   The draft list (ChatGPT, GPT-4, Claude 3, GPT-4o, DeepSeek-R1) is replaced.
>
>   **Disclosure.** The rule's exceptions were chosen with the source's list in view: excluding
>   Gemma and Gemini Ultra, adding ChatGPT by name, and accepting that GPT-4o is absent from the
>   source were each decided after the source's rows, and therefore the resulting dates, had been
>   seen. They are exploratory parameters, and are labelled as chosen with the list in view.
> - **Event windows.** Abnormal return = industry excess return minus its FF5+UMD fit, estimated over
>   trading days [−250, −21]. CARs over [0, +5] and [0, +20], and [0, +9] for the Eisfeldt, Schubert &
>   Zhang (2023) comparison. Each industry CAR is regressed on exposure across industries.
> - **Tercile portfolios.** FF49 sorted on exposure: top 16 minus bottom 16. Membership is fixed at
>   formation, because exposure is static.
>   - **Weighting (P8, chosen):** monthly cap reweighting. At the start of each month, weights within
>     a leg are proportional to the industry's market capitalisation at the prior month-end (average
>     firm size × number of firms, from the frozen `ff49_monthly` file). It is not buy-and-hold from
>     formation.
>   - **Equal-weighted legs** are reported as robustness (P19).
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
> dates and portfolio rules. The objective rule removes the choice of which launches count.
> *Alternatives:* buy-and-hold terciles from formation; a different named event source. Further
> exploratory analyses may be added later only as labelled additions in the deviations log (§11).

---

## 9. Data freeze

Every block marked GENERATED below is produced from the files by `uv run python scripts/pap_freeze.py`,
run with the code tree at the commit in §9.2. The script:
- reads `data/raw/MANIFEST.json`;
- recomputes each raw file's SHA-256 on disk and refuses on a mismatch;
- reads `git rev-parse` for HEAD at generation and the blobs of `confirm_h5.py` and `power.py`, and
  refuses if `src/`, `pyproject.toml` or `uv.lock` is uncommitted or a blob differs on disk;
- copies the Frozen values list of `docs/pap/power.md` verbatim.

Nothing inside those blocks is typed by hand.

### 9.1 Raw data: `data/raw/MANIFEST.json`

<!-- BEGIN GENERATED: MANIFEST table -->
Generated by `scripts/pap_freeze.py` from `data/raw/MANIFEST.json`: **49 keys**; every file's SHA-256 recomputed on disk and equal to the recorded value. SHA-256 of `MANIFEST.json` itself: `eea2ca2dfe0bc77f4c54d652a1702c539087039f818b87aa8e9f5eea32b92a0b`.

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
| `onet_29_3_dwa_reference` | `onet/db_29_3_dwa_reference.txt` | 187200 | 2026-10-22T02:15:59Z | `e38a5b529a06d6803dd80d119f2bff4e1ce9507724ffd648d1f7b20983ab9d18` |
| `onet_29_3_tasks` | `onet/db_29_3_task_statements.txt` | 2759559 | 2026-10-21T21:54:30Z | `fecdcda81a4b8a28e750a6c75ed8bf2d0a9b71186e5be37eec8dc6cef7985d1a` |
| `onet_29_3_tasks_to_dwas` | `onet/db_29_3_tasks_to_dwas.txt` | 1197935 | 2026-10-22T02:15:59Z | `6cb7098b09a6a03cc730b544bd7a17b1eac5d0b5beda947c4f901c42f5a713d6` |
| `sec_tickers` | `sec/company_tickers_exchange.json` | 523851 | 2026-10-21T21:13:25Z | `6c29e2e3db973d4479875164603c2434f81ad22e14c9f1694999aca9cca246cb` |
<!-- END GENERATED: MANIFEST table -->

The market-data end date is frozen at **2026-08-31**: the last date of the frozen French daily files.
French revises its files retroactively; only the frozen files above are used. A later AEI release can
appear only in a clearly marked appendix (spec §5.4.1).

### 9.2 Code

<!-- BEGIN GENERATED: code binding -->
- Code commit the plan binds to, HEAD at generation: **`75a5eed5af191f7ca89ee09cd1efdedeab4f34bd`** ("docs(pap): P-H5 adds the untracked-file check (e); §9 regenerated"), from `git rev-parse HEAD` when this block was generated.
- `src/aideleg/confirm_h5.py` git blob: **`f581264ae9c982ff6a84eb1d1e2f465d18544144`** (`git rev-parse HEAD:src/aideleg/confirm_h5.py`), with `PRIMARY_NULL = "bbar"`.
- `src/aideleg/power.py` git blob: **`a353a7c2683d0cc2e9663e17d3835055b3bb63fc`** (`git rev-parse HEAD:src/aideleg/power.py`).
<!-- END GENERATED: code binding -->

- The commit above is **HEAD at generation**: the commit `scripts/pap_freeze.py` ran on, after the
  last code change and before the PAP commit that records it. The tag `pap-v1` is created on a
  descendant whose code is unchanged. **Signing check**, run before the tag is pushed:
  `git diff --quiet <bound> pap-v1 -- src pyproject.toml uv.lock`, with `<bound>` the commit above;
  it must succeed. `confirm_h5` enforces the same binding against `pap-v1` in code (§0.5, P-H5 step 2).
- The exposure, benchmark, power and confirmatory modules at this commit define every constructed input
  and every computation of the confirmatory market tests.
- Plan 2 and plan 3 code implements this plan; it does not change these modules' outputs for the
  primary specifications. A change that would is a deviation (§11).
- Environment: Python 3.12 via `uv` (lockfile at that commit): Polars 2.0.0, NumPy 2.5.4,
  SciPy 1.18.1, statsmodels 0.15.0.

### 9.3 Confirmatory inputs

| Object | SHA-256 / hash |
|---|---|
| `data/derived/aei_panel.parquet` | `15ba38ec8b65c7311cace1823f713126cd3fccafca376cd6e63769c92ddbb370` |
| `data/derived/exposure_ff49.parquet` | `8d403a702b6a1007b426b510156f6c24e5e7c928e3036bacf247b45973a00c40` |
| `data/derived/benchmark_ff49.parquet` | `032003801622938c3e7e48d35969ec980cdc0dc02b5279c0874e98f39a289b1f` |
| Design B vector `(ff49, ff49_short, z_delegation, z_aioe)`, 49 rows, no nulls, CSV with 10-digit floats (command below) | `bddc49d49b9565bba8daa8bc6fdb709043a6007090b9e7faf7dda1001229ac36` |
| `src/aideleg/confirm_h5.py` and `src/aideleg/power.py` (git blobs, `PRIMARY_NULL = "bbar"`) | see the generated code block in §9.2 |

The parquet hashes are informational (parquet bytes can differ across library versions); they were
recomputed at the §9.2 commit and are unchanged from the draft. The binding checks are the vector hash,
which `confirm_h5` verifies before reading any return, and the script's blob hash:

```
uv run python -c "import hashlib; from aideleg.power import load_exposure; \
df = load_exposure().select('ff49','ff49_short','z_delegation','z_aioe'); \
print(hashlib.sha256(df.write_csv(float_precision=10).encode()).hexdigest())"
git rev-parse HEAD:src/aideleg/confirm_h5.py
```

**Frozen null values (quoted verbatim from `docs/pap/power.md`, Frozen values).** `confirm_h5.FROZEN`
equals this list (tested by `test_frozen_constants_equal_power_md`). Decimal units (0.0227 = 2.27 pp).
s = sd of the 378 overlapping slopes (ddof = 1); bbar = their mean; q = empirical centred quantiles;
crit = max(t21, q). If D21's alternative is chosen, these values are unchanged; only `PRIMARY_NULL`
and the blob hash change.

<!-- BEGIN GENERATED: frozen values -->
- `t21_0.025` = 2.413845016599001
- `t21_0.05` = 2.0796138447276795
- `s_h5` = 0.022709785806829905
- `bbar_h5` = 0.01650391358632771
- `q_h5_0.9875` = 2.08027722179776
- `q_h5_0.975` = 1.896096850699846
- `s_h5_r12` = 0.02211139470714751
- `q_h5_r12_0.9875` = 1.9961589827719277
- `q_h5_r12_0.975` = 1.8109235160395372
- `bbar_h5_r12` = 0.013167677839651046
- `s_h5_r13` = 0.03195141979632061
- `q_h5_r13_0.9875` = 1.9840047664550942
- `q_h5_r13_0.975` = 1.8881504350635059
- `bbar_h5_r13` = 0.016659044239269352
- `s_h5b` = 0.02560409470770698
- `bbar_h5b` = 0.01216949247017634
- `q_h5b_0.9875` = 2.13084415252217
- `q_h5b_0.975` = 1.862988779992977
- `s_h5b_r12` = 0.02981733257175669
- `q_h5b_r12_0.9875` = 2.3039239552905793
- `q_h5b_r12_0.975` = 1.9664328516491718
- `bbar_h5b_r12` = 0.005386065025872529
- `s_h5b_r13` = 0.037132757280610024
- `q_h5b_r13_0.9875` = 2.166482901101018
- `q_h5b_r13_0.975` = 1.962325225285184
- `bbar_h5b_r13` = 0.010684812193646077
- `crit_h5_0.025` = 2.413845016599001
- `crit_h5_0.05` = 2.0796138447276795
- `crit_h5b_0.025` = 2.413845016599001
- `crit_h5b_0.05` = 2.0796138447276795
- `crit_h5_r12_0.025` = 2.413845016599001
- `crit_h5_r12_0.05` = 2.0796138447276795
- `crit_h5b_r12_0.025` = 2.413845016599001
- `crit_h5b_r12_0.05` = 2.0796138447276795
- `crit_h5_r13_0.025` = 2.413845016599001
- `crit_h5_r13_0.05` = 2.0796138447276795
- `crit_h5b_r13_0.025` = 2.413845016599001
- `crit_h5b_r13_0.05` = 2.0796138447276795
<!-- END GENERATED: frozen values -->

### 9.4 Data still to be acquired

> **[PROPOSED — Ajai to confirm] D20. Data acquired after the freeze.**
> *Status:* the O\*NET 29.3 "Tasks to DWAs" and "DWA Reference" files, which the draft listed as
> blocking, were acquired in Task 15b and are in §9.1. Nothing confirmatory is left to acquire.
> *Recommended:* acquire these after the freeze. They are pre-specified here and used only in
> robustness or exploratory work:
> - the BLS SOC 2010→2018 crosswalk (R14);
> - O\*NET 29.3 Work Context (R27);
> - OEWS May 2025 national (R1, if needed);
> - OEWS May 2023 industry and national files, and the O\*NET 29.2 task statements (R32);
> - Ken French Siccodes30/48 and the 30- and 48-industry daily return files (R6);
> - the SEC EDGAR submissions API, full-index `form.idx` files, full-text search results, and 10-K
>   documents (H6).
>
> Each is recorded in the MANIFEST when acquired, and its SHA-256 is logged in §11 as an addition.
> An addition is not a deviation.
>
> *Rationale:* every confirmatory input must be frozen before any post-seal return is read. Robustness
> and exploratory inputs can come later because their use is fixed here.
> *Alternative:* acquire everything before the tag. This is safer for the record, but it delays the
> freeze and adds nothing to the confirmatory tests.

---

## 10. Corrections to the design spec

The spec is not edited. Where it is wrong on a fact, or where this plan departs from it, the item is
listed here with the correction this plan applies.

### 10.1 Corrections of fact

- **S1. §5.3, real-time weights.**
  - *Spec:* OEWS May 2024 is "the latest data before the first market-test formation date".
  - *Correction:* OEWS May 2024 was released on **2025-04-02**, after the Design B formation date
    (2025-03-27) and one trading day into the return window. The vintage public at formation was May
    2023. The O\*NET 29.3 task statements used to link AEI tasks to occupations were released in May
    2025, also after formation.
  - *Consequence:* Design B is out of sample in its AEI data, but not strictly real-time in its
    occupation weights and task links. Strict-real-time variant R32 [facts §1; §2.1].
- **S2. §5.4.1, the start of AI autonomy.**
  - *Spec:* "Mean AI autonomy (from release 3)".
  - *Correction:* `ai_autonomy_mean` is published from **r4** (2026-01-15), so it covers r4–r6
    [MET; audit, "Decisions the audit forces", item 2].
- **S3. §5.4, Design A's release.**
  - *Spec:* Design A uses exposure "built from the *earliest* release only (Feb 2025)", i.e. r1
    (2025-02-10).
  - *Correction:* r1 has only an aggregate collaboration split, with no task- or occupation-level
    automation (as spec §5.4.1 itself says). The earliest release that can form a delegation index is
    r2 (2025-03-27). So A_r2 is the spec's Design A, numerically identical to Design B. This plan's
    A_pooled (r2–r6) is an addition. It uses releases published during and after the return window,
    so it contains look-ahead and is labelled so.
- **S4. The 5 pp plausibility threshold.**
  - *Spec:* §5.4 says "implausibly large" and gives no number.
  - *Correction:* the 5 pp figure comes from plan 1 (Task 15, Step 1, item 7), committed before the
    power analysis ran. It is confirmed by Ajai after the MDE is known (§7, D11). Earlier wording in
    `power.md` that called it "the spec's" threshold has been corrected.
- **S5. §4, the 16.6% of employment with no AEI match.**
  - *Spec:* 16.6% is the complement of the "83.4% of US employment" in the spec's preliminary join
    test, run before the matching rules (rollup, hybrid codes) were built.
  - *Correction:* the audited figures, which supersede it, measure three different things:
    - **7.39%** of May 2024 employment is in OEWS occupations with no AEI r6 published occupation,
      after matching [audit §6];
    - **12.14%** is zero-assigned under Design B (r2, which has fewer matched tasks), the figure that
      matters for the confirmatory test;
    - **6.34%** is zero-assigned under A_pooled.

### 10.2 Departures from the spec (each a proposed decision or a stated change)

- **D-1. §5.4.1, H5/H5b inference.** RI is replaced as primary by the historical-null test (D10)
  because of its documented size (§3.2). RI remains secondary.
- **D-2. §5.4, the wild-cluster bootstrap.** Not used for H5/H5b, which have no cluster structure
  (§3.2). It is used for H2 (D22).
- **D-3. §5.3, the crosswalk.** The spec says "employment-weighted crosswalk". The implementation
  splits equally (D23). The spec's variant is R33.
- **D-4. §5.2, H1 standard errors.** One-way clustering by occupation becomes two-way clustering by
  occupation and task (§4). This is intended as a conservative change; the spec's one-way version is
  R38.
- **D-5. §2, H5 null.** H5/H5b are tested against the frozen historical slope b̄ rather than zero
  (D21), which is a narrower claim than the approved wording. This needs Ajai's approval.
- **D-6. §2 and §5.2, H2.** H2 is reworded as "measured within-task automation rises", tested outside
  the RQ1 Holm family at α = 0.0125 (the Holm family {H1, H3, H4} at 0.0375), with a release-level
  co-condition (D22). Its primary span is r2–r5 rather than
  "Dec 2024 → May 2026" (D2).
- **D-7. §5.4, event dates.** The spec's "pre-registered model-launch dates" are fixed by an objective
  rule over a named source (D19).

---

## 11. Deviations

*None at freeze.*

Any change after `pap-v1` to a hypothesis, specification, sample, inference, decision rule, frozen
input or the confirmatory script is recorded here with its date, the reason, Ajai's approval, and
whether results had been seen at the time. A change made after a confirmatory result has been seen
demotes that hypothesis to exploratory, and the pre-registered specification is still reported as the
primary result (§0.5).
