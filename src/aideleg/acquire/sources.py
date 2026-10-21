"""The registry of every raw file the project uses.

Deliberately excluded: robot_exposure_tasks.csv (99 MB) and the task-penetration files,
which are out of scope.

O*NET vintage. The study's occupation vintage is O*NET-SOC 2019 / SOC 2018 (OEWS May 2024,
AEI r6, Felten AIOE). `onet_29_3_tasks` is O*NET 29.3 because that is the release the AEI
robot-exposure data cite; O*NET 30.0 exists and was deliberately not used. The r2-era
`aei_onet_tasks` file carries O*NET-SOC 2010 codes and is kept only for its task wordings and
legacy Task IDs, which `onet_2010_2019_crosswalk` maps to 2019 codes (see aei/tasks.py).
The crosswalk URL is the CSV download linked from
https://www.onetcenter.org/taxonomy/2019/walk.html; without `?fmt=csv` the server
returns an HTML page.
"""

from aideleg.acquire.fetch import Source

HF = "https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main"
FF = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"
BLS = "https://www.bls.gov/oes/special-requests"
CENSUS = "https://www.census.gov/naics/concordances"
ONET = "https://www.onetcenter.org"


def _aei(key: str, release: str, path: str, tree: str) -> Source:
    """An AEI file: `path` under the release folder on Hugging Face, stored in aei/<tree>/."""
    return Source(key, f"{HF}/{release}/{path}", f"aei/{tree}/{path.rsplit('/', 1)[-1]}")


def _pair(n: int, release: str, folder: str, stamp: str, ext_stub: str) -> list[Source]:
    out = []
    for key, name in (("claude_ai", "claude_ai"), ("api", "1p_api")):
        fname = ext_stub.format(name=name, stamp=stamp)
        out.append(_aei(f"aei_r{n}_{key}", release, f"{folder}{fname}", f"r{n}"))
    out.append(_aei(f"aei_r{n}_docs", release, "data_documentation.md", f"r{n}"))
    return out


def _zip(key: str, url: str, folder: str) -> Source:
    return Source(key, url, f"{folder}/{url.rsplit('/', 1)[-1]}", unzip=True)


SOURCES: list[Source] = [
    # Release 1 (2025-02-10) and the SOC structure
    _aei("aei_r1_task_pct", "release_2025_02_10", "onet_task_mappings.csv", "r1"),
    _aei("aei_r1_collab", "release_2025_02_10", "automation_vs_augmentation.csv", "r1"),
    _aei("aei_r1_wage", "release_2025_02_10", "wage_data.csv", "r1"),
    _aei("aei_soc_structure", "release_2025_02_10", "SOC_Structure.csv", "r1"),
    # Release 2 (2025-03-27)
    _aei("aei_r2_task_pct", "release_2025_03_27", "task_pct_v2.csv", "r2"),
    _aei("aei_r2_collab_by_task", "release_2025_03_27",
         "automation_vs_augmentation_by_task.csv", "r2"),
    _aei("aei_r2_thinking", "release_2025_03_27", "task_thinking_fractions.csv", "r2"),
    _aei("aei_onet_tasks", "release_2025_03_27", "onet_task_statements.csv", "r2"),
    # Releases 3 to 6: raw conversation counts, one file per surface, plus documentation
    *_pair(3, "release_2025_09_15", "data/intermediate/", "2025-08-04_to_2025-08-11",
           "aei_raw_{name}_{stamp}.csv"),
    *_pair(4, "release_2026_01_15", "data/intermediate/", "2025-11-13_to_2025-11-20",
           "aei_raw_{name}_{stamp}.csv"),
    *_pair(5, "release_2026_03_24", "data/", "2026-02-05_to_2026-02-12",
           "aei_raw_{name}_{stamp}.csv"),
    *_pair(6, "release_2026_06_26", "data/", "2026-06-26", "aei_{name}_{stamp}.csv"),
    # O*NET 29.3 task statements (O*NET-SOC 2019) and the 2010 -> 2019 taxonomy crosswalk
    Source("onet_29_3_tasks", f"{ONET}/dl_files/database/db_29_3_text/Task%20Statements.txt",
           "onet/db_29_3_task_statements.txt"),
    Source("onet_2010_2019_crosswalk",
           f"{ONET}/taxonomy/2019/walk/2010_to_2019_Crosswalk.csv?fmt=csv",
           "onet/2010_to_2019_Crosswalk.csv"),
    _aei("aei_job_exposure", "labor_market_impacts", "job_exposure.csv", "labor_market_impacts"),
    # Geography inputs (release 3 intermediates)
    *[
        _aei(key, "release_2025_09_15", f"data/intermediate/{name}", "r3")
        for key, name in (
            ("aei_geo_wap_country", "working_age_pop_2024_country.csv"),
            ("aei_geo_wap_us_state", "working_age_pop_2024_us_state.csv"),
            ("aei_geo_gdp_country", "gdp_2024_country.csv"),
            ("aei_geo_gdp_us_state", "gdp_2024_us_state.csv"),
            ("aei_geo_iso", "iso_country_codes.csv"),
        )
    ],
    # BLS OEWS
    _zip("oews_2024_nat", f"{BLS}/oesm24nat.zip", "bls"),
    _zip("oews_2024_ind", f"{BLS}/oesm24in4.zip", "bls"),
    _zip("oews_2025_ind", f"{BLS}/oesm25in4.zip", "bls"),
    # Kenneth French data library
    _zip("ff49_daily", f"{FF}/49_Industry_Portfolios_daily_CSV.zip", "french"),
    _zip("ff49_monthly", f"{FF}/49_Industry_Portfolios_CSV.zip", "french"),
    _zip("ff5_daily", f"{FF}/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip", "french"),
    _zip("ff5_monthly", f"{FF}/F-F_Research_Data_5_Factors_2x3_CSV.zip", "french"),
    _zip("mom_daily", f"{FF}/F-F_Momentum_Factor_daily_CSV.zip", "french"),
    _zip("mom_monthly", f"{FF}/F-F_Momentum_Factor_CSV.zip", "french"),
    _zip("ff_siccodes49", f"{FF}/Siccodes49.zip", "french"),
    # Benchmarks
    Source("aioe",
           "https://raw.githubusercontent.com/AIOE-Data/AIOE/main/AIOE_DataAppendix.xlsx",
           "benchmarks/AIOE_DataAppendix.xlsx"),
    Source("eloundou_occ",
           "https://raw.githubusercontent.com/openai/GPTs-are-GPTs/main/data/occ_level.csv",
           "benchmarks/occ_level.csv"),
    # Census concordances
    *[
        Source(key, f"{CENSUS}/{name}", f"census/{name}")
        for key, name in (
            ("census_sic87_naics97", "1987_SIC_to_1997_NAICS.xls"),
            ("census_naics97_02", "1997_NAICS_to_2002_NAICS.xls"),
            ("census_naics02_07", "2002_to_2007_NAICS.xls"),
            ("census_naics07_12", "2007_to_2012_NAICS.xls"),
            ("census_naics12_17", "2012_to_2017_NAICS.xlsx"),
            ("census_naics17_22", "2017_to_2022_NAICS.xlsx"),
        )
    ],
    # SEC
    Source("sec_tickers", "https://www.sec.gov/files/company_tickers_exchange.json",
           "sec/company_tickers_exchange.json"),
]

_BY_KEY = {s.key: s for s in SOURCES}


def by_key(key: str) -> Source:
    return _BY_KEY[key]
