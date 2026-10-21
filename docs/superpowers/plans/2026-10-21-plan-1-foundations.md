# Plan 1 — Foundations: Data, Exposure Indices, Power, Pre-Analysis Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build everything the study needs *before* any hypothesis is tested:
- reproducible acquisition of every dataset;
- one harmonised panel across the six AEI releases;
- the jobs → industries → FF49 bridge and the exposure indices;
- a power analysis on pre-ChatGPT history;
- a pre-analysis plan (PAP) that Ajai signs and that is then frozen with a git tag.

**Architecture:** A Python package `aideleg` (src layout) with one module per responsibility. Raw downloads go to `data/raw/` (gitignored, checksummed in a committed manifest), and derived parquet tables go to `data/derived/`. A `Makefile` chains the stages. A **market seal** makes it impossible to load any return on or after 2022-11-30 until the git tag `pap-v1` exists.

**Tech Stack:** Python 3.12, uv, DuckDB, Polars, pandas (Excel I/O only), openpyxl, xlrd, statsmodels, numpy, requests, pyarrow, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-10-21-ai-delegation-design.md` (read it first; §4, §5.1, §5.3, §5.4.1, §6 and §7 govern this plan).

**Scope:** This plan covers spec Stages 0, 1 and 2, plus the parts of Stage 4 the PAP depends on. Stages 3–7 (RQ1 tests, market tests, talk-vs-use, robustness, paper) are Plans 2–4. They will be written after `pap-v1` exists, from the frozen PAP and the data audit (see "Roadmap" at the end).

## Global Constraints

- Repo root: `/Users/ajaiupadhyaya/Documents/ai-delegation`. Package: `src/aideleg/`. Tests: `tests/`.
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Wording rule (spec §6):** in code comments, docs and output labels, AEI data is "conversations matched to X tasks". Never infer job risk, displacement or reassurance. Say "labour market".
- **Market seal:** no code path may read French returns or factors dated ≥ `2022-11-30` unless the git tag `pap-v1` exists. Nothing in this plan is allowed to need them.
- **No hypothesis testing before `pap-v1`:**
  - No regression or correlation between delegation measures and wage, education, error-cost or country variables (H1–H4).
  - No return data after the seal.
  - The audit describes coverage only.
- Raw data are never committed. `data/raw/MANIFEST.json` (URL, retrieval UTC timestamp, bytes, SHA-256) is committed.
- HTTP User-Agent for `bls.gov` and `sec.gov`: `"Ajai Upadhyaya research ajaiupad@gmail.com"`. SEC requests must be ≤ 10/s.
- Randomness is seeded through `aideleg.config.SEED = 20261021`.
- Dates in the spec, copied verbatim:
  - ChatGPT launch: `2022-11-30`
  - Design B formation release: `r2` (published `2025-03-27`)
  - Design B return window: `2025-04-01` → `2026-08-31`
  - OEWS weight vintage: May 2024 (`oesm24*`)
- Release IDs: `r1`=2025-02-10, `r2`=2025-03-27, `r3`=2025-09-15, `r4`=2026-01-15, `r5`=2026-03-24, `r6`=2026-06-26.
- Collaboration buckets (AEI definition):
  - automation = `directive` + `feedback_loop`
  - augmentation = `task_iteration` + `validation` + `learning`
  - Shares are normalised over classified conversations (excluding `filtered`, `none` and `not_classified`), in percent 0–100.

## Review Focus

1. **Task text drift.** The same O\*NET task appears with different case, whitespace, trailing periods or unicode quotes across releases. Expected behaviour: it matches to one `task_id`, and unmatched names are counted and reported, never silently dropped. Test: `test_match_tolerates_case_space_punct` (Task 4).
2. **Unpublished ≠ zero.** AEI omits cells below privacy thresholds. A missing cell must stay missing in the panel, never become 0. The only exception is the explicit, documented zero assignment for occupations with no AEI match in the exposure step. Test: `test_unpublished_cells_stay_missing` (Task 7).
3. **OEWS suppression codes.** `**`, `*` and `#` in OEWS employment and wage columns must become nulls, not parse errors or zeros. Within-industry weights must renormalise over the non-null rows. Test: `test_suppressed_values_become_null` (Task 9).
4. **French file structure.** Each CSV holds several stacked tables (value-weighted, equal-weighted, number of firms, …), and missing values are `-99.99` or `-999`. The loader must return only the requested table, with NaN for missing values. Test: `test_reads_only_requested_table` (Task 3).
5. **SOC vintage and aggregation codes.** OEWS uses some aggregated SOC codes, such as `15-1250`- or `29-1229`-style rollups, that O\*NET-SOC detail codes do not match exactly. Expected behaviour: detailed codes that roll up are aggregated, and residual unmatched employment is reported. Test: `test_soc_rollup_matches_oews_aggregates` (Task 8).

---

## File map

```
pyproject.toml, uv.lock, Makefile, README.md, .gitignore, ruff.toml
src/aideleg/__init__.py
src/aideleg/config.py            paths, constants, release table, SEED, seal date
src/aideleg/acquire/http.py      polite session (UA per host, SEC rate limit, retries)
src/aideleg/acquire/sources.py   SOURCES registry (one Source per file)
src/aideleg/acquire/fetch.py     fetch(), manifest read/write, CLI `python -m aideleg.acquire`
src/aideleg/market/seal.py       pap_frozen(), assert_unsealed()
src/aideleg/market/french.py     read_french_table(), load_industry_returns(), load_factors(), read_siccodes()
src/aideleg/aei/schema.py        PANEL_COLUMNS, canonical metric names, Release enum
src/aideleg/aei/tasks.py         normalise_task_text(), TaskIndex, match_tasks()
src/aideleg/aei/parse_early.py   parse_r1(), parse_r2()
src/aideleg/aei/parse_facet.py   parse_facet_release() for r3–r5
src/aideleg/aei/parse_r6.py      parse_r6()
src/aideleg/aei/metric_map.csv   raw variable → canonical metric (or IGNORE + reason)
src/aideleg/aei/panel.py         build_panel(), quality checks, CLI
src/aideleg/occupations.py       task→SOC allocation, occupation table per release
src/aideleg/bls/oews.py          load_national(), load_industry_matrix()
src/aideleg/crosswalk/naics_ff49.py  concordance chain, naics_to_ff49 weights
src/aideleg/exposure.py          occupation + industry indices (usage, delegation, augmentation)
src/aideleg/benchmarks.py        AIOE + Eloundou loaders, SOC join, industry aggregation
src/aideleg/audit.py             coverage tables → docs/audit/tables/*.md
src/aideleg/power.py             historical-window MDE simulation
docs/audit/data-audit.md         written memo (Task 13)
docs/pap/pre-analysis-plan.md    PAP (Task 15)
tests/fixtures/…                 tiny hand-built files per parser
```

