#!/usr/bin/env bash
# Start/stop the four littleX app servers.
#   ./20-servers.sh start|stop|status [--gti on|off] [--cross-root on|off] [--batch on|off]
# Flag args set the jac ablation env vars (JAC_TOPOLOGY_INDEX etc.) for the
# jaseci server ONLY - they override jac.toml [run] values. Omitted = toml.
# Verify what the serve worker sees: POST /walker/runtime_probe.
# Ports: jaseci 8000, postgres 8001, sqlalchemy 8002, neo4j 8003.
# Logs + pidfiles in scripts/.run/.
source "$(dirname "$0")/lib.sh"

onoff() { # onoff VALUE -> 1|0
    case "$1" in
    on)  echo 1 ;;
    off) echo 0 ;;
    *)   echo "bad flag value '$1' (use on|off)" >&2; exit 1 ;;
    esac
}

CMD="${1:-}"; shift || true
while [[ $# -gt 0 ]]; do
    case "$1" in
    --gti)        export JAC_TOPOLOGY_INDEX="$(onoff "$2")"; shift 2 ;;
    --cross-root) export JAC_CROSS_ROOT_RESOLVE="$(onoff "$2")"; shift 2 ;;
    --batch)      export JAC_BATCH_L3="$(onoff "$2")"; shift 2 ;;
    --read-only)  export JAC_READ_ONLY="$(onoff "$2")"; shift 2 ;;
    *)            echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

# engine:port pairs; baselines run uvicorn, jaseci runs `jac start`.
ENGINES=(jaseci:8000 postgres:8001 sqlalchemy:8002 neo4j:8003)

# Fork dev binary (zig -Ddev build: runs the in-repo JaseciFork source LIVE,
# so the checked-out branch = the served runtime). The uv-tool jac on PATH is
# stock PyPI 0.16.2 - wrong runtime, silently ignores [dev]/[scale.database].
JAC_BIN="${JAC_BIN:-/home/aaron/Dev/Research/DatabaseResearch/JaseciFork/jac/zig-out/bin/jac}"

# CPU pinning (see compose.yml header): DBs 0-5, app servers 6-13, bench 14-19.
APP_CORES="${APP_CORES:-6-13}"

start_one() {
    local engine="$1" port="$2"
    local pidfile="$RUN_DIR/$engine.pid" log="$RUN_DIR/$engine.log"
    if [[ -f $pidfile ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        echo "  $engine already running (pid $(cat "$pidfile"))"
        return 0
    fi
    cd "$LITTLEXS_DIR/$engine"
    if [[ $engine == jaseci ]]; then
        # jac reads jac.toml here; runtime = JaseciFork checkout via dev binary.
        nohup taskset -c "$APP_CORES" "$JAC_BIN" start -p "$port" >"$log" 2>&1 &
    else
        nohup taskset -c "$APP_CORES" uv run uvicorn app:app --port "$port" >"$log" 2>&1 &
    fi
    echo $! >"$pidfile"
    wait_port "$engine" "$port" 60
}

stop_one() {
    local engine="$1"
    local pidfile="$RUN_DIR/$engine.pid"
    if [[ -f $pidfile ]]; then
        kill "$(cat "$pidfile")" 2>/dev/null && echo "  stopped $engine" \
            || echo "  $engine not running (stale pidfile)"
        rm -f "$pidfile"
    else
        echo "  $engine: no pidfile"
    fi
}

case "$CMD" in
start)
    for e in "${ENGINES[@]}"; do start_one "${e%%:*}" "${e##*:}"; done
    echo "all servers up"
    ;;
stop)
    for e in "${ENGINES[@]}"; do stop_one "${e%%:*}"; done
    ;;
status)
    for e in "${ENGINES[@]}"; do
        engine="${e%%:*}" port="${e##*:}"
        if (echo >"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
            echo "  $engine :$port UP"
        else
            echo "  $engine :$port down"
        fi
    done
    ;;
*)
    echo "usage: $0 start|stop|status" >&2
    exit 1
    ;;
esac
