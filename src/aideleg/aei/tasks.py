"""Task-text normalisation and matching of AEI task names to O*NET Task IDs."""

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import polars as pl

_QUOTES = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
})
_WS = re.compile(r"\s+")


def normalise_task_text(s: str) -> str:
    """NFKC, straight quotes, lower-case, collapsed whitespace, one trailing period removed."""
    s = unicodedata.normalize("NFKC", s).translate(_QUOTES).lower()
    s = _WS.sub(" ", s).strip()
    return s[:-1] if s.endswith(".") else s


@dataclass
class TaskIndex:
    _ids_by_text: dict[str, list[int]]
    _occ_by_id: dict[int, list[str]]

    @classmethod
    def from_onet(cls, path: Path) -> "TaskIndex":
        df = pl.read_csv(
            path, columns=["O*NET-SOC Code", "Task ID", "Task"],
            schema_overrides={"Task ID": pl.Int64},
        )
        ids: dict[str, set[int]] = defaultdict(set)
        occ: dict[int, set[str]] = defaultdict(set)
        for code, tid, text in df.iter_rows():
            ids[normalise_task_text(text)].add(tid)
            occ[tid].add(code)
        return cls({k: sorted(v) for k, v in ids.items()}, {k: sorted(v) for k, v in occ.items()})

    def task_ids_for(self, text: str) -> list[int]:
        return list(self._ids_by_text.get(normalise_task_text(text), []))

    def occupations_for(self, task_id: int) -> list[str]:
        return list(self._occ_by_id.get(task_id, []))

    def occupations_for_text(self, text: str) -> list[str]:
        """Sorted union of O*NET-SOC codes over every Task ID carrying this statement."""
        return sorted({o for i in self.task_ids_for(text) for o in self.occupations_for(i)})


def match_tasks(names: pl.Series, index: TaskIndex) -> pl.DataFrame:
    """One row per input name; task_id is the smallest candidate ID, null when unmatched.

    `task_id` is a representative ID only. The same statement can carry different Task IDs
    in different occupations, so occupation allocation must use
    `TaskIndex.occupations_for_text`, not `occupations_for(task_id)`.
    Null names are kept, with null task_id and n_candidates 0.
    """
    cands = [index.task_ids_for(n) if n is not None else [] for n in names.to_list()]
    return pl.DataFrame(
        {
            "task_name": names.to_list(),
            "task_id": [c[0] if c else None for c in cands],
            "n_candidates": [len(c) for c in cands],
        },
        schema={"task_name": pl.String, "task_id": pl.Int64, "n_candidates": pl.Int64},
    )
