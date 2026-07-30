#!/usr/bin/env bash
set -euo pipefail
D=/home/aaron/Dev/Research/DatabaseResearch/DBHarness/results/profiles/leaf-2026-07-29
SPID=287100
rm -f "$D"/anchor_dumps.txt "$D"/leaf_dumps.txt
# interleaved: anchor,leaf,anchor,leaf (150 dumps per pass -> 300/arm)
"$D/pass.sh" load_feed      150 "$D/anchor_dumps.txt" $SPID
"$D/pass.sh" load_feed_leaf 150 "$D/leaf_dumps.txt"   $SPID
"$D/pass.sh" load_feed      150 "$D/anchor_dumps.txt" $SPID
"$D/pass.sh" load_feed_leaf 150 "$D/leaf_dumps.txt"   $SPID
# flamegraphs: 60s record per arm while its driver runs
for W in load_feed load_feed_leaf; do
    python3 "$D/driver.py" "$W" & DRV=$!
    sleep 3
    "$HOME/.local/bin/py-spy" record --pid $SPID --duration 60 --rate 250 \
        -f flamegraph -o "$D/flame_${W}.svg" || true
    kill $DRV 2>/dev/null || true; wait $DRV 2>/dev/null || true
done
echo "ALL DONE"