---

### Task 1: Scaffold, config and polite HTTP fetch with manifest

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `ruff.toml`, `Makefile`, `README.md` (stub: title, one-paragraph intent, `make all`), `src/aideleg/__init__.py`, `src/aideleg/config.py`, `src/aideleg/acquire/__init__.py`, `src/aideleg/acquire/http.py`, `src/aideleg/acquire/fetch.py`
- Test: `tests/acquire/test_fetch.py`

**Interfaces:**
- Produces:
  - `config.ROOT: Path`, `config.RAW: Path` (= ROOT/"data/raw"), `config.DERIVED: Path` (= ROOT/"data/derived"), `config.SEED = 20261021`, `config.SEAL_DATE = date(2022, 11, 30)`, `config.PAP_TAG = "pap-v1"`
  - `config.RELEASES: dict[str, date]` with the six IDs from Global Constraints
  - `http.session_for(url: str) -> requests.Session` (sets the UA for bls.gov/sec.gov, enforces ≤10 req/s for sec.gov)
  - `fetch.Source` (frozen dataclass: `key: str, url: str, dest: str` (path relative to RAW), `unzip: bool = False`)
  - `fetch.fetch(src: Source, raw_dir: Path = RAW, force: bool = False) -> fetch.FetchRecord` (dataclass: `key, url, dest, retrieved_utc: str, bytes: int, sha256: str`)
  - `fetch.load_manifest(raw_dir) -> dict[str, FetchRecord]`, `fetch.write_manifest(raw_dir, records)`

- [ ] **Step 1: Initialise the project.** `uv init --package --name aideleg --python 3.12`. Add the deps listed in Tech Stack, plus dev deps pytest and ruff. `.gitignore` covers `data/raw/`, `data/derived/`, `.venv/` and `__pycache__/`, but **not** `data/raw/MANIFEST.json` (use the `!data/raw/MANIFEST.json` pattern and gitignore `data/raw/*`).
- [ ] **Step 2: Write failing tests** in `tests/acquire/test_fetch.py`, using a `pytest-httpserver`-free approach: monkeypatch `http.session_for` to return a fake session whose `.get` streams fixed bytes.
  - `test_fetch_writes_file_and_sha256`: fetching bytes `b"abc"` writes `RAW/dest` and `record.sha256 == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"`, `record.bytes == 3`.
  - `test_fetch_skips_when_present_and_hash_matches`: second call with `force=False` makes zero GET calls.
  - `test_fetch_rejects_html_error_page`: if the body starts with `b"<!DOCTYPE HTML"` and the dest is not `.html`, raise `fetch.FetchError` (BLS returns an HTML "Access Denied" page with status 200).
  - `test_bls_and_sec_get_contact_user_agent`: `session_for("https://www.bls.gov/x").headers["User-Agent"] == "Ajai Upadhyaya research ajaiupad@gmail.com"`; same for `data.sec.gov`.
  - `test_unzip_extracts_next_to_archive`: a `Source(unzip=True)` whose bytes are a zip containing `a.csv` produces `RAW/<dest stem>/a.csv`.
- [ ] **Step 3: Run** `uv run pytest tests/acquire -v`. Expected: FAIL (module missing).
- [ ] **Step 4: Implement** `config.py`, `http.py` and `fetch.py`. Write to a `.part` file and rename it once complete. Retry 3 times with backoff on 5xx/429.
- [ ] **Step 5: Run** `uv run pytest tests/acquire -v && uv run ruff check`. Expected: all pass.
- [ ] **Step 6: Commit** `feat(acquire): polite fetch with checksummed manifest`.

### Task 2: Source registry and `make data`

**Files:**
- Create: `src/aideleg/acquire/sources.py`, `src/aideleg/acquire/__main__.py`
- Modify: `Makefile` (target `data`)
- Test: `tests/acquire/test_sources.py`

**Interfaces:**
- Consumes: `fetch.Source`, `fetch.fetch`, `fetch.write_manifest` (Task 1)
- Produces: `sources.SOURCES: list[Source]`, plus `sources.by_key(key: str) -> Source`. CLI: `uv run python -m aideleg.acquire [--only KEY ...]`.

The registry must contain exactly these keys (base `HF = https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main`, `FF = https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp`):

