"""The RQ1 testing family, decision rules and fixed wording (PAP §4, §4.0, D17, D22, §0.2).

- {H1, H3, H4} are tested by Holm at family-wise α = 0.0375 on each result's `p_family` (D17).
- H2 is tested on its own at α = 0.0125 (D22). It needs the task-clustered p, the release-level
  wild bootstrap p (`diagnostics["p_wild"]`) and β > 0.
- A significant estimate of the wrong sign "contradicts the hypothesis" (§0.2). A non-rejection
  names its null and is never worded as an absence of effect.
"""

from dataclasses import dataclass
from typing import Literal

from aideleg.rq1.result import Coef, HypothesisResult

RQ1_FAMILY = ("H1", "H3", "H4")
FAMILY_ALPHA = 0.0375
H2_ALPHA = 0.0125
SPLIT_STATEMENT = (
    "RQ1's α = 0.05 is split (D22): H2 is tested on its own at α = 0.0125, and {H1, H3, H4} by "
    "Holm at family-wise α = 0.0375, so the RQ1 family-wise error is at most 0.05.")

NULLS = {"H1": "β_e = 0 or β_w = 0", "H2": "β = 0", "H3": "γ = 0", "H4": "b₁ = b₂ = 0"}
# The tested coefficients are the first n of each result's `coefs`, in estimator order:
# H1 (education, log wage), H2 (trend), H3 (the error-cost indicator), H4 (log AUI, log income).
_N_TESTED = {"H1": 2, "H2": 1, "H3": 1, "H4": 2}

Status = Literal["supported", "contradicts", "rejected_mixed_sign", "not_rejected"]


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


def holm(p: dict[str, float], alpha: float) -> dict[str, HolmStep]:
    """Holm step-down: the k-th smallest p of m (ties by name) is compared with α/(m−k+1)."""
    order = sorted(p, key=lambda h: (p[h], h))
    m = len(order)
    out: dict[str, HolmStep] = {}
    going = True
    for k, h in enumerate(order, start=1):
        level = alpha / (m - k + 1)
        going = going and p[h] <= level
        out[h] = HolmStep(rank=k, level=level, rejected=going)
    return out


def _tested(res: HypothesisResult) -> list[Coef]:
    n = _N_TESTED[res.hypothesis]
    coefs = list(res.coefs.values())
    if len(coefs) < n:
        raise ValueError(f"{res.hypothesis}: expected {n} tested coefficients, got {len(coefs)}")
    if res.hypothesis == "H2":
        return [res.coefs["trend"]]
    return coefs[:n]


def _coef_lines(coefs: list[Coef]) -> str:
    return "; ".join(f"{c.name} = {c.estimate:.3f} (95% CI [{c.ci_low:.3f}, {c.ci_high:.3f}], "
                     f"p = {c.p:.4f})" for c in coefs)


def _supported(h: str, rule: str, lines: str) -> str:
    return f"{h} is supported: {rule}. {lines}"


def _contradicts(h: str, lines: str) -> str:
    return f"{h}: the null is rejected, and the estimate contradicts the hypothesis ({lines})."


def _not_rejected(h: str, lines: str) -> str:
    return f"{h} is not rejected (H0: {NULLS[h]}). {lines}"


def _family_decision(res: HypothesisResult, step: HolmStep) -> Decision:
    h, coefs = res.hypothesis, _tested(res)
    lines = _coef_lines(coefs)
    if not step.rejected:
        return Decision(h, "not_rejected", False, step.level, _not_rejected(h, lines))
    rule = (f"Holm over {{H1, H3, H4}} at family-wise {FAMILY_ALPHA} rejects at step {step.rank} "
            f"(level {step.level:.5f}, p = {res.p_family:.4f})")
    est = [c.estimate for c in coefs]
    status: Status
    if h == "H4":  # two-sided "relates to": no sign condition (PAP §4.4, D17)
        status = "supported"
    elif h == "H1":  # both β_e < 0 and β_w < 0 (PAP §4.1)
        status = ("supported" if all(b < 0 for b in est)
                  else "contradicts" if all(b > 0 for b in est) else "rejected_mixed_sign")
    elif est[0] != 0:  # H3: γ > 0 (PAP §4.3)
        status = "supported" if est[0] > 0 else "contradicts"
    else:
        raise ValueError("H3: the null is rejected with γ exactly 0")
    if status == "supported":
        text = _supported(h, rule, lines)
    elif status == "contradicts":
        text = _contradicts(h, lines)
    else:
        text = (f"{h}: the null is rejected, but the coefficients have mixed signs, so the "
                f"hypothesis is not supported ({lines}).")
    return Decision(h, status, True, step.level, text)


def _h2_decision(res: HypothesisResult) -> Decision:
    (coef,) = _tested(res)
    p_c, p_w = coef.p, float(res.diagnostics["p_wild"])
    lines = _coef_lines([coef])
    failed = []
    if not p_c <= H2_ALPHA:
        failed.append(f"task-clustered p = {p_c:.4f} > {H2_ALPHA}")
    if not p_w <= H2_ALPHA:
        failed.append(f"release-level wild bootstrap p = {p_w:.4f} > {H2_ALPHA}")
    if failed:
        text = f"{_not_rejected('H2', lines)}. Not met: {'; '.join(failed)}."
        return Decision("H2", "not_rejected", False, H2_ALPHA, text)
    if coef.estimate > 0:
        rule = (f"task-clustered p = {p_c:.4f} and release-level wild bootstrap p = {p_w:.4f}, "
                f"both ≤ {H2_ALPHA}, and β > 0")
        return Decision("H2", "supported", True, H2_ALPHA, _supported("H2", rule, lines))
    if coef.estimate < 0:
        return Decision("H2", "contradicts", True, H2_ALPHA, _contradicts("H2", lines))
    raise ValueError("H2: both p-values reject with β exactly 0")


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
