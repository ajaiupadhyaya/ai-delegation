# Plan 4 — controller ledger (plan-4-paper, cut from plan-3-markets at be917b6)

## Preflight
Ajai ratified D-1 in chat (2026-10-23), recorded as §11 C-55 (be917b6) on plan-3-markets before the cut.
Upstream ledgers are committed at docs/superpowers/ledgers/ (plan-2, plan-3), both COMPLETE; the plan's .superpowers/sdd/*plan-*/progress.md paths are superseded by those files.
Plan 3's final fix wave (358c021) already aligned Plan 4's text: guard fixture bytes, hits_from_saved(strict)/saved_ranges(), the R9 placebo name, R4/R8 draws, zero_assigned_lines.
Ruling P4-R1: the plans-commit hash for the "(plans committed at …)" field is a7fb9bd, as in C-33..C-54 — cost if wrong: none
Ruling P4-R2: run tasks in order; Stage E prose tasks may run in parallel only where their files are disjoint — cost if wrong: none

## Tasks
Task 1: dispatched implementer (opus); branch already cut; upstream ledgers are the committed files
Task 1: implemented be917b6..d3d8aac; C-56..C-68 (post-result subsection; paplog files any non-'no' results_seen there); 716 pass; no upstream renames; no upstream §8.2 row
Task 1: review Approved (registry = ownership table, 0 mismatches; guards stricter than the brief; fixtures blob-faithful; C-56..C-68 verbatim and in order; PAP append-only). Post-result subsection placement ruled honest; terse R7/R18 titles verbatim from the brief
Task 1: minor (deferred): the "untouched" repo test compares commit vs HEAD only (the run-time guards cover the working tree)
Task 1: complete (commits be917b6..d3d8aac, review clean)
Tasks 2 and 3: dispatched in parallel (opus; disjoint files: adapter vs acquisition/PAP)
Task 3: implemented 3b46528; A-36..A-46; all 11 URLs as written; files validated; 723 pass (excl. in-progress Task 2)
Task 3: review Approved (11 hashes recomputed; no HTML bodies; A-36..A-46 match MANIFEST; PAP append-only)
Task 3: Task 9 carry: onet_29_2_tasks (A-41) is byte-identical to the frozen onet_29_3_tasks (sha fecdcda81a…, 2,759,559 bytes). Task 9 must establish whether 29.2→29.3 truly left task statements unchanged (e.g. check the full db_29_2 archive or O*NET release notes) before treating R32's task index as a distinct vintage; if identical, say so in R32's notes (the OEWS 2023 part of R32 still varies)
Task 3: complete (commit 3b46528, review clean)
Task 2: BLOCKED at Step 4: H4 p_family (4.8e-24) is not reproducible at rel 1e-12, because Plan 2's bound rq1/h4._mix is order-dependent (~1e-14, already disclosed in C-32); all other parity checks are bit-identical
Task 2: Ruling: option (a): H4 parity compares b and F at 1e-12 and p_family through -log10 p at 1e-12; one C-entry citing C-32; no upstream edit, no D-entry — the metric is a genuine equality check given the known 1e-14 noise — cost if wrong: none (no estimate moves)
Final-review carry: Plan 2's test_results_docs_up_to_date is flaky in the full suite for the same reason (C-32); Task 33/34 require a green suite, so decide before then (rerun policy or an order-insensitive check in that test, logged)
Task 2: implemented 54c57a6 (C-69 H4 parity metric); parity 11/11; full suite 733 + the C-32 flake
Task 2: review Approved (43/43 re-exports identical to upstream; parity 11/11 under -W error; no docs/ trace; C-69 sound: 1e-12 rel on -log10 p = 5.4e-11 rel on p, about 40x headroom over the noise)
Task 2: Ruling: promote 3 test-only minors (state the implied tolerance, assert H4 se/p, identity re-export check) — cost if wrong: none
Task 4: dispatched implementer (opus) concurrent with the Task 2 test fix (disjoint files)
Task 2: fix round 1/5 (bfc22f6, test-only: 47 identity re-exports; H4 se raw, p via -log10); controller checked the stat
Task 2: complete (commits 3b46528..bfc22f6, review clean)
Task 4: implemented 63e631c; primary s/bbar/q equal FROZEN exactly (diff 0.0); R00 matches confirmatory_h5.md (H5 1.958/2.271/0.136/0.8934; H5b 3.461/2.560/0.877/0.3906); 753 pass
Task 5: dispatched implementer (opus) concurrent with the Task 4 read-only review; bls/oews.py and occupations.py are RQ1-bound (meta.blobs), so it must STOP if a parameter is needed there
Task 4: review Approved (guard order correct; crit_* are multipliers of s; CI = b ± c_0.05·s matches confirm_h5; drops recompute nulls on kept columns; no implementer default needs a C-entry)
Task 4: Ruling: promote 4 minors (crit 4 dp, NaN-z refusal, a [default] note must cite C-, signed-zero fmt) — cost if wrong: none
Task 8 carry: R19's notes must state that q is recomputed with the RMS s (the brief's Step 3 rule; inert while crit = t21)
Task 4: fix round 1/5 (833e164; 4 minors); controller checked the stat
Task 4: complete (commits bfc22f6..833e164, review clean)
Task 5: implemented 23e0d33; hash bddc49d4 kept; concerns: R20 majority gives 46 industries (Guns, Gold, Boxes get no NAICS); R15 hq=redistribute is affine (|dz| 8.9e-16, i.e. a no-op on z)
Task 5: review Approved (primary byte-identical, independently re-verified against the old module; bound files untouched)
Task 5: R15 ruled = the PAP's own rule; affine invariance (c = 2.02%) makes z/H5/H5b/RQ2 identical to the primary, so not a bug; a non-proportional rule would be a new spec. R20: 46 industries from the frozen majority rule (Guns, Gold, Boxes), z re-standardised over 46
Task 5: Ruling: the controller filed C-70 (R15 identical by construction) and C-71 (R20 on 46; market drops the 3 from window + history) in 4088433, before either row runs — cost if wrong: none
Task 7 carry: R20's market part must pad Guns/Gold/Boxes as null and pass them in drop (market.py:197 requires all 49 columns); R15's .md note states the identity
Task 6 carry: wage_bill_matrix also changes the across-code FF49 aggregation weights (tot_emp → wage bill); confirm against C-66 ("R2 changes w_oj only")
Task 6/appendix carry: the R11 employment allocation applies to task-basis tables only (published r6 untouched)
Task 5: fix round 1/5 (b5ae35f; exact A_pooled parity; WORDING pointer)
Task 5: complete (commits 833e164..b5ae35f, review clean)
Task 6: dispatched implementer (opus); the 29.2-vs-29.3 identity check moved here, since index_29_2 lives in this task
Task 6: implemented dc6bf7c; dz vs primary: wage_bill .607 (reading A; B .415), emp alloc .0995, emp_weighted .222, 29.2 0 (files identical), bls aioe 0 (dz_aioe .031); R14 needs a C-entry (AIOE 19-1020 mapped via its O*NET successor 19-1029)
Task 6: review Approved (hand-computed tests pass; bound files untouched; primary hash green). Reading A upheld for R2 (w_oj includes the across-code weight, per exposure.py and §2.1); R14 successor mapping = the primary's; R32 O*NET identity accepted
Task 6: Ruling: the controller filed C-72 (R2 reading; discloses that both dz values were computed before the entry), C-73 (R14 19-1020) and C-74 (R32 identity) before those rows run; promoted 3 minors (cite C-numbers, assert the fallback set = {19-1020}, an independent 29.2 count) — cost if wrong: none
Task 9 carry: R2's notes say emp_covered_share is wage-bill weighted (0.731-0.986 vs primary 0.680-0.988)
Task 6: fix round 1/5 (b9c5952; C-number citations, ONET_FALLBACK pinned, independent 29.2 count)
Task 6: complete (commits b5ae35f..b9c5952, review clean)
Task 7: dispatched implementer (opus); first real robustness rows; code+tests committed before the one real run, outputs in a separate commit
Task 7: implemented 3149223 (code before the run) + d9fb4e6 (outputs, one 66 s run); 811 pass; R15 = primary, R17 rho = could_vs_does (both as expected)
Task 7: review Approved (specs/parts/labels exact; R15 = confirmatory_h5.md at full precision; R17 = could_vs_does.csv; R20 n = 46; arithmetic spot-checks exact; commit order verified)
Task 7: Ruling: no fixes now (Rows have outputs; the minors are a guard and presentation, deferred to the final review rather than code-after-results churn). Carry to Tasks 15/29: any prose calling a robustness market result a non-rejection uses the P14 wording verbatim
Task 7: deferred minors: rows.py RQ2 dropped/n_dropped computed only against R20_ABSENT (assert 49 for the other rows); R2.md could say that the D3 share is employment-based while emp_covered_share is wage-bill weighted
Task 7: complete (commits b9c5952..d9fb4e6, review clean)
Task 8: dispatched implementer (opus); R19 q-with-RMS note carried; code before the run
Task 8: implemented 9e5aab4 (code) + d2da8f1 (outputs, one 44 s run); 830 pass; PAP scale values reproduced; R35 CI = b ± t21·κ·SE_Σ chosen without a C-entry (the PAP gives no interval); R10 file holds only the market parts (Task 11 must merge)
Task 8: review Approved (se_sigma and κ match PAP R35; κ's sd(b_w)/mean(b_w) reproduce FROZEN s and b̄ to 17 digits; PAP scale values reproduced; CIs use c_0.05 incl. q > t21 for R7 H5b; commit order clean)
Task 8: Ruling: R35 interval → (a): the controller filed C-75 (presentation-only reading; T/p/scale/criticals unchanged); R35 note tagged [default] + variant-string alignment, regenerated with numbers byte-identical; κ test pinned — cost if wrong: none
Task 11 carry: R10 — do not rerun the market parts; read the committed market_lb/market_ub rows verbatim, add h1/h3 lb/ub records, rebuild notes without a market read, one write_row; test the market rows are byte-identical to d2da8f1
Task 15/29 carry: the appendix/paper must state that every robustness market interval is the c_0.05 one (P14 also defines c_0.025)
Task 8: fix round 1/5 (9526664); controller verified only the R35.csv 'variant' column differs from d2da8f1
Task 8: complete (commits d9fb4e6..9526664, review clean)
Task 9: dispatched implementer (opus); R32 note must cite C-74
Task 9: implemented 75b79f9 (code) + da77caa (outputs); unmapped 2023 = 0.29%; 833 pass + the C-32 flake
Task 9: review Approved (specs exact; commit order clean; the extra R6 sentence verified true from the MANIFEST: FF49 and the factors are the frozen files)
Task 9: complete (commits 9526664..da77caa, review clean)
Task 10: dispatched implementer (opus)
Task 10: implemented 0d884ed (code) + 92e12c3 (outputs, one ~54 s run); 843 pass; R9 actual slopes = event_study.csv exactly; concerns: R9 applies_to 'placebo'; percentile convention (≤); index part is a descriptive point Spearman; C-37 note also on R16
Task 10: review Approved (placebos 56, no 2020, no 'ChatGPT' name; R9 percentiles recomputed 60.714/57.143; commit order clean; no Plan 3 file changed)
Task 10: Ruling: one post-result presentation C-76 (filed by the controller: R9 applies_to label, the percentile convention recorded (<, ≤ and midrank agree; n+1 would give 59.65/56.14), DSR trial-count notes for R4/R16/R8); regenerate with numeric columns byte-identical — cost if wrong: none
Task 10: fix round 1/5 (5cf253c); controller verified only applies_to/note columns differ from 92e12c3
Task 10: complete (commits da77caa..5cf253c, review clean)
Task 11: dispatched implementer (opus); R10 merge carry (market rows verbatim, byte-identity test)
Task 11: implemented cf00271 (code) + 25480d9 (outputs, ~16 s); R38 reproduces p_oneway_occ; R10 market rows byte-identical; R23 condition (both coefficients opposite AND significant) not met: education opposite p<.001, wage same sign p=.177 — the 'any coefficient' reading would print the sentence; no C-entry yet
Task 11: review Needs fixes (documentation/presentation only; estimates, routing, guards, commit order and the R10 carry verified; R38 p = committed p_oneway_occ exactly)
Task 11: R23 ruling: the pre-run "both coefficients" reading kept (it mirrors D17's conjunctive H1; committed with its tests at cf00271 before the run); the controller filed C-77 disclosing the 'any coefficient' reading (would print: education +0.026 vs primary −0.535, p<.001) and the sign-reference alternative; R23.md gets an unconditional sign-check line. Switching would be a post-result D-entry, not recommended. Relay to Ajai as information
Task 11: the controller filed C-78 (RQ1 .md coefficient labels, outcome-aware units, n_dropped note, R38 p_H1 = D17 max of one-way p's); regenerate with CSV numbers byte-identical — cost if wrong: none
Task 11: fix round 1/5 (61b0625); controller verified no CSV changed (25480d9..61b0625) and the R23 sign-check line is present
Task 11: complete (commits 5cf253c..61b0625, review clean)
Task 12: dispatched implementer (opus); R23 append carry (H1 rows byte-identical to 61b0625)
Task 12: implemented 59242bf (code) + f8ea9d1 (outputs, 23.8 s); 890 pass; the 'would meet the H2 rule' flag is no in all 11 parts; concerns: R37 excludes 1141 zero-weight tasks (fixed pre-run, no C-entry), estimand string for R23 h2, stale R23 note
Task 12: review Approved (10 R22 calls exact; R37 = Plan 2's estimate_h2 on two periods at 1e-10; rule flags spot-checked; CI/p recomputed exactly; commit order clean)
Task 12: Ruling: the controller filed C-79 (R37 drops 1,141 zero-weight tasks, fixed in code before the run, consistent with D13/C-30(b); R23 h2 estimand label); presentation fixes regenerated with numbers byte-identical — cost if wrong: none
Task 12: fix round 1/5 (e9d7880; numbers byte-identical; write_row gained label_text=None, default unchanged)
Task 12: deferred minor: R22's header still joins two labels with a comma (not regenerated) — for Task 15's appendix pass
Task 12: complete (commits 61b0625..e9d7880, review clean)
Task 13: dispatched implementer (opus)
Task 13: implemented 19d551c (code) + 00b5432 (outputs, 3.1 s); 908 pass; R25 rejects H4a/H4b only; R28 joint p <= .018 in every part; defaults: r4/r5 GWA union via C-9 (index kwarg), ā_g uses the 1/k split, non-country geo_ids excluded
Task 13: review Approved (R25 Holm recomputed by hand: H4a, H4b rejected, the rest not; C1/C2 follow C-9/C-59 and mirror Plan 2's _candidates; unmatched:* excluded as Plan 2's universe rule would; commit order clean)
Task 13: deferred minors (final review): R28.md note on unmatched:* buckets in n_dropped; R25 "printed decimals" wording; index=None default in h4_frame_r45 (runner passes it); a test pinning _mix_r45 to Plan 2's _mix
Task 13: complete (commits e9d7880..00b5432, review clean)
Task 14: dispatched implementer (opus); network for unsaved phrases (likely automation/robotics 2024) via Plan 3's client; code committed before any fetch
Task 14: BLOCKED after the run: 123abf4 (code); fetched automation (17 req, 1,601 docs) + robotics (5 req, 423 docs) for 2024, clean; R29/R30 ran once (uncommitted). Plan 3's hits_from_saved(phrases=None) loads EVERY saved sec_fts phrase, so the new records would enter the primary H6 numerator on a fresh offline h6 build; 2 parity tests now fail. Plan 4's contract text says the default is fts_phrases(). The fix is a one-line Plan 3 change (None → fts_phrases()) with outputs byte-identical — a Plan 3 analysis-code change after results → D-entry needing Ajai's approval; asking him
Task 14: Ajai approved D-2 in chat ('I approve D-2: make hits_from_saved(phrases=None) mean fts_phrases(), as its docstring says. Log it in §11 with my approval, confirm the primary H6 outputs are byte-identical, then commit Task 14 and continue Plan 4.'); implementer resumed to apply it, verify make h6 byte-identical, file D-2, commit
Task 14: D-2 fix applied; byte-identity verified (hits_from_saved = fts_hits.parquet; make h6 leaves docs/results/h6 + figures clean). Ruling: the test assertion set(saved phrases) == fts_phrases() is amended to subset (test-only, a consequence of D-2/A-47). Incident: a stray git stash briefly removed the fix during make h6; restored at once, parquet verified afterwards, stash list empty
Task 14: committed 123abf4 (code), 701a567 (D-2 fix + tests + D-2 entry), 8b8817a (R29/R30 + MANIFEST + A-47); 920 pass
Task 14: review Approved (D-2 is one functional line, matching the approval; byte-identity independently confirmed: docs/results/h6 and figures unchanged since 0473eda, parquet = 15 phrases; A-47 digest recomputed; 22 JSON files clean; commit order clean)
Task 14: deferred minors: dead 'wanted is None or' in edgar.py:577 (kept to hold D-2 to one line); the float-share wording counts zero floats (disclosed)
Task 14: complete (commits 00b5432..8b8817a, review clean)
Task 15: dispatched implementer (opus); make robustness re-runs all rows offline = determinism check (any committed row change → STOP); carries: c_0.05 interval statement, P14 wording rule, D-2 listed
Task 15: BLOCKED: re-run of all rows offline: every .md byte-identical, 33/36 CSVs identical; R15 (~1e-15), R28 (~9e-12, C-32 bound h4._mix) and R29 float_weighted (~2e-15) differ in the last digits, varying run to run (unordered polars group_by sums, not BLAS)
Task 15: Ruling: the controller filed C-80 (a CSV reproduces when non-numeric cells are equal and numeric cells are within rel 1e-9, abs 1e-12; committed bytes kept so re-runs leave the tree clean; .md still byte-identical; the same rule for Task 33's fresh-clone check); the controller restored the 3 CSVs from HEAD; write_row keeps the committed CSV when equivalent; the helper is to be reused by compare_outputs — cost if wrong: a bit-level replication claim becomes 1e-9 for 3 files (disclosed)
Task 33 carry: compare_outputs uses csv_equivalent for CSVs (C-80); this also covers Plan 2's flaky test_results_docs_up_to_date (same C-32 cause) — the Task 33/34 green-suite requirement must handle that flake
Task 15: implemented e2efc07 (C-80 writer) + 2ba6c9d (appendix, figures, coverage, --summary, make robustness); 941 pass; make robustness leaves the row files unchanged
Task 15: review Needs fixes (1 Important): summary/forest paired R22's six other-outcome H2 parts with the automation_pct primary (a false like-for-like). Everything else verified: csv_equivalent = C-80; no row file changed; all 16 [default]s listed; no counts or verdicts; forest without stars; make robustness offline
Task 15: Ruling: primary_for → None when the outcome ≠ the primary's; real-figure star test; summary precision; explicit rq2/bounds.md exemption; NaN/inf tests — presentation only, no entry needed (summary not yet relied on) — cost if wrong: none
Task 15: fix round 1/5 (839cd59; only summary.md and fig_robustness_rq1 changed; R22's other outcomes and R10's D1-bound outcomes now go to "see file" — consistent with the outcome rule); controller checked the stat and the summary lines
Task 15: complete (commits 8b8817a..839cd59, review clean). STAGE B (robustness) COMPLETE
Task 16: Steps 1-2 dispatched (registry + machinery; the challenges test xfail-strict until the review); Step 3 four hostile referees run by the controller after
Task 16: f30206e (registry, 59 keys = 708 pairs); Step 3: 4 referees dispatched (RQ1, RQ2+D3, RQ3+H6+D11 on C2/C3/C5/C7/C8/C10/C11/C12; cross-cutting on C1/C4/C6/C9 for all keys). C1 ruling: evidence = the existing verified regenerations, re-verified at Task 33
Task 16 referee RQ2: 104 pairs, 72 holds / 31 fails / 1 n/a; fails: C2 cite D6 not D8 for AIOE keys (label); C3 the RQ2 tables need the S1 timing caveat (OEWS May 2024 published 2025-04-02 and O*NET 29.3 after r2; R32 has no RQ2 part); C12 shared occupational weights on both sides of rho plus D3 dependence (R3 moves rho .716→.568) unnamed (wording); C10 D3 'unpublished, not measured as zero' wording
Task 16 referee cross: 236 pairs, 190 holds / 5 fails / 41 n/a. Fails: C1 power.md and audit oews_coverage.md are not in any regeneration check (both rerun byte-identical by the referee) → add to Task 33's compare list; C6 'per log point' unit labels for log wage (H1 β_w), log AUI and log income (H4) overstate the scale 100x → 'per unit of log X (100 log points)'. C4/C9 hold (Holm recomputed with Fractions; single-run commits clean). Note: C-80 is dated 2026-10-24 because paplog stamps UTC dates
Task 16 referee RQ3/H6: 240 pairs, 201 holds / 39 fails. Fails: C3 22 H5/H5b rows (OEWS May 2024 weights released 2025-04-02, after formation and inside the return window; PAP calls it 'not strictly real-time'; R32 strict real-time gives b 2.20/3.72) → label fixed; C3 H6 (current SIC, FTS semantics at 2026 retrieval) → label; C10/C11 b=0 secondaries lack the P14 form and MDE → wording; C11 the H6 Spearman has a CI but no p (§0.2 vs D18) → D or reading; C8 no H6 industry influence (referee LOO: drop Softw .361→.320; R29 parts .081/.190/.267) → D or name rows. Also gap_returns.md has a market null with no MDE beside it
Task 16 referee RQ1: 128 pairs, 114 holds / 12 fails / 2 n/a. Fails (wording/diagnostics, none confirmatory): H1 β_e driven by SOC 15 (drop → −0.015); H1 β_w rests on 15-1299 (drop → 1.50, p .37) and its opposite sign needs neutral wording; 'H is not rejected' phrasing reads as the hypothesis surviving; H2 balancing drops unreported (2,205 vs 1,315 tasks); the H2 trend rests on r2 (leave-out-r2 → −6.55) and the r2→r3 classification-base change; H4 log_aui/log_income corr .916 (joint test holds); R24 r5 would support H1 (name it)
Task 16: red team totals 708 pairs: 577 holds / 87 fails / 44 n/a; no confirmatory issue
Task 16: Ajai approved D-3 in chat (2026-10-24): "I approve D-3: add the labelled post-result influence diagnostics (H1 leave-out by SOC major group and top occupation, H2 leave-one-release-out and the balanced-panel drop count, H6 leave-one-industry-out Spearman and a nominal exploratory p). No confirmatory or committed estimate changes. Log it in" (message cut at 300 characters; the intent — log in §11 with his approval and continue — is the ask he was answering)
Task 16: resolution dispatched: D-3 diagnostics module; label fixes (unit labels, D6 citation); docs/redteam/wording_requirements.md for the prose tasks; challenges.csv filled, log.md rendered, xfail removed
Task 16: resolution c479bc7 (D-3+code), 9b40c17 (D-3 outputs), 94b6a62 (C-81 labels + RQ1 docs regenerated), 0ffc66d (wording_requirements W-1..W-17 + T-1), 9528803 (challenges 708 rows, log.md, xfail removed); 63 wording / 11 label / 13 D-3; test relaxed to accept 'yes: …'
Task 16: review Approved (D-3 scope exactly as approved; spot-checks reproduce: H1 without SOC 15 β_e −0.01498, H2 without r2 β −6.548, H6 ρ .3607 p .0109, without Softw .320; C-81 unit column only; no committed estimate changed; 708 rows; 13 D-3 rows correct)
Task 16: controller fixed W-14 (no ungenerated 0.916 number) and W-16 (adds R5 for H5) in the follow-up commit
Task 16 carries: (a) Task 31's prose red team must read W-1..W-17 and T-1 (63 "wording fixed" rows are binding promises); (b) Task 33's compare list adds docs/pap/power.md and docs/audit/tables/; (c) R23.md:14 still says "per log point of wage" (rows.py:1552) — fix as presentation in the final review; (d) C-81's rule text says the new label restates the PAP's "per log point"; it actually corrects the PAP's loose wording — note it in the final §11 pass; (e) generated RQ2 tables carry no S1 timing label (covered by W-9 in prose); (f) docs/redteam/log.md quotes referee evidence (incl. "no effect") — prose scanners must exempt docs/redteam
Task 16: complete. STAGE C (red team) COMPLETE
Stage D: Tasks 17 (Quarto skeleton, sonnet) and 20 (verified BibTeX, opus) dispatched in parallel (disjoint files)
Task 17: implemented 138f767 (pypdf 6.21.2; lock test passes; Pagella loaded by file name; abstract as an unnumbered section because include does not parse in YAML)
Task 20: implemented 6cbfe20 (43 entries; 30 DOIs 302 at doi.org; Holm by JSTOR URL; Webb 2020 kept with the 2019 SSRN date noted; AEI release citations added)
Task 20: review Approved (all 30 DOIs re-resolved, metadata matches; identity calls right; Holm DOI 404 handled; AEI per-release citations per README)
Task 20: complete (commit 6cbfe20, review clean)
Task 17: review Needs fixes (Important: 'Invalid Date' in the title block because the var shortcode is not expanded in YAML); also render list, HTML appendix letters, drop the empty-bib fallback; Pagella embedded (pypdf), settings exact
Task 17: fix round 1/5 (7d31f10; date printed in the body from the var; render list limited; HTML appendix letters left as default numbering, no simple setting)
Task 17: complete (commits 739bbd7..7d31f10)
Task 18: dispatched implementer (opus)
Task 18: implemented d067441 (2,939 variables incl. the 59 headline keys, 93 tables, 23 figures; power MDEs recomputed 7.43/8.38, R13 10.46/12.15; 1038 pass; summary.md and 13-column tables overflow in the PDF — for the appendix tasks)
Task 18: review Approved with 1 Important (the variables build needs a fallback in a shallow clone or without .git: pap.* and meta.date); also prose-facing decision text and 2-dp interval forms; MDEs recomputed by the reviewer
Task 18: fix round 1/5 (3b3d40e; no-git/shallow fallback tested; decision_text and *_pp2 prose forms; 2,955 variables)
Task 18: complete (commits 7d31f10..3b3d40e)
Tasks 19 and 21: dispatched in parallel (hygiene.py + tests vs includes.py appendices + disclosures)
Task 19: implemented 72bab22 (1109 pass, 15 skipped; the final marker skips unless -m final; '(Task 31)' removed from two stubs)
Task 19: review Needs fixes (the scanner matches the brief, but bypasses: line-wrapped banned phrases; rendered YAML/raw/executable fences stripped; '@0.5' eaten; ½/① not caught; '*' in identifiers; paragraph-rule edges; attribute false positive) — all promoted
Task 19: fix round 1/5 (09f8ce4; all 7 holes closed with fixtures; superscripts allowed only after a letter/bracket; * only between letters; the \appendix raw block allowlisted; pp5/t2025 a documented known limit)
Task 19: complete (commits 3b3d40e..09f8ce4)
Task 21: implemented 3478b57 (131 §11 entries A47/C81/D3; 94 MANIFEST rows; 17 disclosure bullets; PDF 306 pp, 259 landscape; overfull 226 boxes, largest 14pt)
Task 21: review Needs fixes (appendices verbatim and correct, no-git path works; post-freeze.md misses (a) the in-place correction of C-32 (P2 ledger L116) and (b) Plan 3 Task 5's double real run (P3 L46); the sleep sentence is unsupported; 'relayed to Ajai' needs a source; dead ../confirmatory_h5.md link; has_entries none-case)
Controller record (for disclosure sourcing): during Plan 3 Task 13's 10-K download the controller observed from INDEX.jsonl retrieval stamps a near-stall from about 02:30 to 03:40 UTC on 2026-10-23 (588 documents in 02:2x, 9-20 per 10 minutes until 03:4x) while the downloader's own elapsed clock showed ~13 min; read as the Mac sleeping; the agent then held caffeinate; reported to Ajai in chat at the time
Controller record: C-77 (R23 reading) was relayed to Ajai in chat at the time (2026-10-23, "This is for your information; no approval is needed")
Stage E prep: prose-prerequisites pass dispatched (check/add every object the section specs and W-requirements cite; write docs/paper/PROSE_OBJECTS.md); section writers will then run in parallel, forbidden to edit shared files or run make paper (the controller renders)
Task 21: fix round 1/5 (0490517; 20 disclosure bullets; the dead link is plain text; has_entries via paplog.entries). NOTE: post-freeze.md cites this ledger by line (147, 148), so the final committed copy must be this file verbatim, append-only
Task 21: complete (commits 09f8ce4..0490517). STAGE D (paper infrastructure) COMPLETE
Stage E prep complete (fc2bac6, 7cdb575: +88 variables, +3 tables; PROSE_OBJECTS.md; 7 objects not available). Stage E: 10 section writers dispatched in parallel (opus; each commits only its own section file; private tmp renders only; the controller renders)
Prose §2: 9ad42ab (1,471 words)
Prose §10: 314d409 (632 words); unresolved refs pending §5-§7 placing their tables
Prose §6: 6b2247e (1,466 words; includes all 12 RQ2 tables/figures — check duplicate labels at integration; C-/D- numbers not citable in prose because the scanner flags 'C-65', so prose says 'PAP §11')
Prose §9: c1f6cfd (1,186 words); integration check: refs to tables that §3/§5/§7 must place
Prose §1: 817d0b9 (1,719 words); the W-17 '(= 100 log points)' gloss is dropped by the no-digit rule (the unit is still stated as per unit of log); integration: consider a 'hundred log points' wording or a variable
Prose §5: 41fe195 (2,031 words; R23 sign check reported; the map description is read from the images — check in the Task 31 claims red team; diag-h1/h2 placed in §5)
Prose §8: 115dbec (1,196 words; no counting; H3/H4 rows explicitly unordered; c_0.05 stated once)
Prose §3: 7c6e09d (2,449 words; WORDING once; places tbl-releases/regimes/audit-exposure-coverage). Unresolved so far: tbl-rq3-confirmatory, tbl-diag-h6-influence (§7 expected), tbl-rq2-bounds-occupations, tbl-rq3-influence-softw
Prose §4: 0662dc3 (2,498 words; §11/§10.2 ids described by content because the scanner rejects 'D-1'; 10-K/GPT-4 reworded). Integration ruling to apply: allow §11 entry ids [ACD]-<n> and the fixed names '10-K', 'GPT-4' in the scanner (they are names, not numbers); writers' rewordings may then be tightened
Prose §7: 8b8a89e (2,275 words). ALL TEN SECTIONS DRAFTED; integration pass next
Integration pass dispatched (scanner allowlist for [ACD]-n / 10-K / GPT-4 with fail fixtures; restore names; resolve refs; dedupe includes; References page check 30-45; consistency read)
Integration: a4338b0 (scanner allows [ACD]-n, 10-K, GPT-4 with fail fixtures) + 5ffbf30 (names restored, the bounds table placed, 0 unresolved refs, no duplicate labels, a §9-vs-§7 Softw contradiction fixed). References on p.97 of 405 against the 30-45 target
Ruling: the body keeps headline tables only; every other generated table moves to a new Appendix F "Supplementary tables" with pointers; fig-pos H; if still > 45, stop for a prose decision — presentation only, no content lost — cost if wrong: a structural addition beyond the plan's A-E appendices (disclosed in the ledger)
Integration: c609c2a (Appendix F with 45 tables; the scanner allowlists exactly the two landscape-wrapper lines; figures at first mention). References p.58 of 395. Ruling 2: releases table to F; at most 4 headline figures in §5, others to F; figures ≤ 0.42 text height; then concision toward the section minima (no required item or W-n removed); stop if unreachable
Integration: f7ec61e (layout) + 8c3dd35 (concision −220 words): References p.45 of 389, no slack; the 4 headline body tables in small type (2 more exact raw-LaTeX allowlist entries). The abstract + brief (~850-1,100 words) will push to ~p.47, so Task 31 must tighten ~2 pages within the minima (~1,550 words of room)
Task 31a dispatched: abstract + brief + test_brief + concision to the page target; the claims red team (31b) run by the controller after
Task 31a: 225c775 (abstract 199 words, brief 774) + 6ef8478 (concision): References p.45/389, brief.pdf 2 pages; slow tests pass. Zero slack: red-team edits to §8-§10 must not add length. The brief gives the H5/H5b non-rejections in plain words, not the P14 wording verbatim (Global Constraints require verbatim) — for the claims red team
Task 31b (claims red team): scan_headlines + new-key challenges, and the full-PDF claims reviewer, dispatched
Task 31b claims review: 34 rows, 21 fails (19 C10, 2 C5), 13 holds; none confirmatory. Key fails: abstract/brief paraphrase P14 (must quote verbatim); W-1 null clauses missing in the abstract/brief; causal 'changes by' wording (§1, brief); §2 'fixed before returns were examined' overstates (C5; pre-seal returns seen, null recentred, D11 confirmed with the MDE in view); §5 non-monotonic claim unsupported by the quoted deciles; §5 Holm H3 contradiction; §7 'MDE beside every market null' false for the exploratory nulls; §9 states the H2 rise as fact; brief 'adequate power' overstates; W-9 caveats incomplete
Task 31b keys: 438c391 (W-18..W-23, T-2) + c50c33a (63 new keys, 756 rows: 496 holds / 35 fails / 225 n/a; no STOP)
Rulings: (1) the abstract (≤200 words) cannot hold two verbatim P14 sentences: it states both non-rejections in one compressed sentence carrying every P14 element (the H0 b = b̄, the interval and "80% power only against … at least <MDE>") via variables, with a pointer to §7 for the verbatim wording; the brief and body quote P14 verbatim — recorded as a plan-level presentation exception in wording_requirements; (2) W-17's gloss is written as "a hundred log points" (no digits); (3) the controller filed C-82 (C-80's tolerance covers the diagnostics CSVs); (4) Task 33 carry: make all must rebuild power.md, the audit tables and the diagnostics (T-2)
Task 31b resolution: 2f863a5 (prose fixes, W-24) + 34689a7 (challenges/log; test_claim_rows added for the claim: pseudo-keys); References p.45, brief 2 pp, abstract 200 words; all fails resolved (21 claim + 26 key prose; 9 T-2 rows label-fixed pending Task 33)
Task 31: claims fixes verified Approved (all 21 + 26 resolved; P14 verbatim in the brief, character for character; References p.45; brief 2 pp). Deferred minors to the final fix wave: H3 "not rejected at {holm.h3}" in §1/§10 vs §5's "Holm stopped at H1"; "any return dated after the seal" → "any post-seal industry return read by code" (§2, §4, §7); restore two hedges lost in the §7 cuts (s for a longer window unknown; event day-zero convention); §8 leave-out-r2 pointer to tbl-diag-h2-influence; the brief's "is not rejected: H5b is not rejected" repetition and the log-points gloss placement
Task 31: complete. STAGE E (prose) COMPLETE
Stage F: Tasks 32 (README, AEA template) and 33 (make all + fresh-clone check + download check) dispatched in parallel; Task 33 told to STOP on Plan 2 last-digit differences (C-32) rather than widen tolerance
Task 32: implemented 26a8845 (AEA headings; licences quoted per source page, 'see terms' for French/Census/AIOE; runtime block pending Task 33; Natural Earth listed). After Task 33: regenerate the README blocks and check the make/--from-dir wording against Task 33's code
Task 33: 9148505 (from-dir, check-download, Makefile, compare_outputs, replicate.sh, power_block.py), c23db42 (stale data appendix Makefile table regenerated), 3dc9128 (check.md, download_check.md). Fresh clone: make all exit 0 in 86m18s, clone tests 1174 pass; seeding 400/400 MANIFEST + 47,946/47,946 docs verified; compare 315/315 IDENTICAL (none needed the C-80/C-82 tolerance; no C-32 differences). Download check: 87/92 non-bulk match, every French file matches; 5 SEC files differ upstream (2025 Q2-Q4 form.idx, submissions.zip, ticker list); bulk SEC sets not re-downloaded
Task 33 notes: power_block.py calls run_power() directly (skipping power.main's post-freeze refusal) and reproduces power.md byte for byte — for the final review; test runs last in make all; seeding lives in acquire/seed.py; the README runtime line regenerated and committed by the controller
Task 34: final-gate test passes (no stubs); whole-branch review dispatched (be917b6..HEAD, 343 files); then one fix wave incl. deferred minors, re-run Step 1 (make all), then STOP for Ajai
Task 34 whole-branch review: Needs one fix wave; 0 Critical, 8 Important: (1) the abstract/brief give H2 the wrong reason (omit the failed wild co-condition and the clustered trend); (2) §8 'every row fixed before any confirmatory result' overstates (C-56..C-82 are post-result); (3) implementation_choices lists only [default]-tagged notes, missing C-64..C-68, C-70..C-74, C-79(1); (4) the C-for-presentation practice and D-3's top-3 leave-out were never ratified by Ajai; (5) the abstract's P14 exception (W-24) needs Ajai; (6) the Plan 4 ledger is cited but untracked; (7) no AI-use / conflict-of-interest statement; (8) no code LICENSE, no archive deposit location. Minors: unescaped O*NET in Markdown, formatting of upstream vars, H3-at-0.0375 wording, "the one row" counting, the tautological untouched test, power_block writes the frozen power.md in place, check.md predates the final HEAD, C-81 wording, the brief repetition
Controller: filed C-83 (C-81 wording correction; the Plan 4 amendment at 358c021 disclosed)
Fix wave dispatched: prose (I1, I2, minors 1-4, 10 and the Task 31 deferred prose minors) within the page/word budgets; appendix code (I3); untouched test pinned to 75e8956/ebe59be; power_block compare-only; O*NET escaping in includes; open deferred row-note items; ledger committed verbatim + citations repointed (I6). Decisions for Ajai at the STOP: I4, I5, I7, I8 + remote/licence/archive/tag
Fix wave: 06c92a0 (code+tests), 82d7172 (regenerated, no estimate changed), 83b947f (prose), fb2db1c (ledger copy + post-freeze citations repointed). Budgets hold (abstract 200, brief 2 pp, References p.45/395). Not done: the §7 longer-window hedge (page budget). panel_quality.md is still rewritten in place by aideleg.aei (pre-Plan-4 behaviour)
Task 34 Step 1: final fresh-clone replicate.sh at the final HEAD started by the controller (background)
Task 34 Step 1: fresh clone at fb2db1c: seeding 400/400 MANIFEST + 47,946/47,946 docs verified; make all exit 0 in 33m02s, clone tests 1188 pass / 1 skip; first compare 314/315 (paper.pdf page count 389 vs 395: the committed tree's untracked PDF was a pre-fix-wave render); after `make paper brief` in the committed tree, 315/315 IDENTICAL (none needed the C-80/C-82 tolerance). check.md + README runtime block committed. STOP for Ajai (Step 3)
