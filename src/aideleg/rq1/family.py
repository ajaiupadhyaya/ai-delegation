"""The RQ1 testing family, decision rules and fixed wording (PAP §4, §4.0, D17, D22, §0.2).

- {H1, H3, H4} are tested by Holm at family-wise α = 0.0375 on each result's `p_family` (D17).
- H2 is tested on its own at α = 0.0125 (D22). It needs the task-clustered p, the release-level
  wild bootstrap p (`diagnostics["p_wild"]`) and β > 0.
- A significant estimate of the wrong sign "contradicts the hypothesis" (§0.2). A non-rejection
  names its null and is never worded as an absence of effect.
- Levels and comparisons are exact: each α and p is read as the decimal Python prints for it
  (`Fraction(repr(x))`), so p = 0.0125 meets the level 0.0375/3.
"""

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from aideleg.rq1.result import Coef, HypothesisResult

RQ1_FAMILY = ("H1", "H3", "H4")
FAMILY_ALPHA = 0.0375
H2_ALPHA = 0.0125
SPLIT_STATEMENT = (
    "RQ1's α = 0.05 is split (D22): H2 is tested on its own at α = 0.0125, and {H1, H3, H4} by "
    "Holm at family-wise α = 0.0375, so the RQ1 family-wise error is at most 0.05.")

NULLS = {"H1": "β_e = 0 or β_w = 0", "H2": "β = 0", "H3": "γ = 0", "H4": "b₁ = b₂ = 0"}
_N_TESTED = {"H1": 2, "H2": 1, "H3": 1, "H4": 2}

Status = Literal["supported", "contradicts", "rejected_mixed_sign", "rejected_zero_estimate",
                 "not_supported_nonfinite", "not_rejected"]


@dataclass(frozen=True)
class HolmStep:
    rank: int
    level: float
    rejected: bool


@dataclass(frozen=True)
class Decision:
    hypothesis: str
    status: Status
    rejected: bool
    level: float
    text: str


def _exact(x: float) -> Fraction:
    return Fraction(repr(float(x)))


def _meets(p: float, level: Fraction) -> bool:
    """p ≤ level, exactly; a NaN p never meets a level."""
    return not math.isnan(p) and _exact(p) <= level


def holm(p: dict[str, float], alpha: float) -> dict[str, HolmStep]:
    """Holm step-down: the k-th smallest p of m (ties by name) is compared with α/(m−k+1).

    A NaN p sorts last and is never rejected.
    """
    order = sorted(p, key=lambda h: (math.inf if math.isnan(p[h]) else p[h], h))
    m = len(order)
    out: dict[str, HolmStep] = {}
    going = True
    for k, h in enumerate(order, start=1):
        level = _exact(alpha) / (m - k + 1)
        going = going and _meets(p[h], level)
        out[h] = HolmStep(rank=k, level=float(level), rejected=going)
    return out


def _tested(res: HypothesisResult) -> list[Coef]:
    """The tested coefficients, by name: H2 `trend`; H1, H3, H4 `diagnostics["tested"]`."""
    h = res.hypothesis
    names = ["trend"] if h == "H2" else res.diagnostics.get("tested")
    if not isinstance(names, list) or len(names) != _N_TESTED[h]:
        raise ValueError(f"{h}: expected {_N_TESTED[h]} tested coefficient names, got {names!r}")
    missing = [n for n in names if n not in res.coefs]
    if missing:
        raise ValueError(f"{h}: tested coefficients {missing} are not in the result")
    return [res.coefs[n] for n in names]


def _coef_lines(coefs: list[Coef]) -> str:
    return "; ".join(f"{c.name} = {c.estimate:.3f} (95% CI [{c.ci_low:.3f}, {c.ci_high:.3f}], "
                     f"p = {c.p:.4f})" for c in coefs)


def _supported(h: str, rule: str, lines: str) -> str:
    return f"{h} is supported: {rule}. {lines}"


def _contradicts(h: str, lines: str) -> str:
    return f"{h}: the null is rejected, and the estimate contradicts the hypothesis ({lines})."


def _not_rejected(h: str, lines: str) -> str:
    return f"{h} is not rejected (H0: {NULLS[h]}). {lines}"


def _mixed_sign(h: str, wrong: list[Coef], lines: str) -> str:
    names = " and ".join(c.name for c in wrong)
    verb = "have" if len(wrong) > 1 else "has"
    return (f"{h}: the null is rejected, but {names} {verb} the opposite sign, which contradicts "
            f"the hypothesis, so {h} is not supported ({lines}).")


