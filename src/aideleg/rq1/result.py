"""The result record every RQ1 hypothesis estimator returns (PAP section 0.2 reporting).

Every estimate carries its point value, 95% CI and p-value. Wording: AEI data are
conversations matched to O*NET tasks.
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Coef:
    name: str
    estimate: float
    se: float
    ci_low: float
    ci_high: float
    p: float
    df: int | None  # None: normal reference distribution


@dataclass
class HypothesisResult:
    hypothesis: str
    outcome: str
    coefs: dict[str, Coef]
    p_family: float  # the one p-value per hypothesis (D17)
    sample: dict[str, int | float] = field(default_factory=dict)
    drops: dict[str, float] = field(default_factory=dict)  # % of total usage, by reason
    diagnostics: dict[str, object] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """JSON-safe: floats, ints, strings, lists and dicts only."""
        return _plain(asdict(self))


def _plain(x):
    if isinstance(x, dict):
        return {str(k): _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if x is None or isinstance(x, (str, bool)):
        return x
    if isinstance(x, int):
        return int(x)
    if isinstance(x, float):
        return float(x)
    if hasattr(x, "item"):  # numpy scalar
        return _plain(x.item())
    raise TypeError(f"not JSON-safe: {type(x).__name__}")
