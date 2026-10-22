"""H1 and H3 estimators (PAP §4.1, §4.3, D17, P13), on synthetic data and permuted outcomes
only. No real outcome enters these tests (P-RQ1)."""

import dataclasses

import numpy as np
import polars as pl
import pytest
import synth

from aideleg.config import SEED
from aideleg.rq1 import h1h3
from aideleg.rq1.result import HypothesisResult

EDUC, WAGE = "human_education_years_mean", "log_wage"


def _permute_across_tasks(tr, col: str, rng: np.random.Generator):
    """Move each task's value of `col` to another task, with all of its rows."""
    tasks = tr.rows.group_by("task_code").agg(pl.col(col).first()).sort("task_code")
    shuffled = tasks.with_columns(pl.Series(col, rng.permutation(tasks[col].to_numpy())))
    rows = tr.rows.drop(col).join(shuffled, on="task_code", how="left").select(tr.rows.columns)
    return dataclasses.replace(tr, rows=rows)


def test_h1_recovers_planted_education():
    r = h1h3.estimate_h1(synth.task_rows(SEED, beta_educ=-2))
    assert isinstance(r, HypothesisResult) and r.hypothesis == "H1"
    assert r.outcome == "automation_pct"
    assert set(r.coefs) == {EDUC, WAGE}
    assert r.coefs[EDUC].estimate == pytest.approx(-2, abs=0.3)
    assert r.coefs[EDUC].p < 0.01
    # p_family = max(p_educ, p_wage) (D17) is small only when both effects are planted.
    both = h1h3.estimate_h1(synth.task_rows(SEED, beta_educ=-2, beta_wage=-3))
    assert both.coefs[EDUC].estimate == pytest.approx(-2, abs=0.3)
    assert both.p_family < 0.01


def test_h1_wage_coefficient_is_attenuated_as_p13_states():
    r = h1h3.estimate_h1(synth.task_rows(SEED, n_task=2000, beta_wage=-3))
    att = r.diagnostics["attenuation_log_wage"]
    assert 0 < att < 1
    est = r.coefs[WAGE].estimate / att
    assert est == pytest.approx(-3, abs=0.4)
    assert abs(est - -3) < 3 * r.coefs[WAGE].se / att


def _wage_correlated_education(tr, rng: np.random.Generator):
    """Education := 2 x the task's mean log wage + N(0, 2): correlated with the wage."""
    bar = (tr.rows.group_by("task_code").agg(pl.col(WAGE).mean().fill_null(11.0).alias("_b"))
           .sort("task_code"))
    bar = bar.with_columns(_e=2 * pl.col("_b") + pl.Series(rng.normal(0, 2, bar.height)))
    rows = (tr.rows.join(bar.select("task_code", "_e"), on="task_code", how="left")
            .with_columns(pl.col("_e").alias(EDUC)).drop("_e"))
    return dataclasses.replace(tr, rows=rows)


def test_attenuation_uses_the_fwl_residual_of_the_wage():
    """P13 factor: log wage residualised on the IWA FE and on education (FWL)."""
    tr = _wage_correlated_education(synth.task_rows(SEED, n_task=2000, beta_wage=-3),
                                    np.random.default_rng(SEED))
    r = h1h3.estimate_h1(tr)
    rows = tr.rows.filter(pl.col(WAGE).is_not_null())
    args = (rows[WAGE].to_numpy(), rows["weight"].to_numpy(), rows["family"].to_numpy(),
            rows["task_code"].to_numpy())
    iwa_only = h1h3.attenuation_factor(*args)
    fwl = h1h3.attenuation_factor(*args, controls=rows[EDUC].to_numpy())
    assert abs(fwl - iwa_only) > 0.05
    att = r.diagnostics["attenuation_log_wage"]
    assert att == pytest.approx(fwl)
    est = r.coefs[WAGE].estimate / att
    assert est == pytest.approx(-3, abs=0.4)
    assert abs(est - -3) < 3 * r.coefs[WAGE].se / att


def test_attenuation_factor_hand_case():
    x = np.array([0.0, 2.0, 2.0, 4.0])
    got = h1h3.attenuation_factor(x, np.ones(4), np.array(["f"] * 4), np.array([0, 0, 1, 1]))
    assert got == pytest.approx(0.5)


def test_h1_p_family_is_max():
    r = h1h3.estimate_h1(synth.task_rows(SEED, beta_educ=-0.5, beta_wage=-1))
    assert r.p_family == max(r.coefs[EDUC].p, r.coefs[WAGE].p)


def test_h1_size_under_permuted_outcome():
    tr = synth.task_rows(SEED, beta_educ=0)
    rng = np.random.default_rng(SEED)
    rej_family = rej_educ = 0
    n = 200
    for _ in range(n):
        r = h1h3.estimate_h1(_permute_across_tasks(tr, "automation_pct", rng))
        rej_family += r.p_family <= 0.05
        rej_educ += r.coefs[EDUC].p <= 0.05
    assert rej_family / n <= 0.08
    assert 0.01 <= rej_educ / n <= 0.10


def test_h3_recovers_gamma_and_attenuation_one():
    r = h1h3.estimate_h3(synth.task_rows(SEED, n_task=2000, gamma=5,
                                         pure_error_cost_tasks=True))
    assert r.hypothesis == "H3" and r.outcome == "validation_pct"
    assert set(r.coefs) == {"error_cost"}
    g = r.coefs["error_cost"]
    assert g.estimate == pytest.approx(5, abs=0.5)
    assert abs(g.estimate - 5) < 3 * g.se
    assert r.p_family == r.coefs["error_cost"].p
    assert r.diagnostics["attenuation_error_cost"] == pytest.approx(1.0)


