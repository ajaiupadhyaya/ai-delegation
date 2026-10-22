# Plan 3 — Markets and Talk-vs-Use (RQ3 + H6)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
- run the single confirmatory H5/H5b test (PAP §0.5 P-H5) once, from a checkout of `pap-v1`, and commit its record unedited;
- then produce every RQ3 and H6 item the PAP assigns to the period after that run: the Softw influence diagnostics (§3.3 P11), the §8.3 exploratory market analyses (Design A, the D19 event studies, terciles, Fama–MacBeth, the Eisfeldt, Schubert & Zhang replication) and H6 (§6, D18, D12).

**Architecture:**
- Task 1 runs `aideleg.confirm_h5` in a detached git worktree at `pap-v1`, with `data/raw` reached through symlinks. Its two output files are copied byte-for-byte onto `plan-3-markets` and committed alone.
- New code lives in two new packages, `src/aideleg/rq3/` and `src/aideleg/h6/`. The bound modules (`confirm_h5.py`, `power.py`, `market/*.py`) are never edited.
- Every read of market data on this branch goes through `rq3.guard.assert_confirmatory_recorded()`. It refuses until the committed confirmatory record exists.
- Results are generated (never hand-edited) under `docs/results/rq3/` and `docs/results/h6/`. Figures go through Plan 2's `aideleg.figures.save_figure`.

**Tech Stack:** Python 3.12, uv, Polars, NumPy, SciPy, statsmodels 0.15.0 (OLS, HAC, `OLSInfluence`), matplotlib through Plan 2's figure system, requests (SEC), pytest, ruff. No new dependencies.

**Spec / authority (in this order):**
1. `docs/pap/pre-analysis-plan.md`, frozen at `pap-v1`: §0.4, §0.5 P-H5, §3, §6, §8.3, §9, §10; and §11, which this plan writes only through Plan 2's `aideleg.paplog`: `A-<n>` additions (D20), `C-<n>` pre-result clarifications (Task 0), and `D-<n>` deviations only with Ajai's approval.
2. `docs/superpowers/specs/2026-10-21-ai-delegation-design.md` §5.4, §5.5, as corrected by PAP §10.
3. Plan 1 conventions and the controller brief `.superpowers/plans-2-4-brief.md`.

**Scope:**
- **Not in this plan:** every PAP §8.2 robustness row. All of them go to Plan 4, including R5, R6, R8, R9, R18, R19, R29, R30, R32, R34 and R35, which the PAP text attributes to "plan 3". Task 0 records this as an organisational note in §11 (R6, R32 and R35 move from "plan 3" to Plan 4, with no specification change).
- Plan 4 calls this plan's functions with variant inputs. The Interfaces blocks name the parameters it uses: `expo=` and `months=` on `run_terciles` and `run_fm`, `expo=` and `events=` on `run_events`, `fm_panel(expo, months)`, `fts_hits(phrase, start, end)`, `fts_phrases(terms)`, `count_terms(terms=)`, `vector_test(hist=)`. There is no separate Design A cross-sectional test: Design A is analysed by the terciles, Fama–MacBeth and the event slopes.

## Global Constraints

Copied verbatim from Plan 1:

- Repo root: `/Users/ajaiupadhyaya/Documents/ai-delegation`. Package: `src/aideleg/`. Tests: `tests/`.
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Wording rule (spec §6):** in code comments, docs and output labels, AEI data is "conversations matched to X tasks". Never infer job risk, displacement or reassurance. Say "labour market".
- **Market seal:** no code path may read French returns or factors dated ≥ `2022-11-30` unless the git tag `pap-v1` exists. Nothing in this plan is allowed to need them.
- Raw data are never committed. `data/raw/MANIFEST.json` (URL, retrieval UTC timestamp, bytes, SHA-256) is committed.
- HTTP User-Agent for `bls.gov` and `sec.gov`: `"Ajai Upadhyaya research ajaiupad@gmail.com"`. SEC requests must be ≤ 10/s.
- Randomness is seeded through `aideleg.config.SEED = 20261021`.
- Dates in the spec, copied verbatim:
  - ChatGPT launch: `2022-11-30`
  - Design B formation release: `r2` (published `2025-03-27`)
  - Design B return window: `2025-04-01` → `2026-08-31`
  - OEWS weight vintage: May 2024 (`oesm24*`)

**As amended for Plan 3 (PAP §0.5):**
- **The seal.** The tag exists, so the seal line above no longer forbids post-seal reads. It is replaced by P-H5:
  - the first post-seal read is Task 1's single run;
  - nothing else on this branch reads market data until Task 1's commit exists, which `rq3.guard` enforces.
- **Branch.** `plan-3-markets` is cut from the tip of `plan-2-behaviour`. That branch was cut from `plan-1-foundations` and carries `aideleg.figures`; plans run 2 → 3 → 4.
- **Never edit** `src/aideleg/confirm_h5.py`, `src/aideleg/power.py` or `src/aideleg/market/*.py`. Never change the Design B exposure or benchmark outputs. `rq3.data.exposures()` refuses unless the Design B vector hashes to `confirm_h5.EXPOSURE_SHA256`.
- **Labels.**
  - Every §8.3 and H6 output is labelled **exploratory** in its first heading and in every figure title.
  - Every estimate is given with a point value, a CI and a nominal p-value. No stars.
  - A null is reported with the same prominence as a rejection.
  - No output counts significant results.
- **Results-dependent steps are reporting steps only.** No specification, window, sample or parameter below may change after an output has been seen. A needed change is a STOP: it goes in a §11 deviation, with Ajai's approval.
- **No silent fixes.** Every change to Plan 3 analysis code made after any of its results has been seen (a bug fix included) is a §11 `D-<n>` entry (`paplog deviation`) with the date, the reason and both values (before and after), relayed to Ajai and committed with his approval. A commit message saying "bug fixed" is never enough.
- **Pre-result clarifications.** Every default this plan fixes where the PAP is silent is logged as a §11 `C-<n>` entry in Task 0, before Task 1's run. The plan file was committed in Plan 2 Task 1, which timestamps it.
- **Wording.** The one required disclaimer is Plan 2's `aideleg.results.common.WORDING`, imported with `FORBIDDEN_PHRASES`; this plan defines no disclaimer of its own and tests its own docs (Task 8).
- **Exposure reports.** Every doc that reports an exposure index (every rq3 doc, and the h6 docs that use `z_usage`) states the zero-assigned employment share of each design it uses (D3), computed by `audit.design_zero_assigned` and never typed.
- **Figure names** are `fig_rq3_…` and `fig_h6_…`.
- **Dependencies.** None are added. `tests/test_lock_pins.py` (Plan 2) stays green.
- **Generated docs are never hand-edited.** A re-run on unchanged inputs must reproduce them byte for byte (Task 14).
- **Units.**
  - Alphas: annualised pp. CARs: pp.
  - Slopes: pp per 1 SD of exposure.
  - Fama–MacBeth coefficients on exposure: pp per month per 1 SD, with ×12 shown beside them.
- **SEC access** goes only through `aideleg.acquire.http.session_for`, which sets the contact UA and keeps the process-wide 0.1 s spacing; requests run in one process at a time. Every raw SEC file is saved under `data/raw/sec/` and recorded (Tasks 10, 11, 13). Each acquisition is logged in PAP §11 as an **addition**, which D20 says is not a deviation.
- **Test commands:** `uv run pytest tests/rq3 tests/h6 -v` and `uv run ruff check`. Tests marked `data` need the built derived files.

## Review Focus

1. **The EDGAR full-text-search hit cap.**
   - *Failure mode:* a query whose total reaches the cap (relation `gte`, or value ≥ 10,000) silently truncates the numerator.
   - *Expected:* the date range is bisected until every sub-range is exact. A single day still at the cap raises.
   - *Tests:* `test_fts_splits_range_when_total_hits_cap` and `test_fts_single_day_over_cap_raises` (Task 11).
2. **Amendments, co-registrants and duplicates in "talk".**
   - *Expected:* `10-K/A` never counts. Each CIK on a multi-filer hit counts once. A CIK found by several phrases or pages counts once. A hit CIK that is not in that year's full-index denominator is reported, not counted.
   - *Test:* `test_numerator_counts_distinct_ciks_excluding_amendments` (Task 11).
3. **Event days that are not trading days, and gaps in the estimation window.**
   - *Expected:* day 0 moves to the next date present in both daily files, and the move is reported. An industry with any missing return in [−250, −21] or in the event window is dropped for that event and reported.
   - *Tests:* `test_day_zero_moves_to_next_trading_day` and `test_industry_missing_estimation_return_is_dropped` (Task 5).
4. **Acronym false positives and double counting.**
   - *Expected:* `AI` counts only in a filing that also contains "artificial intelligence" or "generative AI", and never inside words such as "MAINE". The `AI` inside "generative AI" is not counted again. "generative artificial intelligence" counts once.
   - *Test:* `test_acronyms_need_the_gate_and_longest_match_wins` (Task 9).
5. **Silent drift from the committed record.**
   - *Failure mode:* derived data rebuilt by changed code, or recomputed confirmatory alphas that no longer match the committed result.
   - *Expected:* a refusal, not a quietly different number.
   - *Tests:* `test_exposures_refuse_on_hash_mismatch` (Task 2) and `test_check_matches_confirmatory_raises_on_mismatch` (Task 3).

---

## File map

```
src/aideleg/rq3/__init__.py
src/aideleg/rq3/guard.py          assert_confirmatory_recorded(): no market read before Task 1's commit
src/aideleg/rq3/data.py           guarded loaders (daily, monthly, FF3 monthly, firm counts/size, BE/ME), exposures(), zero_assigned()
src/aideleg/rq3/inference.py      confirmatory alphas, historical alpha matrix, vector_test(), influence()
src/aideleg/rq3/stats.py          nw_lag, hac_regression, sharpe, psr, dsr, stationary bootstrap
src/aideleg/rq3/events.py         D19 events, day 0, CARs, CAR-on-exposure, Eisfeldt et al. replication
src/aideleg/rq3/terciles.py       fixed-membership terciles, cap/EW legs, alphas, Sharpe/PSR/DSR, costs
src/aideleg/rq3/fama_macbeth.py   momentum, BE/ME timing, monthly cross-sections, NW
src/aideleg/rq3/report.py         markdown helpers (WORDING imported from Plan 2), summary.md
src/aideleg/rq3/__main__.py       python -m aideleg.rq3 {influence,events,terciles,fm,summary,all}
src/aideleg/h6/__init__.py
src/aideleg/h6/dictionary.py      D12 terms, text cleaning, count_terms(), fts_phrases()
src/aideleg/h6/edgar.py           form.idx, bulk submissions SIC, FF49 mapping, FTS queries, rebuild from saved responses
src/aideleg/h6/talk.py            talk index, gap, Spearman bootstrap, gap-return test, figures
src/aideleg/h6/secondary.py       primary-document download, per-10k-word rates, industry means
src/aideleg/h6/__main__.py        python -m aideleg.h6 {acquire,build,talk,secondary,summary,all}; all = build+talk+secondary+summary (no network)
src/aideleg/acquire/sources.py    MODIFY: ff3_monthly (Task 0); 28 form.idx keys + sec_submissions_bulk (Task 10)
src/aideleg/acquire/fetch.py      MODIFY: public download(src, path) wrapper of _download
Makefile                          MODIFY: targets rq3, h6-data (network), h6 (offline)
docs/results/confirmatory_h5.md, confirmatory_h5.attempt   (Task 1, unedited)
docs/results/rq3/*.md|csv, docs/results/h6/*.md|csv        (generated)
docs/pap/pre-analysis-plan.md     MODIFY §11 only, through aideleg.paplog: A- additions, C- clarifications
tests/rq3/*, tests/h6/*, tests/fixtures/french/ind_monthly_small.csv, tests/fixtures/sec/*
```

---

### Task 0: Branch, French firm-size definition, FF3 acquisition, pre-result clarifications

