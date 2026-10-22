"""Which month-end's market equity does a row of French's "Average Firm Size" table hold?

French does not document it. Test: size growth g_t = size_t / size_{t-1} - 1 tracks the
value-weighted return of the month whose end the row's ME is measured at. If row t holds ME
at the end of t-1, g_t ~ r_{t-1}; if at the end of t, g_t ~ r_t. July rows (annual
rebalancing) are dropped. Only rows dated before SEAL_DATE are ever parsed: the reader stops
at the first sealed row. Prints the two correlations and the sample counts only.
"""

import sys

import numpy as np

from aideleg.config import RAW, SEAL_DATE

FILE = RAW / "french" / "49_Industry_Portfolios_CSV" / "49_Industry_Portfolios.csv"


def _table(title: str) -> dict[int, np.ndarray]:
    """{YYYYMM: row of industry values (nan if missing)}, stopping before SEAL_DATE."""
    lines = FILE.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == title) + 2
    out: dict[int, np.ndarray] = {}
    for ln in lines[start:]:
        parts = [p.strip() for p in ln.split(",")]
        if len(parts[0]) != 6 or not parts[0].isdigit():
            break
        ym = int(parts[0])
        if (ym // 100, ym % 100) >= (SEAL_DATE.year, SEAL_DATE.month):
            break  # month-end of this row is on or after the seal: never parsed
        v = np.array([float(x) if x else np.nan for x in parts[1:]])
        out[ym] = np.where(np.isin(v, (-99.99, -999.0)), np.nan, v)
    return out


def _prev(ym: int) -> int:
    return ym - 1 if ym % 100 > 1 else (ym // 100 - 1) * 100 + 12


def main() -> int:
    size = _table("Average Firm Size")
    vw = _table("Average Value Weighted Returns -- Monthly")
    g, r_prev, r_same = [], [], []
    for ym, row in size.items():
        p = _prev(ym)
        if ym % 100 == 7 or p not in size or p not in vw or ym not in vw:
            continue
        g.append(row / size[p] - 1.0)
        r_prev.append(vw[p] / 100.0)
        r_same.append(vw[ym] / 100.0)
    g, r_prev, r_same = map(np.array, (g, r_prev, r_same))
    ok = np.isfinite(g) & np.isfinite(r_prev) & np.isfinite(r_same)
    pooled_prev = np.corrcoef(g[ok], r_prev[ok])[0, 1]
    pooled_same = np.corrcoef(g[ok], r_same[ok])[0, 1]
    per_prev, per_same, n_ind = [], [], 0
    for j in range(g.shape[1]):
        m = ok[:, j]
        if m.sum() < 30:
            continue
        n_ind += 1
        per_prev.append(np.corrcoef(g[m, j], r_prev[m, j])[0, 1])
        per_same.append(np.corrcoef(g[m, j], r_same[m, j])[0, 1])
    print(f"rows (non-July months): {g.shape[0]}  industry-months: {int(ok.sum())}"
          f"  industries: {n_ind}")
    print(f"pooled corr(g_t, r_t-1) = {pooled_prev:.4f}   corr(g_t, r_t) = {pooled_same:.4f}")
    print(f"median per-industry corr(g_t, r_t-1) = {np.median(per_prev):.4f}   "
          f"corr(g_t, r_t) = {np.median(per_same):.4f}")
    mp, ms = np.median(per_prev), np.median(per_same)
    prev_wins = pooled_prev > 0.9 and pooled_same < 0.5 and mp > 0.9 and ms < 0.5
    same_wins = pooled_same > 0.9 and pooled_prev < 0.5 and ms > 0.9 and mp < 0.5
    if prev_wins:
        print("SIZE_ME_OFFSET = 1")
    elif same_wins:
        print("SIZE_ME_OFFSET = 0")
    else:
        print("NOT DECISIVE")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
