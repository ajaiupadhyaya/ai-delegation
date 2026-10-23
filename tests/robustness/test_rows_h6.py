"""Plan 4 Task 14: the H6 rows R29 and R30 (`rows.talk_variant`, `rows.R30_LISTS`), on stubbed
filers and saved hits, plus a parity read of Plan 3's committed 2024 talk index."""

from datetime import date

import polars as pl
import pytest

from aideleg.robustness import rows, upstream

FILER_SCHEMA = {
    "year": pl.Int64,
    "cik": pl.Int64,
    "adsh": pl.String,
    "form": pl.String,
    "date_filed": pl.Date,
    "sic": pl.Int64,
    "ff49": pl.Int64,
}
HIT_SCHEMA = {
    "phrase": pl.String,
    "cik": pl.Int64,
    "adsh": pl.String,
    "form": pl.String,
    "file_date": pl.Date,
    "file_type": pl.String,
}


def _filers(rows_: list[tuple]) -> pl.DataFrame:
    return pl.DataFrame(rows_, schema=FILER_SCHEMA, orient="row")


def _hits(rows_: list[tuple]) -> pl.DataFrame:
    return pl.DataFrame(rows_, schema=HIT_SCHEMA, orient="row")


def _covering(phrases, start, end) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "phrase": list(phrases),
            "start": [start] * len(phrases),
            "end": [end] * len(phrases),
            "leaf": [True] * len(phrases),
            "pages": [1] * len(phrases),
        },
        schema={
            "phrase": pl.String,
            "start": pl.Date,
            "end": pl.Date,
            "leaf": pl.Boolean,
            "pages": pl.Int64,
        },
    )


@pytest.fixture
def no_fetch(monkeypatch):
    def _fail(*a, **k):
        pytest.fail("talk_variant fetched from the network")

    monkeypatch.setattr(upstream, "fts_hits", _fail)
    monkeypatch.setattr(rows, "OFFLINE", False)


def _in(t: pl.DataFrame, name: str):
    return t.filter(pl.col("ff49_short") == name)["T"][0]


def test_r30_term_lists():
    narrow, broad = rows.R30_LISTS["narrow"], rows.R30_LISTS["broad"]
    assert len(narrow) == 9
    assert not {"computer vision", "reinforcement learning", "foundation model"} & set(narrow)
    assert len(broad) == 14
    assert "automation" in broad and "robotics" in broad
    assert set(upstream.PRIMARY_TERMS) <= set(broad)
    assert rows.r30_phrases("narrow") == upstream.fts_phrases(narrow)
    assert rows.r30_phrases("broad") == [*upstream.fts_phrases(), "automation", "robotics"]


def test_r29_cuts_numerator_and_denominator(monkeypatch, no_fetch):
    phrases = upstream.fts_phrases()
    filers = _filers(
        [
            (2025, 1, "a1", "10-K", date(2025, 2, 1), 7372, 36),
            (2025, 2, "a2", "10-K", date(2025, 3, 27), 7372, 36),
            (2024, 3, "a3", "10-K", date(2024, 3, 1), 7372, 36),
        ]
    )
    hits_all = _hits(
        [
            ("machine learning", 1, "a1", "10-K", date(2025, 2, 1), "10-K"),
            ("machine learning", 2, "a2", "10-K", date(2025, 3, 27), "10-K"),
        ]
    )
    seen = {}

    def fake_saved(ph, start, end, **kw):
        seen.update(phrases=list(ph), start=start, end=end, **kw)
        return hits_all.filter(pl.col("file_date").is_between(start, end))

    monkeypatch.setattr(upstream, "load_filers", lambda: filers)
    monkeypatch.setattr(upstream, "hits_from_saved", fake_saved)
    monkeypatch.setattr(
        upstream, "saved_ranges", lambda: _covering(phrases, date(2025, 1, 1), date(2025, 12, 31))
    )
    t = rows.talk_variant(2025, phrases, date_to=date(2025, 3, 26))
    assert seen["start"] == date(2025, 1, 1)
    assert seen["end"] == date(2025, 3, 26)
    assert seen["strict"] is True
    assert t.columns == ["ff49_short", "T"]
    assert t.height == 49
    assert _in(t, "Softw") == pytest.approx(1.0)  # one talker over one filer
    full = rows.talk_variant(2025, phrases)
    assert _in(full, "Softw") == pytest.approx(1.0)  # two talkers over two filers
    stats = rows.talk_stats(2025, phrases, date_to=date(2025, 3, 26))
    assert stats["n_filers"] == 1 and stats["n_talk"] == 1


