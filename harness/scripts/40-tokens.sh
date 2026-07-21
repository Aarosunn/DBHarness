#!/usr/bin/env bash
# Mint offline JWTs for the baselines (jaseci tokens come from seed_jac.py).
# sqlalchemy shares tokens.postgres.json (same DB, same secret).
source "$(dirname "$0")/lib.sh"

cd "$HARNESS_DIR"
uv run python mint_tokens.py --engine postgres
uv run python mint_tokens.py --engine neo4j
# jac tokens are server-side records with a TTL - refresh via login every
# session (server must be up on :8000).
uv run python jac_login.py
