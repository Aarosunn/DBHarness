#!/usr/bin/env bash
# Cross-engine parity gate. Exit 0 = PARITY OK; nonzero = do NOT benchmark.
source "$(dirname "$0")/lib.sh"

# Guard: jac must be MONGO-backed. If the scale deps are missing from the jac
# env, jac silently falls back to a stdlib server on local SQLite - latencies
# become fantasy (no network hop) and cross-engine numbers are invalid.
# Fix when this trips: (cd littleXs/jaseci && jac install), restart, reseed.
anchors=$(docker exec littlex-mongo mongosh --quiet jac_db \
    --eval 'print(db.getCollection("_anchors").countDocuments())' 2>/dev/null || echo 0)
if [[ "${anchors:-0}" -eq 0 ]]; then
    echo "FATAL: jac_db._anchors is empty - jac server is NOT mongo-backed" >&2
    echo "       (stdlib-server fallback? see comment in this script)" >&2
    exit 1
fi

cd "$HARNESS_DIR"
uv run python oracle.py "$@"
