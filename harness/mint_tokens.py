"""
Offline JWT mint for the LittleX DB benchmark.
Run once after seeding, before the load harness. For every seeded user it
mints an HS256 token matching each server's `jwt.decode(..., algorithms=["HS256"])`
verify, and writes a {username: token} JSON map.
"""

import argparse
import json
import os
from datetime import datetime, timedelta, timezone

import jwt


JWT_SECRET = os.environ.get("JWT_SECRET", "supersecretkey_for_testing_only!")
JWT_ALGORITHM = "HS256"


def fetch_users_postgres():
    """(username, user_id_claim) pairs from Postgres/SQLAlchemy profiles."""
    import psycopg

    dsn = os.environ.get(
        "DATABASE_URL", "postgresql://postgres@localhost:5433/littleX"
    )
    with psycopg.connect(dsn) as conn:
        rows = conn.execute("SELECT id, username FROM profiles").fetchall()
    return [(username, int(id)) for id, username in rows]


def fetch_users_neo4j():
    """(username, user_id_claim) pairs from the Neo4j Profile nodes."""
    from neo4j import GraphDatabase

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "littleXpassword")
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        records, _, _ = driver.execute_query(
            "MATCH (p:Profile) RETURN p.id AS id, p.username AS username"
        )
    return [(r["username"], str(r["id"])) for r in records]


def mint(users, expiry_days):
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=expiry_days)
    return {
        username: jwt.encode(
            {"user_id": user_id, "exp": exp, "iat": now},
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )
        for username, user_id in users
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, choices=["postgres", "neo4j"])
    parser.add_argument("--output")
    parser.add_argument("--expiry-days", type=int, default=7)
    args = parser.parse_args()

    if args.engine == "postgres":
        users = fetch_users_postgres()
    else:
        users = fetch_users_neo4j()

    tokens = mint(users, args.expiry_days)

    tokens_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "tokens"
    )
    os.makedirs(tokens_dir, exist_ok=True)
    output = args.output or os.path.join(tokens_dir, f"tokens.{args.engine}.json")
    with open(output, "w") as f:
        json.dump(tokens, f)

    print(f"minted {len(tokens)} tokens -> {output}")


if __name__ == "__main__":
    main()
