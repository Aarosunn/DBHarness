# Shared helpers - source this, don't run it.
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_DIR="$(dirname "$SCRIPTS_DIR")"
ROOT_DIR="$(dirname "$HARNESS_DIR")"
LITTLEXS_DIR="$ROOT_DIR/littleXs"
RUN_DIR="$SCRIPTS_DIR/.run"   # pidfiles + server logs (gitignored)

mkdir -p "$RUN_DIR"

wait_port() { # wait_port NAME PORT [TIMEOUT_S]
    local name="$1" port="$2" timeout="${3:-30}"
    for ((i = 0; i < timeout; i++)); do
        if (echo >"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
            echo "  $name up on :$port"
            return 0
        fi
        sleep 1
    done
    echo "FATAL: $name not reachable on :$port after ${timeout}s" >&2
    return 1
}
