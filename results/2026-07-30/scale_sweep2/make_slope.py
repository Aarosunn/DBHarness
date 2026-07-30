"""Post-fastbuild scale sweep slopegraph, two panels: server p50 (left) + p99 (right).
Same arm colors as feed_latency_2026-07-30.png. Stress-axis framing."""
import csv, json, os
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
CSVDIR = HERE.parent.parent / "csv"
PFX = os.environ.get("SWEEP_PREFIX", "sweep2")
LEVELS = [("t20", 20), ("t50", 50), ("t100", 100), ("t200", 200), ("t500", 500)]
ARMS = [  # fixed order/colors, matches bar chart
    ("postgres", "feed", "postgres (raw)", "#4e79a7"),
    ("sqlalchemy", "feed", "sqlalchemy (ORM)", "#17a2b8"),
    ("jaseci", "feed_leaf", "jac leaf", "#9467bd"),
    ("jaseci", "feed", "jac anchor", "#f28e2b"),
    ("neo4j", "feed", "neo4j", "#2ca02c"),
]

data = {}
for lvl, _ in LEVELS:
    for suffix in ("baselines", "jacanchor", "jacleaf"):
        p = CSVDIR / f"{PFX}_{lvl}_{suffix}.csv"
        if not p.exists():
            continue
        for row in csv.DictReader(open(p)):
            data[(lvl, row["engine"], row["workload"])] = row

med = {}
for lvl, tpu in LEVELS:
    for eng, wl, label, _ in ARMS:
        r = data.get((lvl, eng, wl))
        if r:
            med[f"{lvl}:{eng}:{wl}"] = {
                "tweets_per_user": tpu, "feed_rows": 51 * tpu,
                "requests": int(r["requests"]), "errors": int(r["errors"]),
                "server": [float(r["server_p50_ms"]), float(r["server_p95_ms"]), float(r["server_p99_ms"])],
                "client": [float(r["p50_ms"]), float(r["p95_ms"]), float(r["p99_ms"])],
            }
json.dump(med, open(HERE / f"medians_scale_sweep_{PFX}.json", "w"), indent=1)
print(f"wrote medians_scale_sweep_{PFX}.json ({len(med)} cells)")

INK = "#1a1a1a"; MUT = "#666"; GRID = "#ddd"
present = [(lvl, tpu) for lvl, tpu in LEVELS
           if any((lvl, e, w) in data for e, w, _, _ in ARMS)]
xs = [tpu for _, tpu in present]

fig, (axl, axr) = plt.subplots(1, 2, figsize=(15.5, 6.4))
NUDGE = {("p50", "jac leaf"): 7, ("p50", "sqlalchemy (ORM)"): -7,
         ("p99", "jac anchor"): 9, ("p99", "jac leaf"): -7}
for ax, stat_idx, stat_name in ((axl, 0, "p50"), (axr, 2, "p99")):
    for eng, wl, label, col in ARMS:
        ys = [med.get(f"{lvl}:{eng}:{wl}", {}).get("server", [None, None, None])[stat_idx]
              for lvl, _ in present]
        pts = [(x, y) for x, y in zip(xs, ys) if y is not None]
        if not pts:
            continue
        px, py = zip(*pts)
        ax.plot(px, py, "-o", color=col, linewidth=2, markersize=7, zorder=3,
                markeredgecolor="white", markeredgewidth=1.2)
        slope = (py[-1] - py[0]) / (px[-1] - px[0]) if len(pts) > 1 else 0
        ax.annotate(f"{label}  {py[-1]:.0f}ms  ({slope*1000:.0f} µs/tw)",
                    xy=(px[-1], py[-1]), xytext=(9, NUDGE.get((stat_name, label), 0)),
                    textcoords="offset points", va="center",
                    fontsize=8.8, color=INK, fontweight="bold")
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{t}\n{51*t} rows" if t >= 100 else str(t) for t in xs], fontsize=8.4, color=INK)
    ax.set_xlim(0, max(xs) * 1.60)
    ax.set_ylabel(f"server-side {stat_name} (ms)", color=MUT)
    ax.yaxis.grid(True, color=GRID, zorder=0); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUT)
    ax.set_title(f"server {stat_name}", fontsize=11.5, color=INK)
axl.set_xlabel("tweets per user (users=100, follows=50 frozen)", color=MUT)
axr.set_xlabel("tweets per user (p99 = single run, interpret cell-level noise cautiously)", color=MUT, fontsize=9)
fig.suptitle("load_feed scaling — post-fastbuild (sweep2): server p50 + p99 vs tweets/user (stress axis, unpaginated feed)",
             fontsize=12.5, color=INK)
fig.text(0.5, 0.012,
         "500 req/cell, x1, quiet, perf governor - warmup=100 (full cohort) - per-cohort PG DBs - "
         "jac arms same :8005 boot: all flags + JAC_FAST_BUILD=1, leaf=JAC_LEAF_MATERIALIZE=Tweet - "
         "label = t500 value + marginal cost t20→t500 - 2026-07-30",
         ha="center", fontsize=7.4, color=MUT)
fig.tight_layout(rect=[0, 0.045, 1, 0.94])
fig.savefig(HERE / f"scale_sweep_slope_{PFX}.png", dpi=150, facecolor="white")
print(f"wrote scale_sweep_slope_{PFX}.png")
