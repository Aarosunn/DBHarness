"""Span-only pool shares -> chart buckets (topo,hyd,app,sess,db,other).
Denominator = span-zone samples. Usage: python summarize_pools.py <dir> [stem:engine ...]
If no stems given, uses the default FILES map."""
import collections, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import aggregate as ag  # SIGS/SPAN_MARK/GAP_MARK

BUCKET = {
    'jac': {'gti_decode': 'topo', 'hydration': 'hyd', 'archetype_init': 'hyd',
            'uuid_intern': 'hyd', 'walker_app': 'app', 'memory_l1l2': 'sess',
            'grants': 'sess', 'db_wait': 'db'},
    'jacrel': {'topology_sql': 'topo', 'hydration': 'hyd', 'archetype_init': 'hyd',
               'uuid_intern': 'hyd', 'walker_app': 'app', 'memory_l1l2': 'sess',
               'grants': 'sess', 'db_wait': 'db'},
    'sqla': {'orm_hydration': 'hyd', 'orm_attrs': 'hyd', 'query_compile': 'sess',
             'session_uow': 'sess', 'app': 'app', 'db_wait': 'db'},
    'neo4j': {'packstream': 'hyd', 'driver_hydrate': 'hyd', 'session_tx': 'sess',
              'app': 'app', 'db_wait': 'db'},
    'pg': {'fetch_cursor': 'hyd', 'app': 'app', 'db_wait': 'db'},
}
ORDER = ['topo', 'hyd', 'app', 'sess', 'db', 'other']


def classify(path, eng):
    sigs = ag.SIGS[eng]
    text = open(path).read()
    threads = re.split(r'\n(?=Thread )', text)
    span_pools = collections.Counter(); n_span = 0
    for t in threads:
        if not t.startswith('Thread') or '(idle)' in t.splitlines()[0]:
            continue
        frames = [l.strip() for l in t.splitlines()[1:] if l.strip() and '(' in l]
        if not frames:
            continue
        joined = '\n'.join(frames)
        if re.search(ag.GAP_MARK, joined):
            continue
        if not re.search(ag.SPAN_MARK[eng], joined):
            continue
        pool = 'other'
        for name, rx in sigs:
            if any(re.search(rx, f) for f in frames):
                pool = name; break
        n_span += 1
        span_pools[BUCKET[eng].get(pool, 'other')] += 1
    return n_span, dict(span_pools)


DEFAULT_FILES = {
    'postgres_feed': 'pg', 'postgres_profile': 'pg',
    'sqlalchemy_feed': 'sqla', 'sqlalchemy_profile': 'sqla',
    'neo4j_feed': 'neo4j', 'neo4j_profile': 'neo4j',
    'jacmongo_feed': 'jac', 'jacmongo_profile': 'jac',
    'jacrel_feed': 'jacrel', 'jacrel_profile': 'jacrel',
}

d = Path(sys.argv[1])
files = {}
if len(sys.argv) > 2:
    for spec in sys.argv[2:]:
        stem, eng = spec.split(':')
        files[stem] = eng
else:
    files = DEFAULT_FILES

out = {}
for stem, eng in files.items():
    p = d / f"{stem}_dumps.txt"
    if not p.exists():
        out[stem] = {'span_samples': 0, 'shares': {}, 'missing': True}
        continue
    n, pools = classify(p, eng)
    shares = {b: c / n for b, c in pools.items()} if n else {}
    out[stem] = {'span_samples': n, 'shares': shares}
print(json.dumps(out, indent=1))
