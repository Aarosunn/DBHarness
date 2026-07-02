#!/usr/bin/env python3
"""Deterministic seed generator for the DBHarness benchmark.

Usage: python generate.py --profile {correctness|uniform|skewed}
Writes dataset/<profile>_seed.json. Stdlib only.
"""
import argparse
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATASET_DIR = Path(__file__).resolve().parent
POOL_PATH = DATASET_DIR / "tweet_pool.json"
BASE_TIME = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
SEED = 42

PROFILES = {
    "correctness": {"users": 20, "follows_per_user": 5, "tweets_per_user": 10},
    "uniform": {"users": 500, "follows_per_user": 50, "tweets_per_user": 100},
}


def load_pool():
    with open(POOL_PATH) as f:
        return json.load(f)


def build(profile_name):
    if profile_name == "skewed":
        raise NotImplementedError("skewed profile deferred (power-law), TODO")

    cfg = PROFILES[profile_name]
    n_users, k_follows, tpu = cfg["users"], cfg["follows_per_user"], cfg["tweets_per_user"]

    random.seed(SEED)  # mandatory: byte-identical output across runs
    pool = load_pool()

    profiles = [
        {"id": f"user_{i}", "username": f"sim_user_{i}", "bio": ""}
        for i in range(n_users)
    ]

    follows = []
    for i in range(n_users):
        candidates = [j for j in range(n_users) if j != i]
        for j in random.sample(candidates, min(k_follows, len(candidates))):
            follows.append({"follower": f"user_{i}", "followee": f"user_{j}"})

    tweets = []
    tweet_id = 0
    for i in range(n_users):
        for r in range(tpu):
            # ponytail: interleave authors in time via round*n_users+i offset,
            # instead of a real shuffle, so a DESC created_at sort mixes authors.
            time_index = r * n_users + i
            created_at = (BASE_TIME + timedelta(seconds=time_index * 5)).strftime("%Y-%m-%dT%H:%M:%SZ")
            tweets.append({
                "id": f"tweet_{tweet_id}",
                "author": f"user_{i}",
                "created_at": created_at,
                "content": pool[tweet_id % len(pool)],
                "likes": [],
                "comments": [],
            })
            tweet_id += 1

    return {"profiles": profiles, "follows": follows, "tweets": tweets}


def self_check():
    data = build("correctness")
    profiles, follows, tweets = data["profiles"], data["follows"], data["tweets"]

    assert len(profiles) == 20, f"expected 20 profiles, got {len(profiles)}"
    user_ids = {p["id"] for p in profiles}
    assert len(user_ids) == 20, "duplicate user ids"

    seen_pairs = set()
    for f in follows:
        assert f["follower"] in user_ids, f"unknown follower {f['follower']}"
        assert f["followee"] in user_ids, f"unknown followee {f['followee']}"
        assert f["follower"] != f["followee"], f"self-follow {f}"
        pair = (f["follower"], f["followee"])
        assert pair not in seen_pairs, f"duplicate follow pair {pair}"
        seen_pairs.add(pair)

    assert len(tweets) == 200, f"expected 200 tweets, got {len(tweets)}"
    tweet_ids = [t["id"] for t in tweets]
    assert len(tweet_ids) == len(set(tweet_ids)), "duplicate tweet ids"
    for t in tweets:
        assert t["author"] in user_ids, f"unknown tweet author {t['author']}"

    print("self-check passed", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=list(PROFILES) + ["skewed"])
    args = parser.parse_args()

    data = build(args.profile)
    out_path = DATASET_DIR / f"{args.profile}_seed.json"
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"wrote {out_path} ({len(data['profiles'])} profiles, "
          f"{len(data['follows'])} follows, {len(data['tweets'])} tweets)")


if __name__ == "__main__":
    main()
    self_check()
