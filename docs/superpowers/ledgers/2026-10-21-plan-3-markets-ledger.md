# SDD ledger — plan: docs/superpowers/plans/2026-10-21-plan-3-markets.md
Spec: docs/pap/pre-analysis-plan.md (tag pap-v1 + §11) is binding. Branch: plan-3-markets (from plan-2-behaviour 454fdcf).
Global constraints + review focus: global-constraints.md

## Preflight
Plans 2-4 were cross-reviewed (21 rulings applied). The Plan 2 final review found no blocker for Plan 3's confirm_h5 run: it runs from a worktree at pap-v1, and this branch's src changes don't reach it. Plan-internal dependencies run in order T0→T1→T2→T3..T8 (markets) and T9→T10→T11→T12→T13 (H6), then T14.
Ruling P3-R1: the controller executes Task 1 (the single confirm_h5 run) itself, under the protocol's STOP-on-anything rule, mirroring P2 Task 11 — irreversible single run — cost if wrong: none.
Ruling P3-R2: §11 entries in this plan use paplog with results_seen "RQ1 confirmatory results seen" before Task 1, and "RQ1 and H5 confirmatory results seen" after (post-result subsection) — the honest state — cost if wrong: none.

## Tasks
Task 0: BLOCKED at Step 2 — French documents no timing for "Average Firm Size" (8 pages checked, 2026-10-22)
Task 0: Ruling: determine SIZE_ME_OFFSET empirically from pre-seal rows (<= 2022-11-29, non-July months) via corr(size growth, prior-month vs same-month VW return), with a committed script; the decision needs a decisive gap, else STOP — a mechanical file property; pre-seal reads already allowed — cost if wrong: cap-weight timing off by a month in secondary/exploratory analyses only
Task 0: implemented 454fdcf..1abd4a4; review Approved; SIZE_ME_OFFSET=1 (pooled corr with prior-month return 0.9558 vs same-month 0.0838; median 0.9724 vs 0.0902); §11 A-3 + C-33..C-43 (post-result subsection)
Task 0: minor (deferred): C-35 says <=2022-11-29 but the script stops at 2022-10
Task 0: complete (commits 454fdcf..1abd4a4, review clean)
Task 1 Step 1: all preconditions verified (tag annotated, 6a16b1a, blobs f581264a/a353a7c2, no prior H5 output, WT absent, save_figure on plan-2, status clean); the plan-file names are dated (known, Plan 2 T1)
Task 1 Steps 3-6: worktree at 6a16b1a (/Users/ajaiupadhyaya/Documents/ai-delegation-pap-v1); 8 raw subdirs symlinked, WT status empty; uv sync --locked + make exposure OK, no status changes; preflight printed exactly "preflight ok" (check_binding, check_french_data, EXPOSURE_SHA256 match)
Task 1 Step 7: single run starting — NEVER REPEAT
Task 1 Step 8: outcome A (exit 0; both files; first line "# Confirmatory test of H5 and H5b")
Task 1 Step 9: committed unedited as ebe59be (exactly 2 files; SHA-256 pairs identical); console log: .superpowers/sdd/2026-10-21-plan-3-markets/confirm_h5_console.log
Task 1 Step 10 fixed wording (verbatim):
  - Fixed wording: H5 is not rejected (H0: b = bbar (the 1990-2022 pattern for this exposure vector)). Interval [-2.76, 6.68] pp per 1 SD; the test had 80% power only against a departure from H0 of at least 7.43 pp per 1 SD (MDE at Holm level 0.025).
  - Fixed wording: H5b is not rejected (H0: b = bbar (the 1990-2022 pattern for this exposure vector)). Interval [-1.86, 8.79] pp per 1 SD; the test had 80% power only against a departure from H0 of at least 8.38 pp per 1 SD (MDE at Holm level 0.025).
