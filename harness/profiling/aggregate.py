"""Classify py-spy dump stacks into cost pools (leaf-priority, first-match-wins
across pool order). Zone split: span (walker/app) vs gap (response-pack) vs
framework. Usage: python aggregate.py <dumps.txt> <engine>
engine in {jac, jacrel, sqla, neo4j, pg}."""
import sys, re, collections

SIGS_JAC = [
    ('db_wait',        r'pymongo.*(network|_poll|recv|sock)|_socket|ssl\.py'),
    ('gti_decode',     r'topology_index|_get_col|topo_utils|resolve_hop|resolve_chain'),
    ('uuid_intern',    r'_intern_uuid|uuid\.py'),
    ('hydration',      r'_deserialize|deserialize|repair|schema_rules'),
    ('archetype_init', r'__init__ \(<string>'),
    ('grants',         r'check_read_access|access_level|Permission'),
    ('serialize_gap',  r'_serialize|serialize \(|iterencode|render \(.*responses|dumps|_finalize_call_response'),
    ('memory_l1l2',    r'memory_hierarchy|tiered|batch_get|commit \('),
    ('walker_app',     r'app\.jac'),
]
# pg-rel: jac walker runtime, but psycopg-backed with SQL topology resolution.
SIGS_JACREL = [
    ('db_wait',        r'psycopg|pq\.pyx|_socket|selectors|waiting\.py|generators\.py'),
    ('topology_sql',   r'resolve_hop_sql|resolve_chain_sql|execute_plan|resolve_hop|resolve_chain|topology'),
    ('uuid_intern',    r'_intern_uuid|uuid\.py'),
    ('hydration',      r'_deserialize|deserialize|repair|schema_rules|_id_to_stub'),
    ('archetype_init', r'__init__ \(<string>'),
    ('grants',         r'check_read_access|access_level|Permission'),
    ('serialize_gap',  r'_serialize|serialize \(|iterencode|render \(.*responses|dumps|_finalize_call_response'),
    ('memory_l1l2',    r'memory_hierarchy|tiered|batch_get|commit \('),
    ('walker_app',     r'app\.jac'),
]
SIGS_SQLA = [
    ('db_wait',        r'psycopg.*(wait|_poll|recv)|_socket|selectors'),
    ('orm_hydration',  r'loading\.py|_instance|InstanceState|process_rows'),
    ('orm_attrs',      r'attributes\.py|instrumentation'),
    ('session_uow',    r'session\.py|unitofwork'),
    ('query_compile',  r'compiler|elements\.py|annotation'),
    ('serialize_gap',  r'render \(.*responses|iterencode|dumps|jsonable|serialize'),
    ('app',            r'app\.py'),
]
SIGS_NEO4J = [
    ('db_wait',        r'socket|_socket|select\.py|selectors'),
    ('packstream',     r'packstream|_codec|wire_decode'),
    ('driver_hydrate', r'neo4j.*graph|neo4j.*[Rr]ecord|hydration'),
    ('session_tx',     r'session\.py|work\.py|transaction'),
    ('serialize_gap',  r'render \(.*responses|iterencode|dumps|jsonable|pydantic|serialize'),
    ('app',            r'app\.py'),
]
SIGS_PG = [
    ('db_wait',        r'psycopg.*(wait|_poll|recv)|_socket|selectors'),
    ('fetch_cursor',   r'psycopg|cursor\.py|rows\.py'),
    ('serialize_gap',  r'render \(.*responses|iterencode|dumps|jsonable|pydantic|serialize'),
    ('app',            r'app\.py'),
]
SIGS = {'jac': SIGS_JAC, 'jacrel': SIGS_JACREL, 'sqla': SIGS_SQLA,
        'neo4j': SIGS_NEO4J, 'pg': SIGS_PG}
SPAN_MARK = {
    'jac': r'app\.jac|execute_walker|spawn_', 'jacrel': r'app\.jac|execute_walker|spawn_',
    'sqla': r'app\.py', 'neo4j': r'app\.py', 'pg': r'app\.py',
}
GAP_MARK = r'_finalize_call_response|render \(.*responses|iterencode|JSONResponse|_serialize'

if __name__ == '__main__':
    eng = sys.argv[2] if len(sys.argv) > 2 else 'jac'
    sigs = SIGS[eng]
    text = open(sys.argv[1]).read()
    threads = re.split(r'\n(?=Thread )', text)
    active, idle = [], 0
    for t in threads:
        if not t.startswith('Thread'): continue
        if '(idle)' in t.splitlines()[0]: idle += 1; continue
        frames = [l.strip() for l in t.splitlines()[1:] if l.strip() and '(' in l]
        if frames: active.append(frames)

    pool_count = collections.Counter(); zone_count = collections.Counter()
    leaf_count = collections.Counter(); pool_zone = collections.Counter()
    for frames in active:
        leaf_count[frames[0][:70]] += 1
        joined = '\n'.join(frames)
        pool = 'other'
        for name, rx in sigs:
            if any(re.search(rx, f) for f in frames):
                pool = name; break
        if re.search(GAP_MARK, joined): zone = 'gap'
        elif re.search(SPAN_MARK[eng], joined): zone = 'span'
        else: zone = 'framework'
        pool_count[pool] += 1; zone_count[zone] += 1; pool_zone[(pool, zone)] += 1

    n = len(active)
    print(f"samples: {n} active / {idle} idle")
    print(f"zones: {dict(zone_count)}")
    print(f"\n{'pool':<16}{'share':>7}   zones")
    for p, c in pool_count.most_common():
        zs = {z: pool_zone[(p, z)] for z in ('span','gap','framework') if pool_zone[(p, z)]}
        print(f"{p:<16}{c/n*100:>6.1f}%   {zs}")
    print("\ntop leaf frames:")
    for f, c in leaf_count.most_common(14):
        print(f"  {c:>4}  {f}")
