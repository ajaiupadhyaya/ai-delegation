"""The confirmatory H5/H5b script, on synthetic data only. The real script is never run here:
the seal is monkeypatched and every loader is replaced by synthetic returns."""

import hashlib
import re
import subprocess
from datetime import date

import numpy as np
import polars as pl
import pytest

from aideleg import confirm_h5 as ch
from aideleg import power
from aideleg.config import ROOT
from aideleg.market import seal

FACTORS = ["mkt_rf", "smb", "hml", "rmw", "cma", "umd"]
NAMES = [f"I{i:02d}" for i in range(1, 50)]
NAMES[33] = "Softw"


def _exposure(seed: int = 9) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    z = rng.normal(size=49)
    z[33] = 5.0
    z = (z - z.mean()) / z.std()
    c = 0.7 * z + rng.normal(size=49)
    c = (c - c.mean()) / c.std()
    return pl.DataFrame({"ff49": list(range(1, 50)), "ff49_short": NAMES,
                         "z_delegation": z, "z_aioe": c})


def _market(start: date, end: date, slope_pp: float = 0.0, softw_only: bool = False,
            seed: int = 1, expo: pl.DataFrame | None = None):
    """Daily synthetic factors and industry returns (percent). Each industry's daily excess
    return carries a planted alpha of slope_pp (pp/yr per 1 SD of z) x z_j, inside [start, end]
    only; with softw_only, only Softw carries it."""
    expo = _exposure() if expo is None else expo
    z = expo["z_delegation"].to_numpy()
    rng = np.random.default_rng(seed)
    days = pl.date_range(start, end, "1d", eager=True)
    days = days.filter(days.dt.weekday() <= 5)
    n = days.len()
    f = {c: rng.normal(0.0, 1.0, n) for c in FACTORS}
    factors = pl.DataFrame({"date": days, **f, "rf": np.full(n, 0.01)}).select(
        "date", "mkt_rf", "smb", "hml", "rmw", "cma", "rf", "umd")
    in_win = ((days >= ch.WINDOW[0]) & (days <= ch.WINDOW[1])).to_numpy()
    ret = {}
    for j, nm in enumerate(NAMES):
        a = slope_pp * z[j] / 252 if (not softw_only or nm == "Softw") else 0.0
        ret[nm] = f["mkt_rf"] + 0.01 + rng.normal(0.0, 0.3, n) + np.where(in_win, a, 0.0)
    return pl.DataFrame({"date": days, **ret}), factors


def _vector_hash(expo: pl.DataFrame) -> str:
    df = expo.select("ff49", "ff49_short", "z_delegation", "z_aioe")
    return hashlib.sha256(df.write_csv(float_precision=10).encode()).hexdigest()


@pytest.fixture
def unsealed(monkeypatch):
    """Synthetic world: pap-v1 'exists', loaders return synthetic data, calls are recorded."""
    calls: list[tuple] = []
    state = {"returns": None, "factors": None}
    expo = _exposure()

    def fake_returns(freq, weighting, end):
        calls.append(("returns", freq, weighting, end))
        return state["returns"].filter(pl.col("date") <= end)

    def fake_factors(freq, end):
        calls.append(("factors", freq, end))
        return state["factors"].filter(pl.col("date") <= end)

    monkeypatch.setattr(seal, "pap_frozen", lambda repo=None: True)
    # K1/K2 are tested on tmp git repos below; here they are recorded no-ops
    monkeypatch.setattr(ch, "check_binding", lambda *a, **k: calls.append(("binding",)))
    monkeypatch.setattr(ch, "check_french_data", lambda *a, **k: calls.append(("french",)))
    for mod in (ch, power):
        monkeypatch.setattr(mod, "load_industry_returns", fake_returns)
        monkeypatch.setattr(mod, "load_factors", fake_factors)
    monkeypatch.setattr(power, "load_exposure", lambda: expo)
    monkeypatch.setattr(ch, "EXPOSURE_SHA256", _vector_hash(expo))
    monkeypatch.setattr(ch, "N_PERM", 199)
    return {"calls": calls, "state": state, "expo": expo}


def test_frozen_constants_equal_power_md():
    text = (ROOT / "docs/pap/power.md").read_text()
    assert ch.FROZEN == power.parse_frozen(text)


