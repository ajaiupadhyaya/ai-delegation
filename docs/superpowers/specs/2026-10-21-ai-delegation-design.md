# Delegating to the Machine — Design

**Working title:** *Delegating to the Machine: How People Hand Work to AI, and Whether Equity Markets Priced It*
**Date:** 2026-10-21 · **Author:** Ajai Upadhyaya · **Status:** approved 2026-10-21

Marked throughout: **[owner]** = decided by Ajai; **[call]** = a default chosen by Claude, open to override.

---

## 1. Intent

A research paper plus replication repository that shows a quantitative-analyst audience (interviewers, industry readers, students) two things at once **[owner]**:

1. Technical, quant-grade analysis of a large, messy, multi-release dataset: harmonisation, index construction, asset-pricing tests, formal inference.
2. The ability to connect the numbers to human behaviour: how and when people *delegate* work to AI rather than *collaborate* with it, read through the psychology of trust in automation.

The standard is an **academic research team's working paper** **[owner]**: thorough, highly refined, every number reproducible from raw downloads, every claim bounded by its evidence. It is explicitly *not* a quick analysis on a web dashboard **[owner]**.

### Why this framing
AI's labour-market effects are usually measured with *theoretical* exposure scores (what an LLM *could* do). The Anthropic Economic Index (AEI) instead records *observed* usage, including *how* people work with the model — handing the task over (automation) versus iterating, learning and checking (augmentation). That collaboration mode is a behavioural variable. The paper's contribution is to (a) document the behavioural structure of delegation, (b) turn it into industry-level exposure measures that separate *usage* from *delegation*, and (c) test whether equity markets' repricing of industries since ChatGPT lines up with observed delegation rather than theoretical exposure.

## 2. Research questions and candidate hypotheses

**Claude drafted the hypotheses below, and Ajai approved all of them as written on 2026-10-21 [owner].** They become the pre-registered claims when the pre-analysis plan is frozen (§7). Any later change goes through Ajai and is logged as a deviation.

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

A null on RQ3 is a complete, publishable result and will be reported with the same prominence as a positive **[call, from quant-rigor; Ajai did not object]**.

## 3. Goals, non-goals, anti-goals

**Goals**
- A ~30–45 page working paper (PDF, LaTeX-quality typesetting) with abstract, introduction, literature, data, methods, results, robustness, limitations, conclusion, references, appendices.
- A 2-page executive brief at the front for non-specialist readers.
- A public-ready replication repo: one command rebuilds every table and figure from raw downloads.
- Publication-grade figures in one consistent visual system, including maps.

**Non-goals**
- No web dashboard or interactive app as the deliverable **[owner]**.
- No firm-level stock picking, no trading strategy, no claim of deployable alpha.
- No forecasts of job loss or displacement.

**Anti-goals (failure even if it "works")**
- Any claim that treats conversation data as data about workers ("accountants use AI" instead of "conversations matched to accounting tasks"). AEI measures usage, not jobs or labour-market outcomes.
- Look-ahead bias in the market tests, or exposure scores that use information after the return window they explain.
- Specification searching: running many market specs and reporting the best. Every confirmatory test is fixed in the pre-analysis plan before market returns are touched.
- Pretty charts carrying weak claims; causal language the design cannot support.

## 4. Data (verified 2026-10-21 by download and inspection)