def test_float_weighting_hand_computed(monkeypatch, no_fetch):
    phrases = upstream.fts_phrases()
    filers = _filers(
        [
            (2024, 1, "a1", "10-K", date(2024, 2, 1), 7372, 36),
            (2024, 2, "a2", "10-K", date(2024, 3, 1), 7372, 36),
            (2024, 3, "a3", "10-K", date(2024, 3, 1), 7372, 36),  # no float: left out
        ]
    )
    hits = _hits(
        [
            ("machine learning", 1, "a1", "10-K", date(2024, 2, 1), "10-K"),
            ("machine learning", 3, "a3", "10-K", date(2024, 3, 1), "10-K"),
        ]
    )
    floats = pl.DataFrame(
        {"cik": [1, 2, 99], "public_float_usd": [100.0, 300.0, 5.0]},
        schema={"cik": pl.Int64, "public_float_usd": pl.Float64},
    )
    monkeypatch.setattr(upstream, "load_filers", lambda: filers)
    monkeypatch.setattr(upstream, "hits_from_saved", lambda ph, s, e, **kw: hits)
    monkeypatch.setattr(
        upstream, "saved_ranges", lambda: _covering(phrases, date(2024, 1, 1), date(2024, 12, 31))
    )
    monkeypatch.setattr(rows.inputs, "public_float", lambda: floats)
    t = rows.talk_variant(2024, phrases, weighting="float")
    assert _in(t, "Softw") == pytest.approx(0.25)
    assert t.filter(pl.col("ff49_short") != "Softw")["T"].null_count() == 48
    st = rows.talk_stats(2024, phrases, weighting="float")
    assert st["n_filers"] == 3 and st["n_float"] == 2


def test_float_weighting_with_unit_floats_equals_count(monkeypatch, no_fetch):
    phrases = upstream.fts_phrases()
    filers = _filers(
        [
            (2024, c, f"a{c}", "10-K", date(2024, 2, 1), 7372 if c % 2 else 2000, None)
            for c in range(1, 9)
        ]
    ).with_columns(pl.when(pl.col("cik") % 2 == 1).then(36).otherwise(2).alias("ff49"))
    hits = _hits(
        [("machine learning", c, f"a{c}", "10-K", date(2024, 2, 1), "10-K") for c in (1, 2, 3, 6)]
    )
    floats = pl.DataFrame(
        {"cik": list(range(1, 9)), "public_float_usd": [1.0] * 8},
        schema={"cik": pl.Int64, "public_float_usd": pl.Float64},
    )
    monkeypatch.setattr(upstream, "load_filers", lambda: filers)
    monkeypatch.setattr(upstream, "hits_from_saved", lambda ph, s, e, **kw: hits)
    monkeypatch.setattr(
        upstream, "saved_ranges", lambda: _covering(phrases, date(2024, 1, 1), date(2024, 12, 31))
    )
    monkeypatch.setattr(rows.inputs, "public_float", lambda: floats)
    a = rows.talk_variant(2024, phrases)
    b = rows.talk_variant(2024, phrases, weighting="float")
    assert a.equals(b)
    assert _in(a, "Softw") == pytest.approx(0.5) and _in(a, "Food") == pytest.approx(0.5)


