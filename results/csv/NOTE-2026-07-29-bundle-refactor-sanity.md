# Sanity run 2026-07-29 — post bundle-refactor (NOT real numbers)

Busy machine, sanity only. Config: all-flags recipe (GTI+cross-root+batch, READ_ONLY,
GTI_CACHE, COMPILED_SERIALIZER, PROJECTION arm-B, ORDER_PUSHDOWN='Tweet:created_at:desc',
MEM_POOL, LAZY_HYDRATION, GC_FREEZE, LEAN(+_jac_id), ACCESS_LOG=0, REPORT_ECHO=0).
Data: pre-existing uniform_seed (100 users), oracle run with --seed uniform --users 20.

Oracle: PARITY OK 80/80 (all 4 engines, new node-report/bundle shapes, is_mine gone).

server p50 (ms), 200 req / 20 warmup:
| engine | feed | profile |
|---|---|---|
| jaseci | 74.1 | 7.9 |
| postgres | 15.0 | 1.8 |
| sqlalchemy | 32.7 | 4.0 |
| neo4j | 77.0 | 4.0 |

vs remembered quiet 07-17 ballpark (pg 10.4 / sqla 26.2 / jac 45.6-warmed / neo4j 52.6-fair):
ordering preserved (pg < sqla < jac ~ neo4j), absolutes inflated (busy box).
jac/sqla ratio 2.27 vs old 1.74 — at the edge of the ±30% flag; plausibly cold-ish
GTI cache + busy machine, NOT attributed. Re-measure in a quiet all-engines window
before quoting anything.