Everything here happens before Task 1, reads no return, and changes no specification.

**Files:**
- Modify: `src/aideleg/acquire/sources.py` (key `ff3_monthly`), `tests/acquire/test_sources.py` (`REQUIRED`), `data/raw/MANIFEST.json`, `docs/pap/pre-analysis-plan.md` (§11 only, through `paplog`)
- Test: `tests/acquire/test_sources.py`, `tests/test_pap_frozen.py` (Plan 2)

**Interfaces:**
- Consumes: Plan 2's `aideleg.paplog` CLI; `fetch.Source`, `sources._zip`, `FF`.
- Produces:
  - registry key `ff3_monthly` = `_zip("ff3_monthly", f"{FF}/F-F_Research_Data_Factors_CSV.zip", "french")` (canonical Fama–French 3-factor monthly file);
  - the verified French firm-size convention, as the integer `SIZE_ME_OFFSET` that Task 2 writes into `rq3/data.py`: the number of months between a row's date in the "Average Firm Size" table and the month-end of the market equity (ME) it holds (1 if row t holds ME at the end of t − 1; 0 if row t holds ME at the end of t);
  - §11 entries: one `A-` for `ff3_monthly` and the `C-` entries listed in Step 5.
  - `ff3_daily` is **not** acquired: no FF3 analysis in this plan or in Plan 4 is daily (the event studies use FF5+UMD).

