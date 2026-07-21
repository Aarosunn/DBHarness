#!/usr/bin/env bash
# Full end-to-end: dbs -> servers -> seed -> tokens -> parity gate -> bench -> plot.
# Servers are left running afterwards (./20-servers.sh stop to tear down).
# Skip seeding on an already-seeded stack: SKIP_SEED=1 ./all.sh
cd "$(dirname "$0")"
set -euo pipefail

./10-dbs.sh
./20-servers.sh start
if [[ -z ${SKIP_SEED:-} ]]; then
    ./30-seed.sh
    ./40-tokens.sh
fi
./50-oracle.sh   # exits nonzero on parity failure -> stops here
./60-bench.sh
./70-plot.sh
echo "DONE - results/csv/results.csv + results/plots/"
