#!/usr/bin/env bash
# Tweets-per-user scale sweep: 4 levels x 5 arms, server-side load_feed p50.
# Warmup 100 = one full-cohort rotation (communal-warming hygiene) before timing.
set -uo pipefail
H=/home/aaron/Dev/Research/DatabaseResearch/DBHarness/harness
P=$H/profiling/pg_cohort.sh
PFX="${SWEEP_PREFIX:-sweep2}"   # sweep = 2026-07-30 pre-fix run; sweep2 = post-leaf-fix rerun
cd "$H"

run_level() {
    local lvl=$1 db=$2 req=$3
    echo "===== LEVEL $lvl (db=$db, req=$req) ====="
    bash "$P" "$db"
    # smoke: 2 req/arm, fail loud before burning the timed run
    uv run python run.py --engines postgres,sqlalchemy,neo4j --workloads feed \
        --tokens-dir "tokens-$lvl" --requests 2 --warmup 0 --name "${PFX}_smoke_$lvl" || return 1
    uv run python run.py --engines jaseci --url-jaseci http://localhost:8005 \
        --tokens-dir "tokens-$lvl" --workloads feed,feed_leaf --requests 2 --warmup 0 \
        --name "${PFX}_smoke_$lvl" || return 1
    echo "--- smoke ok, timed runs ---"
    uv run python run.py --engines postgres,sqlalchemy,neo4j --workloads feed \
        --tokens-dir "tokens-$lvl" --requests "$req" --warmup 100 --name "${PFX}_${lvl}_baselines"
    uv run python run.py --engines jaseci --url-jaseci http://localhost:8005 \
        --tokens-dir "tokens-$lvl" --workloads feed --requests "$req" --warmup 100 \
        --name "${PFX}_${lvl}_jacanchor"
    uv run python run.py --engines jaseci --url-jaseci http://localhost:8005 \
        --tokens-dir "tokens-$lvl" --workloads feed_leaf --requests "$req" --warmup 100 \
        --name "${PFX}_${lvl}_jacleaf"
    echo "===== LEVEL $lvl DONE ====="
}

run_level t20  littleX_t20  500 || exit 1
run_level t50  littleX      500 || exit 1
run_level t100 littleX_t100 500 || exit 1
run_level t200 littleX_t200 500 || exit 1
run_level t500 littleX_t500 500 || exit 1

bash "$P" littleX   # restore default
echo "SWEEP DONE"
