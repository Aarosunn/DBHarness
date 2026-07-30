#!/usr/bin/env bash
set -euo pipefail
H=/home/aaron/Dev/Research/DatabaseResearch/DBHarness/harness
D=/home/aaron/Dev/Research/DatabaseResearch/DBHarness/dataset
cd "$H"
uv run python seed_jac.py --base-url http://localhost:8005 --seed "$D/t500_seed.json"
mkdir -p tokens-t500
mv tokens/tokens.jaseci.json tokens/jids.jaseci.json tokens-t500/
# restore T50 defaults
cp tokens-t50/tokens.jaseci.json tokens-t50/jids.jaseci.json tokens/
echo "JAC T500 SEEDED, tokens -> tokens-t500/"
