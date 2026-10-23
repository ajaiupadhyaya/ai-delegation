"""Exposure variants over the existing exposure parameters (Plan 4 Task 5)."""

from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from aideleg.robustness.exposure_variants import (
    ExposureSpec,
    variant_exposure,
    vector_hash,
    zero_assigned_share,
)

PRIMARY_HASH = "bddc49d49b9565bba8daa8bc6fdb709043a6007090b9e7faf7dda1001229ac36"
FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "crosswalk" / "naics_to_ff49_default.csv"
)


def _delta(spec: ExposureSpec) -> tuple[pl.DataFrame, float]:
    base = variant_exposure(ExposureSpec()).select("industry", "z_delegation")
    var = variant_exposure(spec)
    j = base.join(
        var.select("industry", z_v="z_delegation"), on="industry", how="full", coalesce=True
    )
    return var, float((j["z_delegation"] - j["z_v"]).abs().max())


@pytest.mark.data
def test_primary_vector_hash_unchanged():
    from aideleg.crosswalk.naics_ff49 import naics_to_ff49

    assert vector_hash(variant_exposure(ExposureSpec())) == PRIMARY_HASH
    now = naics_to_ff49()
    before = pl.read_csv(FIXTURE, schema=now.schema)
    assert_frame_equal(now, before, check_exact=True)


@pytest.mark.data
def test_pooled_default_equals_exposure_module():
    from aideleg.exposure import build_exposure

    got = variant_exposure(ExposureSpec(design="A_pooled")).select(
        ff49="industry", z_delegation="z_delegation", z_usage="z_usage"
    )
    want = build_exposure("A_pooled").select("ff49", "z_delegation", "z_usage")
    assert_frame_equal(got.sort("ff49"), want.sort("ff49"))


@pytest.mark.data
def test_zero_assigned_share_primary():
    from aideleg import audit
    from aideleg.config import DERIVED

    occ = pl.read_parquet(DERIVED / "exposure_occupation.parquet")
    want = (
        audit.design_zero_assigned(occ).filter(pl.col("design") == "B")["no_usage_emp_pct"].item()
    )
    assert zero_assigned_share(ExposureSpec()) == pytest.approx(want, abs=1e-9)


def test_api_design_b_rejected():
    with pytest.raises(ValueError, match="1p_api"):
        variant_exposure(ExposureSpec(design="B", source="1p_api"))


@pytest.mark.data
def test_siccodes30_crosswalk_weights_sum_to_one():
    from aideleg.crosswalk.naics_ff49 import naics_to_ff49

    xw = naics_to_ff49("split", 4, "exclude", siccodes_key="ff_siccodes30")
    sums = xw.group_by("naics").agg(pl.col("weight").sum())
    assert (sums["weight"] - 1).abs().max() < 1e-9
    nums = xw["ff49"].drop_nulls()
    assert nums.min() >= 1 and nums.max() <= 30


def _check_differs(spec: ExposureSpec, absent: frozenset[int] = frozenset()) -> None:
    var, diff = _delta(spec)
    print(f"{spec}: max |dz_delegation| = {diff:.6f}")
    assert set(range(1, 50)) - set(var["industry"]) == absent
    assert var.height == 49 - len(absent)
    assert diff > 0


@pytest.mark.data
def test_unmatched_drop_differs():
    _check_differs(ExposureSpec(unmatched="drop"))


@pytest.mark.data
def test_majority_differs():
    # The existing `majority()` assigns no NAICS 4-digit code to Guns (26), Gold (27) or
    # Boxes (40), so the variant has 46 industries, not 49 (reported to the controller).
    _check_differs(ExposureSpec(crosswalk="majority"), frozenset({26, 27, 40}))


@pytest.mark.data
def test_hq_redistribute_differs():
    # `hq_shares` gives every FF49 industry 5511 employment in proportion to its own mapped
    # employment, so each E moves by the same affine map (E + c E_5511) / (1 + c) and the
    # z-scores are invariant: z_delegation moves only by float noise (~1e-15) and the vector
    # hash is the primary one. The construction does change: coverage moves (reported).
    primary = variant_exposure(ExposureSpec())
    var = variant_exposure(ExposureSpec(hq="redistribute"))
    assert var.height == 49
    dz = (var["z_delegation"] - primary["z_delegation"]).abs().max()
    dcov = (var["emp_covered_share"] - primary["emp_covered_share"]).abs().max()
    print(f"hq=redistribute: max |dz_delegation| = {dz:.3e}, max |d emp_covered| = {dcov:.6f}")
    assert dz < 1e-12
    assert dcov > 1e-4