def test_offline_never_fetches_and_is_strict(monkeypatch, no_fetch):
    monkeypatch.setattr(rows, "OFFLINE", True)
    filers = _filers([(2024, 1, "a1", "10-K", date(2024, 2, 1), 7372, 36)])
    seen = {}

    def fake_saved(ph, s, e, **kw):
        seen.update(kw)
        raise FileNotFoundError("not covered: 'automation'")

    monkeypatch.setattr(upstream, "load_filers", lambda: filers)
    monkeypatch.setattr(upstream, "hits_from_saved", fake_saved)
    monkeypatch.setattr(
        upstream, "saved_ranges", lambda: _covering([], date(2024, 1, 1), date(2024, 1, 1))
    )
    with pytest.raises(FileNotFoundError, match="automation"):
        rows.talk_variant(2024, ["automation"])
    assert seen["strict"] is True


def test_online_fetches_only_uncovered_phrases(monkeypatch):
    monkeypatch.setattr(rows, "OFFLINE", False)
    filers = _filers([(2024, 1, "a1", "10-K", date(2024, 2, 1), 7372, 36)])
    phrases = ["machine learning", "automation", "robotics"]
    fetched = []
    covered = _covering(["machine learning"], date(2024, 1, 1), date(2024, 12, 31))
    # robotics: saved only for the first half of the year (a gap is not coverage)
    covered = pl.concat([covered, _covering(["robotics"], date(2024, 1, 1), date(2024, 6, 30))])
    monkeypatch.setattr(upstream, "load_filers", lambda: filers)
    monkeypatch.setattr(upstream, "saved_ranges", lambda: covered)
    monkeypatch.setattr(
        upstream,
        "fts_hits",
        lambda ph, s, e, **kw: fetched.append((ph, s, e)) or _hits([]),
    )
    monkeypatch.setattr(upstream, "hits_from_saved", lambda ph, s, e, **kw: _hits([]))
    rows.talk_variant(2024, phrases)
    assert fetched == [
        ("automation", date(2024, 1, 1), date(2024, 12, 31)),
        ("robotics", date(2024, 1, 1), date(2024, 12, 31)),
    ]


def test_uncovered_union_of_leaves():
    sr = pl.concat(
        [
            _covering(["x"], date(2024, 1, 1), date(2024, 6, 30)),
            _covering(["x"], date(2024, 7, 1), date(2024, 12, 31)),
            _covering(["y"], date(2024, 1, 1), date(2024, 12, 31)).with_columns(
                pl.lit(False).alias("leaf")
            ),
        ]
    )
    assert rows.uncovered_phrases(sr, ["x", "y", "z"], date(2024, 1, 1), date(2024, 12, 31)) == [
        "y",
        "z",
    ]


@pytest.fixture
def stubbed_runner(monkeypatch, tmp_path):
    names = [f"I{i:02d}" for i in range(1, 50)]
    calls = []

    def fake_talk(year, phrases, *, date_to=None, weighting="count"):
        calls.append((year, tuple(phrases), date_to, weighting))
        T = pl.DataFrame(
            {
                "ff49_short": names,
                "T": [0.01 * ((k * 7) % 13) + (year % 7) * 1e-3 for k in range(49)],
            }
        )
        stats = {"n_filers": 10, "n_mapped": 8, "n_talk": 4, "no_T": []}
        if weighting == "float":
            stats |= {"n_float": 6, "n_float_mapped": 5, "n_float_zero": 1}
        return T, stats

    expo = pl.DataFrame(
        {
            "design": ["B"] * 49,
            "ff49": list(range(1, 50)),
            "ff49_short": names,
            "z_delegation": [0.0] * 49,
            "z_usage": [float((k * 5) % 11) - 5.0 for k in range(49)],
            "z_aioe": [0.0] * 49,
        }
    )
    res = {
        "b": 0.01,
        "s": 0.02,
        "bbar": 0.001,
        "q_0.975": 1.9,
        "crit_0.05": 2.08,
        "T_bbar": 0.45,
        "p_bbar": 0.65,
        "T_zero": 0.5,
        "p_zero": 0.62,
        "ci_0.05": (-0.03, 0.05),
        "n": 49,
        "dropped": [],
        "no_gap": [],
    }
    monkeypatch.setattr(rows, "_talk", fake_talk)
    monkeypatch.setattr(upstream, "exposures", lambda: expo)
    monkeypatch.setattr(upstream, "gap_returns", lambda g: dict(res))
    monkeypatch.setattr(
        upstream,
        "zero_assigned",
        lambda: pl.DataFrame({"design": ["B"], "no_usage_emp_pct": [12.345]}),
    )
    monkeypatch.setattr(rows.guards, "require_confirmatory_committed", lambda *a, **k: None)
    monkeypatch.setattr(rows, "OUT_DIR", tmp_path)
    return calls


