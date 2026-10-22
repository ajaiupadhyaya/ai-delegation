"""The write-once RQ1 runner (PAP §0.5 P-RQ1). Synthetic inputs and tmp paths only: nothing
here reads AEI outcomes or writes under docs/results."""

import json
import subprocess

import polars as pl
import pytest
import synth

from aideleg.config import ROOT
from aideleg.rq1 import confirm

OUTPUTS = (confirm.JSON_NAME, confirm.MD_NAME, confirm.LOG_NAME)
STATUSES = {"supported", "contradicts", "rejected_mixed_sign", "rejected_zero_estimate",
            "not_supported_nonfinite", "not_rejected"}


@pytest.fixture
def clean(monkeypatch):
    """A clean tree (HEAD "abc"), and no real input is ever loaded."""
    monkeypatch.setattr(confirm, "check_clean", lambda repo=ROOT: "abc")

    def boom():
        raise AssertionError("loaded")

    monkeypatch.setattr(confirm, "load_inputs", boom)


@pytest.fixture(scope="module")
def inputs():
    return synth.synthetic_inputs()


def test_refuses_when_marker_exists_before_loading(clean, tmp_path):
    (tmp_path / confirm.MARKER_NAME).write_text("earlier attempt\n")
    with pytest.raises(confirm.RefusedError):
        confirm.run(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == [confirm.MARKER_NAME]


@pytest.mark.parametrize("name", OUTPUTS)
def test_refuses_when_output_exists(clean, tmp_path, name):
    (tmp_path / name).write_text("x")
    with pytest.raises(confirm.RefusedError):
        confirm.run(tmp_path)
    assert not (tmp_path / confirm.MARKER_NAME).exists()


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                    "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
                   check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/a.py").write_text("a = 1\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "one")
    return tmp_path


def test_refuses_dirty_tree(repo):
    _git(repo, "tag", "-a", "pap-v1", "-m", "frozen")
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()
    assert confirm.check_clean(repo) == head
    (repo / "src/x.py").write_text("shadow = 1\n")
    with pytest.raises(confirm.RefusedError, match="not clean"):
        confirm.check_clean(repo)
    (repo / "src/x.py").unlink()
    (repo / "src/a.py").write_text("a = 2\n")
    with pytest.raises(confirm.RefusedError, match="not clean"):
        confirm.check_clean(repo)


def test_refuses_lightweight_or_missing_tag(repo):
    with pytest.raises(confirm.RefusedError, match="annotated"):
        confirm.check_clean(repo)
    _git(repo, "tag", "pap-v1")
    with pytest.raises(confirm.RefusedError, match="annotated"):
        confirm.check_clean(repo)


def test_refuses_head_not_descending_from_tag(repo):
    _git(repo, "tag", "-a", "pap-v1", "-m", "frozen")
    _git(repo, "checkout", "-q", "--orphan", "other")  # a root commit unrelated to pap-v1
    _git(repo, "commit", "-q", "-m", "unrelated")
    with pytest.raises(confirm.RefusedError, match="descend"):
        confirm.check_clean(repo)


def test_dry_run_refuses_docs_results(clean):
    target = ROOT / "docs/results/rq1-dry-run-test"
    with pytest.raises(confirm.RefusedError, match="docs/results"):
        confirm.run(target, scramble_seed=1)
    assert not target.exists()


def test_scramble_changes_only_outcomes(inputs):
    panel = inputs.panel
    out = confirm.scramble_outcomes(panel, 1)
    assert out.height == panel.height and out.columns == panel.columns
    is_outcome = pl.col("metric").is_in(sorted(confirm.OUTCOME_METRICS))
    before, after = panel.filter(is_outcome), out.filter(is_outcome)
    assert before.height > 0
    assert (before["value"] != after["value"]).all()
    assert before.drop("value").equals(after.drop("value"))
    auto = after.filter(pl.col("metric") == "ai_autonomy_mean")["value"]
    assert auto.min() >= 1 and auto.max() <= 5
    rest = after.filter(pl.col("metric") != "ai_autonomy_mean")["value"]
    assert rest.min() >= 0 and rest.max() <= 100
    assert panel.filter(~is_outcome).equals(out.filter(~is_outcome))
    for m in ("pct", "human_education_years_mean", "usage_per_capita_index", "usage_pct"):
        assert panel.filter(pl.col("metric") == m).height > 0
    assert confirm.scramble_outcomes(panel, 1).equals(out)


def test_scramble_keeps_nulls_and_nans():
    panel = pl.DataFrame({"metric": ["automation_pct", "automation_pct", "automation_pct",
                                     "pct"],
                          "value": [None, float("nan"), 40.0, 3.0]})
    out = confirm.scramble_outcomes(panel, 1)["value"].to_list()
    assert out[0] is None and out[1] != out[1] and out[2] != 40.0 and out[3] == 3.0


