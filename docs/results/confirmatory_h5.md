# Confirmatory test of H5 and H5b

Generated once by `uv run python -m aideleg.confirm_h5`; committed unedited.

AEI data are conversations matched to O*NET tasks; nothing here says anything about job risk or displacement in the labour market.

## Provenance

- Commit: `6a16b1ad052977650b90c8062ceeeab9ac6572e1`; tag `pap-v1` -> `6a16b1ad052977650b90c8062ceeeab9ac6572e1`.
- `src/aideleg/confirm_h5.py` blob: `f581264ae9c982ff6a84eb1d1e2f465d18544144`.
- Exposure vector SHA-256: `bddc49d49b9565bba8daa8bc6fdb709043a6007090b9e7faf7dda1001229ac36` (checked).
- Window 2025-04-01 -> 2026-08-31; dates read in it 2025-04-01 -> 2026-08-31; 356 factor days.
- Industries: 49; dropped for a missing return: none; frozen null scales used.

## Primary (D10, t_21, Holm over {H5, H5b})

Confirmatory null: b = bbar (`PRIMARY_NULL = "bbar"`); the other is secondary.

b, s and bbar in pp of annualised alpha per 1 SD of exposure; both statistics, b / s and (b - bbar) / s; p from t_21 for the primary and the secondary null; c = max(t_21 critical, empirical centred quantile).

| specification | b | s | bbar | b / s | (b - bbar) / s | p primary | p secondary | c_0.025 | c_0.05 |
|---|---|---|---|---|---|---|---|---|---|
| H5 | 1.958 | 2.271 | 1.650 | 0.862 | 0.136 | 0.8934 | 0.3982 | 2.4138 | 2.0796 |
| H5b | 3.461 | 2.560 | 1.217 | 1.352 | 0.877 | 0.3906 | 0.1908 | 2.4138 | 2.0796 |
| H5 R12 (ranks) | -1.065 | 2.211 | 1.317 | -0.482 | -1.077 | 0.2936 | 0.6350 | 2.4138 | 2.0796 |
| H5b R12 (ranks) | -2.386 | 2.982 | 0.539 | -0.800 | -0.981 | 0.3379 | 0.4326 | 2.4138 | 2.0796 |
| H5 R13 (drop Softw) | 1.655 | 3.195 | 1.666 | 0.518 | -0.003 | 0.9974 | 0.6098 | 2.4138 | 2.0796 |
| H5b R13 (drop Softw) | 3.634 | 3.713 | 1.068 | 0.979 | 0.691 | 0.4972 | 0.3389 | 2.4138 | 2.0796 |

- **H5.** Holm level reached: None; primary rejection: False; R13 co-condition met: False.
  - Interval b +- c_0.05 x s: [-2.764, 6.681] pp; b +- c_0.025 x s: [-3.523, 7.440] pp.
  - Fixed wording: H5 is not rejected (H0: b = bbar (the 1990-2022 pattern for this exposure vector)). Interval [-2.76, 6.68] pp per 1 SD; the test had 80% power only against a departure from H0 of at least 7.43 pp per 1 SD (MDE at Holm level 0.025).
  - R13 (Softw dropped) MDE at Holm level 0.025: 10.46 pp; the co-conditioned claim has 80% power only near it.
- **H5b.** Holm level reached: None; primary rejection: False; R13 co-condition met: False.
  - Interval b +- c_0.05 x s: [-1.863, 8.786] pp; b +- c_0.025 x s: [-2.719, 9.642] pp.
  - Fixed wording: H5b is not rejected (H0: b = bbar (the 1990-2022 pattern for this exposure vector)). Interval [-1.86, 8.79] pp per 1 SD; the test had 80% power only against a departure from H0 of at least 8.38 pp per 1 SD (MDE at Holm level 0.025).
  - R13 (Softw dropped) MDE at Holm level 0.025: 12.15 pp; the co-conditioned claim has 80% power only near it.

## Secondary null (not part of the decision)

- H5: secondary null b = 0: T = 0.862, p (t_21) = 0.3982; not part of the decision.
- H5b: secondary null b = 0: T = 1.352, p (t_21) = 0.1908; not part of the decision.

## Secondary inference (never used for the decision)

- RI, permute z_delegation, H5: p = 0.3287.
- RI, permute z_delegation with z_aioe in place, H5b: p = 0.0942 (oversized even under exchangeability).
- Freedman-Lane RI (pivotal t), H5b: p = 0.2099; coefficient-scored on the same draws: p = 0.2052.
- Documented size at nominal 0.025 (pre-seal, full 49 industries; 378 overlapping windows, power.md): 13.8% (H5), 14.8% (H5b, z_aioe in place), 5.6% (Freedman-Lane, pivotal t), 6.1% (Freedman-Lane, coefficient).
- 10,000 permutations each, one `default_rng(SEED = 20261021)` in that order.
- OLS with HC3 SEs: H5 b = 1.958 pp (SE 1.629); H5b b = 3.461 pp (SE 1.638).
