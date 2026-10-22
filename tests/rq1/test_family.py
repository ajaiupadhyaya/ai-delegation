"""RQ1 family: Holm over {H1, H3, H4} at 0.0375, H2 alone at 0.0125 (PAP §4, §4.0, D17, D22).

Synthetic `HypothesisResult` inputs only; no AEI outcome is read here.
"""

import math

import pytest

from aideleg.rq1 import family
from aideleg.rq1.result import Coef, HypothesisResult


def _coef(name: str, est: float, p: float) -> Coef:
    return Coef(name, est, 1.0, est - 1.96, est + 1.96, p, 100)


def _h1(b_e: float, b_w: float, p_e: float = 0.001, p_w: float = 0.002) -> HypothesisResult:
    coefs = {"human_education_years_mean": _coef("human_education_years_mean", b_e, p_e),
             "log_wage": _coef("log_wage", b_w, p_w)}
    return HypothesisResult("H1", "automation_pct", coefs, p_family=max(p_e, p_w),
                            diagnostics={"tested": list(coefs)})


def _h2(beta: float, p_c: float, p_w: float) -> HypothesisResult:
    return HypothesisResult("H2", "automation_pct", {"trend": _coef("trend", beta, p_c)},
                            p_family=p_c, diagnostics={"p_wild": p_w})


def _h3(gamma: float, p: float = 0.001) -> HypothesisResult:
    # A covariate listed first: selection is by name, not position.
    coefs = {"log_wage": _coef("log_wage", -9.0, 0.5), "error_cost": _coef("error_cost", gamma, p)}
    return HypothesisResult("H3", "validation_pct", coefs, p_family=p,
                            diagnostics={"tested": ["error_cost"]})


def _h4(b1: float, b2: float, p: float = 0.001) -> HypothesisResult:
    coefs = {"mix": _coef("mix", 0.5, 0.3), "log_aui": _coef("log_aui", b1, 0.01),
             "log_income": _coef("log_income", b2, 0.02)}
    return HypothesisResult("H4", "automation_pct", coefs, p_family=p,
                            diagnostics={"tested": ["log_aui", "log_income"]})


def _all(h1=None, h2=None, h3=None, h4=None) -> dict[str, HypothesisResult]:
    return {"H1": h1 or _h1(-1.0, -2.0), "H2": h2 or _h2(0.5, 0.001, 0.004),
            "H3": h3 or _h3(3.0), "H4": h4 or _h4(1.0, 1.0)}


def test_constants():
    assert family.RQ1_FAMILY == ("H1", "H3", "H4")
    assert family.FAMILY_ALPHA == 0.0375
    assert family.H2_ALPHA == 0.0125
    assert family.SPLIT_STATEMENT == (
        "RQ1's α = 0.05 is split (D22): H2 is tested on its own at α = 0.0125, and {H1, H3, H4} "
        "by Holm at family-wise α = 0.0375, so the RQ1 family-wise error is at most 0.05.")


def test_holm_stops_at_first_failure():
    out = family.holm({"H1": 0.01, "H3": 0.02, "H4": 0.03}, 0.0375)
    assert [out[h].rank for h in ("H1", "H3", "H4")] == [1, 2, 3]
    assert [out[h].level for h in ("H1", "H3", "H4")] == pytest.approx([0.0125, 0.01875, 0.0375])
    assert [out[h].rejected for h in ("H1", "H3", "H4")] == [True, False, False]


def test_holm_later_pass_after_failure_is_not_rejected():
    # H4's p would pass its own level, but Holm stopped at H3.
    out = family.holm({"H1": 0.001, "H3": 0.03, "H4": 0.031}, 0.0375)
    assert [out[h].rejected for h in ("H1", "H3", "H4")] == [True, False, False]


def test_holm_all_reject():
    out = family.holm({"H1": 0.012, "H3": 0.018, "H4": 0.037}, 0.0375)
    assert all(s.rejected for s in out.values())


