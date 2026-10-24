# Red-team wording requirements for the paper prose (Plan 4 Task 16)

These requirements bind the paper prose of Tasks 22–31: the abstract, the brief, the
introduction, the results sections, the conclusion, the captions and the README. Each one
resolves a "wording fixed" or "label fixed" finding of the Task 16 adversarial review, or a
"holds" finding whose evidence asked for something to be named. The rows are listed in
`docs/redteam/challenges.csv` and `docs/redteam/log.md`. Task 31's prose check reads every item.
Numbers named here are the referees' evidence. The prose takes every number from a generated
file (`{{< var … >}}` or a generated include) and never types one in.

Referee row = `key Cn` in `challenges.csv`.

## Hypothesis decisions and coefficients (RQ1)

**W-1. Decision phrasing.** A non-rejected RQ1 hypothesis is written as "H*k* is not
supported: the null (…) is not rejected at *level*". Examples: "H1 is not supported: the null
(β_e = 0 or β_w = 0) is not rejected at 0.01875", "H2 is not supported: the release-level
co-condition fails", "H3 is not supported: the null γ = 0 is not rejected". "H*k* is not
rejected" is never written on its own, because it reads as if the hypothesis survived. The
committed decision texts stay unedited.
Rows: `rq1.H1.decision C10`, `rq1.H2.decision C10`, `rq1.H3.decision C10`.

**W-2. β_w's sign.** The prose says that β_w is opposite in sign to H1's prediction and is not
significant at its Holm level. It therefore neither supports H1 nor, under PAP §0.2 and C-21,
contradicts it. Its nominal p (below 0.05) is never called significant. Prose never writes
"higher-wage occupations delegate more".
Row: `rq1.H1.beta_w C10`.

**W-3. H2 rests on r2, and drift is not separable.** Beside β of H2 the prose states three
things. First, the measured rise is one r2-to-r3 step followed by a fall (Plan 2's release
effects). Second, leaving out r2 reverses the sign of β (`docs/results/diagnostics/h2_influence.md`,
D-3). Third, the r2-to-r3 step coincides with the change of the classified-conversation base
(r2 renormalises without `filtered`; r3–r5 exclude `not_classified` and `none`; PAP §5), so
classifier or platform drift cannot be separated from behaviour. R22 `api_r3_r5` and R23 are
named as rows that run the other way.
Rows: `rq1.H2.beta C12`, `rq1.H2.beta C8`.

**W-4. The balanced panel's drops.** Beside H2 the prose reports the tasks and the usage share
that the D2 balanced-panel rule removes. It takes both from the `balancing_removed` row of
`docs/results/diagnostics/h2_influence.md` (D-3) and labels them descriptive.
Rows: `rq1.H2.beta C7`, `rq1.H2.p_cluster C7`, `rq1.H2.p_wild C7`, `rq1.H2.decision C7`.

**W-5. Influence is reported from the D-3 files, and the moving rows are named.** The prose
labels these as "post-result diagnostic (PAP §11 D-3); exploratory; not a decision":
- **H1.** Report the leave-out of SOC major group 15, occupation 15-1299 and the top 3
  occupations from `docs/results/diagnostics/h1_influence.md`. Name the robustness rows that
  move the coefficients most: R26 `gwa` and `dwa`, R24 r4 and r5 (β_w changes sign), R24
  `r6_1p_api`, and R10 `ub`.
- **H2.** Report the leave-one-release-out from `h2_influence.md` (see W-3).
- **H6.** Report the leave-one-industry-out from `h6_influence.md`. Name the R29 parts whose
  CIs cover 0 (`change_2019_2024`, `float_weighted`, `pre_formation_2025`) beside the headline.
No diagnostic is called significant or counted.
Rows: `rq1.H1.beta_e C8`, `rq1.H1.beta_w C8`, `rq1.H2.beta C8`, `h6.spearman.rho C8`,
`h6.spearman.ci.lo C8`, `h6.spearman.ci.hi C8`.

