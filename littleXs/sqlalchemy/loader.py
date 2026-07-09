"""
One-shot bulk loader: seeds correctness_seed.json into the SQLAlchemy/ORM backend.
SQLAlchemy-ORM-native counterpart to littleXs/postgres/loader.py (pure ORM, no raw SQL).
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import Base, Profile, Follow, Tweet

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres@localhost:5433/littleX"
)

DEFAULT_SEED_PATH = Path(__file__).parent.parent.parent / "dataset" / "correctness_seed.json"


def load(seed_path: Path) -> None:
    seed = json.loads(seed_path.read_text())

    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        profiles = [
            Profile(username=p["username"], bio=p["bio"]) for p in seed["profiles"]
        ]
        session.add_all(profiles)
        session.flush()

        profile_id_map: dict[str, int] = {
            p["id"]: profile.id for p, profile in zip(seed["profiles"], profiles)
        }
        assert len(profile_id_map) == len(seed["profiles"])
        print(f"profiles inserted: {len(profile_id_map)}")

        follows = [
            Follow(
                follower_id=profile_id_map[f["follower"]],
                followee_id=profile_id_map[f["followee"]],
            )
            for f in seed["follows"]
        ]
        session.add_all(follows)
        print(f"follows inserted: {len(seed['follows'])}")

        tweets = [
            Tweet(
                seed_id=t["id"],
                author_id=profile_id_map[t["author"]],
                content=t["content"],
                created_at=datetime.fromisoformat(t["created_at"]),
                likes=t["likes"],
                comments=t["comments"],
            )
            for t in seed["tweets"]
        ]
        session.add_all(tweets)
        print(f"tweets inserted: {len(seed['tweets'])}")

        session.commit()


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SEED_PATH
    load(path)