| key | url | unzip |
|---|---|---|
| `aei_r1_task_pct` | `HF/release_2025_02_10/onet_task_mappings.csv` | no |
| `aei_r1_collab` | `HF/release_2025_02_10/automation_vs_augmentation.csv` | no |
| `aei_r1_wage` | `HF/release_2025_02_10/wage_data.csv` | no |
| `aei_soc_structure` | `HF/release_2025_02_10/SOC_Structure.csv` | no |
| `aei_r2_task_pct` | `HF/release_2025_03_27/task_pct_v2.csv` | no |
| `aei_r2_collab_by_task` | `HF/release_2025_03_27/automation_vs_augmentation_by_task.csv` | no |
| `aei_r2_thinking` | `HF/release_2025_03_27/task_thinking_fractions.csv` | no |
| `aei_onet_tasks` | `HF/release_2025_03_27/onet_task_statements.csv` | no |
| `aei_r3_claude_ai` / `aei_r3_api` | `HF/release_2025_09_15/data/intermediate/aei_raw_{claude_ai,1p_api}_2025-08-04_to_2025-08-11.csv` | no |
| `aei_r3_docs` | `HF/release_2025_09_15/data_documentation.md` | no |
| `aei_r4_claude_ai` / `aei_r4_api` | `HF/release_2026_01_15/data/intermediate/aei_raw_{claude_ai,1p_api}_2025-11-13_to_2025-11-20.csv` | no |
| `aei_r4_docs` | `HF/release_2026_01_15/data_documentation.md` | no |
| `aei_r5_claude_ai` / `aei_r5_api` | `HF/release_2026_03_24/data/aei_raw_{claude_ai,1p_api}_2026-02-05_to_2026-02-12.csv` | no |
| `aei_r5_docs` | `HF/release_2026_03_24/data_documentation.md` | no |
| `aei_r6_claude_ai` / `aei_r6_api` | `HF/release_2026_06_26/data/aei_{claude_ai,1p_api}_2026-06-26.csv` | no |
| `aei_r6_docs` | `HF/release_2026_06_26/data_documentation.md` | no |
| `aei_job_exposure` | `HF/labor_market_impacts/job_exposure.csv` | no |
| `aei_geo_inputs` | the `HF/release_2025_09_15/data/intermediate/` files `working_age_pop_2024_country.csv`, `working_age_pop_2024_us_state.csv`, `gdp_2024_country.csv`, `gdp_2024_us_state.csv`, `iso_country_codes.csv` (one key each, suffix `_wap_country` etc.) | no |
| `oews_2024_nat` | `https://www.bls.gov/oes/special-requests/oesm24nat.zip` | yes |
| `oews_2024_ind` | `https://www.bls.gov/oes/special-requests/oesm24in4.zip` | yes |
| `oews_2025_ind` | `https://www.bls.gov/oes/special-requests/oesm25in4.zip` | yes |
| `ff49_daily` / `ff49_monthly` | `FF/49_Industry_Portfolios_daily_CSV.zip`, `FF/49_Industry_Portfolios_CSV.zip` | yes |
| `ff5_daily` / `ff5_monthly` | `FF/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip`, `FF/F-F_Research_Data_5_Factors_2x3_CSV.zip` | yes |
| `mom_daily` / `mom_monthly` | `FF/F-F_Momentum_Factor_daily_CSV.zip`, `FF/F-F_Momentum_Factor_CSV.zip` | yes |
| `ff_siccodes49` | `FF/Siccodes49.zip` | yes |
| `aioe` | `https://raw.githubusercontent.com/AIOE-Data/AIOE/main/AIOE_DataAppendix.xlsx` | no |
| `eloundou_occ` | `https://raw.githubusercontent.com/openai/GPTs-are-GPTs/main/data/occ_level.csv` | no |
| `census_sic87_naics97` | `https://www.census.gov/naics/concordances/1987_SIC_to_1997_NAICS.xls` | no |
| `census_naics97_02` … `census_naics17_22` | the Census concordances 1997→2002, 2002→2007, 2007→2012, 2012→2017, 2017→2022 from `https://www.census.gov/naics/concordances/` | no |
| `sec_tickers` | `https://www.sec.gov/files/company_tickers_exchange.json` | no |

- [ ] **Step 1: Write failing tests:**
  - `test_keys_unique_and_dests_unique`;
  - `test_every_url_is_https`;
  - `test_required_keys_present` (asserts the set of keys in the table above, after expanding `{a,b}` pairs);
  - `test_no_robot_or_task_penetration_files` (these large files are deliberately excluded: `robot_exposure_tasks.csv` is 99 MB and out of scope).
- [ ] **Step 2: Run** `uv run pytest tests/acquire/test_sources.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `SOURCES` and the CLI (fetch all, write the manifest, print a summary table of key/bytes/sha256[:12]).
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Real download.** `make data` (= `uv run python -m aideleg.acquire`). Expected: every key fetched with no `FetchError`; `data/raw/MANIFEST.json` lists every key. If a Census concordance filename differs from the one above, find the current filename on `https://www.census.gov/naics/?68967` (concordances page), update the registry and note it in the commit body.
- [ ] **Step 6: Commit** `feat(acquire): source registry; MANIFEST.json`, including `data/raw/MANIFEST.json`.

### Task 3: Market seal and Ken French readers

**Files:**
- Create: `src/aideleg/market/__init__.py`, `src/aideleg/market/seal.py`, `src/aideleg/market/french.py`
- Test: `tests/market/test_seal.py`, `tests/market/test_french.py`, `tests/fixtures/french/ind_daily_small.csv`, `tests/fixtures/french/siccodes_small.txt`

**Interfaces:**
- Produces:
  - `seal.pap_frozen(repo: Path = ROOT) -> bool` (true iff `git tag --list pap-v1` is non-empty)
  - `seal.SealedPeriodError(Exception)`
  - `seal.assert_unsealed(end: date, repo: Path = ROOT) -> None` (raises if `end >= SEAL_DATE` and not frozen)
  - `french.read_french_table(path: Path, title_startswith: str) -> pl.DataFrame` (columns `date: Date` + one Float64 column per series, in **percent** as published; -99.99/-999 → null)
  - `french.load_industry_returns(freq: Literal["D","M"], weighting: Literal["VW","EW"], end: date) -> pl.DataFrame` (calls `assert_unsealed(end)` first, then filters `date <= end`)
  - `french.load_factors(freq, end) -> pl.DataFrame` (columns `date, mkt_rf, smb, hml, rmw, cma, rf, umd`, in percent)
  - `french.read_siccodes(path) -> pl.DataFrame` (columns `ff49: int, ff49_short: str, ff49_name: str, sic_lo: int, sic_hi: int`)

- [ ] **Step 1: Build fixtures.**
  - `ind_daily_small.csv` copies the real layout: the preamble lines, `  Average Value Weighted Returns -- Daily`, a header `,Agric,Food`, three rows including one `-99.99`, a blank line, `  Average Equal Weighted Returns -- Daily`, a header, and two rows.
  - `siccodes_small.txt` holds two industries copied from the real `Siccodes49.txt` layout (`" 1 Agric  Agriculture"` followed by indented `0100-0199 ...` lines).
- [ ] **Step 2: Write failing tests:**
  - `test_reads_only_requested_table`: `read_french_table(fx, "Average Value Weighted Returns -- Daily")` has 3 rows, its columns are `["date","Agric","Food"]`, and the `-99.99` cell is null.
  - `test_monthly_dates_parse_to_month_end`: a `202301` row parses to `date(2023,1,31)`.
  - `test_sealed_without_tag_raises`: in a `tmp_path` git repo with no tags, `assert_unsealed(date(2022,11,30), repo=tmp)` raises `SealedPeriodError` and `assert_unsealed(date(2022,11,29), repo=tmp)` does not.
  - `test_unsealed_after_tag`: after `git tag pap-v1` in the tmp repo, no raise for `date(2026,8,31)`.
  - `test_load_industry_returns_checks_seal_before_reading`: monkeypatch `read_french_table` to fail if called; `load_industry_returns("D","VW", date(2025,1,1))` raises `SealedPeriodError`, not the monkeypatched error.
  - `test_siccodes_ranges`: the fixture yields rows with `sic_lo <= sic_hi`, and `ff49_short == "Agric"` for range `100–199`.
