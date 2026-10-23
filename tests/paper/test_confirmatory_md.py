"""The parser of the committed confirmatory record (Plan 4 Task 18's spec, written in Task 4)."""

from datetime import date

import pytest

from aideleg import confirm_h5 as ch
from aideleg.config import ROOT
from aideleg.paper import confirmatory_md


def _res(b: dict[str, float]) -> dict:
    """A synthetic `res` as `confirm_h5._confirm` builds it, with the frozen null scales."""
    fz = dict(ch.FROZEN)
    return {
        "b": b,
        "T": None,
        "decision": ch.decide(b, fz),
        "ri": {
            "h5_exposure": 0.1234,
            "h5b_exposure": 0.0456,
            "h5b_freedman_lane": 0.3456,
            "h5b_freedman_lane_coef": 0.3567,
        },
        "hc3": {"h5": (0.0123, 0.0045), "h5b": (0.0234, 0.0056)},
        "dropped": [],
        "frozen_used": fz,
        "first_date": date(2025, 4, 1),
        "last_date": date(2026, 8, 31),
        "n": 49,
        "n_days": 356,
    }


@pytest.mark.parametrize("scale", [0.3, 6.0])
def test_parse_confirmatory_fixture(tmp_path, scale):
    fz = ch.FROZEN
    b = {
        v: scale * fz[f"s_{v}"] * (1 if i % 2 else -1) + fz[f"bbar_{v}"]
        for i, v in enumerate(ch.VARIANTS)
    }
    res = _res(b)
    path = tmp_path / "confirmatory_h5.md"
    path.write_text(ch._report(res), encoding="utf-8")
    got = confirmatory_md.parse(path)
    d = res["decision"]
    for v in ch.VARIANTS:
        row = got[ch.LABEL[v]]
        assert row["b"] == f"{b[v] * 100:.3f}"
        assert row["T_bbar"] == f"{d['T_bbar'][v]:.3f}"
        assert row["p_primary"] == f"{d['p_t21'][v]:.4f}"
    for hyp in ("H5", "H5b"):
        assert got["decision"][hyp]["wording"] == d["wording"][hyp]
        assert got["decision"][hyp]["holm_level"] == str(d["holm_level"][hyp])
    assert got["provenance"]["n"] == "49"
    assert got["provenance"]["dropped"] == "none"
    assert got["secondary"]["ri_h5"] == "0.1234"


def test_parse_committed_record():
    got = confirmatory_md.parse()
    assert set(ch.LABEL.values()) <= set(got)
    assert got["H5"]["b"] == "1.958" and got["H5b"]["s"] == "2.560"
    assert got["decision"]["H5"]["rejected"] == "False"
    assert got["decision"]["H5"]["ci_005"] == ("-2.764", "6.681")
    assert got["decision"]["H5b"]["mde_r13"] == "12.15"
    assert got["decision"]["H5"]["wording"].startswith("H5 is not rejected")
    assert got["provenance"]["window"] == "2025-04-01 -> 2026-08-31"


def test_parse_refuses_attempt_record(tmp_path):
    p = tmp_path / "c.md"
    text = (ROOT / "docs/results/confirmatory_h5.md").read_text(encoding="utf-8")
    p.write_text(
        text.replace(
            "# Confirmatory test of H5 and H5b",
            "# Confirmatory test of H5 and H5b: attempt failed",
            1,
        )
    )
    with pytest.raises(ValueError, match="attempt"):
        confirmatory_md.parse(p)
