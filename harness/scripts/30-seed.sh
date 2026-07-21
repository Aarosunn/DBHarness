#!/usr/bin/env bash
# Seed all engines from dataset/correctness_seed.json.
# postgres loader covers sqlalchemy too (shared DB).
# seed_jac.py seeds per-user over HTTP (builds GTI at connect time) and
# writes tokens/tokens.jaseci.json + tokens/jids.jaseci.json.
source "$(dirname "$0")/lib.sh"

SEED="${1:-$ROOT_DIR/dataset/correctness_seed.json}"

echo "== postgres (also sqlalchemy) =="
(cd "$LITTLEXS_DIR/postgres" && uv run python loader.py "$SEED")

echo "== neo4j =="
(cd "$LITTLEXS_DIR/neo4j" && uv run python loader.py "$SEED")

echo "== jaseci (server must be up on :8000) =="
(cd "$HARNESS_DIR" && uv run python seed_jac.py --seed "$SEED")
