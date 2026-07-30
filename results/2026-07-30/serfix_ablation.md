# Serializer-fix ablation — 2026-07-30 quiet window

Same boot family (:8005, all-opts, node-report app), performance governor,
500 req × 3 repeats, server-side span, median-of-3.

**The issue:** `_serialize_attrs` compiled fast path is guarded `projected is None`
(correct — the compiled plan iterates ALL class fields; projected anchors are
partial and would break). But the fallback is a per-object `dir()` + `callable()`
reflection scan, and the headline config (projection ON) sends every feed tweet
down it. **Fix:** third branch — projected anchors iterate their own
`_projected_fields` (sorted). Output verified byte-identical.

| jac anchor (load_feed) | p50 | p95 | p99 |
|---|---|---|---|
| without fix | 57.3 | 199.7 | 220.1 |
| with fix    | 52.9 | 64.6  | 74.5 |
| delta       | **−4.4 (−8%)** | **−135 (−68%)** | **−146 (−66%)** |

The reflective scan was a modest p50 cost but the dominant tail driver.

## Full attribution chain (server p50, this window)
57.3 (anchor, no fix) → 52.9 (serializer fix, −8%) → 38.4 (leaf materialize, −27%)
Total −33%. Leaf p99 51.6 vs no-fix anchor p99 220.1 (−77%).

Repeats (no-fix): 57.3 / 57.5 / 57.3 — spread < 0.4%.
