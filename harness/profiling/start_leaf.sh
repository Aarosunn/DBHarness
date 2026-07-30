#!/usr/bin/env bash
# Boot littleX-mongo jac server on :8005 with leaf-materialize, detached.
set -u
APP=/home/aaron/Dev/Research/DatabaseResearch/DBHarness/littleXs/jaseci
RUN=/home/aaron/Dev/Research/DatabaseResearch/DBHarness/harness/scripts/.run
BIN=/home/aaron/Dev/Research/DatabaseResearch/JaseciFork/jac/zig-out/bin/jac

pkill -f "start -p 8005" 2>/dev/null
sleep 2

export JAC_ACCESS_LOG=0 JAC_REPORT_ECHO=0 JAC_API_LEAN_RESPONSE=1
export JAC_BATCH_L3=1 JAC_COMPILED_SERIALIZER=1 JAC_CROSS_ROOT_RESOLVE=1
export JAC_GC_FREEZE=1 JAC_GTI_CACHE=1 JAC_LAZY_HYDRATION=1 JAC_MEM_POOL=1
export JAC_TOPOLOGY_INDEX=1 JAC_READ_ONLY=1 JAC_FAST_BUILD=1
export JAC_ORDER_PUSHDOWN="Tweet:created_at:desc"
export JAC_PROJECTION="Tweet:content,created_at,author_username,likes,comments,seed_id;Profile:username,bio"
export JAC_LEAF_MATERIALIZE=Tweet

mkdir -p "$RUN"
cd "$APP"
rm -f "$RUN/jaseci-leaf.log"
setsid "$BIN" start -p 8005 > "$RUN/jaseci-leaf.log" 2>&1 < /dev/null &
echo $! > "$RUN/jaseci-leaf.pid"

for i in $(seq 1 90); do
    curl -s -o /dev/null http://127.0.0.1:8005/ 2>/dev/null && break
    sleep 1
done
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8005/ 2>/dev/null | grep -qE "40[45]"; then
    echo "leaf server UP pid=$(pgrep -f 'start -p 8005' | tail -1)"
else
    echo "leaf server FAILED:"
    tail -15 "$RUN/jaseci-leaf.log"
    exit 1
fi
