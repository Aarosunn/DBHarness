#!/usr/bin/env bash
set -euo pipefail
cd /home/aaron/Dev/Research/DatabaseResearch/DBHarness/harness
for r in 1 2 3; do
    uv run python run.py --engines postgres,sqlalchemy,neo4j --workloads feed \
        --requests 500 --warmup 25 --name perf0730_baselines_r$r
    uv run python run.py --engines jaseci --url-jaseci http://localhost:8005 \
        --workloads feed --requests 500 --warmup 25 --name perf0730_jacanchor_r$r
    uv run python run.py --engines jaseci --url-jaseci http://localhost:8005 \
        --workloads feed_leaf --requests 500 --warmup 25 --name perf0730_jacleaf_r$r
    echo "=== repeat $r done ==="
done
echo "BENCH DONE"