def test_r29_runner_parts_and_calls(stubbed_runner):
    csv, md = rows.RUNNERS["R29"]()
    df = pl.read_csv(csv)
    text = md.read_text(encoding="utf-8")
    assert df["part"].unique(maintain_order=True).to_list() == [
        "pre_formation_2025",
        "change_2019_2024",
        "float_weighted",
    ]
    assert df.height == 6
    assert set(df["applies_to"]) == {"H6 divergence", "H6 gap-return"}
    assert set(df["label"]) == {"robustness; exploratory"}
    ph = tuple(upstream.fts_phrases())
    assert stubbed_runner == [
        (2025, ph, date(2025, 3, 26), "count"),
        (2024, ph, None, "count"),
        (2019, ph, None, "count"),
        (2024, ph, None, "float"),
    ]
    ret = df.filter(pl.col("applies_to") == "H6 gap-return")
    assert ret["estimate"].to_list() == pytest.approx([1.0] * 3)
    assert ret["ci_lo"].to_list() == pytest.approx([-3.0] * 3)
    assert "C-61" in text and "Zero-assigned employment share, Design B: 12.35% (D3)" in text
    assert "public float" in text and "6 of 10" in text


def test_r30_runner_parts_and_calls(stubbed_runner):
    csv, md = rows.RUNNERS["R30"]()
    df = pl.read_csv(csv)
    text = md.read_text(encoding="utf-8")
    assert df["part"].unique(maintain_order=True).to_list() == ["narrow", "broad"]
    assert stubbed_runner == [
        (2024, tuple(rows.r30_phrases("narrow")), None, "count"),
        (2024, tuple(rows.r30_phrases("broad")), None, "count"),
    ]
    assert "C-62" in text


def test_cli_offline_flag_sets_rows_offline(monkeypatch):
    from aideleg.robustness import __main__ as cli

    monkeypatch.setattr(rows, "OFFLINE", False)
    monkeypatch.setattr(rows, "RUNNERS", {"R29": lambda: ("a.csv", "a.md")})
    cli.main(["--only", "R29", "--offline"])
    assert rows.OFFLINE is True


@pytest.mark.data
def test_talk_variant_offline_when_saved(monkeypatch):
    from aideleg.h6 import edgar

    def _no_network(*a, **k):
        pytest.fail("talk_variant touched the network")

    for name in ("fts_source", "_get_json", "fts_hits", "acquire_fts"):
        monkeypatch.setattr(edgar, name, _no_network)
    monkeypatch.setattr(upstream, "fts_hits", _no_network)
    monkeypatch.setattr(rows, "OFFLINE", False)
    got = rows.talk_variant(2024, upstream.fts_phrases())
    want = (
        pl.read_csv(upstream.H6_DIR / "talk_index.csv")
        .filter((pl.col("year") == 2024) & pl.col("ff49").is_not_null())
        .select("ff49_short", pl.col("talk").alias("T"))
    )
    assert got.height == want.height == 49
    assert got["ff49_short"].to_list() == want["ff49_short"].to_list()
    assert got["T"].to_list() == pytest.approx(want["T"].to_list(), rel=1e-12, abs=0.0)
