"""Continuous load driver for the leaf A/B profile. Hits one walker on :8005."""
import json, sys, itertools, urllib.request
walker = sys.argv[1]
toks = json.load(open('/home/aaron/Dev/Research/DatabaseResearch/DBHarness/harness/tokens/tokens.jaseci.json'))
users = itertools.cycle(sorted(toks))
while True:
    u = next(users)
    req = urllib.request.Request(f'http://127.0.0.1:8005/walker/{walker}', data=b'{}',
        headers={'Authorization': f'Bearer {toks[u]}', 'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(req).read()
    except Exception:
        pass