def test_exposure_hash_equals_pap():
    text = (ROOT / "docs/pap/pre-analysis-plan.md").read_text()
    assert ch.EXPOSURE_SHA256 in text
    assert re.fullmatch(r"[0-9a-f]{64}", ch.EXPOSURE_SHA256)


def test_refuses_without_pap_tag(monkeypatch, tmp_path):
    monkeypatch.setattr(seal, "pap_frozen", lambda repo=None: False)

    def boom(*a, **k):
        raise AssertionError("a loader was called before the seal check")

    monkeypatch.setattr(ch, "load_industry_returns", boom)
    monkeypatch.setattr(ch, "load_factors", boom)
    with pytest.raises(seal.SealedPeriodError):
        ch.run(out=tmp_path / "c.md")
    assert not (tmp_path / "c.md").exists()


def test_refuses_to_overwrite(unsealed, tmp_path):
    out = tmp_path / "c.md"
    out.write_text("earlier result\n")
    with pytest.raises(FileExistsError):
        ch.run(out=out)
    assert out.read_text() == "earlier result\n"
    assert unsealed["calls"] == []


def _loads(calls):
    return [c for c in calls if c[0] in ("returns", "factors")]


def test_refuses_on_exposure_hash_mismatch(unsealed, monkeypatch, tmp_path):
    monkeypatch.setattr(ch, "EXPOSURE_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="exposure vector"):
        ch.run(out=tmp_path / "c.md")
    assert not (tmp_path / "c.md").exists()


def test_holm_two_steps():
    assert ch.holm({"H5": 0.01, "H5b": 0.04}) == {"H5": 0.025, "H5b": 0.05}
    assert ch.holm({"H5": 0.03, "H5b": 0.04}) == {"H5": None, "H5b": None}
    assert ch.holm({"H5": 0.20, "H5b": 0.02}) == {"H5": None, "H5b": 0.025}


def test_decide_co_condition_and_wording():
    fz = dict(ch.FROZEN)
    s = fz["s_h5"]
    # H5 far beyond its critical; R13 not; H5b not
    b = {"h5": 10 * s, "h5b": 0.0, "h5_r12": 10 * fz["s_h5_r12"], "h5b_r12": 0.0,
         "h5_r13": 0.0, "h5b_r13": 0.0}
    d = ch.decide(b, fz, null="zero")
    assert d["primary"]["H5"] == 0.025 and d["primary"]["H5b"] is None
    assert d["co_condition"]["H5"] is False
    assert "not robust to dropping Softw (R13 not rejected)" in d["wording"]["H5"]
    assert "driven by" not in d["wording"]["H5"]
    b["h5_r13"] = 10 * fz["s_h5_r13"]
    d = ch.decide(b, fz, null="zero")
    assert d["co_condition"]["H5"] is True
    assert "delegation exposure is priced" in d["wording"]["H5"]
    # rejects but within crit of the frozen historical mean -> fixed P5 wording
    # (an artificial frozen mean, so that the rule is exercised without using the real one)
    fz2 = dict(fz, bbar_h5=10 * s)
    d = ch.decide(dict(b, h5=10.5 * s), fz2, null="zero")
    assert d["primary"]["H5"] == 0.025
    assert "not distinguishable from the 1990-2022 pattern" in d["wording"]["H5"]
    d = ch.decide({k: 0.0 for k in b}, fz, null="zero")
    assert d["primary"] == {"H5": None, "H5b": None}
    w = d["wording"]["H5"]
    assert "80% power only against a departure from H0 of at least" in w
    assert w.count("80% power") == 1 and "|b| >=" not in w


def test_end_to_end_synthetic_planted_slope(unsealed, tmp_path):
    r, f = _market(date(1989, 6, 1), date(2026, 9, 30), slope_pp=40.0)
    unsealed["state"].update(returns=r, factors=f)
    out = tmp_path / "confirmatory_h5.md"
    res = ch.run(out=out)
    # loaders asked only for the confirmatory window's end (no dropped industries)
    assert {c[-1] for c in _loads(unsealed["calls"])} == {ch.WINDOW[1]}
    # binding and data checks ran before the first load
    assert [c[0] for c in unsealed["calls"][:3]] == ["binding", "french", "returns"]
    a = power.window_alphas(r, f, *ch.WINDOW).to_numpy()
    z = unsealed["expo"]["z_delegation"].to_numpy()
    assert res["b"]["h5"] == pytest.approx(np.polyfit(z, a, 1)[0])
    assert res["decision"]["T_zero"]["h5"] == pytest.approx(res["b"]["h5"] / ch.FROZEN["s_h5"])
    assert res["decision"]["primary"]["H5"] == 0.025
    assert res["b"]["h5"] == pytest.approx(0.40, abs=0.05)
    text = out.read_text()
    for needle in ("H5", "H5b", "R12", "R13", "Freedman-Lane", "HC3", "Holm",
                   ch.EXPOSURE_SHA256, "conversations matched to"):
        assert needle in text
    assert set(res["ri"]) == {"h5_exposure", "h5b_exposure", "h5b_freedman_lane",
                              "h5b_freedman_lane_coef"}
    assert "pivotal t" in text
    assert all(0 < p <= 1 for p in res["ri"].values())
    with pytest.raises(FileExistsError):
        ch.run(out=out)


def test_end_to_end_synthetic_null_and_softw_only(unsealed, tmp_path):
    r, f = _market(date(1989, 6, 1), date(2026, 9, 30), slope_pp=0.0)
    unsealed["state"].update(returns=r, factors=f)
    res = ch.run(out=tmp_path / "a.md")
    assert res["decision"]["primary"] == {"H5": None, "H5b": None}
    # a huge alpha at Softw alone: H5 rejects, dropping Softw removes it
    r, f = _market(date(1989, 6, 1), date(2026, 9, 30), slope_pp=200.0, softw_only=True,
                   seed=2)
    unsealed["state"].update(returns=r, factors=f)
    res = ch.run(out=tmp_path / "b.md")
    assert res["decision"]["primary"]["H5"] is not None
    assert res["decision"]["co_condition"]["H5"] is False
    assert "not robust to dropping Softw" in res["decision"]["wording"]["H5"]


def test_dropped_industry_rescales_on_pre_seal_history(unsealed, tmp_path, monkeypatch):
    r, f = _market(date(1989, 6, 1), date(2026, 9, 30), slope_pp=0.0)
    r = r.with_columns(pl.when(pl.col("date") == date(2025, 6, 2)).then(None)
                       .otherwise(pl.col("I05")).alias("I05"))
    unsealed["state"].update(returns=r, factors=f)
    res = ch.run(out=tmp_path / "c.md")
    assert res["dropped"] == ["I05"]
    ends = {c[-1] for c in _loads(unsealed["calls"])}
    assert ends == {ch.WINDOW[1], power.END}
    # the rescaled values equal what the power module computes on the kept industries
    expo = unsealed["expo"].filter(pl.col("ff49_short") != "I05")
    monkeypatch.setattr(power, "load_exposure", lambda: expo)
    hist = r.drop("I05")
    monkeypatch.setattr(power, "load_industry_returns",
                        lambda fr, w, end: hist.filter(pl.col("date") <= end))
    monkeypatch.setattr(power, "N_PERM", 9)
    pres = power.run_power(out=tmp_path / "p.md")
    want = power.frozen_values(pres)
    for k in ("s_h5", "s_h5b", "bbar_h5", "s_h5_r13", "s_h5b_r12", "crit_h5_0.025",
              "bbar_h5b", "bbar_h5_r12", "bbar_h5b_r12", "bbar_h5_r13", "bbar_h5b_r13"):
        assert res["frozen_used"][k] == pytest.approx(want[k], rel=1e-12)


def test_holm_stops_when_the_first_fails_the_max_critical():
    fz = dict(ch.FROZEN)
    fz["crit_h5_0.025"] = 50.0  # an empirical quantile above t_21 (not the frozen case)
    b = {"h5": 6 * fz["s_h5"], "h5b": 3 * fz["s_h5b"], "h5_r12": 0.0, "h5b_r12": 0.0,
         "h5_r13": 0.0, "h5b_r13": 0.0}
    d = ch.decide(b, fz, null="zero")
    assert d["holm_level"] == {"H5": 0.025, "H5b": 0.05}
    assert d["primary"] == {"H5": None, "H5b": None}


def test_creates_the_results_directory(unsealed, tmp_path):
    r, f = _market(date(1989, 6, 1), date(2026, 9, 30))
    unsealed["state"].update(returns=r, factors=f)
    out = tmp_path / "docs" / "results" / "confirmatory_h5.md"
    ch.run(out=out)
    assert out.exists()
    assert ch.OUT == ROOT / "docs/results/confirmatory_h5.md"



def test_primary_null_constant_is_bbar_for_now():
    assert ch.PRIMARY_NULL == "bbar"


def test_refuses_when_data_stop_before_the_window_end(unsealed, tmp_path):
    r, f = _market(date(1989, 6, 1), date(2026, 7, 31))
    unsealed["state"].update(returns=r, factors=f)
    out = tmp_path / "c.md"
    with pytest.raises(ValueError, match="window coverage"):
        ch.run(out=out)
    # a refusal after the first read is an attempt, recorded with its traceback
    assert "window coverage" in out.read_text()
    assert ch.attempt_path(out).exists()


def test_refuses_when_data_start_late_or_dates_differ(unsealed, tmp_path):
    r, f = _market(date(2025, 4, 2), date(2026, 9, 30))
    unsealed["state"].update(returns=r, factors=f)
    with pytest.raises(ValueError, match="window coverage"):
        ch.run(out=tmp_path / "a.md")
    r, f = _market(date(1989, 6, 1), date(2026, 9, 30))
    f = f.filter(pl.col("date") != date(2025, 7, 15))
    unsealed["state"].update(returns=r, factors=f)
    with pytest.raises(ValueError, match="window coverage"):
        ch.run(out=tmp_path / "b.md")
    for name in ("a.md", "b.md"):
        assert "window coverage" in (tmp_path / name).read_text()


def test_mde_uses_the_primary_critical():
    fz = dict(ch.FROZEN, **{"crit_h5_0.025": 50.0})
    b = {k: 0.0 for k in ch.VARIANTS}
    d = ch.decide(b, fz, null="zero")
    from scipy import stats
    mde = (50.0 + stats.t.ppf(0.80, 21)) * fz["s_h5"]
    assert f"{mde * 100:.2f} pp" in d["wording"]["H5"]


@pytest.mark.parametrize("null", ["zero", "bbar"])
def test_decide_uses_the_selected_null_and_reports_both(null):
    fz = dict(ch.FROZEN)
    for v in ch.VARIANTS:  # artificial frozen means, so the two nulls disagree
        fz[f"bbar_{v}"] = 3.0 * fz[f"s_{v}"]
    b = {v: 3.0 * fz[f"s_{v}"] for v in ch.VARIANTS}  # = bbar: rejects b = 0 only
    d = ch.decide(b, fz, null=null)
    assert d["null"] == null
    for v in ch.VARIANTS:
        assert d["T_zero"][v] == pytest.approx(3.0)
        assert d["T_bbar"][v] == pytest.approx(0.0)
    if null == "zero":
        assert d["primary"]["H5"] == 0.025 and d["co_condition"]["H5"] is True
        assert "not distinguishable from the 1990-2022 pattern" in d["wording"]["H5"]
    else:
        assert d["primary"] == {"H5": None, "H5b": None}
        assert "not rejected" in d["wording"]["H5"]
    assert d["T"] == (d["T_zero"] if null == "zero" else d["T_bbar"])


@pytest.mark.parametrize("null", ["zero", "bbar"])
def test_end_to_end_reports_both_statistics(unsealed, tmp_path, monkeypatch, null):
    monkeypatch.setattr(ch, "PRIMARY_NULL", null)
    r, f = _market(date(1989, 6, 1), date(2026, 9, 30), slope_pp=40.0)
    unsealed["state"].update(returns=r, factors=f)
    out = tmp_path / "c.md"
    res = ch.run(out=out)
    d = res["decision"]
    assert d["null"] == null and d["primary"]["H5"] == 0.025
    for v in ch.VARIANTS:
        assert d["T_bbar"][v] == pytest.approx(
            (res["b"][v] - ch.FROZEN[f"bbar_{v}"]) / ch.FROZEN[f"s_{v}"])
    text = out.read_text()
    assert f"Confirmatory null: {'b = 0' if null == 'zero' else 'b = bbar'}" in text
    assert "(b - bbar) / s" in text and "b / s" in text
    assert "pre-seal, full 49 industries" in text



# --- K3: attempt marker and crash record ------------------------------------------------------

def test_attempt_marker_and_traceback_on_a_crash(unsealed, tmp_path, monkeypatch):
    r, f = _market(date(1989, 6, 1), date(2026, 9, 30))
    unsealed["state"].update(returns=r, factors=f)
    out = tmp_path / "confirmatory_h5.md"
    marker = ch.attempt_path(out)
    assert marker == tmp_path / "confirmatory_h5.attempt"

    def crash(*a, **k):
        raise RuntimeError("synthetic crash after the first read")

    monkeypatch.setattr(power, "window_alphas", crash)
    with pytest.raises(RuntimeError, match="synthetic crash"):
        ch.run(out=out)
    m = marker.read_text()
    assert re.search(r"started_utc: \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", m)
    assert re.search(r"head: ([0-9a-f]{40}|unknown)", m)
    text = out.read_text()
    assert "Traceback" in text and "synthetic crash after the first read" in text
    # a second run refuses, even with the output removed
    out.unlink()
    unsealed["calls"].clear()
    with pytest.raises(FileExistsError, match="attempt"):
        ch.run(out=out)
    assert unsealed["calls"] == []


def test_no_marker_when_refused_before_the_first_read(unsealed, tmp_path, monkeypatch):
    monkeypatch.setattr(ch, "EXPOSURE_SHA256", "0" * 64)
    out = tmp_path / "c.md"
    with pytest.raises(ValueError, match="exposure vector"):
        ch.run(out=out)
    assert not ch.attempt_path(out).exists() and not out.exists()
    assert _loads(unsealed["calls"]) == []


def test_marker_written_before_the_first_post_seal_read(unsealed, tmp_path, monkeypatch):
    r, f = _market(date(1989, 6, 1), date(2026, 9, 30))
    unsealed["state"].update(returns=r, factors=f)
    out = tmp_path / "c.md"
    seen = []
    orig = ch.load_industry_returns

    def spy(*a, **k):
        seen.append(ch.attempt_path(out).exists())
        return orig(*a, **k)

    monkeypatch.setattr(ch, "load_industry_returns", spy)
    ch.run(out=out)
    assert seen == [True]


def test_binding_failure_reads_nothing(unsealed, tmp_path, monkeypatch):
    def refuse(*a, **k):
        raise ch.BindingError("not bound")

    monkeypatch.setattr(ch, "check_binding", refuse)
    monkeypatch.setattr(power, "load_exposure", lambda: (_ for _ in ()).throw(
        AssertionError("exposure loaded before the binding check")))
    out = tmp_path / "c.md"
    with pytest.raises(ch.BindingError):
        ch.run(out=out)
    assert not out.exists() and not ch.attempt_path(out).exists()
    assert _loads(unsealed["calls"]) == []


# --- K1: the script enforces its own binding (tmp git repos only; never pap-v1 here) ----------

BOUND = ("src/aideleg/confirm_h5.py", "src/aideleg/power.py", "src/aideleg/market/__init__.py",
         "src/aideleg/market/french.py", "src/aideleg/market/seal.py")


def _g(repo, *args):
    import subprocess
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


@pytest.fixture
def bound_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _g(repo, "init", "-q")
    for k, v in (("user.email", "t@example.com"), ("user.name", "t"),
                 ("commit.gpgsign", "false"), ("tag.gpgsign", "false")):
        _g(repo, "config", k, v)
    for rel in BOUND + ("src/aideleg/other.py", "pyproject.toml", "uv.lock", "README.md"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(f"# {rel}\n")
    _g(repo, "add", "-A")
    _g(repo, "commit", "-q", "-m", "plan")
    _g(repo, "tag", "-a", "pap-v1", "-m", "signed plan")
    return repo


def _own(repo):
    return repo / "src/aideleg/confirm_h5.py"


def test_binding_passes_on_the_tagged_commit_and_a_docs_only_descendant(bound_repo):
    ch.check_binding(bound_repo, own=_own(bound_repo))
    (bound_repo / "README.md").write_text("results\n")
    _g(bound_repo, "commit", "-q", "-am", "docs")
    ch.check_binding(bound_repo, own=_own(bound_repo))


def test_binding_refuses_without_the_tag(bound_repo):
    _g(bound_repo, "tag", "-d", "pap-v1")
    with pytest.raises(ch.BindingError, match="annotated"):
        ch.check_binding(bound_repo, own=_own(bound_repo))


def test_binding_refuses_a_lightweight_tag(bound_repo):  # (a)
    _g(bound_repo, "tag", "-d", "pap-v1")
    _g(bound_repo, "tag", "pap-v1")
    with pytest.raises(ch.BindingError, match="annotated"):
        ch.check_binding(bound_repo, own=_own(bound_repo))


def test_binding_refuses_when_head_does_not_descend_from_the_tag(bound_repo):  # (b)
    _g(bound_repo, "checkout", "-q", "--orphan", "elsewhere")
    _g(bound_repo, "commit", "-q", "-m", "unrelated")
    with pytest.raises(ch.BindingError, match="descend"):
        ch.check_binding(bound_repo, own=_own(bound_repo))


def test_binding_refuses_when_the_running_script_differs(bound_repo, tmp_path):  # (c)
    other = tmp_path / "confirm_h5.py"
    other.write_text("# edited copy\n")
    with pytest.raises(ch.BindingError, match="confirm_h5.py"):
        ch.check_binding(bound_repo, own=other)


def test_binding_refuses_an_untracked_market_module(bound_repo):  # (c), invisible to diff
    (bound_repo / "src/aideleg/market/extra.py").write_text("x = 1\n")
    with pytest.raises(ch.BindingError, match="extra.py"):
        ch.check_binding(bound_repo, own=_own(bound_repo))


@pytest.mark.parametrize("rel", ["src/aideleg/power.py", "src/aideleg/market/seal.py"])
def test_binding_refuses_an_edited_bound_module(bound_repo, rel):  # (c)
    (bound_repo / rel).write_text("# edited\n")
    with pytest.raises(ch.BindingError, match=rel.rsplit("/", 1)[-1]):
        ch.check_binding(bound_repo, own=_own(bound_repo))


@pytest.mark.parametrize("rel", ["src/aideleg/other.py", "pyproject.toml", "uv.lock"])
@pytest.mark.parametrize("commit", [False, True])
def test_binding_refuses_src_or_lock_changes_against_the_tag(bound_repo, rel, commit):  # (d)
    (bound_repo / rel).write_text("# changed after the tag\n")
    if commit:
        _g(bound_repo, "commit", "-q", "-am", "change")
    with pytest.raises(ch.BindingError, match="differ from pap-v1"):
        ch.check_binding(bound_repo, own=_own(bound_repo))


@pytest.mark.parametrize("rel", ["src/aideleg/power/__init__.py", "src/aideleg/new_module.py"])
def test_binding_refuses_an_untracked_file_under_src(bound_repo, rel):
    # an untracked package src/aideleg/power/ would shadow power.py on import; (c) and (d) miss it
    (bound_repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (bound_repo / rel).write_text("x = 1\n")
    with pytest.raises(ch.BindingError, match="untracked"):
        ch.check_binding(bound_repo, own=_own(bound_repo))


def test_binding_refuses_in_this_repo_when_src_differs():
    # on a branch whose src/pyproject.toml/uv.lock differ from pap-v1, check_binding refuses
    rc = subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "pap-v1", "--",
                         *ch.DIFF_PATHS]).returncode
    if rc == 0:
        pytest.skip("this checkout equals pap-v1 under DIFF_PATHS")
    with pytest.raises(ch.BindingError, match="differ from"):
        ch.check_binding()


# --- K2: French data bound to the tagged MANIFEST ---------------------------------------------

def _zip_bytes(members: dict[str, bytes]) -> bytes:
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in members.items():
            z.writestr(n, b)
    return buf.getvalue()


@pytest.fixture
def french_repo(bound_repo):
    import json
    raw = bound_repo / "data/raw"
    manifest = {}
    for key in ch.FRENCH_REQUIRED + ("ff_siccodes49",):
        dest = f"french/{key}.zip"
        body = _zip_bytes({f"{key}.csv": f"{key} data\n".encode()})
        (raw / dest).parent.mkdir(parents=True, exist_ok=True)
        (raw / dest).write_bytes(body)
        (raw / dest).with_suffix("").mkdir()
        (raw / dest).with_suffix("").joinpath(f"{key}.csv").write_bytes(f"{key} data\n".encode())
        manifest[key] = {"key": key, "url": "u", "dest": dest, "retrieved_utc": "t",
                         "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    manifest["other"] = {"key": "other", "url": "u", "dest": "bls/x.zip", "retrieved_utc": "t",
                         "bytes": 0, "sha256": "0" * 64}
    (raw / "MANIFEST.json").write_text(json.dumps(manifest))
    _g(bound_repo, "add", "data/raw/MANIFEST.json")
    _g(bound_repo, "commit", "-q", "-m", "manifest")
    _g(bound_repo, "tag", "-f", "-a", "pap-v1", "-m", "signed plan")
    return bound_repo, raw


def test_french_data_passes_when_zips_and_members_match(french_repo):
    repo, raw = french_repo
    ch.check_french_data(repo, raw)


def test_french_data_refuses_a_zip_that_differs_from_the_tagged_manifest(french_repo):
    repo, raw = french_repo
    (raw / "french/ff5_daily.zip").write_bytes(_zip_bytes({"ff5_daily.csv": b"other\n"}))
    with pytest.raises(ch.BindingError, match="ff5_daily.*SHA-256"):
        ch.check_french_data(repo, raw)


def test_french_data_uses_the_manifest_at_the_tag_not_the_working_tree(french_repo):
    import json
    repo, raw = french_repo
    body = _zip_bytes({"ff5_daily.csv": b"other\n"})
    (raw / "french/ff5_daily.zip").write_bytes(body)
    m = json.loads((raw / "MANIFEST.json").read_text())
    m["ff5_daily"]["sha256"] = hashlib.sha256(body).hexdigest()
    (raw / "MANIFEST.json").write_text(json.dumps(m))  # edited, not tagged
    with pytest.raises(ch.BindingError, match="SHA-256"):
        ch.check_french_data(repo, raw)


def test_french_data_refuses_an_edited_extracted_member(french_repo):
    repo, raw = french_repo
    (raw / "french/mom_daily/mom_daily.csv").write_bytes(b"edited\n")
    with pytest.raises(ch.BindingError, match="CRC32"):
        ch.check_french_data(repo, raw)


@pytest.mark.parametrize("change", ["extra", "missing"])
def test_french_data_refuses_extra_or_missing_members(french_repo, change):
    repo, raw = french_repo
    d = raw / "french/ff49_daily"
    if change == "extra":
        (d / "stale.csv").write_text("old\n")
    else:
        (d / "ff49_daily.csv").unlink()
    with pytest.raises(ch.BindingError, match="members"):
        ch.check_french_data(repo, raw)


def test_french_data_requires_the_confirmatory_keys(french_repo):
    import json
    repo, raw = french_repo
    m = json.loads((raw / "MANIFEST.json").read_text())
    del m["mom_daily"]
    (raw / "MANIFEST.json").write_text(json.dumps(m))
    _g(repo, "commit", "-q", "-am", "drop")
    _g(repo, "tag", "-f", "-a", "pap-v1", "-m", "signed plan")
    with pytest.raises(ch.BindingError, match="mom_daily"):
        ch.check_french_data(repo, raw)


def test_report_prints_the_r13_mde(unsealed, tmp_path):
    r, f = _market(date(1989, 6, 1), date(2026, 9, 30))
    unsealed["state"].update(returns=r, factors=f)
    out = tmp_path / "c.md"
    res = ch.run(out=out)
    text = out.read_text()
    from scipy import stats
    for hyp, v in (("H5", "h5_r13"), ("H5b", "h5b_r13")):
        mde = (ch.FROZEN[f"crit_{v}_0.025"] + stats.t.ppf(0.80, 21)) * ch.FROZEN[f"s_{v}"]
        assert res["decision"]["mde_r13"][hyp] == pytest.approx(mde)
        assert f"R13 (Softw dropped) MDE at Holm level 0.025: {mde * 100:.2f} pp" in text
    assert text.count("R13 (Softw dropped) MDE") == 2