def test_holm_ties_by_name():
    out = family.holm({"H4": 0.01, "H1": 0.01, "H3": 0.5}, 0.0375)
    assert (out["H1"].rank, out["H1"].rejected) == (1, True)
    assert out["H1"].level == pytest.approx(0.0125)
    assert (out["H4"].rank, out["H4"].rejected) == (2, True)
    assert out["H4"].level == pytest.approx(0.01875)
    assert (out["H3"].rank, out["H3"].rejected) == (3, False)
    assert out["H3"].level == pytest.approx(0.0375)


def test_h1_statuses():
    sup = family.decide(_all(h1=_h1(-1.0, -2.0)))["H1"]
    assert (sup.status, sup.rejected) == ("supported", True)
    assert sup.text == (
        "H1 is supported: Holm over {H1, H3, H4} at family-wise 0.0375 rejects at step 3 "
        "(level 0.03750, p = 0.0020). "
        "human_education_years_mean = -1.000 (95% CI [-2.960, 0.960], p = 0.0010); "
        "log_wage = -2.000 (95% CI [-3.960, -0.040], p = 0.0020)")
    con = family.decide(_all(h1=_h1(1.0, 2.0)))["H1"]
    assert (con.status, con.rejected) == ("contradicts", True)
    assert con.text == (
        "H1: the null is rejected, and the estimate contradicts the hypothesis "
        "(human_education_years_mean = 1.000 (95% CI [-0.960, 2.960], p = 0.0010); "
        "log_wage = 2.000 (95% CI [0.040, 3.960], p = 0.0020)).")
    mixed = family.decide(_all(h1=_h1(-1.0, 2.0)))["H1"]
    assert (mixed.status, mixed.rejected) == ("rejected_mixed_sign", True)
    assert mixed.text == (
        "H1: the null is rejected, but log_wage has the opposite sign, which contradicts the "
        "hypothesis, so H1 is not supported (human_education_years_mean = -1.000 (95% CI "
        "[-2.960, 0.960], p = 0.0010); log_wage = 2.000 (95% CI [0.040, 3.960], p = 0.0020)).")
    mixed2 = family.decide(_all(h1=_h1(1.0, -2.0)))["H1"]
    assert mixed2.status == "rejected_mixed_sign"
    assert mixed2.text.startswith(
        "H1: the null is rejected, but human_education_years_mean has the opposite sign, ")
    nr = family.decide(_all(h1=_h1(-1.0, -2.0, p_w=0.2)))["H1"]
    assert (nr.status, nr.rejected) == ("not_rejected", False)
    assert nr.text.startswith("H1 is not rejected (H0: β_e = 0 or β_w = 0). ")


def test_h1_not_rejected_when_holm_stops_earlier():
    # H1 p = 0.03 is below its own level 0.0375 at step 3, but H3 (step 2) fails first.
    res = _all(h1=_h1(-1.0, -2.0, p_w=0.03), h3=_h3(3.0, p=0.02), h4=_h4(1.0, 1.0, p=0.001))
    out = family.decide(res)
    assert out["H4"].status == "supported"
    assert out["H3"].status == "not_rejected"
    assert out["H1"].status == "not_rejected"


def test_h3_statuses():
    sup = family.decide(_all(h3=_h3(3.0)))["H3"]
    assert sup.status == "supported"
    assert sup.text == (
        "H3 is supported: Holm over {H1, H3, H4} at family-wise 0.0375 rejects at step 1 "
        "(level 0.01250, p = 0.0010). error_cost = 3.000 (95% CI [1.040, 4.960], p = 0.0010)")
    assert family.decide(_all(h3=_h3(-3.0)))["H3"].status == "contradicts"
    nr = family.decide(_all(h3=_h3(3.0, p=0.5)))["H3"]
    assert nr.status == "not_rejected"
    assert nr.text.startswith("H3 is not rejected (H0: γ = 0). ")


