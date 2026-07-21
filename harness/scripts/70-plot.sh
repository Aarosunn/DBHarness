#!/usr/bin/env bash
# Render plots: server-side headline + client round-trip sanity view.
source "$(dirname "$0")/lib.sh"

cd "$HARNESS_DIR"
uv run python plots/plot.py
uv run python plots/plot.py --metric client
