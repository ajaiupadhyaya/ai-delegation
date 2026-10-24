#!/usr/bin/env bash
# Fresh-clone replication check (Task 33): `bash scripts/replicate.sh WORKDIR`.
#
# 1. clone the committed branch plan-4-paper into WORKDIR (empty or absent);
# 2. install the locked environment (`uv sync --frozen`);
# 3. seed WORKDIR/data/raw from this checkout's data/raw, the frozen archive, verifying every
#    file against the committed MANIFEST and every 10-K document against INDEX.jsonl;
# 4. run `make all` (offline), timed, logging to WORKDIR/make_all.log;
# 5. compare the rebuilt outputs with the committed ones -> docs/replication/check.md.
# Exit status: nonzero if make all failed or any output differs.
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "usage: bash scripts/replicate.sh WORKDIR" >&2
    exit 2
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$1"
OUT="$ROOT/docs/replication/check.md"

git clone --branch plan-4-paper "file://$ROOT" "$WORK"
WORK="$(cd "$WORK" && pwd)"
cd "$WORK"
uv sync --frozen
uv run python -m aideleg.acquire --from-dir "$ROOT/data/raw"

start=$(date +%s)
make_status=0
make all > "$WORK/make_all.log" 2>&1 || make_status=$?
end=$(date +%s)
runtime=$((end - start))

compare_status=0
uv run python scripts/compare_outputs.py "$ROOT" "$WORK" > "$OUT" || compare_status=$?

{
    echo
    echo "## Run"
    echo
    echo "- \`make all\` exit status: $make_status (log: \`make_all.log\` in the work directory)"
    printf -- '- Runtime of `make all`: %dm %02ds (%d s)\n' $((runtime / 60)) $((runtime % 60)) "$runtime"
    echo "- Run on $(date -u +%Y-%m-%dT%H:%M:%SZ), $(uname -sm), $(uv run python -c 'import platform; print("Python", platform.python_version())')"
} >> "$OUT"

echo "make all: exit $make_status in ${runtime}s; compare: exit $compare_status -> $OUT"
if [ "$make_status" -ne 0 ] || [ "$compare_status" -ne 0 ]; then
    exit 1
fi