Worktree /Users/ajaiupadhyaya/Documents/ai-delegation-pap-v1 left in place (removal is Ajai's call)
Task 1: complete (outcome A; commit ebe59be)
Task 2: implemented ebe59be..0e5057a; review: 2 Important (the guard pins the record to HEAD, not ebe59be; public unguarded read_french_annual)
Task 2: Ruling: pin the confirmatory record by blob SHA at ebe59be — a committed edit must not pass the guard — cost if wrong: none
Task 2: carry to Tasks 6/7: test the July boundary (beme.year → months; a July-t me_date selects the prior-June row)
Task 2: fix round 1/5 (2 addressed; 0e5057a..8895099); pins verified by the controller
Task 2: minor (deferred): plan text still names data.read_french_annual (now private)
Task 2: complete (commits ebe59be..8895099, review clean)
Task 3: implemented 8895099..eebcfa1; review Approved; parity H5 1.958 / H5b 3.461; vector_test reproduces the frozen s/bbar/q exactly; Softw DFBETAS +0.148 (H5) / -0.062 (H5b), Cook's D 0.012/0.002
Task 3: Ruling: promoted cache-fingerprint and shape checks (Plan 4 reuses vector_test) — cost if wrong: none
Task 3: fix round 1/5 (cache fingerprint, length checks, mkdir; eebcfa1..01738b6); influence outputs reproduced byte-for-byte
Task 4: dispatched implementer (concurrent with Task 3 read-only re-review; new files only)
Task 3: re-review: all 3 addressed, no new breakage
Task 3: minor (deferred to final review): cache fingerprint hashes shapes/date spans, not values (same-shape revision of French data would slip; raw is MANIFEST-hashed); fingerprint load runs on cache hits
Task 3: complete (commits 8895099..01738b6, review clean)
Task 4: implemented 01738b6..1439d56; 9 tests, full suite 530 passed
Task 4: review Approved (formulas verified term by term; 9 tests pristine)
Task 4: Ruling: promote 4 minors (psr raises ValueError on non-positive variance term instead of NaN — not a spec change, the value is undefined; shared-draw test; use_t pin; DSR sr0 pin) — Plan 4 reuses these — cost if wrong: none
Task 5: dispatched implementer (opus) concurrent with Task 4 fix (disjoint files; explicit staging)
Task 4: fix round 1/5 (1439d56..7b4ef69; 13 stats tests); controller inline re-review of the 41-line diff: all 4 addressed. psr guard is unreachable with sample moments (g4 >= g3^2+1 implies the term >= (1-g3*s/2)^2), so it is defensive only
Task 4: incident: the fix agent ran `git checkout -- src` to undo an accidental ruff format; the tree was clean afterwards; Task 5 agent warned to re-check its tracked edits
Task 4: complete (commits 01738b6..7b4ef69, review clean)
Task 5: implemented 7b4ef69..72be264 (DONE_WITH_CONCERNS: narrowed a Plan 2 figure-dir test; real run twice, the second fixing one md sentence (A_pooled = r2-r6), CSVs byte-identical; fig_dir kwarg; HC3 normal ref); ChatGPT z_aioe [0,+9] -0.135 pp [-0.917, 0.647] p=0.74; n=49, none dropped/moved
Task 5: review Approved (window/AR/CAR/units/calendar/drops/inference match D19 + C-33; D19 list and disclosure verbatim; zero-assigned 12.14%/6.34%)
Task 5: rulings on concerns: Plan 2 test narrowing OK, but exclude only fig_rq3_/fig_h6_ instead; the A_pooled r2-r6 sentence is correct; fig_dir kwarg OK; HC3 normal ref consistent with H4 (t(47) would widen CIs by about 2.6%; switching now would need a D-entry, so kept)
Task 5: Ruling: promote the test prefix fix, the verbatim D19 RULE text, exposure-missing listing, and one post-result §11 C-entry recording the defaults (VW, normal-ref HC3, all-horizon drop rule) plus the post-result label fix — the global constraints require C-entries for defaults — cost if wrong: none
Task 5: fix round 1/5 (72be264..dfb9a42); controller verified: PAP diff append-only (C-44, +6 lines), CSVs + figures byte-identical, only md text changed
Task 5: complete (commits 7b4ef69..dfb9a42, review clean)
Task 6: dispatched implementer (opus); instructed to file a pre-output C-entry for estimate-affecting defaults; July-boundary carry included
Task 6: implemented dfb9a42..b12cb06; C-45 (8 defaults, pre-output); 568 pass; all CIs include 0; B cap FF5+UMD alpha 0.89 pp [-8.78,10.56] p .842 (FF3 12.9 — model-sensitive); A_r2 cap 3.71 [-2.40,9.82] p .226; July carry -> Task 7
Task 6: review Approved; all 8 C-45 defaults legitimately PAP-silent (no D-entry); look-ahead impossible (me_date join); FF3 vs FF5+UMD gap is real (H-L loads -0.67 HML; -0.62 RMW, -0.89 SMB, -0.32 UMD, R2 .87), not an alignment bug
Task 6: reviewer could not verify from git that C-45 was filed before the run (same commit); accepted on the implementer's report
Task 6: Ruling: promote shared NaN/<=0 cap predicate and a public me_date helper (outputs must stay byte-identical) — cost if wrong: none
Plan 4 note: a passed-expo terciles.md/event_study.md defers the zero-assigned share to the caller; Plan 4 robustness docs must state it (D3/ruling 19)
Task 8/paper note: DSR N=6 overstates effective trials (B is a subset of A months; A_r2 ~ A_pooled); B FF5+UMD alpha has 10 df, so the FF3-vs-FF5+UMD contrast is fragile; say so
Task 6: fix round 1/5 (b12cb06..527e2ba); controller verified docs/ unchanged by the fix; data.py refactor checked
Task 6: complete (commits dfb9a42..527e2ba, review clean)
Task 7: dispatched implementer (opus); July-boundary end-to-end test carried in; code+C-entry commit required BEFORE the real run (separate outputs commit) so ordering is verifiable
Task 7: implemented 527e2ba..575b093 (c9bf2fa code+C-46 before run; 575b093 outputs); 589 pass; z slope pp/mo: B .233 [-.40,.87] p .448; A_r2 .208 [-.03,.45] p .087; A_pooled .171 [-.06,.40] p .144; n=48 (Smoke excluded: negative aggregate BE/ME, rule pre-filed)
Task 7: review Approved (t/p/CI/NW lag recomputed from csv exactly; momentum date-indexed; July boundary end-to-end OK; BE/ME label year = formation year, confirmed by the presence of a 2026 row; C-46 in c9bf2fa before outputs 575b093; PAP append-only)
Task 7: Ruling: promote the Smoke reason label (BE/ME <= 0) as a post-result label-only C-entry, a single skip list, and the t-13 momentum test; csv must stay byte-identical — cost if wrong: none
Task 7: fix round 1/5 (575b093..0c66f1d; C-47 label-only); controller verified csv byte-identical, PAP append-only, data.beme default unchanged
Task 7: complete (commits 527e2ba..0c66f1d, review clean)
Task 8: dispatched implementer (opus)
Task 9: dispatched implementer (sonnet) concurrent with Task 8 (disjoint files: new h6 package; explicit staging)
Task 9: implemented acfeafd (15 tests; D12 matches brief exactly); default: gate = any raw regex occurrence of a GATE term, independent of terms arg
Task 8: implemented acfeafd..1625554; 613 pass; make rq3 (with -o exposure parquet: mtimes stale after checkouts) byte-identical, only summary.md new
Task 8: review Approved (fixed wording verbatim 2/2; record commit ebe59be; no estimates in summary; all never runs confirms); the mtime rebuild is a local artefact (derived/ gitignored; data.py checks EXPOSURE_SHA256, so a changed parquet fails loudly); influence.md stays a diagnostic
Task 8: Ruling: promote the zero-assigned-line consolidation (5 copies -> 1 helper; output byte-identical) — cost if wrong: none
Task 9: review Needs fixes (2 Important, plan-mandated): matching defaults not logged as a C-entry; Unicode hyphens (U+2010/2011, soft hyphen) unmatched. Raw-occurrence gate upheld as more faithful to D12 ("also contains")
Task 9: Ruling: U+2010/2011 are hyphens; delete U+00AD/U+200B after NFKC; acronym boundary Unicode letter/digit (D12 "non-letter"); bisect overlap; one C-entry (a)-(g) before any H6 output; Task 13 passes html=False for .txt — D12 wording governs over the brief's ASCII class — cost if wrong: small H6 count differences, all logged pre-result
Task 9: fix round 1/5 (7700309; C-48)
Task 8: fix round 1/5 (297ed3b refactor; docs/results + docs/paper unchanged, verified by controller); no D-entry: a refactor with byte-identical outputs is not an analysis change
Task 8: complete (commits acfeafd..297ed3b, review clean)
Task 9: re-review: all 5 addressed (bisect equivalence argued + 20k randomized cases vs naive), no new breakage
Task 9: complete (commits 0c66f1d..7700309, review clean)
Task 10: dispatched implementer (opus); SEC UA from http.py, SEC-only; C-entry for denominator defaults required before H6 results
Task 10: implemented 297ed3b..4f02da1; C-49 + A-4..A-32; 29 MANIFEST records (submissions.zip 1.57 GB); 49,726 filings, 6.5k-7.7k CIKs/yr; unmapped 810-1038/yr (mostly SIC 6189 ABS); real row offsets 0/17/79/91/103 differ from label offsets
Task 10: review Approved (layout verified on all 28 files: 155-char rows, identical header; MANIFEST/A-entries/disk SHA match; PAP append-only; C-49 defaults upheld, mostly PAP-bound via D18/C-40); unmapped 12-15%/yr follows D18 (nothing covers SIC 6180-6189) — the H6 write-up must state it
Task 10: disclosure: denominator counts were printed at build time, before C-49 was committed; no default changed afterwards and none depends on them (C-49's "before any H6 output" slightly overstates; accepted, no new entry). One ad-hoc 2024Q1 form.idx GET (300 KB) was used to read the layout, then discarded and not recorded
Task 10: Ruling: promote the download wrapper signature, the zero-filled denominator grid, a real Siccodes49 data test, and a comment fix — cost if wrong: none
Task 11/12 note: numerator per-CIK convention must mirror C-49(3) (each co-registrant CIK once per year)
Task 10: fix round 1/5 (d09353f; 4 minors; counts unchanged on rebuild); controller checked the stat
Task 10: complete (commits 297ed3b..d09353f, review clean)
Task 11: dispatched implementer (opus); background resumable FTS acquisition; C-entry before any per-industry numerator on real data
Task 11: implemented d09353f..8fd155e; C-50 (pre-acquisition) + A-33 set digest; 285 sec_fts records, no splits/caps; 20,581 hit rows; offline rebuild equal; 0 out-of-denominator; 869 amendments excluded; added 200-with-error-JSON refetch + 0.5 s pause; FtsPageError exact-total check
Task 11: review Approved (all 105 page-0 eq, max total 3,327 for "artificial intelligence" 2025; 285 files SHA-match; 0 error bodies; every hit's (adsh, cik) is in filers with date_filed == file_date, so 0 out-of-denominator is a real agreement; A-33 digest recomputed; PAP append-only); C-50 timing not git-verifiable (same commit), but no H6 output exists
Task 11: Ruling: promote the partial-response (timed_out/_shards.failed) retry, removal of the unread _ERROR_BODIES, and skipping non-intersecting ranges in hits_from_saved — Plan 4 R29/R30 re-query through this code — cost if wrong: none
Task 11: fix round 1/5 (5469e2e; offline rebuild still equal; no re-acquisition)
Task 11: complete (commits d09353f..5469e2e, review clean)
Task 12: dispatched implementer (opus); first H6 results; code+C-entry commit before real run, outputs in a separate commit
Task 12: implemented 5469e2e..929a094 (0451db1 code+C-51; 929a094 outputs); 665 pass; pooled talk .082 (2019), .198 (2023), .375 (2024), .516 (2025); Spearman(T, z_usage) .361 [.050, .612]; gap-return b -2.398 pp [-6.48, 1.68] p .215 vs bbar; unmapped 14.4% in 2024
Task 12: review Approved (Spearman .36071 and gap-return T/p/CI recomputed exactly; C-51 defaults all consistent, no D-entry; commit split verified; PAP append-only)
Task 12: the 2023->2024 talk jump looks real: "artificial intelligence" 1213->2386 CIKs, "machine learning" 860->1215, specialist terms flat (no index-wide shift), quarterly rise within 2023 follows the 10-K cycle; only 31 of 2538 2024 CIKs are found by gen-AI phrases alone; not checkable offline: EFTS phrase semantics across index years
Task 12: Ruling: promote the figure label collisions and n_talk/n_filers columns in the gap.md ranking (presentation only; one post-result C-entry; csv byte-identical) — cost if wrong: none
Task 12: plan inconsistency noted: Step 1 says every doc's first line contains "exploratory (PAP §6, D18)", Step 5 fixes the summary heading as "(exploratory, PAP §6, D18)"; Step 5 followed and tested separately
Task 13 carry: report a per-filer/year agreement table between the FTS talk indicator and the text-based "any primary term" indicator for 2019-2025 (reporting only) — the direct check on the 2023->2024 jump
Task 12: fix round 1/5 (7ed86cf; C-52 presentation-only; csv byte-identical, verified by controller)
Task 12: complete (commits 5469e2e..7ed86cf, review clean)
Task 13: dispatched implementer (opus); ~49.7k doc download in background after a pilot; FTS-vs-text agreement table carried; C-entry before secondary run
Task 13: implemented 7ed86cf..8e94fab (ef36de5 code+C-53 first; 8e94fab MANIFEST sec_docs_index + A-34 + outputs); 47,946 docs, 138.7 GB raw / 9.2 GB gz, 0 skipped, 0 errors; mean rate/10k words .109 (2019) .349 (2023) .904 (2024) 1.525 (2025); Spearman(sec 2024, T_j) .567; FTS-vs-text agreement >= .999 every year; caffeinate used, no settings changed
Task 13: review Needs fixes (1 Important): 2+ truncated primary docs saved (IronNet 2022, SNAX 2021 FY; fetch.py skips the Content-Length check under gzip Content-Encoding); IronNet is a 2022 FTS-only cell. Otherwise sound: A-34 digest recomputed, C-53 committed 12 s before the first download, agreement >= .999 genuine (same phrases on the same docs; FTS-only 32 = 30 exhibit-only + foundation-model semantics + IronNet truncation); 2x2 2023 1434/4/0/5817, 2024 2533/5/0/4236; Spearman no CI accepted as descriptive (D18 gives the secondary no inference; C-53(8))
Task 13: Ruling: a data-integrity correction, not a PAP spec change — proceed without Ajai, fully logged: completeness check, full tail scan, re-fetch flagged docs, superseding set-digest A-entry, rerun secondary, D-entry with before->after values; plus 3 minors — cost if wrong: Ajai may prefer to have been asked; reported to him in the summary
Task 13: fix round 1/5 (86628e7, dc63b29, f93ad8a): full tail scan flagged exactly the 2 docs; re-fetched whole; A-35 supersedes A-34; D-1 (only 2022 moved: both 1333->1334, FTS-only 5->4; 2024 + Spearman unchanged); end-marker accepts </DOCUMENT> endings (287 bodies with malformed HTML)
Task 13: re-review: all 4 addressed, no new breakage (both docs whole; INDEX 47,946 distinct; MANIFEST/A-35 match; widening made before the refetch and disclosed in D-1; 287 accepted bodies sampled whole)
Task 13: note: .txt truncation is undetectable by check_complete (all 24 current .txt end in </document>); D-1 approval "not sought" — relay to Ajai
Task 13: complete (commits 7ed86cf..f93ad8a, review clean)
Task 14: Ruling: the controller runs Task 14 itself (verification only, like P3-R1) — cost if wrong: none
Task 14 Step 1: rebuild from scratch (rm data/derived/h6; make rq3; make h6, 13 min) is byte-identical except docs/results/h6/summary.md, which was stale (Task 13 never regenerated the index to link secondary_talk.md). Not nondeterminism; committed the regenerated file (link line only) — cost if wrong: none
Task 14 Step 2: first full suite gave 680 pass, 1 fail (test_every_addition_logged still held the superseded A-34 to the current INDEX; the Task 13 fix ran only h6/paplog tests). Fixed test-only: the latest sec_docs_index set entry governs (commit after d26b1fd); now 681 passed, ruff clean; binding-refusal, numeric-versions and pap_frozen tests all pass
Task 14 Step 3: git diff pap-v1 -- confirm_h5.py power.py market/ is empty
Task 14 Step 4: all 23 listed outputs and 10 fig_rq3_/fig_h6_ files are committed; tree clean apart from .superpowers/
Task 14: complete. STOP: no merge or push without Ajai's go-ahead
Final whole-branch review: dispatched (plan-2-behaviour..HEAD)
Final review: Needs a fix wave, 0 Critical, 5 Important, none of which changes an estimate: (1) tercile/FM disclosures (B = A_r2 exposures, DSR N overstates trials, T=17 / 10 df fragility); (2) event-study HC3 size caveat and the "p = 0.0000" format; (3) the §11 process record and D-1 ratification by Ajai; (4) hits_from_saved does not raise on an uncovered range, but Plan 4 assumes it does; (5) the guard needs git (blob pins) for a replication archive
Final review: Ruling: one fix wave (A disclosures + p format + small wording; B saved_ranges/strict; C no-.git blob-hash fallback; D Plan 4 text; E .gitignore .superpowers/; F one process-record C-entry). Deferred minors: duplicated helpers, the value-blind cache fingerprint, fetch.py's Content-Length under gzip (Plan 4 downloads should use secondary-style completeness checks), data-marked tests not auto-skipped
Final fix wave: cf27c32 (code+tests, A/B/C), 0473eda (docs + C-54), 358c021 (Plan 4 text + .gitignore). Controller verified: CSVs and figures byte-identical to b5d137b; PAP append-only; tree clean; 699 tests pass; ruff clean
Final fix wave: Plan 4 text updated for blob-pinned fixture bytes, the README git-clone/no-.git fallback, hits_from_saved(strict=True)/saved_ranges(), no "ChatGPT" placebo name, R4/R8 RNG-order draws, and zero_assigned_lines reuse
Deferred to Plan 4/paper: the HC3 caveat is in event_study.md but not eisfeldt_replication.md; duplicated helpers; the value-blind cache fingerprint; fetch.py's Content-Length check under gzip; data tests not auto-skipped
Open for Ajai: ratify D-1 (the truncated 10-K re-fetch, filed under a controller ruling); merge/push decisions; removal of the pap-v1 worktree
PLAN 3 COMPLETE (plan-2-behaviour..358c021). STOP: no merge or push without Ajai's go-ahead
