"""Leaf A/B pool classifier. Sigs verified against the actual frames in
anchor_dumps.txt / leaf_dumps.txt (2026-07-29). Leaf-priority, first match
walking frames from innermost out. Same taxonomy both arms."""
import re, collections, json, sys

# (pool, regex) -- innermost-frame-first priority
SIGS = [
    ('db_wait',      r'recv_into|network_layer|_socket|ssl\.py|selectors'),
    ('bson_decode',  r'decode_all|bson/'),
    ('uuid',         r'uuid\.py|to_uuid \(utils\.jac|_intern_uuid'),
    ('build_object', r'__init__ \(<string>|deserialize_projected|_load_anchor|Permission'),
    ('value_decode', r'_deserialize_value|coerce \('),
    ('serialize',    r'_serialize_attrs|_serialize_value|iterencode|render \(.*responses|dumps|_finalize_call_response|serialize \('),
    ('topology',     r'topology_index|gti_cache|decode_cached|_get_col|resolve_hop \(|resolve_chain|edges_to_nodes'),
    ('visit_dispatch', r'osp_kernel|osp_spawn|osp_visit|run_typed|run_untyped|node_desc|spawn_call'),
    ('memory_l1l2',  r'memory\.impl\.jac|tiered|batch_get|execute_plan \(memory\.impl'),
    ('mongo_plan',   r'execute_plan \(memory_hierarchy|pymongo|cursor'),
    ('resolver',     r'resolver\.jac|resolver\.impl|query_utils'),
    ('app',          r'app\.jac'),
]
GAP = r'render \(.*responses|iterencode|_finalize_call_response|JSONResponse|responses\.py'
SPAN = r'app\.jac|execute_walker|spawn|resolver|execute_plan|serializer\.impl'

def load(path):
    text = open(path).read()
    out = []
    for t in re.split(r'\n(?=Thread )', text):
        if not t.startswith('Thread') or '(idle)' in t.splitlines()[0]: continue
        frames = [l.strip() for l in t.splitlines()[1:] if l.strip() and '(' in l]
        if frames: out.append(frames)
    return out

result = {}
for arm in ('anchor','leaf'):
    stacks = load(f'{arm}_dumps.txt')
    pools = collections.Counter(); zones = collections.Counter()
    unmatched = collections.Counter()
    for frames in stacks:
        pool = None
        for f in frames:                      # innermost first
            for name, rx in SIGS:
                if re.search(rx, f):
                    pool = name; break
            if pool: break
        if pool is None:
            pool = 'other'; unmatched[frames[0][:70]] += 1
        joined = '\n'.join(frames)
        zone = 'gap' if re.search(GAP, joined) else ('span' if re.search(SPAN, joined) else 'framework')
        pools[pool] += 1; zones[zone] += 1
    n = len(stacks)
    result[arm] = {'n': n, 'pools': dict(pools), 'zones': dict(zones)}
    print(f"\n=== {arm}: {n} active | zones {dict(zones)} ===")
    for p, c in pools.most_common():
        print(f"  {p:<14} {c:>4}  {c/n*100:5.1f}%")
    if unmatched:
        print("  -- unmatched leaves (in 'other'):")
        for f, c in unmatched.most_common(6): print(f"     {c:>3}  {f}")
json.dump(result, open('pool_counts.json','w'), indent=1)