def test_h3_ignores_wage_missingness():
    tr = synth.task_rows(SEED)
    no_code = tr.rows.filter(pl.col("wage_status") == "no_oews_code")
    suppressed = tr.rows.filter(pl.col("wage_status") == "suppressed")
    assert no_code.height > 0 and suppressed.height > 0
    h1, h3 = h1h3.estimate_h1(tr), h1h3.estimate_h3(tr)
    assert h3.sample["n_rows"] == tr.rows.height
    assert h1.sample["n_rows"] == tr.rows.height - no_code.height - suppressed.height
    assert h1.drops["no_oews_code"] == pytest.approx(
        no_code["weight"].sum() / tr.total_weight * 100)
    assert h1.drops["wage_suppressed"] == pytest.approx(
        suppressed["weight"].sum() / tr.total_weight * 100)
    assert "no_oews_code" not in h3.drops and "wage_suppressed" not in h3.drops
    for reason, share in tr.structural_drops.items():
        assert h1.drops[reason] == h3.drops[reason] == share


def test_variable_drops_are_counted_once_in_variable_order():
    """A row missing the outcome and its wage counts under the outcome only; weights are not
    renormalised."""
    tr = synth.task_rows(SEED)
    rows = tr.rows.with_row_index("_i")
    no_code = rows.filter(pl.col("wage_status") == "no_oews_code")["_i"].to_list()
    hit_outcome, hit_educ = no_code[0], rows.filter(
        pl.col("wage_status") == "published")["_i"].to_list()[0]
    rows = rows.with_columns(
        automation_pct=pl.when(pl.col("_i") == hit_outcome).then(None)
        .otherwise(pl.col("automation_pct")),
        human_education_years_mean=pl.when(pl.col("_i") == hit_educ).then(float("nan"))
        .otherwise(pl.col("human_education_years_mean"))).drop("_i")
    tr2 = dataclasses.replace(tr, rows=rows)
    r = h1h3.estimate_h1(tr2)
    w = tr.rows["weight"]
    pct = lambda i: w[i] / tr.total_weight * 100  # noqa: E731
    assert r.drops["missing_automation_pct"] == pytest.approx(pct(hit_outcome))
    assert r.drops[f"missing_{EDUC}"] == pytest.approx(pct(hit_educ))
    no_code_share = sum(pct(i) for i in no_code) - pct(hit_outcome)
    assert r.drops["no_oews_code"] == pytest.approx(no_code_share)
    assert list(r.drops)[:4] == list(tr.structural_drops)
    assert list(r.drops)[4:6] == ["missing_automation_pct", f"missing_{EDUC}"]


def test_outcome_is_an_argument():
    planted = synth.task_rows(SEED, beta_educ=-2)
    rows = planted.rows.with_columns(ai_autonomy_mean=pl.col("automation_pct"))
    tr = _permute_across_tasks(dataclasses.replace(planted, rows=rows), "automation_pct",
                               np.random.default_rng(SEED))
    r = h1h3.estimate_h1(tr, outcome="ai_autonomy_mean")
    assert r.outcome == "ai_autonomy_mean"
    assert r.coefs[EDUC].estimate == pytest.approx(-2, abs=0.3)
    assert h1h3.estimate_h1(tr).coefs[EDUC].estimate == pytest.approx(0, abs=0.5)
    r3 = h1h3.estimate_h3(tr, covariates=(EDUC, WAGE))
    assert list(r3.coefs) == ["error_cost", EDUC, WAGE]
    assert r3.p_family == r3.coefs["error_cost"].p
    assert set(r3.diagnostics["covariates_psd"]) == {"psd_clipped", "min_eigenvalue",
                                                     "zero_variance_fallback"}
    assert "covariates_psd" not in h1h3.estimate_h3(tr).diagnostics


def test_result_fields_and_json():
    tr = synth.task_rows(SEED, beta_educ=-1)
    r = h1h3.estimate_h1(tr)
    assert set(r.sample) == {"n_rows", "n_tasks", "n_occ", "n_family", "g_occ", "g_task",
                             "df_inference"}
    assert r.sample["df_inference"] == min(r.sample["g_occ"], r.sample["g_task"]) - 1
    assert r.sample["n_occ"] == r.sample["g_occ"] and r.sample["n_tasks"] == r.sample["g_task"]
    for k in ("df_inference", "n_obs", "g_occ", "g_task", "psd_clipped", "min_eigenvalue",
              "zero_variance_fallback", "se_oneway_occ", "se_oneway_task", "p_oneway_occ",
              "attenuation_log_wage"):
        assert k in r.diagnostics
    assert "coefs" not in r.diagnostics
    r.to_dict()


def test_non_psd_note_wording(monkeypatch):
    real = h1h3.twoway_wls

    def clipped(*a, **k):
        return dataclasses.replace(real(*a, **k), psd_clipped=True, min_eigenvalue=-0.25,
                                   zero_variance_fallback=[WAGE])

    monkeypatch.setattr(h1h3, "twoway_wls", clipped)
    r = h1h3.estimate_h1(synth.task_rows(SEED))
    assert r.notes == [f"non-PSD rule applied to [{EDUC}, {WAGE}]: smallest eigenvalue -0.25; "
                       f"SE of {WAGE} set to the larger one-way cluster SE"]


def test_tested_coefficients_are_named_in_diagnostics():
    tr = synth.task_rows(SEED)
    assert h1h3.estimate_h1(tr).diagnostics["tested"] == ["human_education_years_mean",
                                                          "log_wage"]
    h3 = h1h3.estimate_h3(tr, covariates=("human_education_years_mean",))
    assert h3.diagnostics["tested"] == ["error_cost"]
