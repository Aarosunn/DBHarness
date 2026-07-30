# Scale sweep 2 (post-fastbuild) — 2026-07-30 afternoon

5 tiers × 5 arms, uniform 500 req/cell, ×1, quiet window, perf governor, warmup=100
(full cohort). jac arms one :8005 boot: all flags + **JAC_FAST_BUILD=1** (new),
leaf = `JAC_LEAF_MATERIALIZE=Tweet`. Per-cohort PG DBs. t500 = new cohort
(seeded this session; oracle parity 40/40). Stress-axis framing (unpaginated feed).

## Server p50 (ms)

| arm | t20 | t50 | t100 | t200 | t500 | µs/tweet (t20→t500) |
|---|---|---|---|---|---|---|
| postgres (raw)   | 3.7  | 11.8 | 23.2  | 43.9  | 129.3 | 262 |
| sqlalchemy (ORM) | 8.4  | 25.3 | 53.3  | 121.5 | 331.0 | 672 |
| jac leaf         | 18.3 | 39.4 | 69.7  | 133.6 | **333.4** | **657** |
| jac anchor       | 25.6 | 53.4 | 100.2 | 206.1 | **845.7** | 1709 |
| neo4j            | 22.5 | 64.1 | 129.9 | 274.6 | 691.4 | 1394 |

## Findings

1. **Leaf ≡ sqlalchemy at t500** (333.4 vs 331.0, 0.7%). Not a crossover — an asymptotic
   merge: identical marginal cost (657 vs 672 µs/tweet), leaf's ~11-18ms fixed intercept
   amortizes away. The sqla "closing in" observed pre-fix was this convergence.
2. **sqla slope bend is real**: ~500 µs/tweet early segments → ~700 from t200 on
   (reproduced across both sweeps + t500). Leaf holds ~630-660 throughout.
3. **Anchor goes super-linear**: t200→t500 segment = 2132 µs/tweet (2× its earlier slope),
   845.7ms p50 — **crosses above neo4j** (691.4). Object materialization at 25k
   objects/req compounds (alloc/GC), it does not scale linearly. Leaf stays linear =
   the compiler-materialization thesis figure.
4. **Tails (p99, ×1 — read cautiously)**: fastbuild halved leaf/anchor p99 at t20 vs
   pre-fix (35.5 vs 60.1 / 70.1 vs 94.8). At t500 leaf p99 = 1061 ≈ anchor 1110 while
   sqla stays 357 — at extreme row counts the jac runtime still has a tail source leaf
   dicts don't cure (open question: response-encode GC bleed into subsequent spans).
   Anchor t50 p99=206 was a transient window burst (leaf+pg clean minutes later).
5. Window ran a few % warmer than the morning pre-fix sweep (pg 11.8 vs 9.1 at t50);
   cross-sweep p50 deltas ≲5% are window, not effect.

## vs pre-fix sweep (scale_sweep/, 4 tiers)

jac p50s consistently equal-or-better despite warmer window (anchor t200 206 vs 219);
baselines within noise. t200 now 500 req (was 300).

## Files

- `scale_sweep_slope_sweep2.png` — two-panel slopegraph (p50 | p99)
- `medians_scale_sweep_sweep2.json` — 25 cells
- `sweep2_tXX_*.csv` — raw rows (copies; originals results/csv/)
- `sweep.sh`, `sweep.log`, `make_slope.py`, `seed_jac_t500.{sh,log}`, `start_leaf_writemode.sh`
- t500 seeding note: first attempt failed (server was booted `JAC_READ_ONLY=1` → anchor
  writes silently dropped, 100 orphan users deleted); reseeded on write-mode boot, then
  bench boot restored. `JAC_FAST_BUILD=1` now in `start_leaf.sh` (uncommitted).
