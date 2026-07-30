#!/usr/bin/env bash
set -euo pipefail
/home/aaron/Dev/Research/DatabaseResearch/DBHarness/results/profiles/leaf-2026-07-29/pass.sh load_feed      150 /home/aaron/Dev/Research/DatabaseResearch/DBHarness/results/2026-07-30/anchor_dumps.txt 3847
/home/aaron/Dev/Research/DatabaseResearch/DBHarness/results/profiles/leaf-2026-07-29/pass.sh load_feed_leaf 150 /home/aaron/Dev/Research/DatabaseResearch/DBHarness/results/2026-07-30/leaf_dumps.txt   3847
/home/aaron/Dev/Research/DatabaseResearch/DBHarness/results/profiles/leaf-2026-07-29/pass.sh load_feed      150 /home/aaron/Dev/Research/DatabaseResearch/DBHarness/results/2026-07-30/anchor_dumps.txt 3847
/home/aaron/Dev/Research/DatabaseResearch/DBHarness/results/profiles/leaf-2026-07-29/pass.sh load_feed_leaf 150 /home/aaron/Dev/Research/DatabaseResearch/DBHarness/results/2026-07-30/leaf_dumps.txt   3847
for W in load_feed load_feed_leaf; do
    python3 /home/aaron/Dev/Research/DatabaseResearch/DBHarness/results/profiles/leaf-2026-07-29/driver.py $W & DRV=$!
    sleep 3
    $HOME/.local/bin/py-spy record --pid 3847 --duration 30 --rate 60 -f flamegraph -o /home/aaron/Dev/Research/DatabaseResearch/DBHarness/results/2026-07-30/flame_${W}_2026-07-30.svg || true
    kill $DRV 2>/dev/null || true; wait $DRV 2>/dev/null || true
done
echo "PROFILE DONE"
