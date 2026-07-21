"""
Latency harness for the littleX DB benchmark

Per engine x workload: warmup requests (untimed), then M timed requests
rotating round-robin through the seeded users

p50/p95/p99 appended to the CSV - server-side span (in-handler
x-server-total-ms header / jac report field) is the headline metric;
client round-trip is kept as a sanity column

Workloads: feed, profile, create_tweet. NOTE create_tweet WRITES: it grows
the DB (reseed before oracle re-runs) and jac's span excludes its post-walker
Mongo commit while baselines' INSERT is in-span - footnote when comparing.

Run ONE engine at a time on an idle machine

Usage:
    python run.py --engines postgres [--workloads feed,profile]
                  [--name myexperiment] [--requests 200] [--warmup 20]
"""

import argparse
import csv
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from oracle import DEFAULT_URLS, ENGINES, TOKENS_DIR, load_tokens

SCRIPT_DIR = Path(__file__).resolve().parent
TIMEOUT = 30


def make_client(base_url):
    """One persistent connection per engine run (keep-alive), like a real client."""
    return httpx.Client(base_url=base_url, timeout=TIMEOUT)


def _jac_walker(client, name, body, token):
    """POST a walker; return (reports[0] payload dict, server_ms)."""
    r = client.post(
        f"/walker/{name}", json=body, headers={"Authorization": f"Bearer {token}"}
    )
    r.raise_for_status()
    resp = r.json()
    data = resp.get("data") or {}
    if "reports" in data:  # classic envelope
        if not resp.get("ok"):
            raise RuntimeError(f"Walker error: {resp.get('error')}")
        reports = data["reports"]
        if not reports:
            raise RuntimeError(f"no reports from walker {name}")
        payload = reports[0]
    else:  # lean-response mode: body IS the report dict
        payload = resp
    srv = r.headers.get("x-server-total-ms")
    return payload, float(srv) if srv else float(payload["server_total_ms"])


def _baseline(client, method, path, token, json=None):
    """Hit a baseline endpoint; return (parsed body, server_ms from header).

    Missing header = hard error (endpoint not instrumented), not a silent zero.
    """
    r = client.request(
        method, path, json=json, headers={"Authorization": f"Bearer {token}"}
    )
    r.raise_for_status()
    return r.json(), float(r.headers["x-server-total-ms"])


def fetch_feed(client, engine, token, i):
    if engine == "jaseci":
        payload, srv = _jac_walker(client, "load_feed", {}, token)
        return payload["feed"], srv
    return _baseline(client, "GET", "/feed", token)


# TODO(you): fetch_feed_page(client, engine, token, i) — jaseci: walker
# "load_feed_page" (already registered on the jaseci-rel app), baselines:
# GET /feed_page. Register as "feed_page" in WORKLOADS below.
def fetch_profile(client, engine, token, i):
    if engine == "jaseci":
        payload, srv = _jac_walker(client, "get_profile", {}, token)
        return payload["profile"], srv
    return _baseline(client, "GET", "/profile", token)


def fetch_create_tweet(client, engine, token, i):
    body = {"seed_id": f"bench_{i}", "content": f"benchmark tweet {i} #bench"}
    if engine == "jaseci":
        payload, srv = _jac_walker(client, "create_tweet", body, token)
        return payload["tweet"], srv
    return _baseline(client, "POST", "/tweet", token, json=body)


# name -> fetch(client, engine, token, i) -> (result, server_ms)
WORKLOADS = {
    "feed": fetch_feed,
    "profile": fetch_profile,
    "create_tweet": fetch_create_tweet,
}


def run_engine(engine, base_url, tokens, n_warmup, n_requests, fetch):
    """Warmup (untimed), then n_requests timed calls, round-robin users.

    Returns (client_ms, server_ms, errors) - one sample per successful request.
    Warmup indexes are offset negative so write workloads (create_tweet) don't
    collide seed_ids with the timed phase.
    """
    usernames = sorted(tokens)
    client_ms, server_ms, errors = [], [], 0

    with make_client(base_url) as client:
        for i in range(n_warmup):
            try:
                fetch(client, engine, tokens[usernames[i % len(usernames)]], -1 - i)
            except Exception:
                pass

        for i in range(n_requests):
            token = tokens[usernames[i % len(usernames)]]
            t0 = time.perf_counter()
            try:
                _, srv = fetch(client, engine, token, i)
            except Exception as e:
                errors += 1
                print(f"    error on request {i}: {type(e).__name__}: {e}")
                continue
            client_ms.append((time.perf_counter() - t0) * 1000)
            server_ms.append(srv)

        return client_ms, server_ms, errors


def percentile(sorted_ms, q):
    """Nearest-rank percentile from an already-sorted list."""
    idx = min(round(q * (len(sorted_ms) - 1)), len(sorted_ms) - 1)
    return sorted_ms[idx]


def stats(samples, prefix=""):
    """p50/p95/p99/mean/min/max column block from raw samples."""
    s = sorted(samples)
    return {
        f"{prefix}p50_ms": round(percentile(s, 0.5), 3),
        f"{prefix}p95_ms": round(percentile(s, 0.95), 3),
        f"{prefix}p99_ms": round(percentile(s, 0.99), 3),
        f"{prefix}mean_ms": round(sum(s) / len(s), 3),
        f"{prefix}min_ms": round(s[0], 3),
        f"{prefix}max_ms": round(s[-1], 3),
    }


def write_row(output, row):
    output.parent.mkdir(parents=True, exist_ok=True)
    new_file = not output.exists()
    with output.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[1])
    parser.add_argument("--engines", default=",".join(ENGINES))
    parser.add_argument("--workloads", default="feed")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--tokens-dir", default=str(TOKENS_DIR))
    parser.add_argument(
        "--name",
        default="results",
        help="experiment name: rows go to results/csv/<name>.csv",
    )
    parser.add_argument(
        "--output", default=None, help="explicit CSV path (overrides --name)"
    )

    for eng in ENGINES:
        parser.add_argument(f"--url-{eng}", default=DEFAULT_URLS[eng])
    args = parser.parse_args()

    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    workloads = [w.strip() for w in args.workloads.split(",") if w.strip()]
    unknown = [w for w in workloads if w not in WORKLOADS]
    if unknown:
        raise SystemExit(f"unknown workloads {unknown}; have {list(WORKLOADS)}")
    output = Path(args.output) if args.output else (
        SCRIPT_DIR.parent / "results" / "csv" / f"{args.name}.csv"
    )

    for engine in engines:
        tokens = load_tokens(engine, Path(args.tokens_dir))
        for workload in workloads:
            print(f"=== {engine} / {workload} ===")
            client_lat, server_lat, errors = run_engine(
                engine,
                getattr(args, f"url_{engine}"),
                tokens,
                args.warmup,
                args.requests,
                WORKLOADS[workload],
            )

            if not client_lat:
                print(f"   ALL {args.requests} requests failed - no samples\n")
                continue
            row = {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "engine": engine,
                "workload": workload,
                "requests": len(client_lat),
                "errors": errors,
                **stats(server_lat, "server_"),  # headline metric
                **stats(client_lat),  # sanity: round-trip incl. serve stack
            }
            write_row(output, row)
            print(
                f"  server p50={row['server_p50_ms']}ms p95={row['server_p95_ms']}ms "
                f"p99={row['server_p99_ms']}ms "
                f"(client p50={row['p50_ms']}ms) errors={errors}\n"
            )
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