| Source | What | Verified facts | Licence |
|---|---|---|---|
| **AEI** (`Anthropic/EconomicIndex`, Hugging Face) | Usage by O\*NET task, SOC occupation, request topic, country, US state; collaboration modes; AI autonomy; time; education | 6 releases: 2025-02-10, 2025-03-27, 2025-09-15 (data 2025-08-04→11), 2026-01-15 (2025-11-13→20), 2026-03-24 (2026-02-05→12), 2026-06-26 (monthly, Apr + May 2026). Latest: 718 SOC occupations, 2,820 O\*NET tasks, 121 countries, 51 metrics. Schemas differ across releases (three distinct layouts). Also `labor_market_impacts/job_exposure.csv`, `task_penetration.csv`, `robot_exposure/`. ~800 MB total. | CC-BY data, MIT code |
| **O\*NET** | Task statements, task→occupation, DWA/IWA/GWA hierarchy | Shipped inside AEI releases; O\*NET 29.x for crosswalks | CC-BY |
| **BLS OEWS by industry** | Employment and wages by occupation × NAICS industry | `oesm24in4.zip`, `oesm25in4.zip` download (BLS requires a contact User-Agent). 85 NAICS-3 industries, 830 detailed occupations. **Join test: 96% of AEI occupations match; matched occupations = 83.4% of US employment.** | Public domain |
| **Ken French Data Library** | 49 industry portfolios (daily/monthly, VW/EW), FF5 + momentum factors, industry BE/ME | Daily file runs to 2026-08-31 (CRSP 202608). Industries defined by **SIC**. | Free, cite |
| **SEC EDGAR** | Company SIC codes (submissions API); full-text search of 10-Ks | Both endpoints respond; e.g. 877 10-Ks in 2025 contain "generative AI". Rate limit 10 req/s, contact UA. | Public |
| **Theoretical exposure benchmarks** | Eloundou et al. (2024) GPT exposure; Felten, Raj & Seamans (2021) AIOE | Public on GitHub — **availability to be confirmed in Stage 0** | Per source |
| **Geography covariates** | GDP, working-age population | Shipped in AEI release 2025-09-15 inputs (IMF, World Bank, BEA, Census) | Per source |

The 16.6% of employment with no AEI match is mostly hands-on occupations with negligible usage. Default treatment: assign zero usage, and show robustness to dropping them **[call]**.

## 5. Methods

### 5.1 Harmonised AEI panel
- Parse the three schema generations into one long table: `release × source(platform) × geo × taxonomy(onet|soc|request) × node × metric → value`, with explicit `unpublished` vs `zero` distinction (AEI omits cells below privacy thresholds).
- Record per release: sampling window, platform scope (Free/Pro → Free/Pro/Max + Cowork), classifier/model version, and taxonomy version (collaboration v1 vs v2). These are **measurement regime changes**; trend analysis must separate behavioural change from measurement change.
- Measurement-drift diagnostics: compare overlapping metrics across adjacent releases; restrict H2 to metrics whose definition is stable; report a "definition-stable" and an "all-releases" series.
- Data-quality tests in code: shares sum to ~100 within node/geo, codes valid against O\*NET/SOC, row counts per release pinned.