- [ ] **Step 3: Run** `uv run pytest tests/market -v`. Expected: FAIL.
- [ ] **Step 4: Implement.** Daily dates are `YYYYMMDD`, monthly `YYYYMM` (month end). Ignore the annual tables. Factor files: join FF5 and momentum on date, rename `Mkt-RF→mkt_rf`, `Mom→umd`, and lower-case the rest.
- [ ] **Step 5: Real-data smoke test** (pre-seal only). `uv run python -c "from aideleg.market.french import *; from datetime import date; d=load_industry_returns('D','VW',date(2022,11,29)); print(d.shape, d['date'].max())"`. Expected: 50 columns and max date `2022-11-29`.
- [ ] **Step 6: Run tests, then commit** `feat(market): sealed Ken French readers`.

### Task 4: Task-text normalisation and O\*NET matching

**Files:**
- Create: `src/aideleg/aei/__init__.py`, `src/aideleg/aei/schema.py`, `src/aideleg/aei/tasks.py`
- Test: `tests/aei/test_tasks.py`

**Interfaces:**
- Produces:
  - `schema.PANEL_COLUMNS = ["release","period_start","period_end","source","geo_level","geo_id","taxonomy","level","node_id","node_name","metric","value","definition"]`
  - `schema.TAXONOMIES = {"overall","onet_task","onet_dwa","onet_iwa","onet_gwa","soc_detailed","soc_major","request"}`
  - `schema.CANONICAL_METRICS` (frozenset including: `usage_pct, pct, automation_pct, augmentation_pct, directive_pct, feedback_loop_pct, task_iteration_pct, validation_pct, learning_pct, none_pct, filtered_pct, ai_autonomy_mean, human_education_years_mean, ai_education_years_mean, human_only_time_mean, human_with_ai_time_mean, human_only_ability_pct, use_case_work_pct, use_case_personal_pct, use_case_coursework_pct, multitasking_pct, usage_per_capita_index, count`)
  - `tasks.normalise_task_text(s: str) -> str` (NFKC, curly quotes → straight, lower-case, collapse whitespace, strip, strip one trailing period)
  - `tasks.TaskIndex.from_onet(path: Path) -> TaskIndex` with `.task_ids_for(text: str) -> list[int]` and `.occupations_for(task_id: int) -> list[str]` (O\*NET-SOC codes)
  - `tasks.match_tasks(names: pl.Series, index: TaskIndex) -> pl.DataFrame` (columns `task_name, task_id (nullable Int64), n_candidates`)

- [ ] **Step 1: Write failing tests:**
  - `test_match_tolerates_case_space_punct`: `"Act as advisers to student organizations."`, `"act  as advisers to student organizations"` and `"act as advisers to student organizations. "` all normalise to the same string.
  - `test_unmatched_is_null_not_dropped`: `match_tasks` keeps the row with `task_id` null and `n_candidates == 0`.
  - `test_shared_statement_lists_all_occupations`: a fixture O\*NET file in which one statement belongs to two O\*NET-SOC codes → `occupations_for` returns both.
  - `test_identical_text_different_ids`: when one text maps to more than one Task ID, `match_tasks` returns `n_candidates > 1` and `task_id` = the smallest ID, so the result is deterministic. The count of such cases is reported in the audit.
- [ ] **Step 2: Run** the tests. Expected: FAIL.
- [ ] **Step 3: Implement.** The source file columns are `O*NET-SOC Code, Title, Task ID, Task, Task Type, ...`.
- [ ] **Step 4: Real-data check.** Matching `aei_r2_collab_by_task.task_name` against `aei_onet_tasks` gives a matched share of 1.0 (verified 2026-10-21: 3,364/3,364). Do the same for `aei_r1_task_pct` and print the share.
- [ ] **Step 5: Run tests, then commit** `feat(aei): task text normalisation and O*NET matching`.

### Task 5: Parsers for releases r1 and r2 (task-name files)

**Files:**
- Create: `src/aideleg/aei/parse_early.py`
- Test: `tests/aei/test_parse_early.py`, `tests/fixtures/aei/r2_collab_small.csv`, `tests/fixtures/aei/r1_task_pct_small.csv`

**Interfaces:**
- Consumes: `TaskIndex`, `match_tasks`, `PANEL_COLUMNS` (Task 4)
- Produces: `parse_r1(raw: Path, index: TaskIndex) -> pl.DataFrame` and `parse_r2(raw: Path, index: TaskIndex) -> pl.DataFrame`, both in `PANEL_COLUMNS` with `geo_level="global"`, `geo_id="GLOBAL"` and `source="claude_ai"`.

Semantics:
- **r1:** `onet_task_mappings.csv` (`task_name,pct`, fraction 0–1) → `taxonomy="onet_task"`, `metric="pct"` and `value = pct*100`. `automation_vs_augmentation.csv` (`interaction_type,pct`, percent) → `taxonomy="overall"`, with metrics `<type>_pct` (spaces → underscores) plus derived `automation_pct`/`augmentation_pct`, renormalised over the classified types.
- **r2:** `task_pct_v2.csv` → `pct` as above. `automation_vs_augmentation_by_task.csv` (fractions per row, the columns `feedback_loop, directive, task_iteration, validation, learning, filtered` summing to 1) → per task: `filtered_pct = filtered*100`; each pattern `X_pct = X/(1-filtered)*100` when `filtered < 1`, else **null** (no classified conversations); `automation_pct = directive_pct + feedback_loop_pct`; `augmentation_pct` = the rest.
- `period_start`/`period_end`: r1 `2024-12-01`/`2025-01-01`, r2 `2025-02-24`/`2025-03-04` (the windows given in the reports). Mark both `definition="collab_v1"` (r1) / `"collab_v2"` (r2). **If the release READMEs/notebooks state different windows, use those and cite the file in a code comment.**

