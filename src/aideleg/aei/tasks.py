"""Task-text normalisation and matching of AEI task names to O*NET Task IDs.

Occupation vintage: every code `TaskIndex.build` / `default_index` returns is O*NET-SOC 2019
(`NN-NNNN.NN`, SOC 2018 in its first 7 characters), the vintage of OEWS May 2024 and AEI r6.

Inputs (columns verified on the downloaded files, 2026-10-21):
- `onet_29_3_tasks`, O*NET 29.3 `Task Statements.txt`: tab-separated, CRLF, unquoted;
  `O*NET-SOC Code, Task ID, Task, Task Type, Incumbents Responding, Date, Domain Source`.
  18,796 rows, one per Task ID, 923 O*NET-SOC 2019 codes.
- `aei_onet_tasks`, the AEI r2 `onet_task_statements.csv`: comma-separated;
  `O*NET-SOC Code, Title, Task ID, Task, Task Type, Incumbents Responding, Date,
  Domain Source`. 19,530 rows, one per Task ID, 974 O*NET-SOC 2010 codes.
- `onet_2010_2019_crosswalk`, the O*NET 2010 -> 2019 taxonomy crosswalk CSV:
  `O*NET-SOC 2010 Code, O*NET-SOC 2010 Title, O*NET-SOC 2019 Code, O*NET-SOC 2019 Title`.
  1,164 rows; 1,110 2010 codes (some split into several 2019 codes), 1,012 2019 codes.
  Every 2010 code in the r2 file appears in it.

Task IDs are stable across O*NET versions: 15,734 IDs are in both task files, 3,796 only in
the legacy file and 3,062 only in 29.3.
"""

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from aideleg.acquire.sources import by_key
from aideleg.config import RAW

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


def _read_tasks(path: Path) -> pl.DataFrame:
    """(code, task_id, text) from either task-statement layout (tab .txt or comma .csv)."""
    tab = path.suffix.lower() == ".txt"
    df = pl.read_csv(
        path, separator="\t" if tab else ",", quote_char=None if tab else '"',
        columns=["O*NET-SOC Code", "Task ID", "Task"],
        schema_overrides={"O*NET-SOC Code": pl.String, "Task ID": pl.Int64, "Task": pl.String},
    )
    return df.rename({"O*NET-SOC Code": "code", "Task ID": "task_id", "Task": "text"})


@dataclass
class TaskIndex:
    _ids_by_text: dict[str, list[int]]
    _occ_by_id: dict[int, list[str]]
    _provenance: dict[str, int] = field(default_factory=dict)

    @classmethod
    def build(cls, onet_2019: Path, onet_legacy: Path, crosswalk: Path) -> "TaskIndex":
        """Index on O*NET-SOC 2019 codes.

        Text -> Task IDs: the union over the 29.3 and the legacy wordings (r1/r2 texts may
        predate 29.3 revisions). Task ID -> occupations: 29.3's 2019 codes when the ID is in
        29.3, else every 2019 successor of its legacy 2010 code(s) through the crosswalk.
        A Task ID with no 2019 occupation is unresolved: it is counted in `provenance()` and
        left out of the index, so texts that only reach it stay unmatched (never silently
        given an occupation-less ID).
        """
        new, old = _read_tasks(onet_2019), _read_tasks(onet_legacy)
        walk = pl.read_csv(crosswalk, columns=["O*NET-SOC 2010 Code", "O*NET-SOC 2019 Code"],
                           infer_schema_length=0)
        succ: dict[str, set[str]] = defaultdict(set)
        for a, b in walk.iter_rows():
            if a and b:
                succ[a.strip()].add(b.strip())

        occ: dict[int, set[str]] = defaultdict(set)
        for code, tid, _ in new.iter_rows():
            occ[tid].add(code)
        in_2019 = set(occ)
        legacy_ids: set[int] = set()
        for code, tid, _ in old.iter_rows():
            if tid in in_2019:
                continue
            legacy_ids.add(tid)
            occ[tid] |= succ.get(code, set())
        resolved = {t: v for t, v in occ.items() if v}
        prov = {
            "onet_2019": len(in_2019),
            "crosswalk": sum(1 for t in legacy_ids if t in resolved),
            "unresolved": sum(1 for t in legacy_ids if t not in resolved),
        }

        ids: dict[str, set[int]] = defaultdict(set)
        for frame in (new, old):
            for _, tid, text in frame.iter_rows():
                if tid in resolved:
                    ids[normalise_task_text(text)].add(tid)
        return cls({k: sorted(v) for k, v in ids.items()},
                   {k: sorted(v) for k, v in resolved.items()}, prov)

    def all_occupations(self) -> set[str]:
        """Every occupation code any indexed Task ID maps to."""
        return {o for v in self._occ_by_id.values() for o in v}

    def provenance(self) -> dict[str, int]:
        """Task IDs resolved via O*NET 29.3, via the 2010 -> 2019 crosswalk, and unresolved."""
        return dict(self._provenance)

    @classmethod
    def from_onet(cls, path: Path) -> "TaskIndex":
        """One task file taken at its own vintage, with no crosswalk (test fixtures)."""
        df = _read_tasks(path)
        ids: dict[str, set[int]] = defaultdict(set)
        occ: dict[int, set[str]] = defaultdict(set)
        for code, tid, text in df.iter_rows():
            ids[normalise_task_text(text)].add(tid)
            occ[tid].add(code)
        return cls({k: sorted(v) for k, v in ids.items()}, {k: sorted(v) for k, v in occ.items()},
                   {"onet_2019": 0, "crosswalk": 0, "unresolved": 0})

    def task_ids_for(self, text: str) -> list[int]:
        return list(self._ids_by_text.get(normalise_task_text(text), []))

    def has_task_id(self, task_id: int) -> bool:
        return task_id in self._occ_by_id

    def occupations_for(self, task_id: int) -> list[str]:
        return list(self._occ_by_id.get(task_id, []))

    def occupations_for_text(self, text: str) -> list[str]:
        """Sorted union of O*NET-SOC codes over every Task ID carrying this statement."""
        return sorted({o for i in self.task_ids_for(text) for o in self.occupations_for(i)})


def default_index(raw: Path | None = None) -> TaskIndex:
    """The study index (O*NET-SOC 2019), built from the three registry sources under `raw`."""
    raw = RAW if raw is None else raw
    return TaskIndex.build(raw / by_key("onet_29_3_tasks").dest,
                           raw / by_key("aei_onet_tasks").dest,
                           raw / by_key("onet_2010_2019_crosswalk").dest)


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
