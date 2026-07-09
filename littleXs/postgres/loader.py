"""
One-shot bulk loader: seeds correctness_seed.json into the Postgres backend.
Postgres-native counterpart to littleXs/jaseci/import_data.jac.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.types.json import Json

from app import SCHEMA

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres@localhost:5433/littleX"
)

DEFAULT_SEED_PATH = Path(__file__).parent.parent.parent / "dataset" / "correctness_seed.json"


def load(seed_path: Path) -> None:
    seed = json.loads(seed_path.read_text())

    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(SCHEMA)

        profile_id_map: dict[str, int] = {}
        for p in seed["profiles"]:
            cur = conn.execute(
                "INSERT INTO profiles (username, bio) VALUES (%s, %s) RETURNING id",
                (p["username"], p["bio"]),
            )
            row = cur.fetchone()
            assert row is not None
            profile_id_map[p["id"]] = row[0]
        assert len(profile_id_map) == len(seed["profiles"])
        print(f"profiles inserted: {len(profile_id_map)}")

        for f in seed["follows"]:
            conn.execute(
                "INSERT INTO follows (follower_id, followee_id) VALUES (%s, %s)",
                (profile_id_map[f["follower"]], profile_id_map[f["followee"]]),
            )
        print(f"follows inserted: {len(seed['follows'])}")

        for t in seed["tweets"]:
            conn.execute(
                """
                INSERT INTO tweets (seed_id, author_id, content, created_at, likes, comments)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    t["id"],
                    profile_id_map[t["author"]],
                    t["content"],
                    datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")),
                    t["likes"],
                    Json(t["comments"]),
                ),
            )
        print(f"tweets inserted: {len(seed['tweets'])}")

        conn.commit()


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SEED_PATH
    load(path)