- [ ] **Step 1: Write failing tests:**
  - `test_r2_pattern_shares_renormalise`: row `(0.0, 0.3829787, 0.3617021, 0.0, 0.0, 0.2553191)` gives `directive_pct ≈ 51.43`, `task_iteration_pct ≈ 48.57`, `automation_pct ≈ 51.43`, `augmentation_pct ≈ 48.57` (abs tol 0.01).
  - `test_r2_fully_filtered_task_is_null`: `filtered == 1.0` → every pattern metric null and `filtered_pct == 100`.
  - `test_r1_pct_converted_to_percent`: fraction `0.006775` → `0.6775`.
  - `test_task_pct_sums_to_100`: over the fixture, the `pct` values sum to 100 ± 0.01.
  - `test_outputs_conform_to_schema`: the columns equal `PANEL_COLUMNS` and every `metric` is in `CANONICAL_METRICS`.
- [ ] **Step 2: Run** the tests. Expected: FAIL.
- [ ] **Step 3: Implement.** `node_id` = the matched O\*NET Task ID as a string (or `"unmatched:<normalised text>"`); `node_name` = the original text.
- [ ] **Step 4: Run tests, then commit** `feat(aei): parsers for releases r1-r2`.

### Task 6: Parser for releases r3–r5 (facet layout) and the metric map

**Files:**
- Create: `src/aideleg/aei/parse_facet.py`, `src/aideleg/aei/metric_map.csv`, `scripts/inventory_facets.py`
- Test: `tests/aei/test_parse_facet.py`, `tests/fixtures/aei/facet_small.csv`

**Interfaces:**
- Consumes: `PANEL_COLUMNS`, `CANONICAL_METRICS`, `TaskIndex` (Task 4)
- Produces: `parse_facet_release(path: Path, release: str, source: str, index: TaskIndex) -> pl.DataFrame` (PANEL_COLUMNS), plus `load_metric_map() -> pl.DataFrame` (columns `release_set, facet, variable, cluster_name_pattern, taxonomy, metric, action` where `action ∈ {"map","ignore"}`, plus a `reason` column).

The raw layout is `geo_id, geography, date_start, date_end, platform_and_product, facet, level, variable, cluster_name, value` (verified for r3, r4 and r5). `geography` ∈ {country, state-level values, global}. `platform_and_product` differs by release (e.g. `"Claude AI (Free and Pro)"` vs `"Claude AI (Free, Pro, and Max)"`) and goes into `definition` as a suffix.

- [ ] **Step 1: Inventory.** `scripts/inventory_facets.py` writes `docs/audit/tables/facet_inventory.md`, listing for each release every distinct `(facet, level, variable)` with row counts and 3 example `cluster_name`s. Run it on r3, r4 and r5, and commit the table.
- [ ] **Step 2: Write `metric_map.csv` from the inventory.** Every observed `(facet, variable)` gets one row, either `map` (to a canonical metric and taxonomy) or `ignore` with a reason (e.g. `*_count` → `count` is mapped; intersection facets that are not needed are ignored with the reason "cross-tab not used in Plans 1–4").
  - Collaboration facets map their `cluster_name` (`directive`, `feedback loop`, `task iteration`, `validation`, `learning`, `none`, `not_classified`) onto the pattern metrics.
  - `automation_pct`/`augmentation_pct` are derived after renormalisation, exactly as in Task 5.
- [ ] **Step 3: Write failing tests:**
  - `test_every_inventoried_variable_is_mapped_or_ignored`: loads the inventory table and `metric_map.csv` and asserts full coverage.
  - `test_collaboration_renormalises_excluding_none_and_unclassified`: fixture with directive 15, feedback loop 5, task iteration 20, none 10, not_classified 50 (counts) → `directive_pct = 37.5`, `automation_pct = 50.0`.
  - `test_geography_levels_normalised`: raw `country` → `geo_level="country"` with an ISO-3 `geo_id`. Raw 2-letter country codes are converted using `aei_geo_inputs_iso`. US states → `geo_level="subregion"`, `geo_id="US-CA"` style.
  - `test_onet_task_cluster_names_matched_to_ids`.
- [ ] **Step 4: Run** the tests. Expected: FAIL. **Step 5: Implement** using DuckDB `read_csv` (the files reach 103 MB). **Step 6: Run** tests and parse all three real releases without error. Print the row count per release.
- [ ] **Step 7: Commit** `feat(aei): facet-layout parser r3-r5 with audited metric map`.

### Task 7: Release r6 parser, panel build and quality checks

**Files:**
- Create: `src/aideleg/aei/parse_r6.py`, `src/aideleg/aei/panel.py`, `src/aideleg/aei/__main__.py`
- Modify: `Makefile` (target `panel` → `data/derived/aei_panel.parquet`)
- Test: `tests/aei/test_parse_r6.py`, `tests/aei/test_panel.py`, `tests/fixtures/aei/r6_small.csv`

**Interfaces:**
- Consumes: Tasks 4–6
- Produces:
  - `parse_r6(path, source, index) -> pl.DataFrame`
  - `panel.build_panel(raw: Path = RAW) -> pl.DataFrame`, written to `DERIVED/"aei_panel.parquet"`
  - `panel.QualityReport` (dataclass of check-name → (passed: bool, detail: str)) and `panel.check_panel(df) -> QualityReport`

r6 columns: `date_start, date_end, geo_id, geo_level, category_name, hierarchy_level, metric_id, value, node_name, node_external_id`.
- Category → taxonomy:
  - `onet`, level 0/1/2/3 → `onet_task`/`onet_dwa`/`onet_iwa`/`onet_gwa`
  - `soc_occupation`, level 0/1 → `soc_detailed`/`soc_major`
  - `request` → `request`
  - `overall` → `overall`
- `collaboration_bucket_automation_pct` → `automation_pct`; `collaboration_<x>_pct` → `<x>_pct`.
- Each of r6's two months is a separate period with `release="r6"`.

