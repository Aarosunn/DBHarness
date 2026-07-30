# Tweets-per-user scale sweep — 2026-07-30

Server-side `load_feed` p50 vs tweets/user. users=100, follows=50 frozen → feed = 51×tpu rows.
500 req/cell (300 @t200), ×1, quiet window, performance governor, warmup=100 (one full cohort
rotation). Per-cohort PG databases (ANALYZE'd); neo4j/jac shared stores with prefix cohorts.
jac arms same :8005 boot, serializer fix in, leaf = `JAC_LEAF_MATERIALIZE=Tweet`.
Framing: **stress axis** — unpaginated feed is a scaling probe, not a product scenario.

## Server p50 (ms)

| arm | t20 | t50 | t100 | t200 | µs/tweet (t20→t200) |
|---|---|---|---|---|---|
| postgres (raw)   | 3.5  | 9.1  | 21.4  | 48.2  | 248 |
| sqlalchemy (ORM) | 8.7  | 24.7 | 49.0  | 123.4 | 637 |
| jac leaf         | 19.7 | 40.9 | 72.4  | 135.5 | **644** |
| jac anchor       | 25.9 | 53.3 | 104.6 | 218.7 | 1071 |
| neo4j            | 23.2 | 63.7 | 130.0 | 275.1 | 1399 |

## Findings

- **Leaf's marginal cost = sqlalchemy's (644 vs 637 µs/tweet).** The dict path scales like an
  ORM row, not like an object graph; the residual gap vs sqla is a near-constant ~11-12ms
  intercept (session/boot overhead), not per-row cost.
- **Anchor pays 1071 µs/tweet — 1.7× leaf.** Divergence between the two jac lines is the
  object tax scaling: per-row archetype+anchor+Permission build.
- **neo4j worst slope (1399)** — per-row packstream decode; falls behind anchor at every level.
- **Tails**: anchor p95 blows up with scale (t100: p95 345 vs p50 105; t200: p95 511 vs 219) —
  alloc churn/GC at 5-10k objects/req. Leaf p95 stays tight (t100: 86; t200: 154; one p99 391
  spike at t200).
- **GTI blob growth** (root anchor `topology_index_data`, uniform across users per cohort):
  t20 3.8 KB → t50 5.4 → t100 8.0 → t200 13.2 KB/root. Cohort-wide cached working set
  (100 roots): ~0.4 → 0.5 → 0.8 → 1.3 MB — trivially cacheable at this scale; blob decode
  cost, not size, remains the lever.

## Files

- `scale_sweep_slope.png` — the slopegraph (make_slope.py)
- `medians_scale_sweep.json` — all 20 cells, server+client p50/p95/p99
- `sweep_tXX_{baselines,jacanchor,jacleaf}.csv` — raw run.py rows (copies; originals in results/csv/)
- `sweep.sh`, `sweep.log` — runner + full log (note: first invocation died at t50 on missing
  `tokens-t50/tokens.postgres.json`, fixed by copying from default `tokens/`; t20 from run 1,
  rest from run 2, same boot for all servers throughout)
