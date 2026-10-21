from urllib.parse import urlparse

import pytest

from aideleg.acquire import sources

REQUIRED = (
    {
        "aei_r1_task_pct", "aei_r1_collab", "aei_r1_wage", "aei_soc_structure",
        "aei_r2_task_pct", "aei_r2_collab_by_task", "aei_r2_thinking", "aei_onet_tasks",
        "aei_job_exposure", "onet_29_3_tasks", "onet_2010_2019_crosswalk",
        "aei_geo_wap_country", "aei_geo_wap_us_state", "aei_geo_gdp_country",
        "aei_geo_gdp_us_state", "aei_geo_iso",
        "oews_2024_nat", "oews_2024_ind", "oews_2025_ind",
        "ff_siccodes49", "aioe", "eloundou_occ", "census_sic87_naics97", "sec_tickers",
    }
    | {f"aei_r{n}_{s}" for n in (3, 4, 5, 6) for s in ("claude_ai", "api", "docs")}
    | {f"{p}_{f}" for p in ("ff49", "ff5", "mom") for f in ("daily", "monthly")}
    | {f"census_naics{p}" for p in ("97_02", "02_07", "07_12", "12_17", "17_22")}
)


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
    assert all(s.unzip == s.dest.endswith(".zip") for s in sources.SOURCES)


def test_no_robot_or_task_penetration_files():
    for s in sources.SOURCES:
        low = s.url.lower()
        assert "robot_exposure" not in low
        assert "penetration" not in low
