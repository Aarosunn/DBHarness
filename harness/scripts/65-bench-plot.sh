#!/usr/bin/env bash
# Bench + plot in one shot. All args pass through to run.py; --name and
# --workloads are also parsed here so each workload gets its plots.
#   ./65-bench-plot.sh --name exp1 --workloads feed,profile --engines jaseci,postgres
source "$(dirname "$0")/lib.sh"

NAME="results"
WORKLOADS="feed"
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
    case "${args[i]}" in
    --name)      NAME="${args[i+1]}" ;;
    --workloads) WORKLOADS="${args[i+1]}" ;;
    esac
done

cd "$HARNESS_DIR"
# bench client pinned away from DB (0-5) and app (6-13) cores - see compose.yml
taskset -c "${BENCH_CORES:-14-19}" uv run python run.py "$@"

for w in ${WORKLOADS//,/ }; do
    uv run python plots/plot.py --name "$NAME" --workload "$w"
    uv run python plots/plot.py --name "$NAME" --workload "$w" --metric client
done