### 5.2 Behavioural analysis (RQ1)
- Descriptive anatomy: collaboration-mode composition by occupation major group, wage decile, education requirement; Lorenz/concentration of usage across tasks.
- **H1:** task-level regressions of delegation on task/occupation characteristics (education years, log median wage, O\*NET task family fixed effects), weighted by usage; SEs clustered by occupation.
- **H2:** within-task change across releases with task fixed effects and release effects; event-style plot by release; definition-stable series is primary.
- **H3:** validation share on error-cost indicators with task-family FE.
- **H4:** country cross-section (and US states) with task-mix adjustment (shift-share style decomposition: how much of a country's delegation share is its task mix vs within-task behaviour). Choropleth maps.
- Inference: cluster-robust SEs; Holm correction across the RQ1 family; effect sizes with CIs, not just stars.

### 5.3 Exposure indices (RQ2)
For occupation *o* and industry *j*, with pre-period OEWS employment weights *w_oj* (OEWS May 2024, the latest data before the first market-test formation date that does not use outcomes) **[call]**:
- Usage intensity *U_o* = AEI usage share of *o* ÷ *o*'s share of US employment.
- Delegation intensity *D_o* = *U_o* × automation share of *o*; augmentation *A_o* analogously.
- Industry index *E_j* = Σ_o *w_oj* · *X_o*, standardised.
- **NAICS → SIC → FF49 mapping:** employment-weighted crosswalk (Census NAICS–SIC concordance via 1997 bridge); mapping weights and coverage reported; sensitivity to an alternative many-to-one assignment.
- Validation: rank correlation with Eloundou and Felten scores; scatter of "could" vs "does"; top/bottom industries tables.

### 5.4 Market tests (RQ3)
**Timing — the central rigour issue.** AEI data begin Dec 2024, after ChatGPT. **Ajai approved this framing on 2026-10-21 [owner]:**
- Design B is the only confirmatory market test.
- Design A, including the ChatGPT-launch event study, is exploratory and labelled that way wherever it appears.
- The power analysis runs before the PAP freeze. If the minimum detectable effect is implausibly large, the paper is led by RQ1 and RQ2, and RQ3 is reported as "what the market evidence can and cannot yet say". In that case the Design B test is still run and reported.

The two designs, labelled distinctly in the paper:
- **Design A — structural exposure (exploratory, 2022–2026 window).** Treat observed delegation as revealing a slow-moving property of an industry's *task content*. Identifying assumption stated explicitly and attacked in robustness: exposure built from the *earliest* release only (Feb 2025), compared against theoretical scores that pre-date 2022.
- **Design B — strict out-of-sample (confirmatory).** Exposure formed from release-2 data only (published 2025-03-27; see §5.4.1); returns measured from 2025-04-01 to 2026-08-31 (17 months). No later release informs these portfolios.

**Tests**
- Event study: industry CARs around ChatGPT launch (2022-11-30) and pre-registered model-launch dates; abnormal returns vs FF5 + momentum estimated on a pre-window; cross-sectional regression of CAR on exposure.
- Calendar-time portfolios: high-minus-low exposure terciles of the 49 industries, value-weighted, monthly; alphas vs CAPM, FF3, FF5+UMD; Newey–West SEs.
- Cross-sectional regressions (Fama–MacBeth) of monthly industry returns on exposure plus industry controls (BE/ME, momentum, size).
- Benchmark replication: reproduce the direction of Eisfeldt, Schubert & Zhang (2023) with theoretical exposure before adding delegation exposure (H5b horse race).
- **Small-N inference (49 industries):** permutation/randomisation inference (shuffle exposure across industries, ≥10,000 draws), wild-cluster bootstrap, stationary block bootstrap for portfolio Sharpe; Romano–Wolf or Holm across the pre-registered exposure variants; minimum detectable effect computed and reported up front so a null is interpretable.
- Portfolio statistics per quant-rigor where meaningful: Sharpe with PSR, bootstrap CIs, turnover, cost sensitivity (0/5/15/30 bps). These portfolios are *measurement devices*, not strategies; DSR reported across the variants tested.

### 5.4.1 Confirmatory core and testing family **[call]**
- **Primary delegation measure everywhere:** automation share (`collaboration_bucket_automation_pct` and its earlier equivalents). It exists at task level from release 2 (2025-03-27, `automation_vs_augmentation_by_task.csv`); release 1 has only an aggregate. Mean AI autonomy (from release 3) is a secondary RQ1 measure only.
- **Design B formation therefore uses release 2** (published 2025-03-27); returns run 2025-04-01 → 2026-08-31. Nothing published later informs Design B.
- **One primary specification per market hypothesis.** H5: the cross-sectional slope of industry FF5+UMD alphas (estimated on daily value-weighted returns over the Design B window) on standardised delegation exposure, with randomisation inference. H5b: the same regression with Felten–Raj–Seamans AIOE added as a control. The confirmatory family is {H5, H5b}, with a Holm correction. Everything else (tercile portfolios, Fama–MacBeth, event studies, alternative indices and weights) is secondary and reported as robustness.
- **Theoretical-exposure control:** Felten, Raj & Seamans (2021) AIOE is primary because it pre-dates 2022. Webb (2020) is the fallback. Eloundou et al. (2023/2024) is used only for descriptive "could vs does" comparisons, since it was published after ChatGPT.
- **Data freeze:** the AEI release set and the market-data end date are frozen at the PAP tag. Later releases can appear only in a clearly marked appendix.

### 5.5 Talk vs use (H6)
- EDGAR full-text search counts of a pre-registered AI term dictionary in 10-K filings per firm-year (2019–2025), normalised by filing length where obtainable; firms mapped to FF49 via SIC; industry "talk" index.
- AI-washing gap = talk residual after regressing talk on usage exposure. Descriptive first; return association exploratory unless promoted.

### 5.6 Robustness (pre-specified list)
Alternative weights (OEWS 2025, wage-bill weights), excluding unmatched occupations, API (1P) vs Claude.ai usage, equal- vs value-weighted portfolios, FF30/FF48 industry granularity, dropping tech industries (to show results are not "tech beta"), excluding 2023 AI-mega-cap rally months, placebo event dates.

## 6. Constraints
- **Wording rule:** describe AEI as usage — "conversations matched to X tasks"; never infer job risk, displacement or reassurance from it; say "labour market".
- **Reproducibility:** every raw file downloaded by script with recorded URL, date and SHA-256; pinned environment; seeded randomness; `make all` rebuilds from scratch. Large raw data are not committed; derived small tables may be.
- **Citations:** every external dataset and paper cited (BibTeX). AEI cited per its README.
- **Ethical/legal:** respect SEC and BLS rate limits and UA rules; CC-BY attribution.
- Lives in its own repo, not OhCamel **[owner]**.
- **No deadline; the audience is Ajai's own portfolio [owner].** Thoroughness takes priority over speed. Every component stays in scope, including the full 10-K text pipeline, US-state maps and the full robustness list. No stage is cut for time.

## 7. Process (how it gets made)
1. **Stage 0 — Data acquisition & audit.** Download scripts, checksums, a data audit memo (coverage, missingness, schema differences, measurement regimes).
2. **Stage 1 — Harmonised panel + tests.**
3. **Stage 2 — Pre-analysis plan (PAP).** Ajai approves hypotheses; PAP frozen and committed (git tag + timestamp) **before any market-return analysis runs**. Deviations after this point are logged in a "deviations from PAP" appendix.
4. **Stage 3 — Behavioural analysis (RQ1).**
5. **Stage 4 — Exposure indices (RQ2).**
6. **Stage 5 — Market tests (RQ3) and talk-vs-use.**
7. **Stage 6 — Robustness, red-team review** (an adversarial reviewer pass trying to break each headline result).
8. **Stage 7 — Paper, brief, figures; replication check** from a clean clone.

## 8. Tooling **[call]**
Python 3.12 managed with `uv`; DuckDB + Polars for data; statsmodels / linearmodels for econometrics; matplotlib with a custom style (+ geopandas for maps); pytest for data and transform tests; Make for the pipeline DAG; Quarto rendering to PDF via XeLaTeX (installed) and to HTML as a secondary format. Repo at `~/Documents/ai-delegation`. Pushing to a public GitHub repo happens only with Ajai's go-ahead.

## 9. Left to the builder
File layout, module boundaries, exact figure list and palette, crosswalk implementation details, the specific term dictionary draft for H6 (subject to PAP approval), and the paper's section-level wording.

## 10. Key references (seed list)
Acemoglu & Restrepo (2019) tasks framework · Autor, Levy & Murnane (2003) · Eloundou, Manning, Mishkin & Rock (2024) *Science* · Felten, Raj & Seamans (2021) · Webb (2020) · Eisfeldt, Schubert & Zhang (2023) NBER w31222 · Brynjolfsson, Li & Raymond (2023/2025) · Noy & Zhang (2023) *Science* · Dell'Acqua et al. (2023) "jagged frontier" · Dietvorst, Simmons & Massey (2015) · Logg, Minson & Moore (2019) · Parasuraman & Riley (1997) · Lee & See (2004) · Handa et al. (2025) AEI · Fama & French (1993, 2015) · Fama & MacBeth (1973) · Newey & West (1987) · Romano & Wolf (2005) · Bailey & López de Prado (2014) · Hassan et al. (2019) text-based firm exposure.