- [ ] **Step 1: Write failing tests:**
  - `test_r6_maps_buckets_and_patterns`.
  - `test_unpublished_cells_stay_missing`: the fixture omits one SOC row for May; the panel holds no row for it, and no 0 is imputed.
  - `test_check_panel_shares_sum`: for every `(release, period, source, geo, taxonomy, level)`, the `pct` values sum to 100 ± 0.5, or the report records the shortfall explicitly as "unpublished mass" (AEI suppression makes sums < 100). The check **fails** only if a sum exceeds 100.5.
  - `test_check_panel_pattern_partition`: wherever all five patterns are present, `automation_pct + augmentation_pct` = 100 ± 0.1.
  - `test_r6_automation_bucket_consistent_with_patterns`: for r6, the published `automation_pct` equals the renormalised `directive + feedback_loop` within 1.0 point. Any disagreement is recorded as a finding, and the published value is kept.
  - `test_panel_row_counts_pinned`: the per-release row counts equal `tests/aei/expected_counts.json`, which is generated once in Step 4 and committed. Changes then require a deliberate update.
- [ ] **Step 2: Run** the tests. Expected: FAIL. **Step 3: Implement.**
- [ ] **Step 4: Build and pin.** Run `make panel` and generate `expected_counts.json`. Save `check_panel`'s output to `docs/audit/tables/panel_quality.md`.
- [ ] **Step 5: Run the full test suite, then commit** `feat(aei): harmonised six-release panel with quality checks`.

### Task 8: Occupation table (tasks → SOC) per release

**Files:**
- Create: `src/aideleg/occupations.py`
- Test: `tests/test_occupations.py`

**Interfaces:**
- Consumes: the panel parquet (Task 7) and `TaskIndex.occupations_for` (Task 4)
- Produces: `occupation_table(panel: pl.DataFrame, release: str, index: TaskIndex, allocation: Literal["equal","full"] = "equal") -> pl.DataFrame` with columns `release, soc6 (str "NN-NNNN"), usage_share (percent of the release's task usage), automation_pct, augmentation_pct, directive_pct, feedback_loop_pct, task_iteration_pct, validation_pct, learning_pct, n_tasks`. Also `soc_rollup(soc6: str, oews_codes: set[str]) -> str`.

Rules **[call, in spec §5.3]**:
- A task shared by *k* occupations contributes `pct/k` of usage to each (`"equal"`), or the full `pct` to each (`"full"`, sensitivity only).
- O\*NET-SOC `NN-NNNN.xx` → `soc6 = NN-NNNN`.
- Occupation pattern shares are usage-weighted means over the occupation's tasks, using only tasks with non-null pattern values. The weights are those tasks' allocated pct.
- For r6, the published `soc_detailed` rows are used directly, and the task-allocated version is computed as a check.
- `soc_rollup` maps a detailed code to the OEWS aggregate that contains it when OEWS publishes only the aggregate. Example: if OEWS has `15-1250`-style codes, any `15-125x` maps there. Derive the rollups from the OEWS code list: a code ending in `0` that is absent from SOC detail.

- [ ] **Step 1: Write failing tests:**
  - `test_equal_allocation_conserves_usage`: the fixture's total usage across occupations equals the total task pct.
  - `test_weighted_pattern_mean`: two tasks with pct 3 and 1 and automation 60 and 20 → occupation automation 50.
  - `test_null_pattern_tasks_excluded_from_mean`.
  - `test_soc_rollup_matches_oews_aggregates`: with `oews_codes={"15-1250"}`, `soc_rollup("15-1252", …) == "15-1250"`; with `{"15-1252"}` it returns `"15-1252"`.
  - `test_r6_task_allocation_close_to_published_soc`: real-data test, marked `@pytest.mark.data` and skipped when `data/raw` is absent. Spearman ρ between allocated and published r6 usage shares ≥ 0.9. Record the actual ρ in the audit; if ρ < 0.9, stop and report.
- [ ] **Step 2–4:** Run the tests and confirm they fail, implement, then run them again.
- [ ] **Step 5: Commit** `feat: occupation table from task usage`.

### Task 9: OEWS loaders

**Files:**
- Create: `src/aideleg/bls/__init__.py`, `src/aideleg/bls/oews.py`
- Test: `tests/bls/test_oews.py`, `tests/fixtures/bls/nat4d_small.xlsx` (built in the test with openpyxl)

**Interfaces:**
- Produces:
  - `load_national(year: int = 2024) -> pl.DataFrame` (`soc6, title, tot_emp, a_median`; detailed occupations only, `O_GROUP == "detailed"`)
  - `load_industry_matrix(year: int = 2024, digits: Literal[3, 4] = 4) -> pl.DataFrame` (`naics, naics_title, soc6, tot_emp, emp_share_in_industry`; cross-ownership rows only, detailed occupations; `emp_share_in_industry` sums to 1 within each industry over non-null employment)

- [ ] **Step 1: Write failing tests:**
  - `test_suppressed_values_become_null` (`"**"`, `"*"`, `"#"`).
  - `test_shares_sum_to_one_per_industry`.
  - `test_only_detailed_occupations`.
  - `test_real_join_coverage` (`@pytest.mark.data`): the AEI r6 SOC codes, joined to the national 2024 file after `soc_rollup`, cover ≥ 80% of total employment. 83.4% was measured on 2025 nat3d on 2026-10-21; record the 2024 value.
- [ ] **Step 2–4:** Run the tests and confirm they fail, implement, then run them again.
- [ ] **Step 5: Commit** `feat(bls): OEWS national and industry-occupation loaders`.

### Task 10: NAICS → FF49 crosswalk

**Files:**
- Create: `src/aideleg/crosswalk/__init__.py`, `src/aideleg/crosswalk/naics_ff49.py`
- Test: `tests/crosswalk/test_naics_ff49.py`

**Interfaces:**
- Consumes: `french.read_siccodes` (Task 3), the Census concordance files (Task 2), `load_industry_matrix` (Task 9)
- Produces:
  - `naics_to_sic(naics_vintage: int = 2022) -> pl.DataFrame` (`naics, sic, weight`; weights sum to 1 per NAICS code)
  - `sic_to_ff49(siccodes: pl.DataFrame) -> Callable[[int], int | None]`
  - `naics_to_ff49(method: Literal["split","majority"] = "split") -> pl.DataFrame` (`naics, ff49, weight`)
  - `coverage_report(matrix) -> pl.DataFrame` (employment share by mapping status)