def _zero_estimate(h: str, zero: list[Coef], lines: str) -> str:
    names = " and ".join(c.name for c in zero)
    verb = "are" if len(zero) > 1 else "is"
    return (f"{h}: the null is rejected, but the estimate of {names} {verb} exactly 0, so the "
            f"hypothesis is not supported ({lines}).")


def _nonfinite(h: str, coefs: list[Coef], level: float) -> Decision | None:
    """Any non-finite tested estimate, SE or p: not rejected and not supported."""
    bad = []
    for c in coefs:
        fields = [f for f in ("estimate", "se", "p") if not math.isfinite(getattr(c, f))]
        if fields:
            bad.append(f"{c.name} has a non-finite {' and '.join(fields)}")
    if not bad:
        return None
    text = f"{h} is not supported: {'; '.join(bad)} ({_coef_lines(coefs)})."
    return Decision(h, "not_supported_nonfinite", False, level, text)


def _signed(h: str, coefs: list[Coef], rule: str, level: float) -> Decision:
    """A rejected directional hypothesis: every tested estimate must have the stated sign."""
    lines = _coef_lines(coefs)
    zero = [c for c in coefs if c.estimate == 0]
    if zero:
        return Decision(h, "rejected_zero_estimate", True, level, _zero_estimate(h, zero, lines))
    sign = -1 if h == "H1" else 1  # H1: β_e, β_w < 0; H2: β > 0; H3: γ > 0
    wrong = [c for c in coefs if c.estimate * sign < 0]
    if not wrong:
        return Decision(h, "supported", True, level, _supported(h, rule, lines))
    if len(wrong) == len(coefs):
        return Decision(h, "contradicts", True, level, _contradicts(h, lines))
    return Decision(h, "rejected_mixed_sign", True, level, _mixed_sign(h, wrong, lines))


def _family_decision(res: HypothesisResult, step: HolmStep) -> Decision:
    h, coefs = res.hypothesis, _tested(res)
    lines = _coef_lines(coefs)
    nonfinite = _nonfinite(h, coefs, step.level)
    if nonfinite:
        return nonfinite
    if not step.rejected:
        return Decision(h, "not_rejected", False, step.level, _not_rejected(h, lines))
    rule = (f"Holm over {{H1, H3, H4}} at family-wise {FAMILY_ALPHA} rejects at step {step.rank} "
            f"(level {step.level:.5f}, p = {res.p_family:.4f})")
    if h == "H4":  # two-sided "relates to": no sign condition (PAP §4.4, D17)
        return Decision(h, "supported", True, step.level, _supported(h, rule, lines))
    return _signed(h, coefs, rule, step.level)


def _h2_decision(res: HypothesisResult) -> Decision:
    (coef,) = _tested(res)
    if "p_wild" not in res.diagnostics:
        raise ValueError('H2: diagnostics["p_wild"] is missing')
    nonfinite = _nonfinite("H2", [coef], H2_ALPHA)
    if nonfinite:
        return nonfinite
    p_c, p_w = float(coef.p), float(res.diagnostics["p_wild"])
    lines = _coef_lines([coef])
    alpha = _exact(H2_ALPHA)
    failed = []
    for label, p in (("task-clustered p", p_c), ("release-level wild bootstrap p", p_w)):
        if not math.isfinite(p):
            failed.append(f"{label} is not finite")
        elif not _meets(p, alpha):
            failed.append(f"{label} = {p:.4f} > {H2_ALPHA}")
    if failed:
        text = f"{_not_rejected('H2', lines)}. Not met: {'; '.join(failed)}."
        return Decision("H2", "not_rejected", False, H2_ALPHA, text)
    rule = (f"task-clustered p = {p_c:.4f} and release-level wild bootstrap p = {p_w:.4f}, "
            f"both ≤ {H2_ALPHA}, and β > 0")
    return _signed("H2", [coef], rule, H2_ALPHA)


def decide(results: dict[str, HypothesisResult]) -> dict[str, Decision]:
    """The PAP §4 decision for each of H1–H4: Holm over {H1, H3, H4} at 0.0375, H2 alone."""
    if set(results) != {"H1", "H2", "H3", "H4"}:
        raise ValueError(f"decide needs exactly H1–H4, got {sorted(results)}")
    for key, res in results.items():
        if res.hypothesis != key:
            raise ValueError(f"results[{key!r}] holds {res.hypothesis}")
    steps = holm({h: results[h].p_family for h in RQ1_FAMILY}, FAMILY_ALPHA)
    out = {h: _family_decision(results[h], steps[h]) for h in RQ1_FAMILY}
    out["H2"] = _h2_decision(results["H2"])
    return {h: out[h] for h in ("H1", "H2", "H3", "H4")}
