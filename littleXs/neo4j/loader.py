"""
One-shot bulk loader: seeds correctness_seed.json into the Neo4j backend.
Neo4j-native counterpart to littleXs/postgres/loader.py.
"""

import json
import sys
from pathlib import Path

from neo4j import GraphDatabase

from app import CONSTRAINTS, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER, _now

DEFAULT_SEED_PATH = Path(__file__).parent.parent.parent / "dataset" / "correctness_seed.json"

# created_at stored as an ISO-8601 string (matches jaseci's _now()), not a
# native Cypher temporal type -> avoids the neo4j.time/pytz hydration tax on
# every read. See app.py::_now.
PROFILES_CYPHER = """
UNWIND $rows AS row
CREATE (p:Profile {id: randomUUID(), username: row.username, bio: row.bio, created_at: $now})
RETURN row.id AS seed_id, p.id AS neo4j_id
"""

FOLLOWS_CYPHER = """
UNWIND $rows AS row
MATCH (a:Profile {id: row.follower_id}), (b:Profile {id: row.followee_id})
CREATE (a)-[:FOLLOWS]->(b)
"""

TWEETS_CYPHER = """
UNWIND $rows AS row
MATCH (author:Profile {id: row.author_id})
CREATE (author)-[:POSTED]->(:Tweet {
    id: randomUUID(),
    seed_id: row.seed_id,
    content: row.content,
    author_username: author.username,
    created_at: row.created_at,
    likes: row.likes,
    comments: []
})
"""


def load(seed_path: Path) -> None:
    seed = json.loads(seed_path.read_text())

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            for stmt in CONSTRAINTS:
                session.run(stmt)

            result = session.run(PROFILES_CYPHER, rows=seed["profiles"], now=_now())
            profile_id_map = {r["seed_id"]: r["neo4j_id"] for r in result}
            assert len(profile_id_map) == len(seed["profiles"])
            print(f"profiles inserted: {len(profile_id_map)}")

            follow_rows = [
                {
                    "follower_id": profile_id_map[f["follower"]],
                    "followee_id": profile_id_map[f["followee"]],
                }
                for f in seed["follows"]
            ]
            session.run(FOLLOWS_CYPHER, rows=follow_rows)
            print(f"follows inserted: {len(follow_rows)}")

            tweet_rows = [
                {
                    "author_id": profile_id_map[t["author"]],
                    "seed_id": t["id"],
                    "content": t["content"],
                    "created_at": t["created_at"],
                    "likes": t["likes"],
                }
                for t in seed["tweets"]
            ]
            session.run(TWEETS_CYPHER, rows=tweet_rows)
            print(f"tweets inserted: {len(tweet_rows)}")
    finally:
        driver.close()


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SEED_PATH
    load(path)
