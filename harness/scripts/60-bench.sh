#!/usr/bin/env bash
# Timed benchmark, ONE engine at a time (idle machine!). Appends to
# results/csv/results.csv with server_* (headline) + client columns.
#   ./60-bench.sh                 # all engines sequentially
#   ./60-bench.sh postgres neo4j  # subset
source "$(dirname "$0")/lib.sh"

ENGINES=("$@")
[[ $# -eq 0 ]] && ENGINES=(jaseci postgres sqlalchemy neo4j)

cd "$HARNESS_DIR"
for engine in "${ENGINES[@]}"; do
    uv run python run.py --engines "$engine"
done
