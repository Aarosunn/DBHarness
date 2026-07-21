"""Re-login every seeded jac user; rewrite tokens/tokens.jaseci.json.

jac tokens are SERVER-SIDE records in jac_db.auth_tokens with a TTL —
they die hours after login regardless of the JWT exp claim. Run this
before any oracle/bench session (cheap: 20 logins).
"""

import json
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
BASE_URL = "http://localhost:8000"
PASSWORD = "benchpass123"  # matches seed_jac.py


def main():
    # optional: --user-prefix pg_  (must match the prefix used at seed time)
    prefix = ""
    if "--user-prefix" in sys.argv:
        prefix = sys.argv[sys.argv.index("--user-prefix") + 1]
    seed_path = HERE.parent / "dataset" / "correctness_seed.json"
    if "--seed" in sys.argv:
        seed_path = Path(sys.argv[sys.argv.index("--seed") + 1]).resolve()
    seed = json.loads(seed_path.read_text())
    client = httpx.Client(base_url=BASE_URL, timeout=30)
    tokens = {}
    for p in seed["profiles"]:
        # username-only auth on rebased fp-new-main+ dev server
        r = client.post("/user/login", json={
            "identity": {"type": "username", "value": prefix + p["id"]},
            "credential": {"type": "password", "password": PASSWORD},
        })
        if r.status_code != 200:
            raise SystemExit(f"LOGIN FAIL {p['id']}: {r.status_code} {r.text[:120]}")
        tokens[p["username"]] = r.json()["data"]["token"]
    out = HERE / "tokens" / "tokens.jaseci.json"
    out.write_text(json.dumps(tokens))
    print(f"re-logged {len(tokens)} users -> {out}")


if __name__ == "__main__":
    main()
