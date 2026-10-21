"""Project-wide constants. Paths, seed, seal date and release calendar."""

from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw"
DERIVED = ROOT / "data/derived"

SEED = 20261021
SEAL_DATE = date(2022, 11, 30)  # ChatGPT launch; no returns dated on or after this before pap-v1
PAP_TAG = "pap-v1"

RELEASES: dict[str, date] = {
    "r1": date(2025, 2, 10),
    "r2": date(2025, 3, 27),
    "r3": date(2025, 9, 15),
    "r4": date(2026, 1, 15),
    "r5": date(2026, 3, 24),
    "r6": date(2026, 6, 26),
}
