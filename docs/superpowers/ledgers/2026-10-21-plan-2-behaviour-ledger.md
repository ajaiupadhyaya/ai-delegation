# SDD ledger — plan: docs/superpowers/plans/2026-10-21-plan-2-behaviour.md
Spec: docs/pap/pre-analysis-plan.md (frozen, tag pap-v1) is the binding authority; design spec as corrected by PAP §10.
Branch: plan-2-behaviour (from plan-1-foundations a7fb9bd)
Global constraints + review focus: global-constraints.md (this dir)

## Preflight scan
A cross-plan review of Plans 2-4 (21 findings, all applied 2026-10-22; docs/superpowers/plans/2026-10-22-plans-2-4-review-rulings.md) checked interfaces, PAP coverage, protocol integrity and test assertions. Plan-internal scan:
| Pair / task | Produces vs consumes | Finding |
|---|---|---|
| T1→all | figures API, the stale binding test replaced, the lock-pin test | consistent |
| T2→T10,T14 | paplog §11 format; geometries | consistent |
| T3→T4,T6,T8 | inputs (D13 two-month mean, wages, D14 families, D15 error cost) | consistent |
| T4→T6 | TaskRows | consistent |
| T5→T6 | the two-way cluster estimator | consistent |
| T6,T7,T8→T9 | HypothesisResult → family/Holm | consistent |
| T9→T10→T11 | runner → single run | P-RQ1: T11 runs exactly once and is write-once; any failure is an attempt, not a result |
| T11→T12 | committed JSON only | consistent |
| T13-T15 | descriptives; no confirmatory estimates | consistent |
| T16 | indexes, Make, wording | consistent |
Ruling P2-R1: T11 is a STOP-on-anything-unexpected task. The controller runs T11's checks; on any refusal or crash, stop and report to Ajai, never retry — the single-run protocol — cost if wrong: none.