def test_h4_two_sided():
    d = family.decide(_all(h4=_h4(-1.0, -2.0)))["H4"]
    assert (d.status, d.rejected) == ("supported", True)
    assert d.text == (
        "H4 is supported: Holm over {H1, H3, H4} at family-wise 0.0375 rejects at step 2 "
        "(level 0.01875, p = 0.0010). log_aui = -1.000 (95% CI [-2.960, 0.960], p = 0.0100); "
        "log_income = -2.000 (95% CI [-3.960, -0.040], p = 0.0200)")
    # Only the two tested coefficients are reported in the decision text.
    assert "log_aui" in d.text and "log_income" in d.text and "mix" not in d.text
    nr = family.decide(_all(h4=_h4(1.0, 1.0, p=0.5)))["H4"]
    assert nr.status == "not_rejected"
    assert nr.text.startswith("H4 is not rejected (H0: b₁ = b₂ = 0). ")


def test_h2_supported():
    d = family.decide(_all(h2=_h2(0.5, 0.001, 0.004)))["H2"]
    assert (d.status, d.rejected, d.level) == ("supported", True, 0.0125)
    assert d.text == (
        "H2 is supported: task-clustered p = 0.0010 and release-level wild bootstrap "
        "p = 0.0040, both ≤ 0.0125, and β > 0. trend = 0.500 (95% CI [-1.460, 2.460], "
        "p = 0.0010)")


def test_h2_contradicts():
    d = family.decide(_all(h2=_h2(-0.5, 0.001, 0.004)))["H2"]
    assert (d.status, d.rejected) == ("contradicts", True)


def test_h2_requires_all_three():
    d = family.decide(_all(h2=_h2(0.5, 0.001, 0.02)))["H2"]
    assert (d.status, d.rejected) == ("not_rejected", False)
    assert "release-level wild bootstrap p = 0.0200 > 0.0125" in d.text
    assert d.text == (
        "H2 is not rejected (H0: β = 0). trend = 0.500 (95% CI [-1.460, 2.460], p = 0.0010). "
        "Not met: release-level wild bootstrap p = 0.0200 > 0.0125.")
    assert "> 0.0125" not in d.text.replace("release-level wild bootstrap p = 0.0200 > 0.0125", "")


def test_h2_task_clustered_fails_alone():
    d = family.decide(_all(h2=_h2(0.5, 0.02, 0.004)))["H2"]
    assert d.status == "not_rejected"
    assert "task-clustered p = 0.0200 > 0.0125" in d.text
    assert "release-level wild bootstrap p =" not in d.text


def test_h2_both_fail_named():
    d = family.decide(_all(h2=_h2(-0.5, 0.3, 0.4)))["H2"]
    assert d.status == "not_rejected"
    assert "task-clustered p = 0.3000 > 0.0125" in d.text
    assert "release-level wild bootstrap p = 0.4000 > 0.0125" in d.text
    assert d.text.startswith("H2 is not rejected (H0: β = 0). ")


def test_h2_not_in_holm_family():
    # H2's tiny p must not change the Holm levels of {H1, H3, H4}.
    out = family.decide(_all(h2=_h2(0.5, 1e-9, 0.004)))
    assert sorted(out[h].level for h in ("H1", "H3", "H4")) == pytest.approx(
        [0.0125, 0.01875, 0.0375])


def test_decide_requires_the_four_hypotheses():
    res = _all()
    del res["H3"]
    with pytest.raises(ValueError):
        family.decide(res)


def test_wording_never_says_no_effect():
    cases = [_all(), _all(h1=_h1(1.0, 2.0)), _all(h1=_h1(-1.0, 2.0)),
             _all(h1=_h1(-1.0, -2.0, p_w=0.5), h3=_h3(3.0, p=0.5), h4=_h4(1.0, 1.0, p=0.5),
                  h2=_h2(0.5, 0.3, 0.4)),
             _all(h3=_h3(-3.0), h2=_h2(-0.5, 0.001, 0.001)), _all(h2=_h2(0.5, 0.001, 0.02))]
    for res in cases:
        for d in family.decide(res).values():
            assert "no effect" not in d.text.lower()