- [ ] **Step 1: Branch.** With `MAIN` as defined in Task 1: `git -C $MAIN switch -c plan-3-markets plan-2-behaviour`. Expected: `Switched to a new branch 'plan-3-markets'`.
- [ ] **Step 2: Verify French's "Average Firm Size" definition.** The `ff49_monthly` zip holds only the CSV, whose preamble does not define it. Read French's "Detail for 49 Industry Portfolios" page (`https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_49_ind_port.html`) and, if it is silent, the general portfolio-formation notes it links. Copy the defining sentence verbatim into the ledger with its URL and retrieval date, and set `SIZE_ME_OFFSET` from it. If no page states the timing, STOP and report: the PAP's "prior month-end" cap cannot be read off the file without it.
- [ ] **Step 3: FF3 key.** Add `ff3_monthly` to `SOURCES` and to `REQUIRED` in `tests/acquire/test_sources.py` (keeping Plan 2's keys). Run `uv run pytest tests/acquire -q`. Expected: PASS.
- [ ] **Step 4: Acquire and log.** `uv run python -m aideleg.acquire --only ff3_monthly` (download and unzip only; no row is parsed). Then `uv run python -m aideleg.paplog addition --keys ff3_monthly --scope "outside §9.4; the PAP names FF3; FF5 2×3 SMB is not FF3 SMB" --used-by "Plan 3 Task 6 tercile FF3 alphas"`. Expected: one MANIFEST record and one new `A-` entry.
- [ ] **Step 5: Log the pre-result clarifications.** One `uv run python -m aideleg.paplog clarification --title … --rule … --plan "Plan 3 Task <k> (plans committed at <Plan 2 Task 1 Step 1 hash>)"` per row, in this order:

  | Title | Task | Rule |
  |---|---|---|
  | Event-study cross-sectional inference | 5 | Each CAR-on-exposure regression is OLS with an intercept and HC3 SEs, nominal and single-test; randomisation inference is not used (PAP §3.2 documents its size). |
  | Tercile ties and size | 6 | k = n // 3 over industries with non-null exposure; ties at a cut broken by ascending `ff49`. |
  | French firm-size timing | 2, 6, 7 | French defines "Average Firm Size" as <the verified sentence, Step 2>. Cap weights for month t and FM `log_size` use the row whose ME is the prior month-end, i.e. the row dated t − (1 − SIZE_ME_OFFSET) months, SIZE_ME_OFFSET = <value>. Cap = average firm size × number of firms, both from that row. |
  | FF3 factors | 6 | FF3 alphas use Mkt-RF, SMB and HML of `F-F_Research_Data_Factors_CSV.zip` (`ff3_monthly`), never FF5 columns. |
  | Tercile bootstrap and DSR | 6 | The stationary bootstrap (block 3, 10,000 draws) is applied to the Sharpe ratio and the mean, one draw set per variant, one `default_rng(SEED)` consumed in `VARIANTS` order; the DSR is taken over the variants run (six in the primary run). |
  | Fama–MacBeth characteristics | 7 | log BE/ME = ln("Sum of BE / Sum of ME") with French's July–June timing; a month with n ≤ regressors + 1 complete industries is skipped and counted. |
  | Exhibit-only CIKs | 11 | A CIK whose only hit is in an exhibit of a 10-K (`file_type` not in FORMS) counts in `n_talk`; such CIKs are also reported separately. |
  | SIC source | 10 | SIC = the current SIC of the EDGAR bulk submissions file. |
  | Secondary measure years | 13 | The secondary talk measure covers all D18 filings, 2019–2025. |
  | Gap–return test | 12 | The gap–return association uses the H5 form (no control) with the D21 null and nominal p. |
  | H6 `all` | 12 | `python -m aideleg.h6 all` = build + talk + secondary + summary from saved raw files, with no network; acquisition is the separate `h6-data` target. |
  | Plan of record for R6, R32, R35 | — | Organisational note: R6, R32 and R35 (PAP text "implemented in plan 3") are implemented in Plan 4, after the single confirmatory run; no specification changes. |

  The "French firm-size timing" rule is filled from Step 2 before the command is run.
- [ ] **Step 6: Check and commit.** `uv run pytest tests/test_pap_frozen.py tests/acquire -q` (PASS). Commit `MANIFEST.json`, `sources.py`, the test and the PAP: `docs(pap): FF3 monthly acquired (§11 A-); Plan 3 pre-result clarifications (§11 C-); before the P-H5 run`.
- [ ] **Step 7: Report.** The controller tells Ajai, in chat, that `ff3_monthly` was acquired outside §9.4 and why ("the PAP names FF3; FF5 2×3 SMB is not FF3 SMB"), and gives the verified firm-size sentence.

### Task 1: The single confirmatory run (P-H5) — STOP on anything unexpected

**Files:**
- Create (by the script, in the worktree): `docs/results/confirmatory_h5.md`, `docs/results/confirmatory_h5.attempt`
- Copied unedited onto `plan-3-markets`: the same two paths

**Interfaces:**
- Consumes: `aideleg.confirm_h5` at `pap-v1` (blob `f581264ae9c982ff6a84eb1d1e2f465d18544144`), `power.py` (blob `a353a7c2683d0cc2e9663e17d3835055b3bb63fc`), `pap-v1` → commit `6a16b1ad052977650b90c8062ceeeab9ac6572e1`
- Produces: the committed record that `rq3.guard` (Task 2) requires

`MAIN=/Users/ajaiupadhyaya/Documents/ai-delegation`, `WT=/Users/ajaiupadhyaya/Documents/ai-delegation-pap-v1` (outside MAIN, so neither checkout sees the other), `LOG=$MAIN/.superpowers/sdd/2026-10-21-plan-3-markets/confirm_h5_console.log`.

**Rule for this task.** Every step lists its expected result. If any result differs, or any check refuses: STOP, report the exact output to the controller, and do not work around it. That rules out editing code, config or data, retrying, or using another path. The one run in Step 7 is never repeated, whatever its outcome.

**Why `data/raw` is linked this way.** These are the facts that fix the method:
- `config.RAW = ROOT / "data/raw"`, with `ROOT` derived from the location of `config.py`. At `pap-v1` there is no environment or config override, and adding one would change `src/` and fail `check_binding` (c)/(d).
- `check_french_data(raw=RAW)` hashes `RAW/<dest>` for each French zip and rglobs the extracted directory beside it.
- `data/raw/MANIFEST.json` is tracked. The worktree therefore already holds the tagged copy, and it must stay a regular tracked file. So `data/raw` itself cannot be one symlink.
- Linking each **subdirectory** of `MAIN/data/raw` into `WT/data/raw` works:
  - the links fall under `data/raw/*` in `.gitignore`, so `git status --porcelain --untracked-files=all` stays empty;
  - nothing under `src`, `pyproject.toml` or `uv.lock` changes;
  - `check_french_data` reaches the zips and the extracted members through a symlinked ancestor. pathlib's rglob in Python 3.12 does not follow symlinks *below* its starting directory, and none are needed, because the members are regular files.
- `data/derived` is **rebuilt** inside the worktree from the tagged code rather than linked. That way the vector hash check sees exactly what `pap-v1` builds, whatever Plan 2 did to MAIN's derived files. The ledger records that a fresh rebuild reproduces `EXPOSURE_SHA256`.

- [ ] **Step 1: Preconditions.** Run each command. Expected values:
  - `git -C $MAIN cat-file -t pap-v1` prints `tag`.
  - `git -C $MAIN rev-list -n1 pap-v1` prints `6a16b1ad052977650b90c8062ceeeab9ac6572e1`.
  - `git -C $MAIN rev-parse pap-v1:src/aideleg/confirm_h5.py pap-v1:src/aideleg/power.py` prints the two blobs above.
  - `git -C $MAIN log --all --oneline -- docs/results/confirmatory_h5.md docs/results/confirmatory_h5.attempt` prints nothing.
  - `ls $MAIN/docs/results/confirmatory_h5.* $WT` reports "No such file" for every path.
  - `git -C $MAIN grep -n "def save_figure" plan-2-behaviour -- src/aideleg/figures` prints one match.
  - `git -C $MAIN ls-files docs/superpowers/plans` lists the three plan files, `plans-2-4-brief.md` and `plans-2-4-review-rulings.md` (committed in Plan 2 Task 1).
  - `git -C $MAIN status --porcelain` lists only untracked `.superpowers/`.
- [ ] **Step 2: Branch.** `git -C $MAIN branch --show-current` prints `plan-3-markets` (cut in Task 0), and `git -C $MAIN log -1 --format=%s -- docs/pap/pre-analysis-plan.md` is Task 0's commit.
- [ ] **Step 3: Worktree.** `git -C $MAIN worktree add --detach $WT pap-v1`. Expected: `git -C $WT rev-parse HEAD` prints `6a16b1ad052977650b90c8062ceeeab9ac6572e1`.
- [ ] **Step 4: Link the raw data.** Run `for d in $MAIN/data/raw/*/; do ln -s "${d%/}" "$WT/data/raw/$(basename "$d")"; done`. Expected:
  - `ls -l $WT/data/raw` shows the regular file `MANIFEST.json` and one symlink per subdirectory (`aei benchmarks bls census french onet sec`, plus `geo` from Plan 2);
  - `git -C $WT status --porcelain --untracked-files=all` prints nothing.
  - The extra `ff3_monthly` zip under `french/` is harmless: `check_french_data` checks only the French keys of the tagged MANIFEST.
- [ ] **Step 5: Environment and derived data from the tagged code.** `cd $WT && uv sync --locked && make exposure`. Expected:
  - both commands succeed;
  - `$WT/data/derived/exposure_ff49.parquet` exists;
  - `git -C $WT status --porcelain --untracked-files=all -- src pyproject.toml uv.lock` prints nothing (STOP otherwise: `check_binding` (e) would refuse).
  - Any other path in `git -C $WT status --porcelain --untracked-files=all` (for example a rewrite of `docs/audit/tables/panel_quality.md` by the panel build) is **recorded** in the ledger with `git -C $WT diff --stat`, not a STOP. It is left uncommitted in `$WT`.
- [ ] **Step 6: Pre-flight (hashes only; reads no return).**
  - Run:

    ```
    cd $WT && uv run python -c "from aideleg import confirm_h5 as ch; from aideleg.power import load_exposure; \
    assert str(ch.ROOT) == '$WT', ch.ROOT; ch.check_binding(); ch.check_french_data(); \
    e = load_exposure(); assert ch._vector_hash(e) == ch.EXPOSURE_SHA256; print('preflight ok')"
    ```

  - Expected: exactly `preflight ok`.
  - This calls the script's own pre-marker checks and runs neither `run()` nor any return loader. Any exception is a STOP.
- [ ] **Step 7: The run (once).**
  - `mkdir -p $(dirname $LOG) && cd $WT && uv run python -m aideleg.confirm_h5 > $LOG 2>&1; echo "exit=$?" >> $LOG; cat $LOG`
  - Do not run it again, under any outcome.
- [ ] **Step 8: Classify the outcome.** Read `$LOG` and `ls $WT/docs/results/`.
  - **A (result):** exit 0, both files exist, and the first line of the `.md` is exactly `# Confirmatory test of H5 and H5b`.
  - **B (attempt, after the marker):** `confirmatory_h5.attempt` exists, and the `.md` begins `# Confirmatory test of H5 and H5b: attempt failed` (or is missing). This read post-seal data. It is an **attempt, not a result** (P-H5 6).
  - **C (refusal before the marker):** non-zero exit and no `.attempt`. No market data were read and no result exists. This is a non-event (P-H5 6).
- [ ] **Step 9: Commit (A and B only).** In `$MAIN` on `plan-3-markets`:
  - `mkdir -p docs/results && cp -p $WT/docs/results/confirmatory_h5.md $WT/docs/results/confirmatory_h5.attempt docs/results/`.
    - Under B with no `.md`, copy the marker alone.
  - `shasum -a 256 $WT/docs/results/confirmatory_h5.* docs/results/confirmatory_h5.*`. Each pair must be identical.
  - `git add docs/results/confirmatory_h5.md docs/results/confirmatory_h5.attempt`.
  - `git diff --cached --name-only` must print exactly those paths and nothing else.
  - Commit: `results(h5): the single confirmatory run of aideleg.confirm_h5 at pap-v1 (PAP §0.5 P-H5); output and attempt marker committed unedited`, plus the trailer. Under B the subject starts `results(h5): attempt record (not a result)`.
- [ ] **Step 10: Ledger.** Append to `.superpowers/sdd/2026-10-21-plan-3-markets/progress.md`:
  - the outcome letter, the commit hash and `$LOG`;
  - the two `- Fixed wording:` lines of the `.md`, copied character for character.
  - Leave `$WT` in place. Only Ajai decides whether it is removed.
- [ ] **Step 11: Gate.**
  - **C:** STOP the plan. Nothing is committed. Rerunning needs a §11 deviation with its reason and Ajai's approval (P-H5 6).
  - **B:** STOP the plan after Step 9. A rerun needs a §11 deviation and Ajai's approval, and the attempt record stays committed.
  - **A:** the controller relays the two fixed-wording lines to Ajai and continues with Task 2. No later step depends on the result's sign or significance.

### Task 2: Guard, guarded loaders and exposure checks

**Files:**
- Create: `src/aideleg/rq3/__init__.py`, `src/aideleg/rq3/guard.py`, `src/aideleg/rq3/data.py`, `tests/rq3/__init__.py`, `tests/rq3/test_guard.py`, `tests/rq3/test_data.py`, `tests/fixtures/french/ind_monthly_small.csv`

**Interfaces:**
- Consumes: `market.french.read_french_table`, `load_industry_returns`, `load_factors`, `_single_file`; `power.load_exposure`; `confirm_h5._vector_hash`, `confirm_h5.EXPOSURE_SHA256`; `benchmarks.benchmark_ff49`; `audit.design_zero_assigned`; `config.DERIVED`; `SIZE_ME_OFFSET` and `ff3_monthly` (Task 0)
- Produces:
  - `guard.CONFIRMATORY = ("docs/results/confirmatory_h5.md", "docs/results/confirmatory_h5.attempt")`; `guard.RESULT_HEADING = "# Confirmatory test of H5 and H5b"`; `class guard.ConfirmatoryNotRecorded(RuntimeError)`.
  - `guard.assert_confirmatory_recorded(repo: Path = ROOT) -> None`. It refuses unless both files are tracked at HEAD, unmodified against HEAD, and the `.md`'s first line equals `RESULT_HEADING` exactly.
  - `data.MARKET_END = date(2026, 8, 31)`.
  - `data.daily(weighting: Literal["VW", "EW"] = "VW") -> tuple[pl.DataFrame, pl.DataFrame]` gives industry returns and factors, daily, in percent.
  - `data.monthly(weighting: Literal["VW", "EW"] = "VW") -> tuple[pl.DataFrame, pl.DataFrame]` is the monthly equivalent.
  - `data.ff3_monthly() -> pl.DataFrame`: `date, mkt_rf, smb, hml, rf` in percent, from `read_french_table(_single_file("ff3_monthly"), "")` (its first, monthly table), rows to `MARKET_END`.
  - Every loader calls the guard first.
  - `data.read_french_annual(path: Path, title: str) -> pl.DataFrame` returns `year: Int64` plus one Float64 column per industry. It reads the YYYY-dated table that follows the title line. −99.99 and −999 become null.
  - `data.SIZE_ME_OFFSET: int`, the value verified in Task 0 Step 2.
  - `data.characteristics() -> pl.DataFrame` is long: `date` (month end of the row), `me_date` (the month end of the ME the row holds = `date` shifted back `SIZE_ME_OFFSET` months), `ff49_short`, `n_firms`, `avg_size`, `cap = n_firms * avg_size`. It reads the tables "Number of Firms in Portfolios" and "Average Firm Size" from `ff49_monthly`. Consumers select rows by `me_date`, never by `date`.
  - `data.zero_assigned() -> pl.DataFrame`: `audit.design_zero_assigned(pl.read_parquet(DERIVED / "exposure_occupation.parquet"))` (columns `design, occupations, no_usage, no_usage_emp_pct`; designs B, A_pooled, A_r2). Reads no market data.
  - `data.beme() -> pl.DataFrame` is long: `year`, `ff49_short`, `beme`. It reads "Sum of BE / Sum of ME" and sets values ≤ 0 to null.
  - `data.exposures() -> pl.DataFrame` has columns `design, ff49, ff49_short, z_delegation, z_usage, z_aioe` for `design ∈ {"B", "A_r2", "A_pooled"}`. It raises `ValueError` mentioning `EXPOSURE_SHA256` unless `_vector_hash(power.load_exposure())` equals it.

- [ ] **Step 1: Fixture.** `ind_monthly_small.csv` copies the real `49_Industry_Portfolios.csv` layout for two industries (`Agric`, `Food `, with the trailing space the real header has):
  - the preamble;
  - `  Average Value Weighted Returns -- Monthly` with rows `202312`, `202401`;
  - `  Number of Firms in Portfolios` with rows `202312` (10, 20), `202401` (10, 21);
  - `  Average Firm Size` with rows `202312` (2.5, 4.0), `202401` (2.6, -99.99);
  - `  Sum of BE / Sum of ME` with annual rows `2023` (0.50, 0.40) and `2024` (0.55, -99.99).
- [ ] **Step 2: Write the failing tests.** `test_guard.py` builds a `tmp_path` git repo, as `tests/test_confirm_h5.py` does:
  - `test_guard_refuses_without_record`: a repo with one unrelated commit raises `ConfirmatoryNotRecorded`, match `"not committed"`.
  - `test_guard_refuses_uncommitted_record`: the two files present but untracked raise.
  - `test_guard_refuses_edited_record`: the files committed, then the `.md` edited, raises, match `"modified"`.
  - `test_guard_refuses_attempt_record`: a committed `.md` whose first line is `# Confirmatory test of H5 and H5b: attempt failed` raises, match `"attempt"`.
  - `test_guard_passes_on_committed_result`: first line `RESULT_HEADING` and a committed marker: no raise.

  `test_data.py`:
  - `test_read_french_annual_reads_beme_table`: the columns are `["year", "Agric", "Food"]`, the years are `[2023, 2024]`, and `Food` in 2024 is null.
  - `test_characteristics_cap_is_firms_times_size`: Agric at `date(2024, 1, 31)` has `cap == 26.0`, and Food at `2024-01-31` has a null `cap`.
  - `test_characteristics_me_date_follows_offset`: with `SIZE_ME_OFFSET` monkeypatched to 1, the row dated 2024-01-31 has `me_date == date(2023, 12, 31)`; with 0, `me_date == date(2024, 1, 31)`.
  - `test_post_seal_loaders_call_the_guard_first`: monkeypatch `guard.assert_confirmatory_recorded` to raise, and the French loaders to `pytest.fail`. `data.daily()`, `data.monthly()` and `data.ff3_monthly()` all raise `ConfirmatoryNotRecorded`.
  - `test_exposures_refuse_on_hash_mismatch`: `power.load_exposure` monkeypatched to add 1e-6 to one `z_delegation` raises `ValueError`, match `"EXPOSURE_SHA256"`.
  - `test_exposures_have_three_designs` (`@pytest.mark.data`): 49 rows per design, and A_r2 `z_delegation` equals B's exactly.
- [ ] **Step 3: Run.** `uv run pytest tests/rq3 -v`. Expected: FAIL (module missing).
- [ ] **Step 4: Implement.** The guard uses `git ls-files --error-unmatch`, `git diff --quiet HEAD --` and the file's first line. The characteristics and BE/ME readers live in `rq3/data.py`, not `market/french.py`.
- [ ] **Step 5: Run.** `uv run pytest tests/rq3 -v && uv run ruff check`. Expected: PASS.
- [ ] **Step 6: Commit.** `feat(rq3): guard every market read on the committed confirmatory record; guarded loaders`.

### Task 3: Recomputed confirmatory alphas, the historical-null engine, Softw influence (§3.3 P11)

**Files:**
- Create: `src/aideleg/rq3/inference.py`, `tests/rq3/test_inference.py`
- Output: `docs/results/rq3/influence.md`, `docs/results/rq3/influence.csv`

**Interfaces:**
- Consumes: `data.daily`, `data.exposures`; `power.window_alphas`, `power._alpha_matrix`, `power.historical_windows`, `power._load_returns`, `power.slope_null_distribution`, `power.own_size`, `power.ols_weights`, `power._design`, `power.t_crit`; `confirm_h5.WINDOW`
- Produces:
  - `inference.confirmatory_alphas() -> tuple[np.ndarray, list[str]]`: 49 annualised decimal alphas over `confirm_h5.WINDOW` (NaN where `window_alphas` gives null), in the order of the return columns.
  - `inference.historical_alphas(names: list[str]) -> np.ndarray`: the 378 × len(names) pre-seal alpha matrix, cached at `DERIVED / "rq3/historical_alphas.npz"` with `names` stored; it is recomputed if `names` differ.
  - `inference.vector_test(alphas: np.ndarray, z: np.ndarray, names: list[str], control: np.ndarray | None = None, hist: np.ndarray | None = None) -> dict` returns the keys `b, s, bbar, q_0.975, crit_0.05, T_bbar, p_bbar, T_zero, p_zero, ci_0.05, n, dropped`, all in decimal. It works in four steps:
    1. drop industries with a NaN alpha;
    2. take historical slopes for the vector on the kept columns of `hist` (default `historical_alphas(kept)`) with `slope_null_distribution(..., alphas=hist_kept, control=...)`;
    3. compute `s` = sd (ddof = 1), `bbar` = mean, `q` from `own_size(b_hist, {})["q_0.975"]` and `crit_0.05 = max(t_crit(0.05), q)`;
    4. compute both nulls of D21 with p from t₂₁, and `ci_0.05 = b ± crit_0.05·s`. Nominal and single-test, with no Holm step.
  - `inference.influence(alphas: np.ndarray, z: np.ndarray, c: np.ndarray, names: list[str]) -> pl.DataFrame` has columns `spec ∈ {"H5", "H5b"}, ff49_short, dfbetas_b, cooks_d, leverage`. It uses `OLSInfluence(sm.OLS(a, power._design(z[, c])).fit())`: `dfbetas[:, 1]` and `cooks_distance[0]`.
  - `inference.check_matches_confirmatory(b: dict[str, float], text: str) -> None` parses the table rows `| H5 | <b> |` and `| H5b | <b> |` of the committed `.md`. It raises `ValueError` unless `round(b[v] * 100, 3)` equals the printed value for `h5` and `h5b`.
  - `inference.main_influence(out_dir: Path) -> pl.DataFrame`.

- [ ] **Step 1: Write the failing tests.**
  - `test_vector_test_reproduces_null_scales`: on a synthetic `hist` (30 × 10) and `z`, `c`, `vector_test(a, z, names, hist=hist)` has `s` and `bbar` equal to `power.null_scales(hist, z, c, names)["s_h5"]` and `["bbar_h5"]` to 1e-15, and the same holds for `control=c` against `"s_h5b"` and `"bbar_h5b"`.
  - `test_vector_test_drops_missing_industries`: `alphas[3] = nan` gives `n == 9` and `dropped == [names[3]]`, and the result equals `vector_test` on the inputs with index 3 removed.
  - `test_vector_test_reports_both_nulls`: `T_bbar == (b - bbar) / s`, `T_zero == b / s` and `p_zero == 2 * scipy.stats.t.sf(abs(T_zero), 21)`.
  - `test_influence_flags_planted_outlier`: 49 industries, `Softw` with z = 4.7 and an alpha shifted by +0.3. Softw has the largest `cooks_d` in H5, and `sign(dfbetas_b) == sign(b_all - b_without_softw)`.
  - `test_influence_matches_statsmodels`: the H5b values equal a direct `OLSInfluence` call to 1e-12. This guards the coefficient index.
  - `test_check_matches_confirmatory_raises_on_mismatch`: text with the lines `| H5 | 1.234 | ...` and `| H5b | -0.500 | ...` passes with `{"h5": 0.01234, "h5b": -0.005}` and raises with `h5 = 0.0124`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Then add `main_influence` to `rq3/__main__.py` as the subcommand `influence`.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Real data (after Task 1).**
  - Run `uv run python -m aideleg.rq3 influence`. It recomputes `b` for H5 and H5b on the kept industries and calls `check_matches_confirmatory` on the committed `.md`. A mismatch is a STOP.
  - It writes `influence.csv` (all rows) and `influence.md`. The `.md` holds:
    - the heading `# Influence diagnostics for the confirmatory H5/H5b fits (PAP §3.3, P11) — not part of the decision`;
    - Softw's `dfbetas_b`, `cooks_d` and `leverage` for H5 and H5b;
    - the five largest `cooks_d` per spec;
    - Design B's zero-assigned employment share from `data.zero_assigned()`;
    - `WORDING` as its last line.
- [ ] **Step 6: Commit** the code, tests and both outputs: `feat(rq3): Softw DFBETAS and Cook's D for the confirmatory fits (P11); historical-null vector_test`.

### Task 4: Portfolio statistics library

**Files:**
- Create: `src/aideleg/rq3/stats.py`, `tests/rq3/test_stats.py`

**Interfaces:**
- Produces:
  - `nw_lag(T: int) -> int` = `floor(4 * (T / 100) ** (2 / 9))`.
  - `hac_regression(y: np.ndarray, X: np.ndarray | None, lag: int | None = None) -> dict` returns the keys `coef, se, t, p, lag, T`, one entry per column with the constant first. It calls `sm.OLS(y, add_constant(X)).fit(cov_type="HAC", cov_kwds={"maxlags": L, "kernel": "bartlett", "use_correction": False}, use_t=True)`, with `L = nw_lag(T)` by default. `X=None` gives the mean.
  - `sr(r: np.ndarray) -> float` is the per-period mean/sd (ddof = 1). `sharpe(r, periods: int = 12) -> float` is `sr(r) * sqrt(periods)`.
  - `psr(r: np.ndarray, sr_star: float = 0.0) -> float` is `Φ((ŝ − s*)·√(T−1) / √(1 − γ₃ŝ + (γ₄−1)/4·ŝ²))`, with ŝ = `sr(r)`, γ₃ = `scipy.stats.skew(r)` and γ₄ = `scipy.stats.kurtosis(r, fisher=False)` (both with `bias=True`).
  - `dsr(r: np.ndarray, sr_variants: np.ndarray) -> float` is `psr(r, sr0)` with `sr0 = sqrt(var(sr_variants, ddof=1)) * ((1 − γ)Φ⁻¹(1 − 1/N) + γΦ⁻¹(1 − 1/(N·e)))`, γ = 0.5772156649, N = len ≥ 2.
  - `stationary_indices(n: int, mean_block: float, rng: np.random.Generator) -> np.ndarray` (Politis–Romano: each step a new random start with probability 1/mean_block, otherwise the next index, wrapping).
  - `bootstrap(r: np.ndarray, stats: dict[str, Callable], n_draws: int, mean_block: float, rng) -> dict[str, np.ndarray]` takes one index draw per replicate and applies every statistic to it.
  - `percentile_ci(draws: np.ndarray, level: float = 0.95) -> tuple[float, float]`.

- [ ] **Step 1: Write the failing tests.**
  - `test_nw_lag_rule`: `[nw_lag(t) for t in (17, 45, 100, 250)] == [2, 3, 4, 4]`.
  - `test_hac_lag0_equals_hc0`: on random `y` and `X`, `hac_regression(y, X, lag=0)["se"]` equals the `fit(cov_type="HC0")` bse to 1e-10, and `coef` equals the OLS coefficients.
  - `test_psr_is_half_at_its_own_sr`: `psr(r, sr(r)) == 0.5`.
  - `test_psr_matches_formula`: a hand computation on a fixed 24-value series equals `psr` to 1e-12.
  - `test_dsr_below_psr_zero`: with `sr_variants = [0.1, 0.2, 0.3]`, `dsr(r, ...) < psr(r, 0.0)`, and `dsr` raises `ValueError` for N = 1.
  - `test_stationary_bootstrap_mean_block_length`: over 200 draws with n = 1000 and mean_block = 3, the mean run length of consecutive indices is within 3 ± 0.15.
  - `test_bootstrap_reproducible`: two runs with `default_rng(SEED)` are identical.
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit.** `feat(rq3): Newey-West, PSR/DSR and stationary bootstrap helpers`.

### Task 5: Event studies under D19, and the Eisfeldt, Schubert & Zhang replication

**Files:**
- Create: `src/aideleg/rq3/events.py`, `tests/rq3/test_events.py`
- Output: `docs/results/rq3/event_study.md`, `event_study.csv`, `event_days.csv`, `eisfeldt_replication.md`; figure `fig_rq3_event_slopes`

**Interfaces:**
- Consumes: `data.daily`, `data.exposures`; `aideleg.figures.save_figure(fig, name)` (Plan 2)
- Produces:
  - `@dataclass(frozen=True) class Event: name: str; announced: date`.
  - `EVENTS: tuple[Event, ...]` holds exactly these 14, in this order:

    | name | announced |
    |---|---|
    | `ChatGPT` | 2022-11-30 |
    | `GPT-4` | 2023-03-14 |
    | `PaLM 2` | 2023-05-10 |
    | `Claude 2` | 2023-07-11 |
    | `Claude 2.1` | 2023-11-21 |
    | `Gemini 1.0` | 2023-12-06 |
    | `Gemini 1.5` | 2024-02-15 |
    | `Claude 3` | 2024-03-04 |
    | `Claude 3.5` | 2024-06-20 |
    | `OpenAI o1` | 2024-09-12 |
    | `Gemini 2.0` | 2025-02-05 |
    | `Claude 3.7` | 2025-02-24 |
    | `GPT-4.5` | 2025-02-27 |
    | `Gemini 2.5` | 2025-03-25 |

  - `EXCLUDED: dict[str, str]` lists GPT-4o, o3-mini, DeepSeek-R1, Gemma and Gemini Ultra with the PAP's reason. It is printed in the doc together with D19's "chosen with the list in view" disclosure.
  - `ESTIMATION = (-250, -21)`; `HORIZONS = (5, 20)`; `ESZ_HORIZON = 9`.
  - `day_zero(announced: date, trading_days: Sequence[date]) -> date` is the first date ≥ `announced` present in both the industry and the factor files.
  - `event_cars(returns, factors, event: Event, horizons: Sequence[int]) -> pl.DataFrame`. Columns: `ff49_short`, `car_<k>` (decimal), `dropped` (reason or null).
    - The estimation is the daily OLS of decimal excess return on `[1, mkt_rf, smb, hml, rmw, cma, umd]` over trading-day positions [−250, −21] relative to day 0.
    - AR = excess − fitted (the intercept included), and CAR_k = the sum of AR over days 0..k.
  - `car_regression(car: np.ndarray, regressors: dict[str, np.ndarray]) -> dict` is OLS with an intercept and HC3. Per regressor it returns `b`, `se`, `ci95`, `p`, plus `n`. It drops rows with a NaN.
  - `event_days(events, trading_days) -> pl.DataFrame` has columns `event, announced, day0, moved, overlaps`. `overlaps` lists the other events whose day 0 lies in this event's [0, +20].
  - `run_events(out_dir: Path, events: Sequence[Event] = EVENTS, expo: pl.DataFrame | None = None) -> pl.DataFrame`. It returns one row per regression with columns `event, day0, horizon, design, regressors, regressor, b, se, ci_lo, ci_hi, p, n` (`b`, `se` and the CI in pp per 1 SD).
    - `expo=None` uses `data.exposures()`. A given `expo` has the same columns (`design, ff49, ff49_short, z_delegation, z_usage, z_aioe`) and replaces it; the regressions run for the Design A labels it holds (`A_r2`, `A_pooled`), in that order.
    - Plan 4 passes placebo `events` (R9) and variant exposures (R4, R16), with an `out_dir` under `data/derived/robustness/`.
    - The Eisfeldt et al. replication runs only when an event named `ChatGPT` is in `events`.
    - `event_study.csv` is the returned frame, written with `write_csv` (Plan 4's parity test compares the two).
- **Regressions.** Each event × horizon ∈ {5, 20}: CAR on A_r2 `z_delegation`, then CAR on A_pooled `z_delegation`, each alone. A_pooled is labelled look-ahead.
- **Exposure share.** `event_study.md` and `eisfeldt_replication.md` state the zero-assigned employment share of each design used (`data.zero_assigned()`; for a passed `expo`, the caller supplies it in the row's own notes).
- **Eisfeldt et al. replication** (`ChatGPT`, horizon 9):
  1. CAR on `z_aioe` alone. Report the slope's sign, its CI and p.
  2. Then the horse race `[z_aioe, z_delegation]`, with A_r2 and then A_pooled.
- **Inference.** HC3, nominal, every regression reported. PAP §3.2 documents that RI is oversized, so it is not used here.

- [ ] **Step 1: Write the failing tests.** Synthetic data: 400 weekday dates, factors N(0, 1), industries = β·f + small noise.
  - `test_fourteen_events_exact`: `[(e.name, e.announced) for e in EVENTS]` equals the list above.
  - `test_day_zero_moves_to_next_trading_day`: with 2024-06-20 absent from the dates, `day_zero(date(2024, 6, 20), days) == date(2024, 6, 21)`, and `event_days` has `moved == True`.
  - `test_estimation_window_is_250_to_21`: a +5% shock planted at position −20 (outside estimation) and at −251 leaves the fitted betas unchanged. The estimation uses exactly 230 rows.
  - `test_car_recovers_planted_jump`: +1% added on day 0 for one industry gives `car_5` = 0.01 ± 1e-3, and the others are ≈ 0 ± 1e-3.
  - `test_industry_missing_estimation_return_is_dropped`: a null at position −100 gives `car_5` null and `dropped == "estimation"`, and the industry is excluded from `car_regression`'s `n`.
  - `test_overlap_flag`: on a 2025 weekday calendar, `"GPT-4.5"` is in Claude 3.7's `overlaps`.
  - `test_esz_runs_aioe_alone_then_with_delegation`: `run_events` on synthetic inputs writes the replication rows in this order: `[z_aioe]`, `[z_aioe, z_delegation A_r2]`, `[z_aioe, z_delegation A_pooled]`.
  - `test_run_events_takes_expo_and_placebos`: with `data.exposures` monkeypatched to `pytest.fail`, `run_events(tmp, events=(Event("P", date(2019, 3, 14)),), expo=<synthetic A_r2-only frame>)` returns rows with `design == "A_r2"` only, `event == "P"`, horizons {5, 20}, and writes no `eisfeldt_replication.md`.
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement**, with the subcommand `events`. **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Real data.** `uv run python -m aideleg.rq3 events`.
  - `event_study.md` starts `# Event studies (exploratory, PAP §8.3 D19)`. It contains the rule, the 14 dates, the exclusions, the disclosure, `event_days`, the zero-assigned shares and every regression in pp per 1 SD, with the dropped industries listed.
  - `eisfeldt_replication.md` starts `# Eisfeldt, Schubert & Zhang (2023) replication (exploratory)`. It states the sign of the `z_aioe` slope, then the horse race.
  - The figure shows the A_r2 slopes per event with 95% CIs, both horizons, titled with "exploratory".
- [ ] **Step 6: Commit** the code, tests, outputs and figure: `feat(rq3): D19 event studies and the Eisfeldt et al. replication (exploratory)`.

### Task 6: Tercile portfolios (Design B secondary; Design A exploratory)

**Files:**
- Create: `src/aideleg/rq3/terciles.py`, `tests/rq3/test_terciles.py`
- Output: `docs/results/rq3/terciles.md`, `terciles.csv`; figure `fig_rq3_tercile_cumulative`

**Interfaces:**
- Consumes: `data.monthly`, `data.ff3_monthly`, `data.characteristics`, `data.exposures`, `data.zero_assigned`; the `stats.*` helpers (Task 4); `save_figure`
- Produces:
  - `members(expo: pl.DataFrame, col: str = "z_delegation") -> dict[str, list[str]]`. It drops null exposure and sets k = n // 3. `high` is the top k and `low` the bottom k, by `col` descending with ties broken by ascending `ff49`; `mid` is the rest.
  - `leg_returns(monthly_ret: pl.DataFrame, chars: pl.DataFrame, legs: dict, months: Sequence[date], weighting: Literal["cap", "ew"]) -> pl.DataFrame` has columns `date, high, low, hml`, in percent.
    - Under `"cap"`, the weights in month t ∝ `cap` at the `chars` row whose `me_date` is the month end before t (the PAP's "prior month-end" ME; Task 0's verified `SIZE_ME_OFFSET` fixes which row that is), so no look-ahead is possible.
    - Under `"ew"`, the weights are equal.
    - An industry with a missing return or cap in month t leaves that month's leg, and the weights renormalise over the rest.
  - `WINDOWS = {"B": (date(2025, 4, 30), date(2026, 8, 31)), "A": (date(2022, 12, 31), date(2026, 8, 31))}`; month ends inclusive, T = 17 and 45.
  - `VARIANTS = (("B", "cap"), ("B", "ew"), ("A_r2", "cap"), ("A_r2", "ew"), ("A_pooled", "cap"), ("A_pooled", "ew"))`, which is also the DSR set (N = 6) and the RNG order.
  - `MODELS = {"CAPM": ("ff5", ["mkt_rf"]), "FF3": ("ff3", ["mkt_rf", "smb", "hml"]), "FF5+UMD": ("ff5", ["mkt_rf", "smb", "hml", "rmw", "cma", "umd"])}`: (factor file, columns). `"ff5"` is `data.monthly()`'s factor frame; `"ff3"` is `data.ff3_monthly()`, the canonical FF3 file acquired in Task 0. FF3 is never built from FF5 columns. Excess returns use each file's own `rf`.
  - `COSTS_BPS = (0, 5, 15, 30)`; `FORMATION_TURNOVER = 2.0` (100% long plus 100% short, one way).
  - `costed(hml: np.ndarray, bps: int) -> np.ndarray` deducts `FORMATION_TURNOVER * bps / 100` percent from the first month only.
  - `tercile_stats(hml: np.ndarray, factors: dict[str, pl.DataFrame], rng) -> dict` (`factors` keyed `"ff5"`, `"ff3"`, rows aligned to the `hml` months) covers:
    - per model, the alpha ×12 in pp, with NW SE, CI and p;
    - the annualised Sharpe, PSR(0), and stationary-bootstrap 95% CIs of the Sharpe and of the mean (10,000 draws, mean block 3 months, one draw set per variant);
    - the costed mean and Sharpe at each `COSTS_BPS`.
  - `run_terciles(out_dir: Path, months: dict[str, Sequence[date]] | None = None, expo: pl.DataFrame | None = None) -> pl.DataFrame`.
    - `months` maps a `WINDOWS` key (`"B"`, `"A"`) to the month ends used; `None` means every month end of each window. Plan 4's R8 passes `{"A": <the A month ends outside calendar 2023>}`.
    - `expo=None` uses `data.exposures()`; a given `expo` (same columns) replaces it, and only the `VARIANTS` whose design it holds are run, in `VARIANTS` order (Plan 4's R4, R8, R16).
    - It uses one `default_rng(SEED)` consumed in the order of the variants run, then computes the DSR for each variant from the gross monthly SRs of the variants run (null when fewer than two).
    - It returns one row per (design, weighting, statistic) with columns `design, weighting, statistic, estimate, se, ci_lo, ci_hi, p, T`; `statistic` ∈ {`alpha_CAPM`, `alpha_FF3`, `alpha_FF5+UMD`, `sharpe`, `psr`, `dsr`, `mean`} (alphas in annualised pp).
    - `terciles.md` states the zero-assigned share of each design (`data.zero_assigned()`); `terciles.csv` is the returned frame.

- [ ] **Step 1: Write the failing tests.**
  - `test_members_sizes_16_17_16`: 49 distinct z give lengths 16/17/16.
  - `test_ties_broken_by_ff49`: two equal z at the cut leave the lower `ff49` in `high`.
  - `test_null_exposure_excluded`: 48 non-null of 49 give k = 16 with `mid` = 16.
  - `test_cap_weights_use_prior_month_end_me`: caps differ at rows dated `2024-01-31` and `2024-02-29`. With `SIZE_ME_OFFSET = 1` the February 2024 leg uses the caps of the row dated 2024-02-29 (its ME is at 2024-01-31); with `SIZE_ME_OFFSET = 0` it uses the row dated 2024-01-31.
  - `test_missing_return_reweights_within_leg`: one member null in a month gives the leg as the cap-weighted mean of the other two.
  - `test_cost_deducted_once_from_first_month`: `costed(h, 30)` equals `h - [0.6, 0, 0, ...]`.
  - `test_ff3_alpha_uses_ff3_file`: `MODELS["FF3"] == ("ff3", ["mkt_rf", "smb", "hml"])`, and on synthetic factor frames whose FF3 `smb` differs from FF5 `smb`, the FF3 alpha equals an OLS on the FF3 frame's columns (and not on FF5's).
  - `test_rng_order_is_variants_order`: on synthetic inputs, the CIs from `run_terciles` equal those from calling `tercile_stats` per variant in `VARIANTS` order with one shared `default_rng(SEED)`.
  - `test_run_terciles_months_and_expo`: with `months={"A": <synthetic A month ends without 2023>}` and an `expo` holding only `A_r2` and `A_pooled`, the returned `design` set is {A_r2, A_pooled}, no 2023 month enters any leg (spy on `leg_returns`' `months`), and `data.exposures` is not called.
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement**, with the subcommand `terciles`. **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Real data.** `uv run python -m aideleg.rq3 terciles`. `terciles.md` holds:
  - the heading `# Tercile portfolios (exploratory, PAP §8.3 D19; Design B rows are secondary)`;
  - the members per design, and one table per variant;
  - the DSR;
  - the note that these are measurement devices, not strategies (spec §5.4).

  The figure shows the cumulative H−L for the six variants and is titled "exploratory".
- [ ] **Step 6: Commit.** `feat(rq3): fixed-membership tercile portfolios, cap and EW legs (exploratory)`.

### Task 7: Fama–MacBeth

**Files:**
- Create: `src/aideleg/rq3/fama_macbeth.py`, `tests/rq3/test_fama_macbeth.py`
- Output: `docs/results/rq3/fama_macbeth.md`, `fama_macbeth.csv`

**Interfaces:**
- Consumes: `data.monthly`, `data.characteristics`, `data.beme`, `data.exposures`; `stats.hac_regression`, `stats.nw_lag`; `terciles.WINDOWS`
- Produces:
  - `momentum_12_2(monthly_ret: pl.DataFrame) -> pl.DataFrame` has columns `date, ff49_short, mom`, where mom_t = Π_{s=t−12}^{t−2}(1 + r_s/100) − 1. It is null unless all 11 returns are present.
  - `beme_year(d: date) -> int` = `d.year` if `d.month >= 7` else `d.year - 1`. The French row for year y is BE for fiscal y−1 over ME at December y−1, used from July y to June y+1.
  - `fm_panel(expo: pl.DataFrame, months: Sequence[date]) -> pl.DataFrame` has columns `date, ff49_short, ret_x, z, log_size, log_beme, mom`.
    - `ret_x` = VW return − rf, in percent.
    - `log_size` = ln(`avg_size` at the row whose `me_date` is the prior month end).
    - `log_beme` = ln(`beme` for `beme_year(date)`).
  - `fama_macbeth(panel: pl.DataFrame, regressors: Sequence[str] = ("z", "log_size", "log_beme", "mom")) -> dict[str, dict]`.
    - Each month: OLS of `ret_x` on [1, regressors] over the industries with every value. A month with n ≤ len(regressors) + 1 is skipped and counted.
    - Per regressor, it reports the time-series mean of the coefficients with `hac_regression(coefs, None)`: `mean, se, ci95, p, T, n_mean, skipped`.
  - `run_fm(out_dir: Path, months: dict[str, Sequence[date]] | None = None, expo: pl.DataFrame | None = None) -> pl.DataFrame` covers (design, window) ∈ {(B, B), (A_r2, A), (A_pooled, A)}, building each panel with `fm_panel(expo_design, months[window])`.
    - `months` and `expo` behave as in `run_terciles`: `None` means every month end of the window and `data.exposures()`; a given `expo` restricts the runs to the designs it holds.
    - It returns columns `design, window, regressor, mean, se, ci_lo, ci_hi, p, T, n_mean, skipped`. The coefficient on z is shown in pp per month and ×12 in the doc.
    - `fama_macbeth.md` states the zero-assigned share of each design; `fama_macbeth.csv` is the returned frame.

- [ ] **Step 1: Write the failing tests.**
  - `test_momentum_skips_most_recent_month`: a +50% return planted at t−1 leaves `mom_t` unchanged, while one at t−2 changes it.
  - `test_beme_year_assignment`: `beme_year(date(2023, 6, 30)) == 2022` and `beme_year(date(2023, 7, 31)) == 2023`.
  - `test_size_uses_prior_month_end_me`: with `SIZE_ME_OFFSET = 1`, `log_size` for 2024-02-29 equals ln of the `avg_size` in the row dated 2024-02-29 (ME at 2024-01-31); with `SIZE_ME_OFFSET = 0`, ln of the row dated 2024-01-31.
  - `test_run_fm_months_and_expo`: `run_fm(tmp, months={"A": ms}, expo=<A_r2-only frame>)` returns `design == "A_r2"` rows only, with `T == len(ms)` minus skipped months.
  - `test_fm_recovers_planted_slope`: on a synthetic panel with return = 0.5·z + noise, the mean coefficient on `z` is within 0.05 of 0.5.
  - `test_fm_se_is_nw_of_monthly_coefficients`: `se` equals `hac_regression(coef_series, None)["se"][0]`.
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement**, with the subcommand `fm`. **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Real data.** `uv run python -m aideleg.rq3 fm`. The doc starts `# Fama–MacBeth (exploratory, PAP §8.3)`, followed by one table per design.
- [ ] **Step 6: Commit.** `feat(rq3): Fama-MacBeth with size, BE/ME and 12-2 momentum (exploratory)`.

### Task 8: RQ3 summary, CLI and Make target

**Files:**
- Create: `src/aideleg/rq3/report.py`, `src/aideleg/rq3/__main__.py` (subcommands `influence, events, terciles, fm, summary, all`), `tests/rq3/test_report.py`
- Modify: `Makefile`, adding `rq3: data/derived/exposure_ff49.parquet` → `uv run python -m aideleg.rq3 all`
- Output: `docs/results/rq3/summary.md`

**Interfaces:**
- Produces:
  - `report` imports `WORDING` and `FORBIDDEN_PHRASES` from `aideleg.results.common` (Plan 2) and defines no disclaimer of its own. Every rq3 and h6 doc ends with `WORDING`.
  - `report.zero_assigned_lines(designs: Sequence[str]) -> list[str]`: one line per design, `"Zero-assigned employment share, Design <d>: <no_usage_emp_pct:.2f>% (D3)"`, from `data.zero_assigned()`.
  - `report.md_table(df: pl.DataFrame, floats: int = 3) -> str`.
  - `report.fixed_wording(text: str) -> list[str]` returns the `  - Fixed wording:` lines of the confirmatory `.md`, verbatim and in order.
  - `report.write_summary(out_dir: Path) -> Path`. It writes:
    - the heading `# RQ3: what the market evidence can and cannot yet say` (D11 fires: primary MDE 7.43 pp > 5 pp, so the paper is led by RQ1–RQ2);
    - the confirmatory section, which quotes `fixed_wording` verbatim and names the record's commit (`git log -n1 --format=%H -- docs/results/confirmatory_h5.md`) and file path;
    - a pointer to `influence.md`;
    - an exploratory index with one line per doc: the file link and its label, and no estimates.

- [ ] **Step 1: Write the failing tests.**
  - `test_fixed_wording_verbatim`: a synthetic `.md` with two wording lines returns them unchanged.
  - `test_summary_reports_no_exploratory_estimates`: on synthetic docs, `summary.md` has no markdown table rows (no line starts with `|`), and every `- Fixed wording:` line of the record appears in it verbatim.
  - `test_every_exploratory_doc_is_labelled` (`@pytest.mark.data`): the first line of each of `event_study.md`, `eisfeldt_replication.md`, `terciles.md`, `fama_macbeth.md` and every `docs/results/h6/*.md` contains `exploratory`, and each ends with `WORDING`.
  - `test_rq3_h6_docs_wording` (`@pytest.mark.data`): every `docs/results/rq3/*.md` and `docs/results/h6/*.md` contains `WORDING` exactly once and, with it removed, contains no `FORBIDDEN_PHRASES` (case-insensitive). It scans only these two directories.
  - `test_rq3_docs_state_zero_assigned_share` (`@pytest.mark.data`): `influence.md`, `event_study.md`, `eisfeldt_replication.md`, `terciles.md`, `fama_macbeth.md` and `h6/gap.md` each contain the `zero_assigned_lines` line of every design they report.
  - `test_figure_names_prefixed`: every figure name passed to `save_figure` in `rq3/` and `h6/` (AST scan of string literals) starts with `fig_rq3_` or `fig_h6_`.
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: PASS.
- [ ] **Step 5:** `make rq3`. Expected: it regenerates every rq3 doc; `git diff --stat docs/results/rq3` shows only `summary.md` as new.
- [ ] **Step 6: Commit.** `feat(rq3): summary under the D11 framing; make rq3`.

### Task 9: The D12 dictionary and text matching

**Files:**
- Create: `src/aideleg/h6/__init__.py`, `src/aideleg/h6/dictionary.py`, `tests/h6/__init__.py`, `tests/h6/test_dictionary.py`

**Interfaces:**
- Produces:
  - `PRIMARY_TERMS: tuple[str, ...]` holds the 12 terms in PAP order: `"artificial intelligence", "machine learning", "deep learning", "neural network", "generative AI", "generative artificial intelligence", "large language model", "natural language processing", "computer vision", "reinforcement learning", "foundation model", "ChatGPT"`.
  - `PLURAL = frozenset({"neural network", "large language model", "foundation model"})`.
  - `ACRONYMS = ("AI", "A.I.", "GenAI", "LLM", "LLMs")`; `GATE = ("artificial intelligence", "generative AI")`.
  - `fts_phrases(terms: Sequence[str] = PRIMARY_TERMS) -> list[str]` returns the 12 terms plus the 3 plurals: 15 phrases.
  - `clean_text(raw: str, html: bool = True) -> str`, in four steps:
    1. drop `<ix:header>…</ix:header>`, `<script>…</script>` and `<style>…</style>`;
    2. replace every remaining tag with a space;
    3. `html.unescape`;
    4. `unicodedata.normalize("NFKC", ·)`.
  - `count_terms(text: str, terms: Sequence[str] = PRIMARY_TERMS) -> dict` returns `{"primary": {term: n}, "acronym": {acr: n}, "gated": bool, "n_words": int}`. The rules:
    - Primary terms are case-insensitive whole words (`(?<!\w)` … `(?!\w)`). A space in a term matches `[\s-]+`, and a `PLURAL` term also matches with a final `s`.
    - Acronyms are case-sensitive and bounded by `(?<![A-Za-z0-9])` … `(?![A-Za-z0-9])`.
    - All spans are resolved by keeping the longest, then leftmost, non-overlapping span. Acronym counts are zeroed unless `gated`, meaning a GATE term occurs at least once.
    - `n_words` = `len(re.findall(r"\S+", text))`.
    - Plan 4's R30 passes `terms`.

- [ ] **Step 1: Write the failing tests.**
  - `test_twelve_terms_fifteen_phrases`: the list equality above, and `len(fts_phrases()) == 15` including `"neural networks"`.
  - `test_whitespace_and_hyphen_match`: `"Machine-learning"` and `"neural \n networks"` count 1 each.
  - `test_longest_match_counts_once`: `"generative artificial intelligence"` counts once in total, with `"artificial intelligence"` at 0.
  - `test_acronyms_need_the_gate_and_longest_match_wins`:
    - `"AI-driven tools in MAINE"` alone gives `acronym["AI"] == 0` (not gated).
    - With `" artificial intelligence"` appended, it gives `AI == 1` and `MAINE` no match.
    - `"Generative AI and AI"` gives `primary["generative AI"] == 1` and `acronym["AI"] == 1`.
    - `"LLMs"` counts under `LLMs`, not `LLM`.
  - `test_clean_text_strips_ix_header_and_entities`: `"<ix:header>secret</ix:header><p>A&amp;I</p>"` gives `"A&I"` once whitespace is stripped.
  - `test_word_count`: `"a  b\nc"` gives 3.
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit.** `feat(h6): D12 dictionary and matching rules`.

### Task 10: EDGAR denominator — full index, SIC from the bulk submissions, FF49

**Files:**
- Create: `src/aideleg/h6/edgar.py` (denominator part), `tests/h6/test_edgar_index.py`, `tests/fixtures/sec/form_small.idx`, `tests/fixtures/sec/submissions_small.zip` (built in the test from JSON literals)
- Modify: `src/aideleg/acquire/sources.py`, `src/aideleg/acquire/fetch.py`, `tests/acquire/test_sources.py`, `docs/pap/pre-analysis-plan.md` (§11 only)
- Output: `data/derived/h6/filers.parquet`

**Interfaces:**
- Consumes: `fetch.Source`, `fetch.fetch`, `crosswalk.naics_ff49.sic_to_ff49`, `crosswalk.naics_ff49._siccodes`
- Produces:
  - In `sources.SOURCES`:
    - the keys `sec_formidx_{y}q{q}` for y ∈ 2019..2025 and q ∈ 1..4, with URL `https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/form.idx` and dest `sec/full-index/{y}/QTR{q}/form.idx`;
    - `sec_submissions_bulk` (`https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip`, dest `sec/submissions.zip`, `unzip=False`; members are read in place). This is the bulk form of the submissions API.
  - `fetch.download(src: Source, path: Path) -> None` is a public alias of `_download`.
  - `FORMS = ("10-K", "10-K405", "10-KT")`; `YEARS = tuple(range(2019, 2026))`.
  - `parse_form_idx(path: Path) -> pl.DataFrame` has columns `form, company, cik: Int64, date_filed: Date, file_name, adsh`.
    - The fixed-width columns start at the header offsets of `Form Type`, `Company Name`, `CIK`, `Date Filed` and `File Name`.
    - Rows begin after the dashed line.
    - `adsh` = the basename of `file_name` without `.txt`.
  - `ten_k_filers(year: int) -> pl.DataFrame` is the rows with `form ∈ FORMS` from that year's four files.
  - `submissions_json(cik: int, zf: zipfile.ZipFile) -> dict | None` reads the member `CIK{cik:010d}.json`.
  - `sic_of(js: dict | None) -> int | None` gives `int(js["sic"])`, or None if absent or empty.
  - `ff49_of(sic: int | None) -> int | None`.
  - `build_filers(years: Sequence[int] = YEARS) -> pl.DataFrame` has columns `year, cik, adsh, form, date_filed, sic, ff49` and writes `filers.parquet`.
  - `denominator(filers: pl.DataFrame) -> pl.DataFrame` has columns `year, ff49, n_filers`, counting distinct CIKs. The unmapped CIKs are counted under `ff49 = null` and reported.
  - The §11 log uses Plan 2's `paplog` (one `A-` entry per key; `paplog.set_digest` for the bulk sets of Tasks 11 and 13). `edgar` defines no digest of its own.

- [ ] **Step 1: Fixture.** `form_small.idx` copies the real layout. Check it against the first 15 lines of one fetched file; if the real header offsets differ, use the real ones, keep the test's meaning and note it in the commit. It holds the 4-line preamble, the header line, the dashed line, and rows for `10-K`, `10-K/A`, `10-KT`, `8-K`, plus a company name containing double spaces.
- [ ] **Step 2: Write the failing tests.**
  - `test_parse_form_idx_fixed_width`: the double-spaced company name is kept whole, `cik` is int, and `adsh == "0001234567-24-000001"`.
  - `test_ten_k_filers_excludes_amendments`: the forms come out as `{"10-K", "10-KT"}`.
  - `test_sic_from_bulk_zip`: `sic_of` gives 7372, and `""` or a missing member gives None.
  - `test_unmapped_sic_reported`: a SIC outside every Siccodes49 range gets `ff49` null and is counted in the unmapped row.
  - `test_denominator_counts_distinct_ciks`: two filings by one CIK in a year count 1.
  - `test_sources_include_full_index_and_bulk`: update `REQUIRED` in `tests/acquire/test_sources.py` with the 29 new keys, keeping any keys Plan 2 added.
- [ ] **Step 3: Run.** Expected: FAIL. **Step 4: Implement.** **Step 5: Run.** Expected: PASS.
- [ ] **Step 6: Acquire.**
  - `uv run python -m aideleg.acquire --only $(python -c "print(' '.join([f'sec_formidx_{y}q{q}' for y in range(2019,2026) for q in range(1,5)]+['sec_submissions_bulk']))")`.
  - Then `uv run python -m aideleg.h6 build --filers`, which runs `build_filers` on the saved files (no network).
  - Expected: 29 MANIFEST records, and a printed count of filers and unmapped CIKs per year.
- [ ] **Step 7: Log the additions.** `uv run python -m aideleg.paplog addition --keys <the 28 sec_formidx keys> sec_submissions_bulk --scope "pre-specified in §9.4" --used-by "H6 denominator and SIC (D18), Plan 3 Task 10"`. Expected: 29 new `A-` entries under "Additions (D20)" and `test_every_addition_logged` passes. Nothing else in the PAP changes.
- [ ] **Step 8: Commit.** Code, tests, `MANIFEST.json` and §11: `feat(h6): EDGAR full-index denominator and SIC to FF49 (D18); §11 addition`.

### Task 11: EDGAR full-text-search numerator

**Files:**
- Modify: `src/aideleg/h6/edgar.py` (FTS part), `docs/pap/pre-analysis-plan.md` (§11 only, through `paplog`)
- Create: `tests/h6/test_edgar_fts.py`, `tests/fixtures/sec/fts_sample.json`
- Output: `data/derived/h6/fts_hits.parquet`

**Interfaces:**
- Consumes: `fetch.fetch`, `dictionary.fts_phrases`, `build_filers` (Task 10)
- Produces:
  - `FTS_URL = "https://efts.sec.gov/LATEST/search-index"`; `FTS_PAGE = 100`; `FTS_CAP = 10_000`.
  - `fts_url(phrase: str, start: date, end: date, offset: int) -> str`. Its parameters are `q` = the phrase in double quotes, `dateRange=custom`, `startdt`, `enddt`, `forms=10-K,10-K405,10-KT` and `from`, built with `urlencode(..., quote_via=quote)`.
  - `fts_source(phrase, start, end, offset) -> fetch.Source` has key `sec_fts/{start}_{end}/{slug}/{offset:05d}` and dest `sec/fts/{start.year}/{slug}/{start}_{end}_{offset:05d}.json`, with slug = the phrase lower-cased and spaces turned into `_`. Each response is one MANIFEST record, as D18 requires.
  - `class FtsCapError(RuntimeError)`.
  - `fts_hits(phrase: str, start: date, end: date) -> pl.DataFrame` has columns `phrase, cik: Int64, adsh, form, file_date, file_type`, one row per (hit, CIK in `_source.ciks`). The search proceeds in four steps:
    1. Fetch page 0. If `total.relation != "eq"` or `total.value >= FTS_CAP`, split at `mid = start + (end − start) // 2` into [start, mid] and [mid + 1, end], then recurse.
    2. If `start == end` and the range is still capped, raise `FtsCapError`.
    3. Otherwise fetch offsets 0, 100, … below `total.value`.
    4. Keep the hits with `form ∈ FORMS`. The other forms are counted and printed.
  - `numerator(hits: pl.DataFrame, filers: pl.DataFrame) -> pl.DataFrame` has columns `year, ff49, n_talk, n_exhibit_only`: `n_talk` = distinct CIKs per year with at least one hit, restricted to that year's filers. A CIK whose only hits are in an exhibit of the 10-K (`file_type` not in `FORMS`) **counts in `n_talk`** and is also counted in `n_exhibit_only` (the C- rule of Task 0).
  - `out_of_denominator(hits: pl.DataFrame, filers: pl.DataFrame) -> pl.DataFrame`: `year, cik` of hit CIKs that are not that year's filers; reported, never counted.
  - `acquire_fts(years: Sequence[int] = YEARS, phrases: Sequence[str] | None = None) -> pl.DataFrame` fetches (network) and writes `fts_hits.parquet`. Plan 4's R29 and R30 pass other ranges and phrases through `fts_hits`.
  - `hits_from_saved(phrases: Sequence[str] | None = None, start: date | None = None, end: date | None = None) -> pl.DataFrame` rebuilds the same frame offline from every saved `sec_fts/` response in the MANIFEST, optionally restricted to `phrases` and to hits whose `file_date` lies in [`start`, `end`] (FTS date ranges filter on the file date, so a sub-range of saved ranges needs no new query). It uses only leaf ranges: a range whose page 0 has `relation == "eq"` and `value < FTS_CAP`, with all its pages; a capped page-0 response that was split is skipped. It raises `FileNotFoundError` naming the first missing page.

- [ ] **Step 1: Fixture.**
  - Save one live response as `fts_sample.json`: `"computer vision"`, 2024-01-01 → 2024-01-31, offset 0, trimmed to 3 hits.
  - The parser reads `hits.total.value`, `hits.total.relation`, and `hits.hits[]._source.{ciks, adsh, form, file_date, file_type}`. If the live names differ, use the live names and keep the tests' meaning.
- [ ] **Step 2: Write the failing tests.** They monkeypatch `edgar._get_json(src) -> dict`, a fake that keys responses by `(startdt, enddt, from)`.
  - `test_fts_url_quotes_phrase_and_forms`: the URL contains `q=%22neural%20networks%22`, `forms=10-K%2C10-K405%2C10-KT`, `startdt=2024-01-01`, `enddt=2024-12-31` and `from=200`.
  - `test_fts_paginates_until_total`: total 250 gives offsets `[0, 100, 200]`.
  - `test_fts_splits_range_when_total_hits_cap`: the full year returns `{"value": 10000, "relation": "gte"}`, and the halves return exact totals of 6000 and 3000.
    - The requested ranges include (2024-01-01, 2024-07-01) and (2024-07-02, 2024-12-31).
    - No offset ≥ 10,000 is requested, and the hits come out as the union.
  - `test_fts_single_day_over_cap_raises`: raises `FtsCapError`.
  - `test_numerator_counts_distinct_ciks_excluding_amendments`:
    - the input hits are: CIK 1 found by two phrases; CIK 2 only on a `10-K/A`; a co-registrant hit with `ciks = [3, 4]`; CIK 5 found only in a document with `file_type == "EX-99.1"` of a `10-K`; and CIK 9, which is not a filer;
    - `n_talk` counts {1, 3, 4, 5} (4), `n_exhibit_only == 1` (CIK 5), and `out_of_denominator` lists CIK 9 only.
  - `test_raw_response_recorded`: each fetched page leaves a MANIFEST record whose key starts `sec_fts/`.
  - `test_hits_from_saved_equals_acquired`: after the split scenario of `test_fts_splits_range_when_total_hits_cap` (fake responses saved through the fake fetch), `hits_from_saved()` with network calls monkeypatched to `pytest.fail` equals `fts_hits`'s frame (sorted), and the capped full-year page 0 contributes no row.
- [ ] **Step 3: Run.** Expected: FAIL. **Step 4: Implement**, with `_get_json` = `fetch.fetch(src)`, then `json.loads` of the saved file. **Step 5: Run.** Expected: PASS.
- [ ] **Step 6: Acquire.**
  - `uv run python -m aideleg.h6 acquire --fts` covers 15 phrases × 2019–2025.
  - Expected: no `FtsCapError`. A `FtsCapError` is a STOP: report the phrase and the day, since the D18 measure would not be computable as written.
- [ ] **Step 7: Log the addition** in the set-digest form: `uv run python -m aideleg.paplog set-addition --source sec_fts/ --scope "pre-specified in §9.4" --used-by "H6 numerator (D18), Plan 3 Task 11"`. The entry carries the `sec_fts/` record count, the set digest and the first and last retrieval times; this is the retrieval date that D18's "FTS phrase semantics … on the retrieval date" refers to.
- [ ] **Step 8: Commit.** `feat(h6): EDGAR full-text-search numerator with exact-total bisection; §11 addition`.

### Task 12: Talk index, the AI-washing gap, divergence and the gap–return association

**Files:**
- Create: `src/aideleg/h6/talk.py`, `src/aideleg/h6/__main__.py` (subcommands `acquire, build, talk, secondary, summary, all`), `tests/h6/test_talk.py`, `tests/h6/test_cli.py`
- Modify: `Makefile`, adding `h6-data` (`uv run python -m aideleg.h6 acquire`; network) and `h6` (`uv run python -m aideleg.h6 all`; offline)
- Output: `docs/results/h6/talk_index.md`, `talk_index.csv`, `gap.md`, `gap.csv`, `gap_returns.md`, `summary.md`; figures `fig_h6_talk_by_year`, `fig_h6_talk_vs_usage`

The CLI (the H6 rebuild must work from a fresh clone whose `data/raw` was seeded by Plan 4's `--from-dir`):
- `acquire [--filers] [--fts] [--docs]`: network only. It fetches raw files into `data/raw/sec/` and the MANIFEST (Tasks 10, 11, 13); with no flag, all three.
- `build [--filers] [--fts]`: offline. `--filers` runs `build_filers()` from the saved form.idx files and submissions zip; `--fts` writes `hits_from_saved()` to `fts_hits.parquet`; with no flag, both. It never fetches.
- `talk`, `secondary`, `summary`: offline, from the derived files and the saved documents.
- `all` = `build` + `talk` + `secondary` + `summary`, with no acquisition. `make h6` runs it; `make h6-data` is the only H6 target that touches the network.

**Interfaces:**
- Consumes: `numerator`, `denominator`, `build_filers` output; `rq3.data.exposures` (Design B `z_usage`, `z_aioe`); `rq3.inference.confirmatory_alphas`, `rq3.inference.vector_test`; `rq3.report.*`; `save_figure`
- Produces:
  - `talk_table(num: pl.DataFrame, den: pl.DataFrame) -> pl.DataFrame` has columns `year, ff49, ff49_short, n_talk, n_filers, talk`. `talk` is null when `n_filers == 0`, and such industries are reported.
  - `T_YEAR = 2024`, i.e. filings dated 2024-01-01 to 2024-12-31, all public before 2025-03-27.
  - `gap(T: pl.DataFrame, expo_b: pl.DataFrame) -> pl.DataFrame` has columns `ff49_short, T, zT, z_usage, resid, gap`.
    - zT = (T − mean)/population SD over the industries with T.
    - The OLS is zT on [1, z_usage]; `gap` = resid / population SD(resid).
  - `spearman_ci(x: np.ndarray, y: np.ndarray, n_draws: int = 10_000, rng=None) -> dict` returns `rho, ci95, n_nan`. It resamples industries with replacement using `default_rng(SEED)`, takes the percentile CI, and drops and counts undefined draws.
  - `gap_returns(gap_df: pl.DataFrame) -> dict` calls `vector_test(alphas, gap, names)` over the Design B window, with no control. This is §6's "the §3.1 regression with gap_j in place of z_delegation" and the same D21 null. It reports the results with nominal p-values, in no family.
  - `run_talk(out_dir: Path) -> None`. `talk_index.csv` is `talk_table` over every year 2019–2025 (its columns); the pooled series is in `talk_index.md`. Its outputs:
    - the talk series by year, for each industry and pooled;
    - Spearman(T, z_usage) with its CI;
    - the full ranking of `gap`;
    - the gap–return result (b, s, b̄, both T and both p, the CI);
    - the two figures, titled "exploratory".

- [ ] **Step 1: Write the failing tests.**
  - `test_talk_share_is_numerator_over_denominator`: 3/10 gives 0.3, and `n_filers == 0` gives null, which is listed.
  - `test_gap_is_standardised_residual`: `gap` has mean 0 (to 1e-12) and population SD 1, and `|corr(gap, z_usage)| < 1e-12`.
  - `test_spearman_ci_reproducible`: two calls are equal, and for a monotone x, y the result is `rho == 1.0`.
  - `test_gap_return_test_uses_vector_test`: a spy sees `vector_test` called with `z` = gap ordered as the return columns and `control=None`.
  - `test_h6_docs_labelled`: each generated doc's first line contains `exploratory (PAP §6, D18)`.
  - `test_all_never_acquires` (`tests/h6/test_cli.py`): with `fetch.fetch`, `fetch.download` and `edgar._get_json` monkeypatched to `pytest.fail`, and `build`, `talk`, `secondary`, `summary` replaced by recorders, `main(["all"])` calls exactly `build, talk, secondary, summary` in that order.
  - `test_make_h6_is_offline`: `make -n h6` output contains `aideleg.h6 all` and not `acquire`; `make -n h6-data` contains `aideleg.h6 acquire`.
  - `gap.md` states Design B's zero-assigned share (`report.zero_assigned_lines(["B"])`), since `gap` uses `z_usage`.
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Real data.** `uv run python -m aideleg.h6 talk && uv run python -m aideleg.h6 summary`. `summary.md` has the heading `# H6: talk vs use (exploratory, PAP §6, D18)` and links each doc, with no estimates.
- [ ] **Step 6: Commit.** `feat(h6): talk index, AI-washing gap, Spearman CI, gap-return association (exploratory)`.

### Task 13: Secondary talk measure on downloaded 10-K primary documents

**Files:**
- Create: `src/aideleg/h6/secondary.py`, `tests/h6/test_secondary.py`
- Modify: `docs/pap/pre-analysis-plan.md` (§11 only, through `paplog`)
- Output: `docs/results/h6/secondary_talk.md`, `secondary_talk.csv`

**Interfaces:**
- Consumes: `filers.parquet`; the `sec_submissions_bulk` zip; `fetch.download`; `dictionary.clean_text`, `dictionary.count_terms`; `talk.talk_table` (for the comparison)
- Produces:
  - `primary_document(cik: int, adsh: str, zf: zipfile.ZipFile) -> str | None`. It searches `filings.recent` (`accessionNumber`, `primaryDocument`) of `CIK{cik:010d}.json`, then each `filings.files[].name` member.
  - `doc_url(cik, adsh, doc) -> str` = `https://www.sec.gov/Archives/edgar/data/{cik}/{adsh without dashes}/{doc}`.
  - `MIN_FREE_GIB = 30`; `assert_disk(path: Path) -> None` raises `OSError` below that.
  - `download_documents(filers: pl.DataFrame) -> pl.DataFrame`. It saves each document gzip-compressed at `data/raw/sec/docs/{cik}/{adsh}/{doc}.gz` and appends `{key, url, dest, retrieved_utc, bytes, sha256}` to `data/raw/sec/docs/INDEX.jsonl`, where `bytes` and `sha256` are of the **uncompressed** body.
    - It skips documents already indexed, so it is resumable.
    - When done, it records one MANIFEST record `sec_docs_index` for `INDEX.jsonl`.
    - A missing `primaryDocument` or a PDF is skipped and counted.
  - `download_documents` runs only under `acquire --docs`. Everything below reads the saved `.gz` files and never fetches, so `h6 all` rebuilds it offline.
  - `filing_rates(filers: pl.DataFrame) -> pl.DataFrame` has columns `year, cik, adsh, ff49, n_words, hits_primary, hits_acronym, rate_per_10k`, where rate = 10,000 × (primary + gated acronym hits) / `n_words`.
  - `industry_secondary(rates: pl.DataFrame) -> pl.DataFrame`: first the mean over a CIK's filings in that year, then the equal-weight mean over CIKs, per (year, ff49).
  - `run_secondary(out_dir: Path) -> None`. Its outputs:
    - the series by year;
    - the 2024 industry table;
    - Spearman(secondary 2024, T_j), descriptive with no CI;
    - the counts of skipped filings, and of filings under 2,000 words, which are kept.
  - Years: all 2019–2025 filers, the D18 filing set. The PAP names no subset.

- [ ] **Step 1: Write the failing tests.**
  - `test_primary_document_lookup_uses_recent_then_extra_pages`: a zip in which the accession appears only in `CIK0000000001-submissions-001.json` is still found, and an unknown accession gives None.
  - `test_rate_per_10k_words`: 2 primary hits in 20,000 words give 1.0.
  - `test_firm_year_mean_then_industry_mean`: CIK A has two filings (rates 1, 3) and CIK B one (rate 6), so the industry rate is (2 + 6)/2 = 4.
  - `test_disk_guard_refuses_below_threshold`: `shutil.disk_usage` monkeypatched to report 10 GiB free raises `OSError`.
  - `test_resume_skips_indexed_documents`: a second run makes 0 downloads.
  - `test_gzip_hash_is_of_uncompressed_body`.
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Acquire and run.** `uv run python -m aideleg.h6 acquire --docs && uv run python -m aideleg.h6 secondary` (the second command is offline). Expected: an `sec_docs_index` record, and a printed count of documents downloaded and skipped.
- [ ] **Step 6: Log the addition** in the set-digest form: `uv run python -m aideleg.paplog set-addition --source sec_docs_index --scope "pre-specified in §9.4" --used-by "H6 secondary measure, Plan 3 Task 13"`. The entry carries the number of documents (lines of `INDEX.jsonl`), its SHA-256 and the retrieval span.
- [ ] **Step 7: Commit.** `feat(h6): secondary per-10k-word talk measure on 10-K primary documents; §11 addition`.

### Task 14: Determinism and completeness check — STOP at the end

**Files:**
- Modify: none, unless a check fails, in which case STOP and report.

- [ ] **Step 1:** `rm -rf data/derived/h6 && make rq3 && make h6` (offline). Expected: `git status --porcelain docs/results` prints nothing. Byte-identical regeneration means nothing random escaped `SEED`, and no output depends on run order.
- [ ] **Step 2:** `uv run pytest -v && uv run ruff check`.
  - Expected: every test passes, including Plan 2's `tests/test_confirm_h5.py::test_binding_refuses_in_this_repo_when_src_differs` (this branch's `src` differs from `pap-v1`), `test_core_numeric_versions_unchanged_since_pap_v1` and `tests/test_pap_frozen.py`. Any failure is a STOP.
- [ ] **Step 3:** `git diff pap-v1 -- src/aideleg/confirm_h5.py src/aideleg/power.py src/aideleg/market` prints nothing.
- [ ] **Step 4:** the coverage table below is re-checked against the files that exist. Each listed output path is present and committed.
- [ ] **Step 5:** ledger entry: the commits and every STOP or note. **STOP:** no merge and no push without Ajai's go-ahead.

---

## Self-review

**PAP coverage**

| PAP item | Task | Output |
|---|---|---|
| §0.5 P-H5 1–4, 6 (single run, binding, marker, unedited two-file commit, refusal handling) | 1 | `docs/results/confirmatory_h5.{md,attempt}` |
| §0.5 P-H5 5 (every other post-seal read in later commits) | 2 (guard), 3–13 | `rq3.guard` |
| §3.1 dropped industries; §3.3 decision, intervals, secondary inference | done by the script in Task 1 | the record |
| §3.3 P11 Softw DFBETA (`dfbetas`) and Cook's D, H5 and H5b, in a later commit | 3 | `rq3/influence.*` |
| §7 D11 (RQ3 "can and cannot yet say") | 8 | `rq3/summary.md` |
| §8.3 Design A (A_r2, A_pooled; 2022-12-01 → 2026-08-31; A_pooled look-ahead label) | 5, 6, 7 | event study, terciles, FM |
| §8.3 D19 event rule, 14 dates, exclusions, disclosure, next-trading-day rule and mechanical check, [−250, −21], [0, +5], [0, +20], CAR-on-exposure | 5 | `event_study.*`, `event_days.csv` |
| §8.3 Eisfeldt et al.: sign of the CAR–`z_aioe` slope over [0, +9] at 2022-11-30, before `z_delegation` | 5 | `eisfeldt_replication.md` |
| §8.3 terciles: top 16 − bottom 16, fixed membership, monthly cap reweighting at the prior month-end, EW legs, CAPM/FF3/FF5+UMD, NW lag rule, Sharpe and PSR, stationary bootstrap (block 3, 10,000, SEED), costs 0/5/15/30 bps on formation turnover, DSR; Design B and Design A | 4, 6 | `terciles.*` |
| §8.3 Fama–MacBeth: exposure, log size, log BE/ME, 12-2 momentum, NW | 7 | `fama_macbeth.*` |
| §6 D18 filings (forms, amendments excluded, 2019–2025), SIC → FF49 with unmapped reported, FTS numerator with saved raw responses in the MANIFEST, full-index denominator | 10, 11 | `filers.parquet`, `fts_hits.parquet`, MANIFEST |
| §6 T_j (2024), gap, Spearman with bootstrap CI, ranking, series by year, gap–return association under the §3.3 procedure and the D21 null, nominal | 12 | `h6/talk_index.*`, `gap.*`, `gap_returns.md` |
| §6 secondary measure per 10,000 words, firm-level, then industry mean | 13 | `h6/secondary_talk.*` |
| §6.1 D12 terms, plurals, acronym gate, matching rules | 9 | `h6/dictionary.py` |
| §9.4 D20 (record and log the acquisitions as additions) | 0 (FF3, outside §9.4), 10, 11, 13 | §11 `A-` entries (set form for `sec_fts/` and `sec_docs_index`) |
| §11 pre-result clarifications and the R6/R32/R35 organisational note | 0 | §11 `C-` entries |
| §8.2 R1–R38 | **Plan 4** (the brief's boundary), using `vector_test`, `run_events(events=, expo=)`, `run_terciles(months=, expo=)`, `run_fm(months=, expo=)`, `fts_hits(start, end)`, `hits_from_saved`, `fts_phrases(terms)`, `count_terms(terms=)` | — |

**Choices this plan fixes where the PAP is silent.** They are fixed here, before any output exists, logged as §11 `C-` entries in Task 0 (before Task 1), and each is stated in its output:
- event-study cross-sectional inference = HC3, nominal;
- FF3 = the canonical `F-F_Research_Data_Factors_CSV.zip` (`ff3_monthly`, an `A-` addition outside §9.4), never FF5 columns;
- the cap and size row = the one whose ME is the prior month end, per French's verified definition (`SIZE_ME_OFFSET`);
- tercile ties broken by `ff49`, with k = n // 3;
- the bootstrap applied to the Sharpe and the mean, from one draw set per variant;
- DSR over the six tercile variants;
- FM `log_size` = ln of the average firm size at the prior row; BE/ME = "Sum of BE / Sum of ME" with French's July–June timing; months with too few complete industries skipped and counted;
- the gap–return test uses the H5 form only, with no control;
- an FTS hit in any document of a 10-K counts, so exhibit-only CIKs count in `n_talk` and are also reported;
- SIC = the current SIC from the bulk submissions file;
- the secondary measure covers all D18 years;
- `h6 all` = build + talk + secondary + summary, offline; acquisition is `h6-data`.

Review rulings of 2026-10-22 applied here: no Design A cross-sectional test (Design A = terciles, FM, events, each taking `expo=`); Task 0 (branch, firm-size verification, FF3 acquisition, `C-` entries) before the run; the narrowed Task 1 Step 5 status check; plan files expected committed (Task 1 Step 1); the shared `WORDING`; zero-assigned shares in every exposure doc; `fig_rq3_`/`fig_h6_` names; exhibit-only CIKs counted; the offline H6 rebuild; §11 through `paplog`; no silent fixes.

**Checks run.**
- **Steps.** No "TBD". Every test step names the test and its assertions.
- **Types.** `vector_test` (Task 3) is consumed in Task 12 with the same signature. `exposures()`, `daily()`, `monthly()`, `ff3_monthly()`, `characteristics()` (with `me_date`) and `zero_assigned()` (Task 2) are used unchanged in Tasks 3 and 5–7. `FORMS` and `YEARS` (Task 10) are used in Tasks 11 and 13. `WORDING` is Plan 2's, imported by `report` (Task 8) and used by every rq3 and h6 doc.
- **Cross-plan.** Plan 4's adapter calls `run_terciles(out_dir, months=, expo=)`, `run_fm(out_dir, months=, expo=)`, `run_events(out_dir, events=, expo=)` and their return columns as defined in Tasks 5–7; `rq3.guard.assert_confirmatory_recorded` (Task 2) is the guard Plan 4's return loader reuses; `fts_hits`, `hits_from_saved`, `numerator`, `denominator`, `talk_table`, `gap`, `spearman_ci`, `gap_returns`, `fts_phrases` and `PRIMARY_TERMS` keep these names. Plan 2's `paplog`, `WORDING`, `FORBIDDEN_PHRASES` and `save_figure` are used with Plan 2's spellings.
- **Review Focus.** Each of its five lines has its test in Task 2, 3, 5, 9 or 11.
- **Proportion.** Code blocks are commands only; bodies are left to the implementer.
