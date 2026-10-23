from urllib.parse import urlparse

import pytest

from aideleg.acquire import sources

REQUIRED = (
    {
        "aei_r1_task_pct", "aei_r1_collab", "aei_r1_wage", "aei_soc_structure",
        "aei_r2_task_pct", "aei_r2_collab_by_task", "aei_r2_thinking", "aei_onet_tasks",
        "aei_job_exposure", "onet_29_3_tasks", "onet_2010_2019_crosswalk",
        "onet_29_3_tasks_to_dwas", "onet_29_3_dwa_reference",
        "aei_geo_wap_country", "aei_geo_wap_us_state", "aei_geo_gdp_country",
        "aei_geo_gdp_us_state", "aei_geo_iso",
        "oews_2024_nat", "oews_2024_ind", "oews_2025_ind",
        "ff3_monthly", "ff_siccodes49", "aioe", "eloundou_occ", "census_sic87_naics97",
        "sec_tickers",
        "ne_admin0_50m", "census_states_20m",
    }
    | {f"aei_r{n}_{s}" for n in (3, 4, 5, 6) for s in ("claude_ai", "api", "docs")}
    | {f"{p}_{f}" for p in ("ff49", "ff5", "mom") for f in ("daily", "monthly")}
    | {f"census_naics{p}" for p in ("97_02", "02_07", "07_12", "12_17", "17_22")}
    | {f"sec_formidx_{y}q{q}" for y in range(2019, 2026) for q in range(1, 5)}
    | {"sec_submissions_bulk"}
)

# Zips read in place (members opened with zipfile), never extracted.
READ_IN_PLACE = {"sec_submissions_bulk"}


def test_keys_unique_and_dests_unique():
    keys = [s.key for s in sources.SOURCES]
    dests = [s.dest for s in sources.SOURCES]
    assert len(keys) == len(set(keys))
    assert len(dests) == len(set(dests))


def test_every_url_is_https():
    assert all(urlparse(s.url).scheme == "https" for s in sources.SOURCES)


def test_required_keys_present():
    assert {s.key for s in sources.SOURCES} == REQUIRED


def test_by_key():
    assert sources.by_key("aei_geo_iso").dest.endswith("iso_country_codes.csv")
    with pytest.raises(KeyError):
        sources.by_key("nope")


def test_zip_flags():
    assert all(s.unzip == (s.dest.endswith(".zip") and s.key not in READ_IN_PLACE)
               for s in sources.SOURCES)


def test_no_robot_or_task_penetration_files():
    for s in sources.SOURCES:
        low = s.url.lower()
        assert "robot_exposure" not in low
        assert "penetration" not in low


def test_onet_dwa_files_are_29_3_text_database():
    base = "https://www.onetcenter.org/dl_files/database/db_29_3_text/"
    assert sources.by_key("onet_29_3_tasks_to_dwas").url == base + "Tasks%20to%20DWAs.txt"
    assert sources.by_key("onet_29_3_dwa_reference").url == base + "DWA%20Reference.txt"


def test_new_geo_keys_registered():
    for key in ("ne_admin0_50m", "census_states_20m"):
        assert sources.by_key(key).unzip
    assert sources.by_key("ne_admin0_50m").dest == "geo/ne_50m_admin_0_countries.zip"
    assert sources.by_key("census_states_20m").dest == "geo/cb_2023_us_state_20m.zip"


def test_sources_include_full_index_and_bulk():
    for y in range(2019, 2026):
        for q in range(1, 5):
            s = sources.by_key(f"sec_formidx_{y}q{q}")
            assert s.url == f"https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/form.idx"
            assert s.dest == f"sec/full-index/{y}/QTR{q}/form.idx"
            assert not s.unzip
    bulk = sources.by_key("sec_submissions_bulk")
    assert bulk.url == "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip"
    assert bulk.dest == "sec/submissions.zip"
    assert not bulk.unzip