def test_holm_exact_levels_at_the_boundary():
    # 0.0375 / 3 is 0.012499999999999999 in floats; the exact level is 0.0125.
    out = family.holm({"H1": 0.0125, "H3": 0.5, "H4": 0.6}, 0.0375)
    assert out["H1"].rejected and out["H1"].level == 0.0125
    out = family.holm({"H1": 0.001, "H3": 0.01875, "H4": 0.6}, 0.0375)
    assert out["H3"].rejected and out["H3"].level == 0.01875
    assert not out["H4"].rejected


def test_h2_exact_alpha_at_the_boundary():
    assert family.decide(_all(h2=_h2(0.5, 0.0125, 0.0125)))["H2"].status == "supported"


def test_holm_nan_sorts_last_and_is_not_rejected():
    out = family.holm({"H1": math.nan, "H3": 0.001, "H4": 0.002}, 0.0375)
    assert (out["H1"].rank, out["H1"].rejected) == (3, False)
    assert out["H3"].rejected and out["H4"].rejected
    res = _all(h1=HypothesisResult("H1", "automation_pct", _h1(-1.0, -2.0).coefs,
                                   p_family=math.nan,
                                   diagnostics={"tested": ["human_education_years_mean",
                                                           "log_wage"]}))
    assert family.decide(res)["H1"].status == "not_rejected"


def test_zero_estimate_is_rejected_but_not_supported():
    d = family.decide(_all(h3=_h3(0.0)))["H3"]
    assert (d.status, d.rejected) == ("rejected_zero_estimate", True)
    assert d.text == (
        "H3: the null is rejected, but the estimate of error_cost is exactly 0, so the hypothesis "
        "is not supported (error_cost = 0.000 (95% CI [-1.960, 1.960], p = 0.0010)).")
    assert family.decide(_all(h1=_h1(0.0, -2.0)))["H1"].status == "rejected_zero_estimate"
    d2 = family.decide(_all(h2=_h2(0.0, 0.001, 0.004)))["H2"]
    assert (d2.status, d2.rejected) == ("rejected_zero_estimate", True)


def test_structural_errors_raise():
    bad = _all()
    bad["H4"].diagnostics.pop("tested")
    with pytest.raises(ValueError, match="tested"):
        family.decide(bad)
    bad = _all()
    bad["H3"].diagnostics["tested"] = ["missing_coef"]
    with pytest.raises(ValueError, match="missing_coef"):
        family.decide(bad)
    bad = _all()
    bad["H2"].diagnostics.pop("p_wild")
    with pytest.raises(ValueError, match="p_wild"):
        family.decide(bad)


def test_h1_nan_estimate_is_not_supported():
    d = family.decide(_all(h1=_h1(-1.0, math.nan)))["H1"]
    assert (d.status, d.rejected) == ("not_supported_nonfinite", False)
    assert d.text == (
        "H1 is not supported: log_wage has a non-finite estimate (human_education_years_mean"
        " = -1.000 (95% CI [-2.960, 0.960], p = 0.0010); log_wage = nan (95% CI [nan, nan], "
        "p = 0.0020)).")


def test_nonfinite_se_is_not_supported():
    res = _all()
    c = res["H3"].coefs["error_cost"]
    res["H3"].coefs["error_cost"] = Coef(c.name, c.estimate, math.inf, c.ci_low, c.ci_high,
                                         c.p, c.df)
    d = family.decide(res)["H3"]
    assert (d.status, d.rejected) == ("not_supported_nonfinite", False)
    assert "error_cost has a non-finite se" in d.text


def test_h2_nan_p():
    d = family.decide(_all(h2=_h2(0.5, math.nan, 0.004)))["H2"]
    assert (d.status, d.rejected) == ("not_supported_nonfinite", False)
    assert "trend has a non-finite p" in d.text
    assert "nan > 0.0125" not in d.text
    w = family.decide(_all(h2=_h2(0.5, 0.001, math.nan)))["H2"]
    assert (w.status, w.rejected) == ("not_rejected", False)
    assert w.text.endswith("Not met: release-level wild bootstrap p is not finite.")
    assert "nan > 0.0125" not in w.text