## Tasks
Task 1: first dispatch interrupted by a machine restart (no changes); re-dispatched
Task 1: minor (deferred): save_figure leaves the figure open on a bad name; pyplot import inside the function
Task 1: complete (commits a7fb9bd..6634973, review clean)
Task 2: implemented 6634973..1155087; note: TDD RED not evidenced (tests written alongside code)
Task 2: minor (deferred): no synthetic test for the iso3 de-dup rule; _ensure_subsections assumes §11 is last; type-ignore casts
Task 2: carry to Task 14: alias AEI XKX → Natural Earth KOS (Kosovo) in the choropleth join; the other unmatched codes are tiny or defunct
Task 2: complete (commits 6634973..1155087, review clean)
Task 3: implemented 1155087..f6fdf41; review: 1 Important (task→family uses the smallest candidate ID, not the union)
Task 3: Ruling: the task→family mapping uses the union over all candidate Task IDs (consistent with R6); logged as an extra §11 C- clarification in Task 10 Step 8 — the same statement carries different IDs across occupations — cost if wrong: family sets for about 1% of tasks
Task 3: Ruling: promoted 4 silent-failure minors (duplicate periods, DWA→IWA uniqueness, non-finite JSON, null soc6) — the same standard as Plan 1 — cost if wrong: none
Task 3: fix round 1/5 (2 addressed; commits f6fdf41..75cd30e); IWA coverage 0.9900
Task 3: minor (deferred): the coverage gate pinned at 0.9899 (the brief says 0.9); families_for_text level param unused
Task 3: carry to Task 10 Step 8: add a C- clarification for the task→family union rule (text in task-3-report.md "C- clarification for Task 10")
Task 3: carry to Task 4: the H1/H3 rows must use inputs.families_for_text (union), not node_id
Task 3: complete (commits 1155087..75cd30e, review clean)
Task 4: implemented 75cd30e..1a81193; review Approved; weight conservation verified on r6 (90.375); 1689 rows / 1147 tasks / 391 soc6 / 161 IWA
Task 4: Ruling: promoted node-count drop reporting plus 2 branch tests — ~1676 of 2823 r6 nodes leave silently (likely pct rounded to 0.00) — transparency for the paper — cost if wrong: none
Task 4: fix round 1/5 (3 addressed; commits 1a81193..bb3018e); r6 node drops: unmatched 2, no_family 63, zero_weight 1611 (pct rounded to 0.00 on the 0.01 grid), kept 1147
Task 4: minor (deferred): rows.py:37 docstring says "no usage" for zero_weight (should be "rounds to 0")
Task 4: note for the paper: 1650 of 2823 r6 task nodes have published pct 0.00 (rounding) — a measurement fact to report
Task 4: complete (commits 75cd30e..bb3018e, review clean)
Task 5: implemented bb3018e..7466b77; review Approved; matches the PAP §4 call token for token; manual CGM cross-check rtol 1e-10
Task 5: carry to Task 10 Step 8: C- entries for (i) the zero-variance fallback also applying when the block was not clipped, plus ZERO_VARIANCE_RTOL=1e-12; (ii) the all-zero case raises (STOP); add a docstring line for (ii)
Task 5: complete (commits bb3018e..7466b77, review clean)
Task 6: implemented 7466b77..c04f138; review: 1 Important (fragile seeded tests); plan correction: the brief's test_h1_recovers_planted_education was unpassable (p_family = max(p_e, p_w) with β_w = 0) — the amended test keeps the intent
Task 6: Ruling: the P13 attenuation factor uses the full FWL residual (IWA FE + the other regressors), not IWA-only — that is the variation β_w is identified from — cost if wrong: the reported attenuation diagnostic only; C-entry in Task 10
Task 6: carry to Task 9/12: the H1 decision requires β_e<0 and β_w<0; H3 requires γ>0 — check the sign handling there
PAUSE (owner closing session until ~3:30PM): Task 6 fix round 1 was dispatched to the implementer (fragile tests → n_task=2000 + 3·se; FWL attenuation factor; diagnostics; n_occ). On resume: check git log for a commit after c04f138 and the "Fix round" section in task-6-report.md; if absent, re-dispatch the fix round fresh using the items in the ledger lines above
RESUMED after pause; the Task 6 fix round finished by the resumed implementer
Task 6: fix round 1/5 (4 addressed; commits c04f138..f52dc16)
Task 6: carry to Task 10 Step 8: the C- entries in task-6-report.md (P13 FWL factor; H3 own variables; no_wage_row; γ-only non-PSD block under R31)
Task 6: minor (deferred): the FWL test sample filters only on wage nulls
Task 6: complete (commits 7466b77..f52dc16, review clean)
Task 7: implemented f52dc16..cc8b011; note for Task 12 / the paper: with G=4 releases the Webb wild bootstrap has 1296 draws and a coarse floor (p >= 6/1296); a strong synthetic trend gives p_wild 0.009-0.042, so the H2 co-condition at alpha 0.0125 has very low power — a PAP design property (the referee disclosed it), report it, do not change it; the real balanced r2-r5 panel has 1315 tasks (r2-r6: 384, R22 only)
Task 7: review Approved; D22 bootstrap matches the PAP exactly; t_r midpoints verified on the real windows
Task 7: carry to Task 10 Step 8: a C- disclosure of the H2 wild-bootstrap granularity (p_wild >= 6/1296; near-ties give 0.009-0.042 even for strong trends, so the co-condition at 0.0125 can fail an unambiguous trend) — a PAP design property, no rule change; surfaced to Ajai
Task 7: carry to Task 10 dry run: verify every real H2 panel task has weight > 0 (_Within raises on w <= 0; a crash in Task 11 would be an attempt)
Task 7: minor (deferred): no definition-stable outcome guard (for Plan 4 R22); duplicate _Within build; no RI near-tie test
Task 7: complete (commits f52dc16..cc8b011, review clean)
Task 8: implemented cc8b011..3bd64bf; review Approved; r6 countries n=113 (missing_month 7, missing_income 1), US states 51
Task 8: Ruling: promoted the silent all-missing_mix / NaN m_global path to raises; the shift-share output exposes the m_global vs global offset — cost if wrong: none
Task 8: carry to Task 10 Step 8: the five H4 C- defaults from task-8-report.md
Task 8: carry to Task 9/11: confirm the panel overall automation_pct is renormalised over the five patterns (parsers did this, per the Plan 1 ledger)
Task 8: fix round 1/5 (5 addressed; commits 3bd64bf..645d27c)
Task 8: carry to Task 14: shift_share(frame, global_automation, *, m_global) — the plan text at L574/L898 shows the old 2-arg signature
Task 8: minor (deferred): h4.py:174/208 all-null global automation gives a TypeError, not a ValueError
Task 8: complete (commits cc8b011..645d27c, review clean)
Task 9: implemented 645d27c..14a9d89; review: 3 Important (float-inexact Holm level 0.0375/3; mixed-sign text lacks the §0.2 "contradicts"; data-condition raises in decide could turn the single run into an attempt)
Task 9: Ruling: add status rejected_zero_estimate (rejected, not supported) instead of raising; promoted minors (NaN sorts last; tested coefs by name; full-text tests) — family.py is bound at Task 11 — cost if wrong: none
Task 9: carry to Task 10: confirm.run must serialise every HypothesisResult BEFORE calling decide; carry the C- entries (mixed-sign wording, rejected_zero_estimate) to Step 8
Task 9: carry to Task 12: the H2 report wording must be "measured within-task automation rises across releases" (D22 item 1)
Task 9: fix round 1/5 (6 addressed; 14a9d89..66b8937); Fraction(repr(p)) verified sound for the short-decimal levels
Task 9: Ruling: promoted the NaN-estimate gives supported path and the h1h3 max() NaN-dropping into fix round 2 (status not_supported_nonfinite) — bound files; a wrong "supported" is costly — cost if wrong: none
Task 9: fix round 2/5 (3 addressed; 66b8937..25b21fc); Holm with a NaN member verified to match the PAP procedure
Task 9: minor (deferred): no decide-level test that a NaN member leaves the other decisions unchanged
Task 9: complete (commits 645d27c..25b21fc, review clean)
Task 10: implemented 25b21fc..4255c07; review Approved, "ready for Task 11: yes" conditional on the Step 7 whole-RQ1 gate; scrambled dry run OK (H1 1684 rows, H3 1689, H2 1315 tasks with 0 nonpositive weights, H4 113); §11 C-1..C-29 append-only, verified by the controller
Task 10: Ruling: pre-bind hardening round (refuse a programmatic real run outside the protocol; logger inside try; H2 granularity note so C-15 holds; test_frozen binds to the marker HEAD after a failed attempt; attenuation factors printed in the md) — these files bind at Task 11 — cost if wrong: none
Task 10: Ruling: run a separate Step 7 whole-RQ1 gate review (Tasks 3-9 vs PAP §4/§5, holistically) after the hardening and before Task 11 — the brief requires it and no review covered it holistically — cost if wrong: none
Task 10: fix round 1/5 (5 addressed; 4255c07..6606ca1); controller re-ran the scrambled dry run after the fix: completed, H4 n=113, h2_nonpositive 0, docs/results absent
Task 10: complete (commits 25b21fc..6606ca1, review clean); waiting on the Step 7 whole-RQ1 gate before Task 11
STEP 7 GATE: FAIL with 1 blocking item (H1/H3 task unit is the node_id, not the statement — 1 same-statement pair, ~0.02% of usage, no C-entry). Ruling: fix via C-30 (also zero_weight drop, r6 bucket nulls, H3 sample reading) + panel-hash refusal + H2 atol + drop node counts in the output, then re-gate — cost if wrong: none
Gate N9 (for Plan 3): confirm_h5 must run from a worktree at pap-v1; from this branch check_binding refuses (src differs) — already Plan 3 Task 1 design
Task 10 gate fix round: e954766 (panel-hash refusal, H2 atol, drop node counts) + a3e626e (C-30); a stray unit-test artefact (stubbed run, HEAD "abc", load_inputs raised, no data read) was written to docs/results/rq1 and removed — Ruling: disclosed as §11 C-31 by the controller (3ef3fb7) — transparency, as for the Task 3 incident — cost if wrong: none
RE-GATE: PASS (6606ca1..3ef3fb7). The C-31 artefact copy is committed under docs/pap/evidence/c-31
Task 11 Step 1 preconditions (controller-verified): gate PASS; PAP C-entries at 3ef3fb7, an ancestor of HEAD; pytest 415 passed / 1 skipped; ruff clean; src/tests/pyproject/uv.lock status empty; docs/results/rq1 absent; HEAD edface2ec33ef5be40f0ca400b0902c9532a11a0
Task 11 Step 2: single run starting (make rq1-confirm) — DO NOT RERUN
Task 11 Step 3: output committed unedited as 75e8956 (4 files only); HEAD at the run edface2
Task 11 Step 4: statuses as printed: H1 not_rejected (Holm level 0.01875); H2 not_rejected (0.0125); H3 not_rejected (0.0375); H4 supported (rejected at 0.0125). Not interpreted here.
Task 11 Step 5: test_frozen 3 passed (not skipped) — bound files frozen from here; any change is a §11 deviation
Task 11: complete (commit 75e8956)
Task 12: implemented 75e8956..dd37760; review Approved; 9 numbers verified against the JSON exactly; bound files and the JSON unchanged
Task 12: minor (deferred): the H4 mix control row shows status "supported" (blank it for tested=false); H2 legend placement; hand-typed unit sentence; sys.path insert in the test
Task 12: complete (commits 75e8956..dd37760, review clean)
Task 13: implemented dd37760..7eda4ea; review: 1 Important — the r6 Gini 0.89 is driven by 1649 zero-usage tasks (positive-only 0.738, inside the r1-r5 range); add positive-only + harmonised columns; full suite 439 and exposure hash verified by the controller
Task 13: fix round 1/5 (3 of 4 addressed; 7eda4ea..160232d); round 2/5 docstring-only (160232d..296df64), verified directly by the controller (one-file docstring diff)
Task 13: complete (commits dd37760..296df64, review clean)
Task 14: implemented 296df64..b90bf9f; review: numbers verified (NOR, MNG); layout defects (clipped colourbar labels on all 8 maps; AUI in log10 units; state title clipped; invisible insets)
Task 14: Ruling: the AUI map is diverging, centred at parity (log10 AUI = 0) — a natural neutral point; presentation only — cost if wrong: none
Task 14: controller verified Kosovo XKX is in r3-r5 but absent from r6 (not lost in a join)
Task 14: fix round 1/5 (5 addressed, 1 open: the AUI tick-label overlap found by the controller viewing the PNG; b90bf9f..e5d0e26)
Task 14: fix round 2/5 (3 addressed; e5d0e26..b8ea7e0)
Task 14: minor (deferred → Task 16 / final review): regenerated CSVs differ at the 1e-16 level (not bit-stable) — round CSV floats on write so regeneration diffs are clean
Task 14: complete (commits 296df64..b8ea7e0, review clean)
Task 15: implemented b8ea7e0..0fd71cb; review Approved; Design B Spearman reproduces Plan 1 (0.763 / 0.716 / 0.815); bit-stable
Task 15: carry to Task 16: label only the outliers in fig_rq2_could_vs_does (4pt labels overprint in the dense cluster), plus 10-sig-digit CSV rounding for the rq1 anatomy/geography CSVs (bit-stability, Task 14 note)
Task 15: complete (commits b8ea7e0..0fd71cb, review clean)
Task 16: implemented 0fd71cb..5c165d8; review Approved; requirement map: all rows met; confirmatory files and bound code unchanged since 75e8956
Task 16: minor (deferred): the regeneration test compares md/csv only, not figure bytes
Task 16: complete (commits 0fd71cb..5c165d8, review clean)
ALL PLAN 2 TASKS COMPLETE → final whole-branch review
FINAL REVIEW (opus): With fixes; 0 Critical, 5 Important (H4 mix nondeterminism ~1e-14 / figure bit-stability; wording breach in anatomy.md; choropleth re-export missing; PAP-required coefficient units missing; paplog "Results seen" hardcoded no); all fixable outside bound code; Plan 3 run: no blocker
Ruling: ONE final fix wave (final-fix-wave.md) covering I1-I5, M1, M2, M4, M5, M7-M10 and the test-only minors; M3 (p = 0.0000 in the bound decision text) → Plan 4 must take p-values from the JSON/table; M6 dropped (the file-map typo); T7/T8/T6 → Plan 4
Final fix wave re-review: 19/19 addressed; 1 new Important (C-32 typed "pre-result" while results were seen). Ruling: fix it (paplog post-result clarification subsection + C-32 corrected in place on the unmerged branch) despite the one-fix-wave rule — Plans 3/4 add post-result entries; §11 must be self-consistent — cost if wrong: none
Note for the paper: the regeneration test can flake rarely (~1e-4/run) at the round10 boundary because h4._mix ordering is frozen code (C-32)
Final residual fix (f5bdd0a..07f5043): re-review clean. PLAN 2 COMPLETE at 07f5043 (482 tests; bound files and confirmatory output unchanged since 75e8956)
