# Delegating to the Machine

Replication package for *Delegating to the Machine*, by Ajai Upadhyaya. This README follows the
AEA Data Editor's "Template README and Guidance"
(<https://social-science-data-editors.github.io/template_README/>). The blocks between
`<!-- BEGIN GENERATED: … -->` and `<!-- END GENERATED: … -->` are written by
`uv run python -m aideleg.paper` (`aideleg.paper.includes.readme_blocks`); do not edit them by
hand. `tests/test_readme.py` fails when one of them is stale.

<!-- BEGIN GENERATED: wording -->
AEI data are conversations matched to O*NET tasks. Nothing here says anything about job risk, displacement or reassurance about the labour market.
<!-- END GENERATED: wording -->

## Overview

The study joins the Anthropic Economic Index (AEI: conversations matched to O\*NET tasks) to
O\*NET, BLS Occupational Employment and Wage Statistics, Census and BLS concordances, two
published exposure benchmarks (AIOE; Eloundou et al.), SEC EDGAR filings and Kenneth French's
factor and industry returns. RQ1 describes how delegation to the model varies across tasks,
occupations, wages, education and geography (H1–H4); RQ2 compares the AEI measures with the
exposure benchmarks; RQ3 asks what the market evidence can and cannot yet say (H5/H5b, H6).

Every hypothesis, specification, sample, inference and decision rule was fixed in a
pre-analysis plan before any of these results were seen:

<!-- BEGIN GENERATED: preregistration -->
The pre-analysis plan (`docs/pap/pre-analysis-plan.md`) was signed and frozen as the annotated git tag `pap-v1` on commit `6a16b1ad052977650b90c8062ceeeab9ac6572e1` (2026-10-21). Every later change to it is an entry of its §11.
<!-- END GENERATED: preregistration -->

The code in this repository rebuilds every derived file, result table, figure and the paper from
the raw files listed below. Two confirmatory outputs are inputs, not outputs, of the rebuild: the
single logged run of H1–H4 (`docs/results/rq1/confirmatory_rq1.*`) and the single confirmatory
run of H5/H5b (`docs/results/confirmatory_h5.md` and `.attempt`). Both were committed once and
are never re-executed (see Instructions to Replicators).

The paper's Statements section records the use of AI tools and the author's declaration of
interests. In short: the code, analysis and drafts were produced with Claude (Anthropic)
running in Claude Code under the author's direction; the author set the research questions and
hypotheses, signed the pre-analysis plan and approved every deviation. The author has no
employment, funding, consulting or equity relationship with Anthropic, OpenAI or any other AI
developer, and holds no position in the industry portfolios studied beyond broad index funds.

## Data Availability and Provenance Statements

### Statement about Rights

- [x] I certify that the author(s) of the manuscript have legitimate access to and permission
  to use the data used in this manuscript.
- [ ] I certify that the author(s) of the manuscript have documented permission to
  redistribute/publish the data contained within this replication package.

The second box is not checked because this repository redistributes no raw data: every raw file
is downloaded from its original source by `make data`, and only `data/raw/MANIFEST.json` (URL,
retrieval time, size and SHA-256 of each file) is committed. Each source's own terms are quoted
below.

### License for Code

The code (`src/`, `scripts/`, `tests/`, the `Makefile` and the Quarto configuration) is
licensed under the MIT License (`LICENSE`).

### License for Data

The paper, the brief, the pre-analysis plan, the results and the other documentation are
licensed under CC BY 4.0 (`LICENSE-text.md`). The raw data are not covered by either licence:
each source keeps its own terms, quoted below, and every figure or table built from a source
carries that source's attribution.

### Archive deposit

The frozen raw archive is deposited at Zenodo in two records, built from `data/raw` by
`uv run python -m aideleg.acquire --build-deposit OUT` (`OUT/public`, `OUT/restricted`):

- **Public record:** this repository at its release tag together with every raw file whose
  source allows redistribution: the AEI, O\*NET, BLS, Census, SEC EDGAR (including the 10-K
  documents of `INDEX.jsonl`), Natural Earth and Eloundou et al. files.
- **Restricted record (access on request):** the Kenneth R. French Data Library files and AIOE,
  whose pages state no licence (below). They are shared on request for replication only.

To restore the archive, unpack both records' raw parts into one directory `DIR` and run
`uv run python -m aideleg.acquire --from-dir DIR`.

DOIs:
- Code, pre-analysis plan, results and paper (this repository, release v1.0.0):
  <https://doi.org/10.5281/zenodo.23631273> (all versions: <https://doi.org/10.5281/zenodo.23631272>).
- Raw data, public part: <https://doi.org/10.5281/zenodo.23632464> (`public.zip`).
- Raw data, restricted part (access on request): <https://doi.org/10.5281/zenodo.23632457>
  (`restricted.zip`).

### Summary of Availability

- [x] All data **are** publicly available.
- [ ] Some data **cannot be made** publicly available.
- [ ] **No data can be made** publicly available.

Every source is public and needs no registration. Exact replication needs the same file
vintages: the MANIFEST pins each file's SHA-256, and the Fama-French files are revised
retroactively by their publisher, so a fresh download of them may differ (see Instructions to
Replicators).

### Details on each Data Source

Each licence statement below is quoted from the source's own page (checked 2026-10-24); where a
page states no licence, that is said, with a pointer to the source's terms. Citation keys are
those of `docs/paper/references.bib`.

**Anthropic Economic Index** (MANIFEST keys `aei_*`: releases r1–r6 and the labour market
impacts file). Source: <https://huggingface.co/datasets/Anthropic/EconomicIndex>. The dataset
README states: "Data released under CC-BY, code released under MIT License." (its metadata
field reads `license: mit`). The README gives one citation per release; they are
`handa2025economic` (second release), `appel2025uneven` (third), `appel2026economic` (fourth),
`massenkoff2026learning` (fifth) and `anthropic2026economicindex` (sixth), as given there.

**O\*NET 29.2 and 29.3 databases and the 2010–2019 taxonomy crosswalk** (`onet_*`). Source:
<https://www.onetcenter.org/database.html>. The licence page
(<https://www.onetcenter.org/license_db.html>) states that the database content "is licensed
under a Creative Commons Attribution 4.0 International License" (CC BY 4.0). Following its
attribution form for the releases used here: this package includes information from the O\*NET
29.2 and 29.3 Databases by the U.S. Department of Labor, Employment and Training Administration
(USDOL/ETA), used under the CC BY 4.0 license; the author has modified all or some of this
information; USDOL/ETA has not approved, endorsed, or tested these modifications. O\*NET® is a
trademark of USDOL/ETA. Citation: `onet2025database`.

**BLS Occupational Employment and Wage Statistics, May 2023–2025, and the 2010-to-2018 SOC
crosswalk** (`oews_*`, `bls_soc_2010_2018`). Source: <https://www.bls.gov/oes/> and
<https://www.bls.gov/soc/2018/crosswalks.htm>. The BLS copyright page
(<https://www.bls.gov/opub/copyright-information.htm>) states that "everything that we
publish, both in hard copy and electronically, is in the public domain" (except previously
copyrighted photographs and illustrations), and asks "that you cite the Bureau of Labor
Statistics as the source." Citations: `bls2025oews`, `bls2018soccrosswalk`.

**Kenneth R. French Data Library** (`ff*`, `mom_*`: factors, momentum, industry portfolios and
SIC definitions). Source:
<https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html>. The page carries
the notice "Copyright Eugene F. Fama and Kenneth R. French" and states no licence or terms of
use; see the source's terms at that URL. Citation: `french2026datalibrary`.

**SEC EDGAR** (`sec_*`: full-text search records, quarterly `form.idx` files, the submissions
bulk file, the ticker file, the XBRL public-float frame and 10-K primary documents). Source:
<https://www.sec.gov/edgar/search/>. The SEC's website policy (<https://www.sec.gov/privacy>,
"Website Dissemination") states: "Information presented on sec.gov is considered public
information and may be copied or further distributed by users of the web site without the SEC's
permission", and asks users to "consider appropriate citation to the SEC as the source."
Citation: `sec2026edgar`.

**U.S. Census Bureau NAICS concordances and the 2023 cartographic state boundaries**
(`census_*`). Source: <https://www.census.gov/naics/concordances/> and
<https://www2.census.gov/geo/tiger/GENZ2023/shp/>. The pages checked state no licence; the
Census citation policy asks users to "cite the Census Bureau as the source of the original data
only"; see the source's terms at <https://www.census.gov/about/policies/citation.html>.
Citation: `census2022concordances`.

**AI Occupational Exposure (AIOE)** (`aioe`). Source: <https://github.com/AIOE-Data/AIOE>. The
repository states no licence; see the source's terms at that URL. It asks: "If you use any of
the AIOE data, please include the following citation" (Felten, Raj and Seamans 2021).
Citations: `felten2021occupational`, `aioe2021data`.

**Eloundou et al., "GPTs are GPTs", occupation-level data** (`eloundou_occ`). Source:
<https://github.com/openai/GPTs-are-GPTs>. The repository's `LICENSE` file is the MIT License
("Copyright (c) 2024 OpenAI"). Citations: `eloundou2024gpts`, `openai2023gptsdata`.

**Natural Earth 1:50m admin-0 countries** (`ne_admin0_50m`). Source:
<https://www.naturalearthdata.com/>. Its terms of use
(<https://www.naturalearthdata.com/about/terms-of-use/>) state: "All versions of Natural Earth
raster + vector map data found on this website are in the public domain."

## Dataset list

<!-- BEGIN GENERATED: datasets -->
Generated from `data/raw/MANIFEST.json`, as in the data appendix: one row per raw file, with the two bulk sets collapsed to one row each. No raw file is provided in the repository; every one is downloaded by `make data` or restored from the frozen archive, and checked against its SHA-256.

| key | URL | retrieved (UTC) | bytes | SHA-256 (first 16) | status |
|----|----------|----|---|----|----|
| `aei_geo_gdp_country` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2025_09_15/data/intermediate/gdp_2024_country.csv> | 2026-10-21T21:13:17Z | 4115 | e0618d6ba634a612 | frozen at `pap-v1` |
| `aei_geo_gdp_us_state` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2025_09_15/data/intermediate/gdp_2024_us_state.csv> | 2026-10-21T21:13:18Z | 2179 | cb1573e8143bd407 | frozen at `pap-v1` |
| `aei_geo_iso` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2025_09_15/data/intermediate/iso_country_codes.csv> | 2026-10-21T21:13:18Z | 4564 | eee318d4ab2c2c30 | frozen at `pap-v1` |
| `aei_geo_wap_country` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2025_09_15/data/intermediate/working_age_pop_2024_country.csv> | 2026-10-21T21:13:17Z | 6321 | 3a9e0edc0453702e | frozen at `pap-v1` |
| `aei_geo_wap_us_state` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2025_09_15/data/intermediate/working_age_pop_2024_us_state.csv> | 2026-10-21T21:13:17Z | 1079 | e2d0fb7239934f4f | frozen at `pap-v1` |
| `aei_job_exposure` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/labor_market_impacts/job_exposure.csv> | 2026-10-21T21:13:16Z | 37176 | 4f0a3adf5feeb2ec | frozen at `pap-v1` |
| `aei_onet_tasks` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2025_03_27/onet_task_statements.csv> | 2026-10-21T21:12:42Z | 3592256 | 82e4c418dc08475e | frozen at `pap-v1` |
| `aei_r1_collab` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2025_02_10/automation_vs_augmentation.csv> | 2026-10-21T21:12:41Z | 197 | d1e264882b17618d | frozen at `pap-v1` |
| `aei_r1_task_pct` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2025_02_10/onet_task_mappings.csv> | 2026-10-21T21:12:41Z | 461306 | 8de89c99f762146c | frozen at `pap-v1` |
| `aei_r1_wage` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2025_02_10/wage_data.csv> | 2026-10-21T21:12:41Z | 128047 | 4453fc56402c9430 | frozen at `pap-v1` |
| `aei_r2_collab_by_task` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2025_03_27/automation_vs_augmentation_by_task.csv> | 2026-10-21T21:12:42Z | 561368 | f6570714a9af31ae | frozen at `pap-v1` |
| `aei_r2_task_pct` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2025_03_27/task_pct_v2.csv> | 2026-10-21T21:12:42Z | 435372 | 0c20f184cd4a1e3d | frozen at `pap-v1` |
| `aei_r2_thinking` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2025_03_27/task_thinking_fractions.csv> | 2026-10-21T21:12:42Z | 372332 | 35a78bc803b610e4 | frozen at `pap-v1` |
| `aei_r3_api` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2025_09_15/data/intermediate/aei_raw_1p_api_2025-08-04_to_2025-08-11.csv> | 2026-10-21T21:12:44Z | 7027019 | c0fc061ea7d4feb7 | frozen at `pap-v1` |
| `aei_r3_claude_ai` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2025_09_15/data/intermediate/aei_raw_claude_ai_2025-08-04_to_2025-08-11.csv> | 2026-10-21T21:12:43Z | 18894517 | c8ef9c5eee0c42fe | frozen at `pap-v1` |
| `aei_r3_docs` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2025_09_15/data_documentation.md> | 2026-10-21T21:12:44Z | 20133 | d7e23aa0888628fd | frozen at `pap-v1` |
| `aei_r4_api` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2026_01_15/data/intermediate/aei_raw_1p_api_2025-11-13_to_2025-11-20.csv> | 2026-10-21T21:12:52Z | 41518256 | 432f8d14348ba384 | frozen at `pap-v1` |
| `aei_r4_claude_ai` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2026_01_15/data/intermediate/aei_raw_claude_ai_2025-11-13_to_2025-11-20.csv> | 2026-10-21T21:12:49Z | 94086309 | 70dc16780061b84d | frozen at `pap-v1` |
| `aei_r4_docs` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2026_01_15/data_documentation.md> | 2026-10-21T21:12:52Z | 18721 | 50f117f8f9956060 | frozen at `pap-v1` |
| `aei_r5_api` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2026_03_24/data/aei_raw_1p_api_2026-02-05_to_2026-02-12.csv> | 2026-10-21T21:13:00Z | 43957174 | b3bcd68e7f6d820f | frozen at `pap-v1` |
| `aei_r5_claude_ai` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2026_03_24/data/aei_raw_claude_ai_2026-02-05_to_2026-02-12.csv> | 2026-10-21T21:12:58Z | 103287181 | 69ebf6f9afc1e3be | frozen at `pap-v1` |
| `aei_r5_docs` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2026_03_24/data_documentation.md> | 2026-10-21T21:13:01Z | 17739 | 0a194ff1e317567e | frozen at `pap-v1` |
| `aei_r6_api` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2026_06_26/data/aei_1p_api_2026-06-26.csv> | 2026-10-21T21:13:16Z | 77282477 | 62197f003e001945 | frozen at `pap-v1` |
| `aei_r6_claude_ai` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2026_06_26/data/aei_claude_ai_2026-06-26.csv> | 2026-10-21T21:13:12Z | 219174671 | f974b358bce0e5a8 | frozen at `pap-v1` |
| `aei_r6_docs` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2026_06_26/data_documentation.md> | 2026-10-21T21:13:16Z | 7397 | 1a01eeb7d34250b1 | frozen at `pap-v1` |
| `aei_soc_structure` | <https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2025_02_10/SOC_Structure.csv> | 2026-10-21T21:12:41Z | 77176 | 05eb5e689fb471b7 | frozen at `pap-v1` |
| `aioe` | <https://raw.githubusercontent.com/AIOE-Data/AIOE/main/AIOE_DataAppendix.xlsx> | 2026-10-21T21:13:24Z | 170359 | c123b4c64840aff3 | frozen at `pap-v1` |
| `bls_soc_2010_2018` | <https://www.bls.gov/soc/2018/soc_2010_to_2018_crosswalk.xlsx> | 2026-10-23T15:27:35Z | 46630 | f3a847561562d3e5 | added under D20 (A-36) |
| `census_naics02_07` | <https://www.census.gov/naics/concordances/2002_to_2007_NAICS.xls> | 2026-10-21T21:13:24Z | 161280 | a4b00b2195e31842 | frozen at `pap-v1` |
| `census_naics07_12` | <https://www.census.gov/naics/concordances/2007_to_2012_NAICS.xls> | 2026-10-21T21:13:25Z | 171520 | 302b8abcd78881f1 | frozen at `pap-v1` |
| `census_naics12_17` | <https://www.census.gov/naics/concordances/2012_to_2017_NAICS.xlsx> | 2026-10-21T21:13:25Z | 58543 | 17f463f7e8385df1 | frozen at `pap-v1` |
| `census_naics17_22` | <https://www.census.gov/naics/concordances/2017_to_2022_NAICS.xlsx> | 2026-10-21T21:13:25Z | 59656 | 4662cc7ed9e7f3fb | frozen at `pap-v1` |
| `census_naics97_02` | <https://www.census.gov/naics/concordances/1997_NAICS_to_2002_NAICS.xls> | 2026-10-21T21:13:24Z | 1282560 | c9940c1236a03302 | frozen at `pap-v1` |
| `census_sic87_naics97` | <https://www.census.gov/naics/concordances/1987_SIC_to_1997_NAICS.xls> | 2026-10-21T21:13:24Z | 367616 | ba04e2332bbe5d56 | frozen at `pap-v1` |
| `census_states_20m` | <https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_state_20m.zip> | 2026-10-22T14:41:41Z | 186432 | 0fd2d6562708ff81 | added under D20 (A-2) |
| `eloundou_occ` | <https://raw.githubusercontent.com/openai/GPTs-are-GPTs/main/data/occ_level.csv> | 2026-10-21T21:13:24Z | 126022 | 40c74f53de40aec9 | frozen at `pap-v1` |
| `ff30_daily` | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/30_Industry_Portfolios_daily_CSV.zip> | 2026-10-23T15:27:44Z | 2597362 | 04a7a74fcd7c12e9 | added under D20 (A-42) |
| `ff3_monthly` | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip> | 2026-10-22T21:55:15Z | 13065 | 593f4fbef03181bc | added under D20 (A-3) |
| `ff48_daily` | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/48_Industry_Portfolios_daily_CSV.zip> | 2026-10-23T15:27:45Z | 4098912 | 95b65f678bfe12be | added under D20 (A-43) |
| `ff49_daily` | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/49_Industry_Portfolios_daily_CSV.zip> | 2026-10-21T21:13:23Z | 4173817 | 8f394fe34bea54d4 | frozen at `pap-v1` |
| `ff49_monthly` | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/49_Industry_Portfolios_CSV.zip> | 2026-10-21T21:13:23Z | 489433 | 16b3f20bf5bd1db8 | frozen at `pap-v1` |
| `ff5_daily` | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip> | 2026-10-21T21:13:23Z | 150292 | 7881223b51929ee0 | frozen at `pap-v1` |
| `ff5_monthly` | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip> | 2026-10-21T21:13:23Z | 11964 | 36756c5c25596485 | frozen at `pap-v1` |
| `ff_siccodes30` | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Siccodes30.zip> | 2026-10-23T15:27:45Z | 9244 | eddab10956ef97c8 | added under D20 (A-44) |
| `ff_siccodes48` | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Siccodes48.zip> | 2026-10-23T15:27:45Z | 9551 | f37edffc024fe7b9 | added under D20 (A-45) |
| `ff_siccodes49` | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Siccodes49.zip> | 2026-10-21T21:13:24Z | 9587 | 36761b4009107e11 | frozen at `pap-v1` |
| `mom_daily` | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip> | 2026-10-21T21:13:23Z | 85269 | ecf82b116e6ec56d | frozen at `pap-v1` |
| `mom_monthly` | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_CSV.zip> | 2026-10-21T21:13:24Z | 5600 | c06d1c2e9a5e4f69 | frozen at `pap-v1` |
| `ne_admin0_50m` | <https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip> | 2026-10-22T14:41:41Z | 799734 | 5fed433373581fa6 | added under D20 (A-1) |
| `oews_2023_ind` | <https://www.bls.gov/oes/special-requests/oesm23in4.zip> | 2026-10-23T15:27:44Z | 31801148 | 2da9b5426eba1a3a | added under D20 (A-40) |
| `oews_2023_nat` | <https://www.bls.gov/oes/special-requests/oesm23nat.zip> | 2026-10-23T15:27:43Z | 271583 | 8ce5e8277c3ba68a | added under D20 (A-39) |
| `oews_2024_ind` | <https://www.bls.gov/oes/special-requests/oesm24in4.zip> | 2026-10-21T21:13:20Z | 32425931 | 0d76287e92de226c | frozen at `pap-v1` |
| `oews_2024_nat` | <https://www.bls.gov/oes/special-requests/oesm24nat.zip> | 2026-10-21T21:13:18Z | 282052 | 5fa368aa034ca784 | frozen at `pap-v1` |
| `oews_2025_ind` | <https://www.bls.gov/oes/special-requests/oesm25in4.zip> | 2026-10-21T21:13:22Z | 31514940 | 3ef0e42fab1b42a7 | frozen at `pap-v1` |
| `oews_2025_nat` | <https://www.bls.gov/oes/special-requests/oesm25nat.zip> | 2026-10-23T15:27:43Z | 279525 | b5855a37f3e03e77 | added under D20 (A-38) |
| `onet_2010_2019_crosswalk` | <https://www.onetcenter.org/taxonomy/2019/walk/2010_to_2019_Crosswalk.csv?fmt=csv> | 2026-10-21T21:54:31Z | 108052 | 8f026a33134bfde5 | frozen at `pap-v1` |
| `onet_29_2_tasks` | <https://www.onetcenter.org/dl_files/database/db_29_2_text/Task%20Statements.txt> | 2026-10-23T15:27:43Z | 2759559 | fecdcda81a4b8a28 | added under D20 (A-41) |
| `onet_29_3_dwa_reference` | <https://www.onetcenter.org/dl_files/database/db_29_3_text/DWA%20Reference.txt> | 2026-10-22T02:15:59Z | 187200 | e38a5b529a06d680 | frozen at `pap-v1` |
| `onet_29_3_tasks` | <https://www.onetcenter.org/dl_files/database/db_29_3_text/Task%20Statements.txt> | 2026-10-21T21:54:30Z | 2759559 | fecdcda81a4b8a28 | frozen at `pap-v1` |
| `onet_29_3_tasks_to_dwas` | <https://www.onetcenter.org/dl_files/database/db_29_3_text/Tasks%20to%20DWAs.txt> | 2026-10-22T02:15:59Z | 1197935 | 6cb7098b09a6a03c | frozen at `pap-v1` |
| `onet_29_3_work_context` | <https://www.onetcenter.org/dl_files/database/db_29_3_text/Work%20Context.txt> | 2026-10-23T15:27:42Z | 35975227 | dbe428983db68eef | added under D20 (A-37) |
| `sec_docs_index` | SEC EDGAR 10-K primary documents, 47946 documents (<https://www.sec.gov/Archives/edgar/data/>) | 2026-10-23T09:58:41Z | 16077303 | c416d6bcba7e41cf | added under D20 (A-34, A-35) |
| `sec_formidx_2019q1` | <https://www.sec.gov/Archives/edgar/full-index/2019/QTR1/form.idx> | 2026-10-23T01:14:27Z | 46348993 | 88901ad5ec510ebf | added under D20 (A-4) |
| `sec_formidx_2019q2` | <https://www.sec.gov/Archives/edgar/full-index/2019/QTR2/form.idx> | 2026-10-23T01:14:28Z | 38937900 | 64a108ce2f798cbf | added under D20 (A-5) |
| `sec_formidx_2019q3` | <https://www.sec.gov/Archives/edgar/full-index/2019/QTR3/form.idx> | 2026-10-23T01:14:29Z | 30960533 | 2a2b2ac46d85e10b | added under D20 (A-6) |
| `sec_formidx_2019q4` | <https://www.sec.gov/Archives/edgar/full-index/2019/QTR4/form.idx> | 2026-10-23T01:14:29Z | 32230060 | a8e6d873ff24cd31 | added under D20 (A-7) |
| `sec_formidx_2020q1` | <https://www.sec.gov/Archives/edgar/full-index/2020/QTR1/form.idx> | 2026-10-23T01:14:30Z | 50685481 | 593cbf371d422fe5 | added under D20 (A-8) |
| `sec_formidx_2020q2` | <https://www.sec.gov/Archives/edgar/full-index/2020/QTR2/form.idx> | 2026-10-23T01:14:31Z | 41419860 | 038d6eb07e7fca5b | added under D20 (A-9) |
| `sec_formidx_2020q3` | <https://www.sec.gov/Archives/edgar/full-index/2020/QTR3/form.idx> | 2026-10-23T01:14:32Z | 34590653 | d378841b0abbe2d2 | added under D20 (A-10) |
| `sec_formidx_2020q4` | <https://www.sec.gov/Archives/edgar/full-index/2020/QTR4/form.idx> | 2026-10-23T01:14:33Z | 36414292 | 84aa7452907f2415 | added under D20 (A-11) |
| `sec_formidx_2021q1` | <https://www.sec.gov/Archives/edgar/full-index/2021/QTR1/form.idx> | 2026-10-23T01:14:34Z | 56365441 | 78b6719feb4d8da2 | added under D20 (A-12) |
| `sec_formidx_2021q2` | <https://www.sec.gov/Archives/edgar/full-index/2021/QTR2/form.idx> | 2026-10-23T01:14:36Z | 46825572 | 9bddf421721ec657 | added under D20 (A-13) |
| `sec_formidx_2021q3` | <https://www.sec.gov/Archives/edgar/full-index/2021/QTR3/form.idx> | 2026-10-23T01:14:37Z | 39349433 | 8c8ef9f8be2acdc3 | added under D20 (A-14) |
| `sec_formidx_2021q4` | <https://www.sec.gov/Archives/edgar/full-index/2021/QTR4/form.idx> | 2026-10-23T01:14:38Z | 40299160 | 025be2086f7e0118 | added under D20 (A-15) |
| `sec_formidx_2022q1` | <https://www.sec.gov/Archives/edgar/full-index/2022/QTR1/form.idx> | 2026-10-23T01:14:39Z | 55621633 | 3fa246248e37398a | added under D20 (A-16) |
| `sec_formidx_2022q2` | <https://www.sec.gov/Archives/edgar/full-index/2022/QTR2/form.idx> | 2026-10-23T01:14:39Z | 45498636 | 6b72ce7a562225bc | added under D20 (A-17) |
| `sec_formidx_2022q3` | <https://www.sec.gov/Archives/edgar/full-index/2022/QTR3/form.idx> | 2026-10-23T01:14:40Z | 37094765 | bce3e54373776e80 | added under D20 (A-18) |
| `sec_formidx_2022q4` | <https://www.sec.gov/Archives/edgar/full-index/2022/QTR4/form.idx> | 2026-10-23T01:14:41Z | 35987632 | e4fa292fcd6e15eb | added under D20 (A-19) |
| `sec_formidx_2023q1` | <https://www.sec.gov/Archives/edgar/full-index/2023/QTR1/form.idx> | 2026-10-23T01:14:43Z | 54362089 | 0f11bf75dd8c43d6 | added under D20 (A-20) |
| `sec_formidx_2023q2` | <https://www.sec.gov/Archives/edgar/full-index/2023/QTR2/form.idx> | 2026-10-23T01:14:44Z | 48017880 | de6bea77f33fd87c | added under D20 (A-21) |
| `sec_formidx_2023q3` | <https://www.sec.gov/Archives/edgar/full-index/2023/QTR3/form.idx> | 2026-10-23T01:14:45Z | 39411989 | 58e7d1100b2f7f6b | added under D20 (A-22) |
| `sec_formidx_2023q4` | <https://www.sec.gov/Archives/edgar/full-index/2023/QTR4/form.idx> | 2026-10-23T01:14:46Z | 39211372 | a6fde59991513226 | added under D20 (A-23) |
| `sec_formidx_2024q1` | <https://www.sec.gov/Archives/edgar/full-index/2024/QTR1/form.idx> | 2026-10-23T01:14:47Z | 57770533 | 5f91755d27d18df0 | added under D20 (A-24) |
| `sec_formidx_2024q2` | <https://www.sec.gov/Archives/edgar/full-index/2024/QTR2/form.idx> | 2026-10-23T01:14:48Z | 49302228 | a213f3926c23261d | added under D20 (A-25) |
| `sec_formidx_2024q3` | <https://www.sec.gov/Archives/edgar/full-index/2024/QTR3/form.idx> | 2026-10-23T01:14:49Z | 42269441 | 2c6e48b5c6a26450 | added under D20 (A-26) |
| `sec_formidx_2024q4` | <https://www.sec.gov/Archives/edgar/full-index/2024/QTR4/form.idx> | 2026-10-23T01:14:50Z | 44336440 | a94001eef171b013 | added under D20 (A-27) |
| `sec_formidx_2025q1` | <https://www.sec.gov/Archives/edgar/full-index/2025/QTR1/form.idx> | 2026-10-23T01:14:52Z | 53059957 | becca6a54875c22d | added under D20 (A-28) |
| `sec_formidx_2025q2` | <https://www.sec.gov/Archives/edgar/full-index/2025/QTR2/form.idx> | 2026-10-23T01:14:53Z | 51759696 | 78a2722d7d483bfe | added under D20 (A-29) |
| `sec_formidx_2025q3` | <https://www.sec.gov/Archives/edgar/full-index/2025/QTR3/form.idx> | 2026-10-23T01:14:54Z | 44912705 | 924d6992695d0337 | added under D20 (A-30) |
| `sec_formidx_2025q4` | <https://www.sec.gov/Archives/edgar/full-index/2025/QTR4/form.idx> | 2026-10-23T01:14:54Z | 43155988 | 8555ad43d2a491e1 | added under D20 (A-31) |
| `sec_fts/` | EDGAR full-text search, 307 records (<https://efts.sec.gov/LATEST/search-index>) | 2026-10-23T01:35:03Z to 2026-10-23T23:36:05Z | 13738487 | set digest ac5a3a2966e29a47 | added under D20 (A-33, A-47) |
| `sec_public_float_cy2024q2` | <https://data.sec.gov/api/xbrl/frames/dei/EntityPublicFloat/USD/CY2024Q2I.json> | 2026-10-23T15:27:45Z | 578973 | d5ef310add8635a1 | added under D20 (A-46) |
| `sec_submissions_bulk` | <https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip> | 2026-10-23T01:19:58Z | 1570500398 | b6534bf3efaca6ea | added under D20 (A-32) |
| `sec_tickers` | <https://www.sec.gov/files/company_tickers_exchange.json> | 2026-10-21T21:13:25Z | 523851 | 6c29e2e3db973d44 | frozen at `pap-v1` |

- `sec_docs_index`: 47946 documents; SHA-256 of `sec/docs/INDEX.jsonl` `c416d6bcba7e41cf92d042d2ec5b09cea75ecd8bae5861f201044953ce3b5fed`.
- `sec_fts/`: 307 records; set digest (`paplog.set_digest`, SHA-256 of the sorted `<key> <sha256>` lines) `ac5a3a2966e29a4713af1cf83a4f497b7f702dd0dc1f18b69fb60370de501f12`.
<!-- END GENERATED: datasets -->

Derived files (`data/derived/*.parquet`) are not committed; `make all` rebuilds them from
`data/raw`.

## Computational requirements

### Software Requirements

- Python 3.12, with every package pinned by `uv.lock` and installed by `uv sync --frozen`
  ([uv](https://docs.astral.sh/uv/)). The direct dependencies at their locked versions:

<!-- BEGIN GENERATED: environment -->
Python 3.12 (`.python-version`; `uv.lock` requires-python `>=3.12`), with every direct dependency at its `uv.lock` version:

| package | version | group |
|---|---|---|
| `duckdb` | 2.0.0 | runtime |
| `geopandas` | 1.2.0 | runtime |
| `matplotlib` | 3.11.2 | runtime |
| `numpy` | 2.5.4 | runtime |
| `openpyxl` | 3.1.5 | runtime |
| `pandas` | 3.0.6 | runtime |
| `polars` | 2.0.0 | runtime |
| `pyarrow` | 26.0.0 | runtime |
| `requests` | 2.34.2 | runtime |
| `scipy` | 1.18.1 | runtime |
| `statsmodels` | 0.15.0 | runtime |
| `xlrd` | 2.0.2 | runtime |
| `pypdf` | 6.21.2 | dev |
| `pytest` | 9.1.1 | dev |
| `ruff` | 0.17.1 | dev |
<!-- END GENERATED: environment -->

- [Quarto](https://quarto.org/) for the paper and the brief (checked with Quarto 1.9.38).
- XeLaTeX for the PDF output (checked with TeX Live 2025).
- GNU Make (checked with GNU Make 3.81) and git (see Instructions to Replicators for why a clone
  is preferred).

### Controlled Randomness

<!-- BEGIN GENERATED: seed -->
`aideleg.config.SEED` = 20261021. Every random draw comes from `numpy.random.default_rng(SEED)`.
<!-- END GENERATED: seed -->

The seed is set in `src/aideleg/config.py`. Draws are consumed in these places, each from its own
`default_rng(SEED)` in a fixed order:

- `aideleg.confirm_h5`: the H5/H5b permutations (single run; its committed record is an input);
- `aideleg.power`: the pre-seal power analysis (frozen at `pap-v1`; it refuses to rerun);
- `aideleg.describe.rq2.bootstrap_indices`: the RQ2 industry-resample bootstrap, one matrix per
  design in order;
- `aideleg.rq3.terciles`: the block bootstrap, one draw set per variant in `VARIANTS` order;
- `aideleg.h6.talk`: the Spearman bootstrap of the H6 gap;
- `aideleg.robustness` (the rows and the PAP §11 D-3 diagnostics): through the same functions,
  with the same seed.

### Memory, Runtime, Storage Requirements

<!-- BEGIN GENERATED: storage -->
- `data/raw`, as listed in the MANIFEST: 3603241615 bytes (3.60 GB) in 400 records (zip archives are also extracted next to themselves, which adds to this).
- Largest single raw file: `sec_submissions_bulk`, 1570500398 bytes (1.57 GB).
- The 47946 10-K documents listed in `data/raw/sec/docs/INDEX.jsonl` (gzip, on disk): 9732096262 bytes (9.73 GB), in addition to the MANIFEST total.
- Runtime of `make all`: 51m 02s (3062 s) (quoted from `docs/replication/check.md`)
<!-- END GENERATED: storage -->

#### Computational Details

The code was last run on an Apple M2 Pro (12 cores, 16 GB memory) under macOS 26. On that
machine `data/raw`, with every zip extracted, occupied about 13 GB. No GPU is used. Network
access is needed only by `make data` (and by the confirmatory and H6 acquisition targets, which
a replicator does not run).

## Description of programs/code

All code is in the Python package `src/aideleg/`; `make` targets drive it.

- `acquire/`: downloads every raw file, writes and checks `data/raw/MANIFEST.json`
  (`make data`); `--from-dir DIR` restores the frozen archive instead.
- `aei/`: parses the six AEI releases into `data/derived/aei_panel.parquet` (`make panel`).
- `occupations.py`, `bls/`, `crosswalk/`, `exposure.py`: the O\*NET–SOC–OEWS weighting and the
  NAICS-to-FF49 crosswalk; exposure by occupation and by industry (`make exposure`).
- `benchmarks.py`: the AIOE and Eloundou benchmarks by industry (`make benchmarks`).
- `audit.py`: coverage tables in `docs/audit/tables/` (`make audit`).
- `power.py`: the pre-seal power analysis (frozen).
- `rq1/`: the H1–H4 estimators and the single logged confirmatory run (`make rq1-confirm`,
  write-once).
- `results/`, `describe/`, `figures/`: the RQ1 and RQ2 reports, tables and figures
  (`make results-rq1`, `make results-rq2`).
- `market/`: the French reader and the market seal; `confirm_h5.py`: the single confirmatory
  H5/H5b script (bound, never re-executed).
- `rq3/`: the exploratory and diagnostic market analyses and the confirmatory guard (`make rq3`).
- `h6/`: the 10-K talk index and its secondary measures (`make h6`; `make h6-data` fetches).
- `robustness/`: the PAP §8.2 robustness rows, their appendix and figures, and the protocol
  guards (`make robustness`).
- `paper/`: the paper's variables, generated includes, appendices and this README's generated
  blocks (`make paper-includes`); `paplog.py` writes PAP §11 entries.
- `scripts/`: the PAP freeze helper, the replication scripts and one-off inventories.

## Instructions to Replicators

1. **Start from a clone.** `git clone` the repository (with its full history and the tag
   `pap-v1`) and run `uv sync --frozen`. A `git clone` is the preferred starting point: the
   protocol guards read git. They check that each confirmatory file is tracked and unmodified at
   HEAD, that it matches its pinned blob, and which commit recorded it.
2. **Get the raw data.** Either run `make data` (first set `AIDELEG_CONTACT` to your name and
   email, e.g. `export AIDELEG_CONTACT="Jane Doe research <your email>"`: the SEC and BLS
   require a contact User-Agent, which is sent only to them), which downloads every file and reports any
   whose SHA-256 differs from the MANIFEST, or restore the frozen raw archive (see Archive
   deposit) with
   `uv run python -m aideleg.acquire --from-dir DIR`, which copies each file from `DIR/<dest>`,
   checks its SHA-256 (and each 10-K document against `INDEX.jsonl`) and refuses, naming it, any
   file that differs. The French files are revised retroactively, so exact replication needs
   the frozen raw archive: a fresh download of them may not match the MANIFEST.
3. **Rebuild everything.** `make all` runs offline: lint, the tests, the confirmatory check,
   every derived file, the RQ1, RQ2, RQ3, H6 and robustness outputs, the paper's includes, the
   paper and the brief. It never runs `aideleg.confirm_h5`, `make rq1-confirm`, `make h6-data`
   or any other network target.

The confirmatory H5 script (`aideleg.confirm_h5`) is single-run and is never re-executed: its
committed output, `docs/results/confirmatory_h5.md` with its `.attempt` marker, is an input to
the rebuild, as is the single logged H1–H4 run (`docs/results/rq1/confirmatory_rq1.*`).

**Without `.git`** (an unpacked archive), the H5 guard `rq3.guard.assert_confirmatory_recorded`
falls back to the bytes on disk: the git blob SHA-1 of each H5 file,
`sha1(b"blob <len>\0" + data)`, must equal the pinned blob ID, so an edited record is still
refused. `rq3.report._record_commit` then reads the record's commit from the committed
`docs/results/rq3/RECORD_COMMIT` (written by `python -m aideleg.rq3 summary`). Plan 4's own
git-based guards have no such fallback and need a clone: `robustness.guards.require_rq1_run_committed`
(used by the confirmatory check of `make all`, by every RQ1 robustness row of `make robustness`
and by `python -m aideleg.robustness --diagnostics`) and the test
`test_confirmatory_files_untouched` (run by `make test`). So `make all`, `make test`,
`make robustness` and the diagnostics need a clone. The other targets (`make panel`,
`make exposure`, `make benchmarks`, `make audit`, `make results-rq1`, `make results-rq2`,
`make rq3`, `make h6`, `make paper-includes`, `make paper`, `make brief`) also run from an
archive.

## List of tables and programs

Each table and figure of the paper (`docs/paper/tables.csv`, `docs/paper/figures.csv`), the
program that writes it, its output file and the include the paper reads. A table is copied
unchanged from its output file into its include by `make paper-includes`.

<!-- BEGIN GENERATED: tables -->
| exhibit | id | program | output file | paper include |
|----|----|----|----|----|
| table | `rq3-confirmatory` | `aideleg.confirm_h5` (single run, never re-executed; the committed record is an input) | `docs/results/confirmatory_h5.md` | `docs/paper/_generated/tables/rq3-confirmatory.md` |
| table | `diag-h1-influence` | `python -m aideleg.robustness --diagnostics` | `docs/results/diagnostics/h1_influence.md` | `docs/paper/_generated/tables/diag-h1-influence.md` |
| table | `diag-h2-influence` | `python -m aideleg.robustness --diagnostics` | `docs/results/diagnostics/h2_influence.md` | `docs/paper/_generated/tables/diag-h2-influence.md` |
| table | `diag-h6-influence` | `python -m aideleg.robustness --diagnostics` | `docs/results/diagnostics/h6_influence.md` | `docs/paper/_generated/tables/diag-h6-influence.md` |
| table | `h6-divergence` | `make h6` (`aideleg.h6 all`) | `docs/results/h6/gap.md#1` | `docs/paper/_generated/tables/h6-divergence.md` |
| table | `h6-gap-ranking` | `make h6` (`aideleg.h6 all`) | `docs/results/h6/gap.md#2` | `docs/paper/_generated/tables/h6-gap-ranking.md` |
| table | `h6-gap-returns` | `make h6` (`aideleg.h6 all`) | `docs/results/h6/gap_returns.md` | `docs/paper/_generated/tables/h6-gap-returns.md` |
| table | `h6-secondary-by-year` | `make h6` (`aideleg.h6 all`) | `docs/results/h6/secondary_talk.md#1` | `docs/paper/_generated/tables/h6-secondary-by-year.md` |
| table | `h6-secondary-coverage` | `make h6` (`aideleg.h6 all`) | `docs/results/h6/secondary_talk.md#2` | `docs/paper/_generated/tables/h6-secondary-coverage.md` |
| table | `h6-secondary-vs-index` | `make h6` (`aideleg.h6 all`) | `docs/results/h6/secondary_talk.md#3` | `docs/paper/_generated/tables/h6-secondary-vs-index.md` |
| table | `h6-secondary-agreement` | `make h6` (`aideleg.h6 all`) | `docs/results/h6/secondary_talk.md#4` | `docs/paper/_generated/tables/h6-secondary-agreement.md` |
| table | `h6-secondary-industry-year` | `make h6` (`aideleg.h6 all`) | `docs/results/h6/secondary_talk.md#5` | `docs/paper/_generated/tables/h6-secondary-industry-year.md` |
| table | `h6-talk-by-year` | `make h6` (`aideleg.h6 all`) | `docs/results/h6/talk_index.md#1` | `docs/paper/_generated/tables/h6-talk-by-year.md` |
| table | `h6-talk-industry-year` | `make h6` (`aideleg.h6 all`) | `docs/results/h6/talk_index.md#2` | `docs/paper/_generated/tables/h6-talk-industry-year.md` |
| table | `rob-summary` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/summary.md` | `docs/paper/_generated/tables/rob-summary.md` |
| table | `rq1-major` | `make results-rq1` (`aideleg.results.rq1`) | `docs/results/rq1/anatomy.md#1` | `docs/paper/_generated/tables/rq1-major.md` |
| table | `rq1-wage-decile` | `make results-rq1` (`aideleg.results.rq1`) | `docs/results/rq1/anatomy.md#2` | `docs/paper/_generated/tables/rq1-wage-decile.md` |
| table | `rq1-education` | `make results-rq1` (`aideleg.results.rq1`) | `docs/results/rq1/anatomy.md#3` | `docs/paper/_generated/tables/rq1-education.md` |
| table | `rq1-concentration` | `make results-rq1` (`aideleg.results.rq1`) | `docs/results/rq1/anatomy.md#4` | `docs/paper/_generated/tables/rq1-concentration.md` |
| table | `rq1-concentration-harmonised` | `make results-rq1` (`aideleg.results.rq1`) | `docs/results/rq1/anatomy.md#5` | `docs/paper/_generated/tables/rq1-concentration-harmonised.md` |
| table | `rq1-confirmatory` | `make rq1-confirm` (`aideleg.rq1.confirm`, write-once; the committed record is an input) | `docs/results/rq1/confirmatory_rq1.md` | `docs/paper/_generated/tables/rq1-confirmatory.md` |
| table | `rq1-confirmatory-table` | `make results-rq1` (`aideleg.results.rq1`) | `docs/results/rq1/confirmatory_table.md` | `docs/paper/_generated/tables/rq1-confirmatory-table.md` |
| table | `rq1-countries` | `make results-rq1` (`aideleg.results.rq1`) | `docs/results/rq1/geography.md#1` | `docs/paper/_generated/tables/rq1-countries.md` |
| table | `rq1-states` | `make results-rq1` (`aideleg.results.rq1`) | `docs/results/rq1/geography.md#2` | `docs/paper/_generated/tables/rq1-states.md` |
| table | `rq2-bounds-industries` | `make results-rq2` (`aideleg.results.rq2`) | `docs/results/rq2/bounds.md#1` | `docs/paper/_generated/tables/rq2-bounds-industries.md` |
| table | `rq2-bounds-occupations` | `make results-rq2` (`aideleg.results.rq2`) | `docs/results/rq2/bounds.md#2` | `docs/paper/_generated/tables/rq2-bounds-occupations.md` |
| table | `rq2-could-vs-does-b` | `make results-rq2` (`aideleg.results.rq2`) | `docs/results/rq2/could_vs_does.md#1` | `docs/paper/_generated/tables/rq2-could-vs-does-b.md` |
| table | `rq2-could-vs-does-a-pooled` | `make results-rq2` (`aideleg.results.rq2`) | `docs/results/rq2/could_vs_does.md#2` | `docs/paper/_generated/tables/rq2-could-vs-does-a-pooled.md` |
| table | `rq2-rank-gaps-eloundou` | `make results-rq2` (`aideleg.results.rq2`) | `docs/results/rq2/rank_gaps.md#1` | `docs/paper/_generated/tables/rq2-rank-gaps-eloundou.md` |
| table | `rq2-rank-gaps-eloundou-gpt4` | `make results-rq2` (`aideleg.results.rq2`) | `docs/results/rq2/rank_gaps.md#2` | `docs/paper/_generated/tables/rq2-rank-gaps-eloundou-gpt4.md` |
| table | `rq2-rank-gaps-aioe` | `make results-rq2` (`aideleg.results.rq2`) | `docs/results/rq2/rank_gaps.md#3` | `docs/paper/_generated/tables/rq2-rank-gaps-aioe.md` |
| table | `rq2-top-bottom-usage` | `make results-rq2` (`aideleg.results.rq2`) | `docs/results/rq2/top_bottom.md#1` | `docs/paper/_generated/tables/rq2-top-bottom-usage.md` |
| table | `rq2-top-bottom-delegation` | `make results-rq2` (`aideleg.results.rq2`) | `docs/results/rq2/top_bottom.md#2` | `docs/paper/_generated/tables/rq2-top-bottom-delegation.md` |
| table | `rq2-top-bottom-augmentation` | `make results-rq2` (`aideleg.results.rq2`) | `docs/results/rq2/top_bottom.md#3` | `docs/paper/_generated/tables/rq2-top-bottom-augmentation.md` |
| table | `rq3-eisfeldt-step1` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/eisfeldt_replication.md#1` | `docs/paper/_generated/tables/rq3-eisfeldt-step1.md` |
| table | `rq3-eisfeldt-step2` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/eisfeldt_replication.md#2` | `docs/paper/_generated/tables/rq3-eisfeldt-step2.md` |
| table | `rq3-event-dates` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/event_study.md#1` | `docs/paper/_generated/tables/rq3-event-dates.md` |
| table | `rq3-event-days` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/event_study.md#2` | `docs/paper/_generated/tables/rq3-event-days.md` |
| table | `rq3-event-slopes` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/event_study.md#3` | `docs/paper/_generated/tables/rq3-event-slopes.md` |
| table | `rq3-fama-macbeth-b` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/fama_macbeth.md#1` | `docs/paper/_generated/tables/rq3-fama-macbeth-b.md` |
| table | `rq3-fama-macbeth-a-r2` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/fama_macbeth.md#2` | `docs/paper/_generated/tables/rq3-fama-macbeth-a-r2.md` |
| table | `rq3-fama-macbeth-a-pooled` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/fama_macbeth.md#3` | `docs/paper/_generated/tables/rq3-fama-macbeth-a-pooled.md` |
| table | `rq3-influence-softw` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/influence.md#1` | `docs/paper/_generated/tables/rq3-influence-softw.md` |
| table | `rq3-influence-top` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/influence.md#2` | `docs/paper/_generated/tables/rq3-influence-top.md` |
| table | `rq3-terciles-b-cap` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/terciles.md#1` | `docs/paper/_generated/tables/rq3-terciles-b-cap.md` |
| table | `rq3-terciles-b-cap-costs` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/terciles.md#2` | `docs/paper/_generated/tables/rq3-terciles-b-cap-costs.md` |
| table | `rq3-terciles-b-ew` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/terciles.md#3` | `docs/paper/_generated/tables/rq3-terciles-b-ew.md` |
| table | `rq3-terciles-b-ew-costs` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/terciles.md#4` | `docs/paper/_generated/tables/rq3-terciles-b-ew-costs.md` |
| table | `rq3-terciles-a-r2-cap` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/terciles.md#5` | `docs/paper/_generated/tables/rq3-terciles-a-r2-cap.md` |
| table | `rq3-terciles-a-r2-cap-costs` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/terciles.md#6` | `docs/paper/_generated/tables/rq3-terciles-a-r2-cap-costs.md` |
| table | `rq3-terciles-a-r2-ew` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/terciles.md#7` | `docs/paper/_generated/tables/rq3-terciles-a-r2-ew.md` |
| table | `rq3-terciles-a-r2-ew-costs` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/terciles.md#8` | `docs/paper/_generated/tables/rq3-terciles-a-r2-ew-costs.md` |
| table | `rq3-terciles-a-pooled-cap` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/terciles.md#9` | `docs/paper/_generated/tables/rq3-terciles-a-pooled-cap.md` |
| table | `rq3-terciles-a-pooled-cap-costs` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/terciles.md#10` | `docs/paper/_generated/tables/rq3-terciles-a-pooled-cap-costs.md` |
| table | `rq3-terciles-a-pooled-ew` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/terciles.md#11` | `docs/paper/_generated/tables/rq3-terciles-a-pooled-ew.md` |
| table | `rq3-terciles-a-pooled-ew-costs` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/terciles.md#12` | `docs/paper/_generated/tables/rq3-terciles-a-pooled-ew-costs.md` |
| table | `rq3-terciles-dsr` | `make rq3` (`aideleg.rq3 all`) | `docs/results/rq3/terciles.md#13` | `docs/paper/_generated/tables/rq3-terciles-dsr.md` |
| table | `rob-r01` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R01.md` | `docs/paper/_generated/tables/rob-r01.md` |
| table | `rob-r02` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R02.md` | `docs/paper/_generated/tables/rob-r02.md` |
| table | `rob-r03` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R03.md` | `docs/paper/_generated/tables/rob-r03.md` |
| table | `rob-r04` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R04.md` | `docs/paper/_generated/tables/rob-r04.md` |
| table | `rob-r05` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R05.md` | `docs/paper/_generated/tables/rob-r05.md` |
| table | `rob-r06` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R06.md` | `docs/paper/_generated/tables/rob-r06.md` |
| table | `rob-r07` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R07.md` | `docs/paper/_generated/tables/rob-r07.md` |
| table | `rob-r08` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R08.md` | `docs/paper/_generated/tables/rob-r08.md` |
| table | `rob-r09` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R09.md` | `docs/paper/_generated/tables/rob-r09.md` |
| table | `rob-r10` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R10.md` | `docs/paper/_generated/tables/rob-r10.md` |
| table | `rob-r11` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R11.md` | `docs/paper/_generated/tables/rob-r11.md` |
| table | `rob-r14` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R14.md` | `docs/paper/_generated/tables/rob-r14.md` |
| table | `rob-r15` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R15.md` | `docs/paper/_generated/tables/rob-r15.md` |
| table | `rob-r16` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R16.md` | `docs/paper/_generated/tables/rob-r16.md` |
| table | `rob-r17` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R17.md` | `docs/paper/_generated/tables/rob-r17.md` |
| table | `rob-r18` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R18.md` | `docs/paper/_generated/tables/rob-r18.md` |
| table | `rob-r19` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R19.md` | `docs/paper/_generated/tables/rob-r19.md` |
| table | `rob-r20` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R20.md` | `docs/paper/_generated/tables/rob-r20.md` |
| table | `rob-r21` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R21.md` | `docs/paper/_generated/tables/rob-r21.md` |
| table | `rob-r22` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R22.md` | `docs/paper/_generated/tables/rob-r22.md` |
| table | `rob-r23` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R23.md` | `docs/paper/_generated/tables/rob-r23.md` |
| table | `rob-r24` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R24.md` | `docs/paper/_generated/tables/rob-r24.md` |
| table | `rob-r25` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R25.md` | `docs/paper/_generated/tables/rob-r25.md` |
| table | `rob-r26` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R26.md` | `docs/paper/_generated/tables/rob-r26.md` |
| table | `rob-r27` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R27.md` | `docs/paper/_generated/tables/rob-r27.md` |
| table | `rob-r28` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R28.md` | `docs/paper/_generated/tables/rob-r28.md` |
| table | `rob-r29` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R29.md` | `docs/paper/_generated/tables/rob-r29.md` |
| table | `rob-r30` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R30.md` | `docs/paper/_generated/tables/rob-r30.md` |
| table | `rob-r31` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R31.md` | `docs/paper/_generated/tables/rob-r31.md` |
| table | `rob-r32` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R32.md` | `docs/paper/_generated/tables/rob-r32.md` |
| table | `rob-r33` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R33.md` | `docs/paper/_generated/tables/rob-r33.md` |
| table | `rob-r34` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R34.md` | `docs/paper/_generated/tables/rob-r34.md` |
| table | `rob-r35` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R35.md` | `docs/paper/_generated/tables/rob-r35.md` |
| table | `rob-r36` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R36.md` | `docs/paper/_generated/tables/rob-r36.md` |
| table | `rob-r37` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R37.md` | `docs/paper/_generated/tables/rob-r37.md` |
| table | `rob-r38` | `make robustness` (`aideleg.robustness`) | `docs/results/robustness/R38.md` | `docs/paper/_generated/tables/rob-r38.md` |
| table | `releases` | `make audit` (`aideleg.audit`) | `docs/audit/tables/releases.md#1` | `docs/paper/_generated/tables/releases.md` |
| table | `regimes` | `make audit` (`aideleg.audit`) | `docs/audit/tables/releases.md#2` | `docs/paper/_generated/tables/regimes.md` |
| table | `audit-exposure-coverage` | `make audit` (`aideleg.audit`) | `docs/audit/tables/exposure_coverage.md#1` | `docs/paper/_generated/tables/audit-exposure-coverage.md` |
| figure | `h6-secondary-by-year` | `make h6` (`aideleg.h6 all`) | `docs/paper/figures/fig_h6_secondary_by_year.pdf`, `.png` | `docs/paper/_generated/figures/h6-secondary-by-year.md` |
| figure | `h6-talk-by-year` | `make h6` (`aideleg.h6 all`) | `docs/paper/figures/fig_h6_talk_by_year.pdf`, `.png` | `docs/paper/_generated/figures/h6-talk-by-year.md` |
| figure | `h6-talk-vs-usage` | `make h6` (`aideleg.h6 all`) | `docs/paper/figures/fig_h6_talk_vs_usage.pdf`, `.png` | `docs/paper/_generated/figures/h6-talk-vs-usage.md` |
| figure | `robustness-market` | `make robustness` (`aideleg.robustness --summary`) | `docs/paper/figures/fig_robustness_market.pdf`, `.png` | `docs/paper/_generated/figures/robustness-market.md` |
| figure | `robustness-rq1` | `make robustness` (`aideleg.robustness --summary`) | `docs/paper/figures/fig_robustness_rq1.pdf`, `.png` | `docs/paper/_generated/figures/robustness-rq1.md` |
| figure | `rq1-coefficients` | `make results-rq1` (`aideleg.results.rq1`) | `docs/paper/figures/fig_rq1_coefficients.pdf`, `.png` | `docs/paper/_generated/figures/rq1-coefficients.md` |
| figure | `rq1-composition-education` | `make results-rq1` (`aideleg.results.rq1`) | `docs/paper/figures/fig_rq1_composition_education.pdf`, `.png` | `docs/paper/_generated/figures/rq1-composition-education.md` |
| figure | `rq1-composition-major` | `make results-rq1` (`aideleg.results.rq1`) | `docs/paper/figures/fig_rq1_composition_major.pdf`, `.png` | `docs/paper/_generated/figures/rq1-composition-major.md` |
| figure | `rq1-composition-wage-decile` | `make results-rq1` (`aideleg.results.rq1`) | `docs/paper/figures/fig_rq1_composition_wage_decile.pdf`, `.png` | `docs/paper/_generated/figures/rq1-composition-wage-decile.md` |
| figure | `rq1-h2-release-effects` | `make results-rq1` (`aideleg.results.rq1`) | `docs/paper/figures/fig_rq1_h2_release_effects.pdf`, `.png` | `docs/paper/_generated/figures/rq1-h2-release-effects.md` |
| figure | `rq1-lorenz` | `make results-rq1` (`aideleg.results.rq1`) | `docs/paper/figures/fig_rq1_lorenz.pdf`, `.png` | `docs/paper/_generated/figures/rq1-lorenz.md` |
| figure | `rq1-map-country-aui` | `make results-rq1` (`aideleg.results.rq1`) | `docs/paper/figures/fig_rq1_map_country_aui.pdf`, `.png` | `docs/paper/_generated/figures/rq1-map-country-aui.md` |
| figure | `rq1-map-country-automation` | `make results-rq1` (`aideleg.results.rq1`) | `docs/paper/figures/fig_rq1_map_country_automation.pdf`, `.png` | `docs/paper/_generated/figures/rq1-map-country-automation.md` |
| figure | `rq1-map-country-mix` | `make results-rq1` (`aideleg.results.rq1`) | `docs/paper/figures/fig_rq1_map_country_mix.pdf`, `.png` | `docs/paper/_generated/figures/rq1-map-country-mix.md` |
| figure | `rq1-map-country-within` | `make results-rq1` (`aideleg.results.rq1`) | `docs/paper/figures/fig_rq1_map_country_within.pdf`, `.png` | `docs/paper/_generated/figures/rq1-map-country-within.md` |
| figure | `rq1-map-state-aui` | `make results-rq1` (`aideleg.results.rq1`) | `docs/paper/figures/fig_rq1_map_state_aui.pdf`, `.png` | `docs/paper/_generated/figures/rq1-map-state-aui.md` |
| figure | `rq1-map-state-automation` | `make results-rq1` (`aideleg.results.rq1`) | `docs/paper/figures/fig_rq1_map_state_automation.pdf`, `.png` | `docs/paper/_generated/figures/rq1-map-state-automation.md` |
| figure | `rq1-map-state-mix` | `make results-rq1` (`aideleg.results.rq1`) | `docs/paper/figures/fig_rq1_map_state_mix.pdf`, `.png` | `docs/paper/_generated/figures/rq1-map-state-mix.md` |
| figure | `rq1-map-state-within` | `make results-rq1` (`aideleg.results.rq1`) | `docs/paper/figures/fig_rq1_map_state_within.pdf`, `.png` | `docs/paper/_generated/figures/rq1-map-state-within.md` |
| figure | `rq2-bound-widths` | `make results-rq2` (`aideleg.results.rq2`) | `docs/paper/figures/fig_rq2_bound_widths.pdf`, `.png` | `docs/paper/_generated/figures/rq2-bound-widths.md` |
| figure | `rq2-could-vs-does` | `make results-rq2` (`aideleg.results.rq2`) | `docs/paper/figures/fig_rq2_could_vs_does.pdf`, `.png` | `docs/paper/_generated/figures/rq2-could-vs-does.md` |
| figure | `rq3-event-slopes` | `make rq3` (`aideleg.rq3 all`) | `docs/paper/figures/fig_rq3_event_slopes.pdf`, `.png` | `docs/paper/_generated/figures/rq3-event-slopes.md` |
| figure | `rq3-tercile-cumulative` | `make rq3` (`aideleg.rq3 all`) | `docs/paper/figures/fig_rq3_tercile_cumulative.pdf`, `.png` | `docs/paper/_generated/figures/rq3-tercile-cumulative.md` |
<!-- END GENERATED: tables -->

## References

The full bibliography is `docs/paper/references.bib`. The data citations, by key:

- `handa2025economic`, `appel2025uneven`, `appel2026economic`, `massenkoff2026learning`,
  `anthropic2026economicindex`: the Anthropic Economic Index releases.
- `onet2025database`: National Center for O\*NET Development, O\*NET 29.3 Database.
- `bls2025oews`, `bls2018soccrosswalk`: U.S. Bureau of Labor Statistics.
- `french2026datalibrary`: Kenneth R. French, Data Library.
- `sec2026edgar`: U.S. Securities and Exchange Commission, EDGAR.
- `census2022concordances`: U.S. Census Bureau, NAICS concordances.
- `felten2021occupational`, `aioe2021data`: Felten, Raj and Seamans, AIOE.
- `eloundou2024gpts`, `openai2023gptsdata`: Eloundou, Manning, Mishkin and Rock.