Method **[call]**:
- Chain SIC87 → NAICS97 → 02 → 07 → 12 → 17 → 22. At each many-to-many link, split weight equally across targets, unless a concordance file supplies an explicit share column (use it if present).
- Invert to NAICS22 → SIC by normalising.
- SIC codes outside every FF49 range go to FF49 #48 "Other" only if French assigns them there; otherwise they are unmapped.
- OEWS 4-digit codes are padded (`"511200"` style) or BLS aggregates containing letters. Map them by their first 4 digits, and for letter aggregates use the union of their NAICS components, listed in `oesm24in4/file_descriptions.xlsx`.
- Government (NAICS 99xxxx) is a separate "no public equity" bucket and is excluded from FF49 indices.
- `"majority"` assigns each NAICS code wholly to its largest-weight FF49 industry (robustness).

- [ ] **Step 1: Write failing tests:**
  - `test_weights_sum_to_one`.
  - `test_known_mappings` (majority method): NAICS `5112` (or its 2022 successor `5132`) → FF49 `Softw`; `5221` → `Banks`; `3254` → `Drugs`; `4841` → `Trans`; `5241` → `Insur`.
  - `test_government_excluded_not_unmapped`.
  - `test_unmapped_private_employment_below_1pct` (`@pytest.mark.data`): private-sector OEWS employment with no FF49 mapping is < 1% of private employment. If it fails, list the codes and stop.
- [ ] **Step 2–4:** Run the tests and confirm they fail, implement, then run them again.
- [ ] **Step 5: Commit** `feat(crosswalk): NAICS to Fama-French 49 industries`.

### Task 11: Exposure indices

**Files:**
- Create: `src/aideleg/exposure.py`
- Modify: `Makefile` (target `exposure` → `data/derived/exposure_{occupation,ff49}.parquet`)
- Test: `tests/test_exposure.py`

**Interfaces:**
- Consumes: `occupation_table` (Task 8), `load_national` / `load_industry_matrix` (Task 9), `naics_to_ff49` (Task 10)
- Produces:
  - `occupation_exposure(occ: pl.DataFrame, national: pl.DataFrame, unmatched: Literal["zero","drop"] = "zero") -> pl.DataFrame` (`soc6, usage_intensity U, delegation_intensity D, augmentation_intensity A`)
  - `industry_exposure(occ_exp, matrix, crosswalk) -> pl.DataFrame` (`ff49, ff49_short, E_usage, E_delegation, E_augmentation, z_usage, z_delegation, z_augmentation, emp_covered_share`)
  - `build_exposure(design: Literal["B","A_pooled","A_r2"]) -> pl.DataFrame`

Definitions (spec §5.3):
- `U_o = usage_share_o / emp_share_o`, where `emp_share_o` is the occupation's share of national detailed-occupation employment, May 2024.
- `D_o = U_o * automation_pct_o / 100`, and `A_o = U_o * augmentation_pct_o / 100`.
- An occupation with no AEI usage (`unmatched="zero"`) gets `U = D = A = 0`.
- An occupation with usage but null pattern shares gets `D` and `A` null and is excluded from those industry sums, with the weights renormalised. This is counted in `emp_covered_share`.
- Industry: `E_j = Σ_o w_oj X_o`, where `w_oj` is the within-industry employment share. NAICS-level `E` is mapped to FF49 as a weighted mean using crosswalk weight × NAICS employment.
- `z_*` = standardised across the 49 industries (population SD).

Designs:
- **B:** release r2 only (the confirmatory input).
- **A_pooled:** each occupation's metrics averaged over r2–r6 with equal release weights, definition-stable metrics only (exploratory).
- **A_r2:** identical to B but labelled for the exploratory design.

- [ ] **Step 1: Write failing tests** (on a 3-occupation, 2-industry toy built in the test):
  - `test_usage_intensity_hand_computed`: usage shares [50, 30, 20], employment shares [25, 25, 50] → U = [2.0, 1.2, 0.4].
  - `test_delegation_uses_automation_share`: automation 40 → D = 0.4·U.
  - `test_industry_is_employment_weighted`: industry with weights [0.5, 0.5, 0] → E_usage = 1.6.
  - `test_z_scores_have_unit_sd`.
  - `test_design_b_reads_only_r2`: build_exposure("B") from a panel containing r2 and r6 rows uses no r6 values (perturbing r6 leaves the output identical).
- [ ] **Step 2–4:** Run the tests and confirm they fail, implement, then run them again.
- [ ] **Step 5:** Run `make exposure`. Print the top and bottom 5 FF49 industries by `z_delegation` for Design B (descriptive, allowed before the PAP).
- [ ] **Step 6: Commit** `feat: occupation and FF49 exposure indices`.

### Task 12: Theoretical-exposure benchmarks

**Files:**
- Create: `src/aideleg/benchmarks.py`
- Test: `tests/test_benchmarks.py`

**Interfaces:**
- Consumes: `load_national`, `load_industry_matrix`, `naics_to_ff49`, and the industry aggregation from Task 11 (reuse `industry_exposure` with a generic column)
- Produces:
  - `load_aioe() -> pl.DataFrame` (`soc6, aioe`) from `AIOE_DataAppendix.xlsx`, using the occupation-level sheet. Read the sheet names, choose the occupation-level AIOE sheet and assert its columns.
  - `load_eloundou() -> pl.DataFrame` (`soc6, beta_human, beta_gpt4` or the equivalent columns present in `occ_level.csv`; the column names are confirmed in Step 1)
  - `benchmark_ff49() -> pl.DataFrame` (`ff49, z_aioe, z_eloundou`)

- [ ] **Step 1: Inspect** both files and write their exact column names into the docstring.
- [ ] **Step 2: Write failing tests:**
  - `test_aioe_soc_codes_valid_format`.
  - `test_aioe_coverage_of_national_employment_above_80pct` (`@pytest.mark.data`).
  - `test_benchmark_ff49_has_49_rows_or_reports_missing`.
- [ ] **Step 3–5:** Implement, run the tests, then commit `feat: AIOE and Eloundou benchmarks aggregated to FF49`.

### Task 13: Data audit

**Files:**
- Create: `src/aideleg/audit.py`, `docs/audit/data-audit.md`
- Modify: `Makefile` (target `audit`)

**Interfaces:**
- Consumes: everything above
- Produces: `docs/audit/tables/*.md` (generated), and a written memo

Generated tables:
- per release: window, platform scope, taxonomy levels present, metrics present, row counts;
- task match rates per release, and multi-candidate task counts;
- unpublished mass per taxonomy and release;
- r6 bucket-consistency finding (Task 7);
- allocated-vs-published ρ (Task 8);
- OEWS employment coverage (Task 9);
- crosswalk coverage (Task 10);
- exposure coverage per FF49 industry;
- benchmark coverage;
- the "measurement regimes" table: release × platform × classifier/model × collaboration taxonomy version, with sources cited to the release docs.

