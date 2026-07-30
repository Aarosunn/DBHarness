#!/usr/bin/env bash
# Boot the pg-rel jac server on :8004, fully detached. Usage:
#   start_pgrel.sh seed   # writes enabled (for seeding)
#   start_pgrel.sh bench  # read_only (for bench/profile)
#   start_pgrel.sh trace  # bench + JAC_QUERY_TRACE=1
set -u
MODE="${1:-bench}"
APP=/home/aaron/Dev/Research/DatabaseResearch/DBHarness/littleXs/jaseci-rel
RUN=/home/aaron/Dev/Research/DatabaseResearch/DBHarness/harness/scripts/.run
BIN=/home/aaron/Dev/Research/DatabaseResearch/JaseciFork/jac/zig-out/bin/jac

pkill -f "start -p 8004" 2>/dev/null
sleep 3

export JAC_SCALE_BACKEND=postgres-rel
export POSTGRESQL_URI="postgresql://postgres@localhost:5433/littleX"
export JAC_TOPOLOGY_SQL=1
export JAC_TOPOLOGY_SQL_CHAIN=1
export JAC_GC_FREEZE=1
export JAC_READ_AUTOCOMMIT=1
export JAC_API_LEAN_RESPONSE=1
export JAC_COMPILED_SERIALIZER=1
export JAC_LAZY_HYDRATION=1
export JAC_MEM_POOL=1
export JAC_ACCESS_LOG=0
export JAC_REPORT_ECHO=0
export JAC_PROJECTION="Tweet:content,created_at,author_username,likes,comments,seed_id;Profile:username,bio"
unset JAC_GTI_CACHE
case "$MODE" in
    seed)  unset JAC_READ_ONLY ;;
    bench) export JAC_READ_ONLY=1 ;;
    trace) export JAC_READ_ONLY=1; export JAC_QUERY_TRACE=1 ;;
esac
# extra env passed as KEY=VAL after the mode
shift || true
for kv in "$@"; do export "$kv"; done

cd "$APP"
rm -f "$RUN/jaseci-rel.log"
setsid taskset -c 6-13 "$BIN" start -p 8004 > "$RUN/jaseci-rel.log" 2>&1 < /dev/null &
echo $! > "$RUN/jaseci-rel.pid"

for i in $(seq 1 60); do
    curl -s -o /dev/null http://127.0.0.1:8004/ 2>/dev/null && break
    sleep 1
done
if curl -sI http://127.0.0.1:8004/ 2>/dev/null | grep -qi "^server:"; then
    echo "pg-rel UP ($MODE) pid=$(pgrep -f 'start -p 8004' | tail -1)"
else
    echo "pg-rel FAILED to start ($MODE):"
    grep -av "^$" "$RUN/jaseci-rel.log" | tail -6
    exit 1
fi
