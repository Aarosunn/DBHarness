#!/usr/bin/env bash
# Point the postgres (:8001) + sqlalchemy (:8002) apps at a cohort DB.
# Usage: pg_cohort.sh littleX_t20   (or littleX to restore the T50 default)
set -u
DB="$1"
LX=/home/aaron/Dev/Research/DatabaseResearch/DBHarness/littleXs
RUN=/home/aaron/Dev/Research/DatabaseResearch/DBHarness/harness/scripts/.run
for e in postgres sqlalchemy; do
    [ -f "$RUN/$e.pid" ] && kill "$(cat "$RUN/$e.pid")" 2>/dev/null
    rm -f "$RUN/$e.pid"
done
sleep 2
export DATABASE_URL_PG="postgresql://postgres@localhost:5433/$DB"
cd "$LX/postgres"
DATABASE_URL="$DATABASE_URL_PG" setsid taskset -c 6-13 uv run uvicorn app:app --port 8001 > "$RUN/postgres.log" 2>&1 < /dev/null &
echo $! > "$RUN/postgres.pid"
cd "$LX/sqlalchemy"
DATABASE_URL="postgresql+psycopg://postgres@localhost:5433/$DB" setsid taskset -c 6-13 uv run uvicorn app:app --port 8002 > "$RUN/sqlalchemy.log" 2>&1 < /dev/null &
echo $! > "$RUN/sqlalchemy.pid"
for p in 8001 8002; do
    for i in $(seq 1 40); do curl -s -o /dev/null -m 1 http://127.0.0.1:$p/ && break; sleep 1; done
done
echo "pg+sqla now on $DB"
