#!/usr/bin/env bash
# One jittered dump pass: pass.sh WALKER NDUMPS OUTFILE SERVER_PID
set -euo pipefail
W="$1" N="$2" OUT="$3" SPID="$4"
D=/home/aaron/Dev/Research/DatabaseResearch/DBHarness/results/profiles/leaf-2026-07-29
python3 "$D/driver.py" "$W" &
DRV=$!
trap 'kill $DRV 2>/dev/null || true' EXIT
sleep 4
kill -0 $DRV 2>/dev/null || { echo "driver died"; exit 1; }
for i in $(seq 1 "$N"); do
    echo "===DUMP $i $(date +%s.%N)===" >> "$OUT"
    "$HOME/.local/bin/py-spy" dump --pid "$SPID" >> "$OUT" 2>&1 || true
    sleep "0.$(printf '%03d' $((RANDOM % 350 + 50)))"
done
kill $DRV 2>/dev/null || true; wait $DRV 2>/dev/null || true
echo "$W pass done: $(grep -c '^===DUMP' "$OUT") dumps"
