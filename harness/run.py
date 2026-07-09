"""
Latency harness for the littleX DB benchmark

Per engine: warmup requests (untimed), then M timed feed requests rotating
round-robin through the seeded users

p50/p95/p99 appended to results.csv

Run ONE engine at a time on an idle machine: client latency is the metric

Usage:
    python run.py --engines postgres [--requests 200] [--warmup 20]
"""

import argparse
import csv
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from oracle import DEFAULT_URLS, ENGINES, load_tokens

SCRIPT_DIR = Path(__file__).resolve().parent
TIMEOUT = 30


def make_client(base_url):
    """One persistent connection per engine run (keep-alive), like a real client."""
    return httpx.Client(base_url=base_url, timeout=TIMEOUT)


def fetch_feed(client, engine, token):
    """Fire one feed request; return the parsed feed list"""
    headers = {"Authorization": f"Bearer {token}"}
    if engine == "jaseci":
        r = client.post("/walker/load_feed", json={}, headers=headers)
        r.raise_for_status()
        body = r.json()
        if not body.get("ok"):
            raise RuntimeError(f"Walker error: {body.get('error')}")
        reports = body["data"]["reports"]
        return reports[0] if reports else []
    r = client.get("/feed", headers=headers)
    r.raise_for_status()
    return r.json()


def run_engine(engine, base_url, tokens, n_warmup, n_requests):
    """Warmup (untimed), then n_requests timed feed calls, round-robin users.

    Returns (latencies_ms, errors) - one sample per successful request.
    """
    usernames = sorted(tokens)
    latencies, errors = [], 0

    with make_client(base_url) as client:
        for i in range(n_warmup):
            try:
                fetch_feed(client, engine, tokens[usernames[i % len(usernames)]])
            except Exception:
                pass

        for i in range(n_requests):
            token = tokens[usernames[i % len(usernames)]]
            t0 = time.perf_counter()
            try:
                fetch_feed(client, engine, token)
            except Exception as e:
                errors += 1
                print(f"    error on request {i}: {type(e).__name__}: {e}")
                continue
            latencies.append((time.perf_counter() - t0) * 1000)

        return latencies, errors


def percentile(sorted_ms, q):
    """Nearest-rank percentile from an already-sorted list."""
    idx = min(round(q * (len(sorted_ms) - 1)), len(sorted_ms) - 1)
    return sorted_ms[idx]


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
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--tokens-dir", default=str(SCRIPT_DIR))
    parser.add_argument(
        "--output", default=str(SCRIPT_DIR.parent / "results" / "csv" / "results.csv")
    )

    for eng in ENGINES:
        parser.add_argument(f"--url-{eng}", default=DEFAULT_URLS[eng])
    args = parser.parse_args()

    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    output = Path(args.output)

    for engine in engines:
        print(f"=== {engine} ===")
        tokens = load_tokens(engine, Path(args.tokens_dir))
        lat, errors = run_engine(
            engine, getattr(args, f"url_{engine}"), tokens, args.warmup, args.requests
        )

        if not lat:
            print(f"   ALL {args.requests} requests failed - no samples\n")
            continue
        lat.sort()
        row = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "engine": engine,
            "workload": "feed",
            "requests": len(lat),
            "errors": errors,
            "p50_ms": round(percentile(lat, 0.5), 3),
            "p95_ms": round(percentile(lat, 0.95), 3),
            "p99_ms": round(percentile(lat, 0.99), 3),
            "mean_ms": round(sum(lat) / len(lat), 3),
            "min_ms": round(lat[0], 3),
            "max_ms": round(lat[-1], 3),
        }
        write_row(output, row)
        print(
            f"  p50={row['p50_ms']}ms p95={row['p95_ms']}ms "
            f"  p99={row['p99_ms']}ms errors={errors}\n"
        )


if __name__ == "__main__":
    main()
