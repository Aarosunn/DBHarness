#!/usr/bin/env python3
"""Cross-engine parity oracle for the LittleX DB benchmark.

Before any latency numbers are trusted, this proves every engine returns THE
SAME FEED per user. Ground truth is computed from the seed file itself (own
tweets + followees' tweets), so "all engines equally wrong" is also caught.

Membership (set of seed_ids) is the gate; ordering (created_at desc) is
checked per engine but only warns. Exit code 0 only if ALL engine x user
membership checks pass.

Usage:
    python oracle.py [--seed ../dataset/correctness_seed.json]
                     [--engines jaseci,postgres,sqlalchemy,neo4j]
                     [--tokens-dir ./tokens] [--users N] [--url-<engine> URL]

Wire shapes (verified against the servers):
    baselines: GET /feed, Bearer auth -> JSON list of tweets with `seed_id`
               (+ x-server-total-ms header, ignored here).
    jaseci:    POST /walker/load_feed, Bearer auth, body {} ->
               {"ok": bool, "data": {"result": ..., "reports": [...]}, ...};
               reports[0] = {"server_total_ms": float, "feed": [tweet, ...]}.
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

try:
    import httpx as http
except ImportError:  # ponytail: same .get/.post/.json surface for our use
    import requests as http

SCRIPT_DIR = Path(__file__).resolve().parent
TOKENS_DIR = SCRIPT_DIR / "tokens"
ENGINES = ["jaseci", "postgres", "sqlalchemy", "neo4j"]
DEFAULT_URLS = {
    "jaseci": "http://localhost:8000",
    "postgres": "http://localhost:8001",
    "sqlalchemy": "http://localhost:8002",
    "neo4j": "http://localhost:8003",
}
# sqlalchemy shares the postgres DB (same profile ids, same JWT secret),
# so its tokens are mintable as tokens.postgres.json.
TOKEN_FALLBACK = {"sqlalchemy": "postgres"}
TIMEOUT = 30


def expected_feeds(seed):
    """{username: set(seed_id)} = own tweets + tweets of everyone followed."""
    username_of = {p["id"]: p["username"] for p in seed["profiles"]}
    tweets_of = {pid: set() for pid in username_of}
    for t in seed["tweets"]:
        tweets_of[t["author"]].add(t["id"])
    feeds = {pid: set(tweets_of[pid]) for pid in username_of}
    for f in seed["follows"]:
        feeds[f["follower"]] |= tweets_of[f["followee"]]
    return {username_of[pid]: ids for pid, ids in feeds.items()}


def load_tokens(engine, tokens_dir):
    for name in (engine, TOKEN_FALLBACK.get(engine)):
        if name:
            path = tokens_dir / f"tokens.{name}.json"
            if path.exists():
                return json.loads(path.read_text())
    raise FileNotFoundError(f"no tokens.{engine}.json in {tokens_dir}")


def fetch_feed(engine, base_url, token):
    """Return the feed as a list of tweet dicts (each with seed_id, created_at)."""
    headers = {"Authorization": f"Bearer {token}"}
    if engine == "jaseci":
        r = http.post(
            f"{base_url}/walker/load_feed", json={}, headers=headers, timeout=TIMEOUT
        )
        r.raise_for_status()
        body = r.json()
        data = body.get("data") or {}
        if "reports" in data:  # classic envelope
            if not body.get("ok"):
                raise RuntimeError(f"walker error: {body.get('error')}")
            reports = data["reports"]
            return reports[0]["feed"] if reports else []
        return body["feed"]  # lean-response mode: body IS the report
    r = http.get(f"{base_url}/feed", headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


# TODO(you): feed_page parity — expected_pages(seed, expected) computes the
# per-user ordered top-20 (sort ids by seed created_at desc, take 20; stamps
# are unique so no tie handling needed), fetch_feed_page() hits
# /walker/load_feed_page / GET /feed_page, and a --page flag switches the main
# loop to an ordered-list compare. Ran 2026-07-16: 20/20 jac + 100/100 each
# baseline before removal.
def order_violations(tweets):
    """Indexes where created_at increases (feed must be newest-first)."""
    stamps = [
        datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")) for t in tweets
    ]
    return [i for i in range(1, len(stamps)) if stamps[i] > stamps[i - 1]]


def main():
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "--seed", default=str(SCRIPT_DIR / ".." / "dataset" / "correctness_seed.json")
    )
    parser.add_argument("--engines", default=",".join(ENGINES))
    parser.add_argument("--tokens-dir", default=str(TOKENS_DIR))
    parser.add_argument(
        "--users", type=int, default=None, help="check only the first N seeded users"
    )
    for eng in ENGINES:
        parser.add_argument(
            f"--url-{eng}",
            default=os.environ.get(f"{eng.upper()}_URL", DEFAULT_URLS[eng]),
        )
    args = parser.parse_args()

    seed = json.loads(Path(args.seed).resolve().read_text())
    expected = expected_feeds(seed)
    usernames = [p["username"] for p in seed["profiles"]][: args.users]
    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    tokens_dir = Path(args.tokens_dir)

    tokens, passed, failed = {}, {e: 0 for e in engines}, {e: 0 for e in engines}
    for eng in engines:
        try:
            tokens[eng] = load_tokens(eng, tokens_dir)
        except Exception as e:
            print(f"WARN  {eng}: cannot load tokens ({e}); all its checks FAIL")
            tokens[eng] = {}

    for user in usernames:
        for eng in engines:
            url = getattr(args, f"url_{eng}")
            token = tokens[eng].get(user)
            if token is None:
                print(f"FAIL  {user:<14} {eng:<11} no token")
                failed[eng] += 1
                continue
            try:
                feed = fetch_feed(eng, url, token)
            except Exception as e:
                print(f"FAIL  {user:<14} {eng:<11} {type(e).__name__}: {e}")
                failed[eng] += 1
                continue
            got = {t["seed_id"] for t in feed}
            dupes = {}
            if len(feed) != len(got):
                dupes = {
                    s: n
                    for s, n in Counter(t["seed_id"] for t in feed).items()
                    if n > 1
                }
            missing, extra = expected[user] - got, got - expected[user]
            if missing or extra or dupes:
                if missing or extra:
                    print(
                        f"FAIL  {user:<14} {eng:<11} missing={sorted(missing)} "
                        f"extra={sorted(extra)}"
                    )
                if dupes:
                    print(
                        f"FAIL  {user:<14} {eng:<11} duplicates="
                        f"{sorted(dupes.items())}"
                    )
                failed[eng] += 1
            else:
                print(f"PASS  {user:<14} {eng:<11} {len(got)} tweets")
                passed[eng] += 1
            bad = order_violations(feed)
            if bad:
                print(
                    f"WARN  {user:<14} {eng:<11} created_at not desc at "
                    f"positions {bad[:5]}{'...' if len(bad) > 5 else ''}"
                )

    print("\n=== summary ===")
    print(f"{'engine':<12} {'passed':>7} {'failed':>7}")
    for eng in engines:
        print(f"{eng:<12} {passed[eng]:>7} {failed[eng]:>7}")
    total_failed = sum(failed.values())
    print(
        f"\n{'PARITY OK' if total_failed == 0 else 'PARITY BROKEN'} "
        f"({sum(passed.values())} passed, {total_failed} failed)"
    )
    sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    main()
