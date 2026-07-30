"""Continuous load driver for profiling passes. Runs until killed.
Usage: python load_driver.py <engine> <workload> [url] [tokens_dir]
- engine: harness engine name (jaseci|postgres|sqlalchemy|neo4j). pg-rel runs
  as engine 'jaseci' with a url override to :8004 and its own tokens_dir.
"""
import itertools
import sys
from pathlib import Path

HARNESS = "/home/aaron/Dev/Research/DatabaseResearch/DBHarness/harness"
sys.path.insert(0, HARNESS)

from run import WORKLOADS, make_client
from oracle import DEFAULT_URLS, load_tokens, TOKENS_DIR

engine = sys.argv[1]
workload = sys.argv[2]
url = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_URLS[engine]
tokens_dir = Path(sys.argv[4]) if len(sys.argv) > 4 else TOKENS_DIR

fetch = WORKLOADS[workload]
tokens = load_tokens(engine, tokens_dir)
users = itertools.cycle(sorted(tokens))

with make_client(url) as client:
    i = 0
    while True:
        try:
            fetch(client, engine, tokens[next(users)], i)
        except Exception:
            pass
        i += 1
