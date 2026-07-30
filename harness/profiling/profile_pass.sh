#!/usr/bin/env bash
# One jittered dump-loop profiling pass. Driver + sampler + cleanup in ONE
# invocation (nohup-reap trap). Refuses idle capture if the driver dies.
# Usage: profile_pass.sh ENGINE WORKLOAD SERVER_PID NDUMPS OUTFILE [URL] [TOKENS_DIR]
set -euo pipefail
ENGINE="$1" WORKLOAD="$2" SPID="$3" NDUMPS="$4" OUT="$5"
URL="${6:-}" TOKDIR="${7:-}"
HARNESS=/home/aaron/Dev/Research/DatabaseResearch/DBHarness/harness
SELF="$(dirname "$0")"
PYSPY="$HOME/.local/bin/py-spy"

cd "$HARNESS"
taskset -c 14-19 uv run python "$SELF/load_driver.py" "$ENGINE" "$WORKLOAD" $URL $TOKDIR &
DRIVER=$!
trap 'kill $DRIVER 2>/dev/null || true' EXIT
sleep 5  # warmup
if ! kill -0 "$DRIVER" 2>/dev/null; then
    echo "FATAL: load driver died during warmup - refusing idle capture" >&2
    exit 1
fi

: > "$OUT"
for i in $(seq 1 "$NDUMPS"); do
    echo "===DUMP $i $(date +%s.%N)===" >> "$OUT"
    "$PYSPY" dump --pid "$SPID" >> "$OUT" 2>&1 || true
    sleep "0.$(printf '%03d' $((RANDOM % 350 + 50)))"  # jittered 50-400ms
done
kill $DRIVER 2>/dev/null || true
wait $DRIVER 2>/dev/null || true
echo "PASS DONE: $(grep -c '^===DUMP' "$OUT") dumps -> $OUT"