def test_failure_after_marker_writes_traceback(clean, tmp_path, monkeypatch, inputs):
    def broken(*a, **k):
        raise RuntimeError("H2 estimator failed")

    monkeypatch.setattr(confirm, "estimate_h2", broken)
    with pytest.raises(RuntimeError, match="H2 estimator failed"):
        confirm.run(tmp_path, scramble_seed=1, inputs=inputs)
    assert (tmp_path / confirm.MARKER_NAME).exists()
    md = (tmp_path / confirm.MD_NAME).read_text()
    assert "Traceback" in md and "H2 estimator failed" in md
    assert not (tmp_path / confirm.JSON_NAME).exists()
    with pytest.raises(confirm.RefusedError):  # the attempt blocks any rerun
        confirm.run(tmp_path, scramble_seed=1, inputs=inputs)


def test_results_are_written_before_decide(clean, tmp_path, monkeypatch, inputs):
    def broken(results):
        raise RuntimeError("decision layer failed")

    monkeypatch.setattr(confirm, "decide", broken)
    with pytest.raises(RuntimeError, match="decision layer failed"):
        confirm.run(tmp_path, scramble_seed=1, inputs=inputs)
    log = (tmp_path / confirm.LOG_NAME).read_text()
    line = next(x for x in log.splitlines() if confirm.RESULTS_LOG_PREFIX in x)
    results = json.loads(line.split(confirm.RESULTS_LOG_PREFIX, 1)[1])
    assert set(results) == {"H1", "H2", "H3", "H4"}
    assert "Traceback" in (tmp_path / confirm.MD_NAME).read_text()


def test_run_on_synthetic_inputs_writes_schema(clean, tmp_path, inputs):
    out = confirm.run(tmp_path, scramble_seed=1, inputs=inputs)
    data = json.loads((tmp_path / confirm.JSON_NAME).read_text())
    assert data == out
    assert list(data) == ["meta", "alpha", "results", "decisions"]
    assert set(data["results"]) == {"H1", "H2", "H3", "H4"}
    assert data["alpha"]["family"] == 0.0375 and data["alpha"]["H2"] == 0.0125
    assert data["alpha"]["members"] == ["H1", "H3", "H4"]
    assert {d["status"] for d in data["decisions"].values()} <= STATUSES
    meta = data["meta"]
    assert meta["scrambled"] is True and meta["head"] == "abc"
    assert set(meta["versions"]) == {"python", "numpy", "scipy", "polars", "statsmodels"}
    assert list(meta["blobs"]) == list(confirm.BOUND_FILES)
    assert meta["checks"]["h2_nonpositive_weight_tasks"] == 0
    assert meta["checks"]["pattern_sum_max_abs_dev"] < 1e-9
    assert meta["checks"]["automation_bucket_max_abs_dev"] < 1e-9
    for h in ("H1", "H2", "H3", "H4"):
        assert data["results"][h]["sample"]
    assert data["results"]["H4"]["sample"]["n"] == len(synth.SYNTH_COUNTRIES)
    md = (tmp_path / confirm.MD_NAME).read_text()
    assert md.startswith("Generated by `aideleg.rq1.confirm`. Do not edit by hand.")
    assert "conversations matched to O*NET tasks" in md
    assert "Holm at family-wise α = 0.0375" in md and "SCRAMBLED" in md
    for d in data["decisions"].values():
        assert d["text"] in md
    log = (tmp_path / confirm.LOG_NAME).read_text()
    assert "H1 fitted in" in log and confirm.RESULTS_LOG_PREFIX in log
    assert (tmp_path / confirm.MARKER_NAME).read_text().split()[-1] == "abc"


def test_main_dry_run_prints_only_coverage(clean, tmp_path, monkeypatch, inputs, capsys):
    monkeypatch.setattr(confirm, "load_inputs", lambda: inputs)
    assert confirm.main(["--dry-run", str(tmp_path / "dry")]) == 0
    printed = capsys.readouterr().out
    assert "completed without exception" in printed and "sample" in printed
    assert "estimate" not in printed and "p_family" not in printed


def test_main_reports_refusal(clean, tmp_path, capsys):
    (tmp_path / confirm.MARKER_NAME).write_text("x")
    assert confirm.main(["--dry-run", str(tmp_path)]) == 2
    assert "refused" in capsys.readouterr().err


def test_bound_files_exist():
    assert len(set(confirm.BOUND_FILES)) == len(confirm.BOUND_FILES) == 13
    for path in confirm.BOUND_FILES:
        assert (ROOT / path).is_file(), path
