#!/usr/bin/env bash
set -euo pipefail
H=/home/aaron/Dev/Research/DatabaseResearch/DBHarness/harness
D=/home/aaron/Dev/Research/DatabaseResearch/DBHarness/dataset
cd "$H"
# preserve the live T50 token files
mkdir -p tokens-t50 && cp tokens/tokens.jaseci.json tokens/jids.jaseci.json tokens-t50/ 2>/dev/null || true
for c in t20 t100 t200; do
    uv run python seed_jac.py --seed "$D/${c}_seed.json"
    mkdir -p "tokens-$c"
    mv tokens/tokens.jaseci.json tokens/jids.jaseci.json "tokens-$c/"
    echo "=== jac cohort $c seeded, tokens -> tokens-$c/ ==="
done
# restore T50 tokens as the default set
cp tokens-t50/tokens.jaseci.json tokens-t50/jids.jaseci.json tokens/
echo "JAC SEEDING DONE"
