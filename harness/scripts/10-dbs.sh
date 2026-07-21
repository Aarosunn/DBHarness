#!/usr/bin/env bash
# Start the database containers (postgres :5433, neo4j :7687, mongo :27017).
source "$(dirname "$0")/lib.sh"

docker start littlex-pg littlex-mongo littlex-neo4j

wait_port postgres 5433
wait_port mongo 27017
wait_port neo4j-bolt 7687 60   # neo4j is the slow one
echo "all databases up"