- [ ] **Step 1: Implement** `audit.py`. Every table is generated from the derived data, with no hand-typed numbers.
- [ ] **Step 2: Constraint check.** `audit.py` contains no regression or correlation between delegation measures and wage, education, error-cost or country variables (Global Constraints). The reviewer verifies this.
- [ ] **Step 3: Write the memo** `data-audit.md` (2–4 pages). It covers what each source is, the coverage numbers (linked to the tables), every known measurement-regime change, the decisions they force (e.g. which metrics are "definition-stable" for H2), and open data risks.
- [ ] **Step 4: Run** `make audit`, check the tables render, then commit `docs: data audit`.

### Task 14: Power analysis on pre-seal history

**Files:**
- Create: `src/aideleg/power.py`, `docs/pap/power.md` (generated section + interpretation)
- Test: `tests/test_power.py`

**Interfaces:**
- Consumes: `load_industry_returns("D","VW", end=date(2022,11,29))`, `load_factors("D", end=date(2022,11,29))` (Task 3), and Design B `z_delegation` and `z_aioe` (Tasks 11–12)
- Produces:
  - `window_alphas(returns, factors, start: date, end: date) -> pl.Series` (49 annualised FF5+UMD alphas from daily OLS; annualise ×252; returns and factors in percent → decimal)
  - `slope_null_distribution(z: np.ndarray, windows: list[tuple[date, date]]) -> np.ndarray` (cross-sectional OLS slope of alphas on the **fixed** Design B exposure vector `z`, one per historical window)
  - `mde(null_slopes: np.ndarray, alpha: float = 0.025, power: float = 0.80) -> float` = `(z_{1-alpha/2} + z_{power}) * sd(null_slopes)`
  - `run_power() -> dict` (writes `docs/pap/power.md`)

Design:
- Historical windows are 17-month periods (the length of the Design B window, 2025-04-01 → 2026-08-31), stepped monthly from 1990-01 to the last window ending ≤ 2022-11-29.
- Report both overlapping-window and non-overlapping-window sd.
- Report the MDE for H5, in annualised alpha per 1 SD of delegation exposure, and the MDE for H5b, the delegation slope with `z_aioe` as a control.
- `alpha = 0.025` because Holm's first step over the family {H5, H5b} uses 0.05/2.

- [ ] **Step 1: Write failing tests:**
  - `test_window_alpha_recovers_planted_alpha`: synthetic daily returns = 1.0·mkt + 0.0004 + noise(seed) → annualised alpha ≈ 0.10 ± 0.02.
  - `test_mde_formula`: sd = 1 → `mde ≈ 2.241 + 0.8416 = 3.0826` (tol 1e-3).
  - `test_power_never_reads_sealed_dates`: run with monkeypatched loaders that record the requested `end`; every `end` is < `2022-11-30`.
- [ ] **Step 2–4:** Run the tests and confirm they fail, implement, then run them again.
- [ ] **Step 5: Run** `uv run python -m aideleg.power`. `docs/pap/power.md` reports both MDEs and the window counts.
- [ ] **Step 6: Commit** `feat: pre-seal power analysis for H5/H5b`.

### Task 15: Pre-analysis plan and freeze

**Files:**
- Create: `docs/pap/pre-analysis-plan.md`

The PAP is written from spec §2, §5 and §5.4.1, the audit (Task 13) and the power results (Task 14). It must state, in this order:
1. hypotheses H1–H6 verbatim from the spec (approved by Ajai 2026-10-21);
2. for each hypothesis: the outcome variable, the exposure or predictor, the sample, the estimator, the SEs/inference, the decision rule, and whether it is confirmatory or exploratory;
3. the confirmatory market family {H5, H5b} with Holm correction, the primary specification exactly as in spec §5.4.1, and randomisation inference with 10,000 permutations seeded `SEED`;
4. the RQ1 Holm family {H1, H2, H3, H4} with each one's primary specification;
5. the definition-stable metric list for H2 (from the audit);
6. the H6 AI term dictionary (drafted here; Ajai approves it with the PAP);
7. the power results and the **pre-registered plausibility rule:** *if the H5 MDE exceeds 5 percentage points of annualised alpha per 1 SD of exposure, RQ3 is reported as "what the market evidence can and cannot yet say", and the paper is led by RQ1–RQ2* **[call: threshold for Ajai to confirm or change before signing]**;
8. the robustness list (spec §5.6);
9. the data freeze: the MANIFEST.json SHA-256 values for all sources;
10. a "Deviations" section, empty at freeze.

- [ ] **Step 1: Draft the PAP**, then dispatch a fresh reviewer subagent as a hostile referee. Prompt: "find every place this PAP leaves a researcher degrees of freedom to choose after seeing results". Close every gap the reviewer finds.
- [ ] **Step 2: Commit** `docs: pre-analysis plan draft`.
- [ ] **Step 3: STOP — human gate.** Give Ajai the PAP, the power results and the 5-pp plausibility threshold for sign-off. Do not tag until Ajai approves in chat.
- [ ] **Step 4: Freeze.** After approval, record "Signed: Ajai Upadhyaya, <date>" in the PAP, commit, then `git tag -a pap-v1 -m "Pre-analysis plan frozen"`. Verify `uv run python -c "from aideleg.market.seal import pap_frozen; assert pap_frozen()"`.

---

## Roadmap (written after `pap-v1`; not part of this plan)

- **Plan 2 — Behaviour (RQ1, spec Stage 3):** descriptive anatomy, H1–H4 estimation exactly as frozen, shift-share country decomposition, choropleth maps.
- **Plan 3 — Markets and talk-vs-use (RQ3/H6, Stage 5):** confirmatory H5/H5b with randomisation inference; then the exploratory Design A, event studies, tercile portfolios, Fama–MacBeth and the Eisfeldt et al. replication; the EDGAR 10-K pipeline.
- **Plan 4 — Robustness, red team, paper (Stages 6–7):** the spec §5.6 list, an adversarial review of every headline number, figure system, the Quarto/XeLaTeX paper, the 2-page brief and replication from a clean clone.