**W-6. The H6 p is nominal.** The H6 Spearman's p is quoted only from
`docs/results/diagnostics/h6_influence.md`, together with its method (t-approximation, n − 2
df). It is called "nominal and exploratory (PAP §11 D-3)", sits in no testing family and is
never called significant.
Rows: `h6.spearman.rho C11`, `h6.spearman.ci.lo C11`, `h6.spearman.ci.hi C11`.

## RQ2 and the exposure measure

**W-7. RQ2 shares occupational weights and depends on D3.** RQ2 prose states two things.
First, ρ inherits the same OEWS occupation-to-industry weights on both sides (AEI exposure and
AIOE or Eloundou), so part of the correlation is common occupational mix. Second, ρ depends on
the D3 zero assumption, and R3 lowers it most.
Rows: `C12` of all twelve `rq2.B.*` keys.

**W-8. D3 zeros are unpublished, not measured as zero.** Wherever the zero-assigned
employment share is quoted, the prose says that those occupations are unpublished in AEI and
are assigned zero by assumption (D3). They are not measured as zero.
Row: `d3.zero_assigned_pct C10`.

**W-9. The S1 timing caveat goes beside RQ2 and H5/H5b.** Beside every RQ2 Spearman and every
H5/H5b number (b̂, T, p, intervals, wording, decision, the b = 0 secondaries), the prose says
three things. Design B's OEWS May 2024 weights were released on 2025-04-02, after the
2025-03-27 formation date and inside the return window, and O*NET 29.3 links postdate
formation (PAP §10 S1; C-74: its task text is byte-identical to 29.2). Design B is out of
sample in AEI data only (PAP §2.1, "not strictly real-time"). The prose then cites R32, the
strict real-time row (OEWS May 2023), from `docs/results/robustness/R32.md`, and labels R1
consistently as look-ahead.
Rows: `C3` of all twelve `rq2.B.*` keys and of the 22 `rq3.h5*` keys listed under C3 in
`challenges.csv`.

**W-10. H6 retrieval vintages.** Beside the H6 Spearman and its CI the prose says that two
inputs are fixed at retrieval in 2026, not in 2024. The FF49 industry is each filer's current
SIC from the EDGAR submissions file, applied to every year (C-40). The numerator uses the SEC
full-text search's phrase matching on the retrieval date (PAP §6).
Rows: `h6.spearman.rho C3`, `h6.spearman.ci.lo C3`, `h6.spearman.ci.hi C3`.

## Market nulls and their power

**W-11. The secondary b = 0 nulls.** The H5/H5b b = 0 results are reported only as labelled
secondary T and p ("secondary null b = 0; not part of the decision"). If prose calls one "not
rejected", it uses the P14 sentence with H0: b = 0. The MDE (the same s and c₀.₀₂₅ as the
primary: the H5 or H5b MDE of `confirmatory_h5.md`) is printed beside it wherever it is quoted.
Rows: `rq3.h5.b0.T C10`, `rq3.h5.b0.p C10`, `rq3.h5b.b0.T C10`, `rq3.h5b.b0.p C10`,
`rq3.h5.b0.T C11`, `rq3.h5.b0.p C11`, `rq3.h5b.b0.T C11`, `rq3.h5b.b0.p C11`.

**W-12. The gap–return null gets an MDE or says it has none.** The H6 gap–return association
(`docs/results/h6/gap_returns.md`) is a market null. Beside it the prose prints an MDE from a
generated file or states "no MDE computed (exploratory)". The Spearman itself is not a market
null, so the MDE rule does not apply to it.
Rows: `h6.spearman.rho C11` (evidence: "Not a market null, so the MDE rule does not apply"),
and challenge C11 ("The MDE sits beside each market null").

## Numbers quoted from the right place

**W-13. p from tables, not from decision texts.** RQ1 p-values are quoted from
`docs/results/rq1/confirmatory_table.csv` (through the generated includes), shown as "< 0.001"
under the formatting rule. The "p = 0.0000" of the committed decision texts is never quoted.
Rows: `rq1.H2.p_cluster C10`, `rq1.H4.p_wald C10` (holds, with this note).

