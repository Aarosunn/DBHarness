"""
Multi-root seed driver for the jac-scale LittleX benchmark server.

jac models each user as their OWN graph root, so seeding is per-user over
HTTP: register+login every profile, then call the walker:priv seeders
(seed_profile / seed_tweet / seed_follow from import_data.jac) on each
user's own token. Connect ops fire on_edge_created, so GTI builds at seed
time. Writes tokens.jaseci.json ({username: token}, same shape as
mint_tokens.py) and jids.jaseci.json ({username: profile_jid}).
"""

import argparse
import json
import os
import sys

import httpx

PASSWORD = "benchpass123"


def die(what, resp):
    sys.exit(f"FATAL: {what} -> HTTP {resp.status_code}: {resp.text}")


def reports(resp):
    """Walker envelope: {ok, data: {result, reports: [...]}, error, meta}."""
    return resp.json()["data"]["reports"]


class Seeder:
    def __init__(self, base_url):
        self.client = httpx.Client(base_url=base_url, timeout=30.0)

    def get_token(self, profile_id):
        """Register (idempotent: falls back to login if taken) -> JWT.

        Dev-server auth (rebased fp-new-main+) is USERNAME-only; the old
        email-identity flow 400s. Login handle = profile_id (user_0 ...).
        """
        cred = {"type": "password", "password": PASSWORD}
        r = self.client.post("/user/register", json={
            "identities": [{"type": "username", "value": profile_id}],
            "credential": cred,
        })
        # 400/409 = "already registered" on reruns.
        if r.status_code not in (200, 201, 400, 409):
            die(f"register {profile_id}", r)
        # Register never returns a token; login always.
        r = self.client.post("/user/login", json={
            "identity": {"type": "username", "value": profile_id},
            "credential": cred,
        })
        if r.status_code != 200:
            die(f"login {profile_id}", r)
        return r.json()["data"]["token"]

    def walker(self, name, token, body):
        r = self.client.post(
            f"/walker/{name}", json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
        if not (200 <= r.status_code < 300):
            die(f"walker {name} {body}", r)
        return r


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url",
                        default=os.environ.get("JAC_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--seed",
                        default=os.path.join(here, "..", "dataset", "correctness_seed.json"))
    parser.add_argument("--user-prefix", default="",
                        help="prefix for LOGIN handles (e.g. 'pg_'): registers a "
                             "distinct user namespace so an alternate anchor store "
                             "(postgres-L3) gets fresh roots instead of orphaned "
                             "identity rows. Display usernames are unaffected.")
    args = parser.parse_args()

    with open(os.path.abspath(args.seed)) as f:
        seed = json.load(f)
    profiles, follows, tweets = seed["profiles"], seed["follows"], seed["tweets"]

    s = Seeder(args.base_url)

    # 1. Register + login every profile.
    tokens = {}  # profile_id -> token
    for p in profiles:
        tokens[p["id"]] = s.get_token(args.user_prefix + p["id"])
    print(f"registered/logged in {len(tokens)} users"
          + (f" (handle prefix '{args.user_prefix}')" if args.user_prefix else ""))

    # 2. seed_profile on each user's own root; collect profile jids.
    jid_by_pid = {}
    jid_by_username = {}
    for p in profiles:
        r = s.walker("seed_profile", tokens[p["id"]],
                     {"username": p["username"], "bio": p["bio"]})
        jid = reports(r)[0]
        jid_by_pid[p["id"]] = jid
        jid_by_username[p["username"]] = jid
    print(f"seeded {len(jid_by_pid)} profiles")

    # 3. Tweets on the author's token, seed created_at (deterministic timeline).
    username_by_pid = {p["id"]: p["username"] for p in profiles}
    for t in tweets:
        s.walker("seed_tweet", tokens[t["author"]], {
            "seed_id": t["id"],
            "content": t["content"],
            "created_at": t["created_at"],
            "author_username": username_by_pid[t["author"]],
        })
    print(f"seeded {len(tweets)} tweets")

    # 4. Follows on the follower's token, target = followee's profile jid.
    for fw in follows:
        s.walker("seed_follow", tokens[fw["follower"]],
                 {"target_id": jid_by_pid[fw["followee"]]})
    print(f"seeded {len(follows)} follows")

    # 5. Token + jid maps, keyed by sim username (matches mint_tokens.py shape).
    tokens_dir = os.path.join(here, "tokens")
    os.makedirs(tokens_dir, exist_ok=True)
    tokens_path = os.path.join(tokens_dir, "tokens.jaseci.json")
    with open(tokens_path, "w") as f:
        json.dump({username_by_pid[pid]: tok for pid, tok in tokens.items()}, f)
    jids_path = os.path.join(tokens_dir, "jids.jaseci.json")
    with open(jids_path, "w") as f:
        json.dump(jid_by_username, f)

    print(f"done: {len(tokens)} users, {len(jid_by_pid)} profiles, "
          f"{len(tweets)} tweets, {len(follows)} follows")
    print(f"wrote {tokens_path} and {jids_path}")


if __name__ == "__main__":
    main()