**W-14. H4 regressor collinearity.** H4 prose states, without a number, that log AUI and log
GDP per working-age person are strongly correlated across countries (both share the
working-age population denominator), so b₁ and b₂ are weakly separable one by one, even though
their joint Wald test is not. No correlation value is quoted: no generated file reports one
(the referee's 0.916 came from a scratch run).
Rows: `rq1.H4.b1 C12`, `rq1.H4.b2 C12`, `rq1.H4.p_wald C12` (holds, with this note).

**W-15. R24 r5 is named.** Beside the H1 decision the prose names R24 r5 as the one robustness
row under which p_H1 falls below H1's Holm level with both coefficients negative. It is a
pre-registered robustness row that changes no decision (PAP §8.1).
Rows: `rq1.H1.p C8`, `rq1.H1.decision C8` (holds, with this note).

**W-16. The rows that move H5/H5b most are named.** Beside b̂ of H5 the prose names R7 (dropping
Hardw, Softw and Chips), R12 (ranks) and R5 (equal-weighted returns); beside b̂ of H5b it names
R12, R7 and R6 (FF30). All are reported as robustness and change no decision.
Rows: `rq3.h5.b C8`, `rq3.h5b.b C8` (holds, with this note).

**W-17. RQ1 units.** RQ1 log-regressor coefficients are written per unit of the log
(= 100 log points), as the C-81 labels give them. Prose never writes "per log point" for these
coefficients.
Rows: `rq1.H1.beta_w C6`, `rq1.H4.b1 C6`, `rq1.H4.b2 C6` (label fixed, C-81).

## Not prose: Task 33's compare list

**T-1.** Task 33's fresh-clone compare list must include `docs/pap/power.md` (its generated
block, which `power._write` writes before the hand-written interpretation) and
`docs/audit/tables/` (`make audit`). Both reproduced byte-identical in the referee's scratch
rerun (PAP §11 C-81).
Rows: `d11.primary_mde C1`, `d3.zero_assigned_pct C1` (label fixed, C-81).

## Task 31: the variables of the abstract, the brief, §1 and §10

These items come from the Task 31 challenge of the 63 headline keys that
`headlines.scan_headlines()` added (status "declared (Task 31)" in `headlines.csv`). They bind
the prose fixes that follow the Task 31 claims review. The page budget (References on p.45)
and the abstract's 200 words are constraints on how, not on whether, each item is met; where
they conflict the controller decides and records the ruling.

**W-18. Market non-rejections in the abstract and the brief.** "H5 is not rejected" and "H5b is
not rejected" are never written without their H0, for the reason of W-1. The Global Constraints
(plan, "Nulls get the same prominence") require the P14 wording verbatim
(`{{< var rq3.h5.wording >}}`, `{{< var rq3.h5b.wording >}}`), which also puts each MDE beside
its null. Where the abstract cannot hold both sentences, it says at least that the null of no
departure from the 1990–2022 pattern (b = b̄) is not rejected for either, and prints H5b's MDE
(`rq3.h5b.mde`) beside H5b as it prints H5's.
Rows: `rq3.h5.decision_text C10`, `rq3.h5b.decision_text C10`, `rq3.h5b.decision_text C11`.

**W-19. The S1 timing caveat beside the market results of the abstract and the brief.** W-9
applies to the decisions and slopes printed there. The abstract names R32 as the strict
real-time row (or says "not strictly real-time"). The brief's RQ3 paragraph says, beside H5 and
H5b, that the OEWS May 2024 weights were released after formation and inside the return window
and that the O*NET 29.3 links postdate formation; the RQ2 paragraph's sentence does not reach
the RQ3 numbers.
Rows: `C3` of `rq3.h5.decision_text`, `rq3.h5b.decision_text` and the six `rq3.h5*_pp2` keys.

**W-20. Labels on diagnostic and robustness numbers.** The conclusion labels the leave-out-r2 β
"post-result diagnostic (PAP §11 D-3); exploratory; not a decision", as the introduction does
(W-5). The brief labels the balanced-panel drops descriptive (W-4) and names R3 as the
pre-registered robustness row that drops the unpublished occupations.
Rows: `diag.h2.leave_out_release_r2.beta C5`, `diag.h2.balancing_removed.n_tasks C5`,
`diag.h2.balancing_removed.usage_share_pct C5`, `rob.r03.spearman_z_eloundou_vs_z_delegation.estimate C5`.

**W-21. Uncertainty beside robustness and diagnostic estimates.** Where prose quotes a
robustness or diagnostic estimate it gives its interval or p from the generated file, or points
to the table that does. R3's ρ has an industry-bootstrap interval (`R03.csv`), R32's slopes have
intervals and p (`R32.csv`; both non-rejections), and the leave-out-r2 β has a release-level wild
p (`h2_influence.md`) that is far from any level: a sign reversal without it overstates the
diagnostic.
Rows: `rob.r03.spearman_z_eloundou_vs_z_delegation.estimate C11`, `rob.r32.h5.estimate C11`,
`rob.r32.h5b.estimate C11`, `diag.h2.leave_out_release_r2.beta C11`.

**W-22. The seal date is not the test window.** The introduction's third contribution says the
paper tests whether repricing "since the launch of ChatGPT" on the seal date lines up with
delegation. The test reads returns only in the 2025-04-01 to 2026-08-31 window, after Design B's
formation (PAP §3.1; `confirmatory_h5.md`). The seal date bounds the pre-seal history from which
b̄ and s come. The sentence says so, or names the window.
Row: `design.seal_date C2`.

**W-23. The log-unit gloss.** W-17's "(= 100 log points)" is not printed beside the
log-regressor coefficients and intervals in §1, §10 or the brief (the integration pass dropped
it under the no-digit rule). It is restored in words ("a hundred log points") or by a variable.
Rows: `C6` of `rq1.h1.log_wage.ci_low`, `rq1.h1.log_wage.ci_high`, `rq1.h4.log_aui.ci_low`,
`rq1.h4.log_aui.ci_high`, `rq1.h4.log_income.ci_low`, `rq1.h4.log_income.ci_high`.

**W-24. The abstract's market sentence (documented exception to W-18; controller ruling).** The
abstract's word cap (150–200 words) cannot hold the two P14 sentences verbatim. It states both
non-rejections in one compressed sentence that keeps every P14 element through variables: each
decision (`rq3.h5.decision_text`, `rq3.h5b.decision_text`), the null H0: b = b̄, each interval
(`rq3.h5.ci_005.*_pp2`, `rq3.h5b.ci_005.*_pp2`), and "80% power only against a departure of at
least" each MDE (`power.power_pct`, `rq3.h5.mde`, `rq3.h5b.mde`) "pp per SD". It points to the
market section for the verbatim wording. The exception is the abstract word cap only: P14
elements are kept, and the P14 sentences appear verbatim (`rq3.h5.wording`, `rq3.h5b.wording`)
in §7, the brief and the body (§1, §10).
Rows: `claim:00-abstract:1 C10`, `rq3.h5.decision_text C10`, `rq3.h5b.decision_text C10`,
`rq3.h5b.decision_text C11`.

**T-2. Task 33 rebuilds what it compares.** `make all` regenerates none of
`docs/results/diagnostics/` (`python -m aideleg.robustness --diagnostics`, D-3),
`docs/pap/power.md`'s generated block or `docs/audit/tables/` (`make audit`), so comparing them
in a fresh clone (T-1) would compare the committed bytes with themselves. Task 33 adds those
steps to `make all`. A scratch rerun of the diagnostics on 2026-10-24 reproduced every `.md`
and two of the three `.csv` byte for byte; `h2_influence.csv` differed only in the last digit
of `balancing_removed.usage_share_pct` (5.388848255183692 against the committed
…691), summation-order noise of the kind C-80 covers for robustness CSVs. C-80 does not name the
diagnostics, so Task 33 records the tolerance for them in PAP §11 (a clarification) or makes
the sum order-stable.
Rows: `C1` of `diag.h2.balancing_removed.n_tasks`, `diag.h2.balancing_removed.usage_share_pct`,
`diag.h2.leave_out_release_r2.beta`, and of the power.md and audit-table keys
(`power.mde_over_s`, `design.window.months`, `design.alpha.h5_first`, `design.alpha.h5_second`,
`vintage.oews.primary`, `vintage.onet.primary`).

AEI data are conversations matched to O*NET tasks. Nothing here says anything about job risk, displacement or reassurance about the labour market.
