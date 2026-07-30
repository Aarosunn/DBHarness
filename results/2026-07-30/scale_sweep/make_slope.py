"""Tweets-per-user scale sweep slopegraph. x = tweets/user, y = server p50.
Same arm colors as feed_latency_2026-07-30.png. Stress-axis framing (unpaginated
feed = scaling probe, not product scenario)."""
import csv, json, os
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
CSVDIR = HERE.parent.parent / "csv"
# SWEEP_PREFIX=sweep -> 2026-07-30 pre-fix run (4 tiers); sweep2 -> post-leaf-fix rerun (adds t500)
PFX = os.environ.get("SWEEP_PREFIX", "sweep")
LEVELS = [("t20", 20), ("t50", 50), ("t100", 100), ("t200", 200), ("t500", 500)]
ARMS = [  # (engine, workload, label, color) — fixed order/colors, matches bar chart
    ("postgres", "feed", "postgres (raw)", "#4e79a7"),
    ("sqlalchemy", "feed", "sqlalchemy (ORM)", "#17a2b8"),
    ("jaseci", "feed_leaf", "jac leaf", "#9467bd"),
    ("jaseci", "feed", "jac anchor", "#f28e2b"),
    ("neo4j", "feed", "neo4j", "#2ca02c"),
]

data = {}  # (lvl, engine, workload) -> row
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
print(f"wrote medians_scale_sweep.json ({len(med)} cells)")

INK = "#1a1a1a"; MUT = "#666"; GRID = "#ddd"
fig, ax = plt.subplots(figsize=(11.2, 6.4))
# only levels that actually have data (pre-fix run has no t500)
present = [(lvl, tpu) for lvl, tpu in LEVELS
           if any((lvl, e, w) in data for e, w, _, _ in ARMS)]
xs = [tpu for _, tpu in present]
# right-edge label nudge (pts) to avoid collisions of close endpoints
NUDGE = {"jac leaf": 7, "sqlalchemy (ORM)": -7}
for eng, wl, label, col in ARMS:
    ys = [med.get(f"{lvl}:{eng}:{wl}", {}).get("server", [None])[0] for lvl, _ in present]
    pts = [(x, y) for x, y in zip(xs, ys) if y is not None]
    if not pts:
        continue
    px, py = zip(*pts)
    ax.plot(px, py, "-o", color=col, linewidth=2, markersize=8, zorder=3,
            markeredgecolor="white", markeredgewidth=1.2)
    # per-tweet marginal cost over the sweep = (y200-y20)/(200-20)
    slope = (py[-1] - py[0]) / (px[-1] - px[0]) if len(pts) > 1 else 0
    ax.annotate(f"{label}  {py[-1]:.0f}ms  ({slope*1000:.0f} µs/tweet)",
                xy=(px[-1], py[-1]), xytext=(10, NUDGE.get(label, 0)),
                textcoords="offset points", va="center",
                fontsize=9.5, color=INK, fontweight="bold")

ax.set_xticks(xs); ax.set_xticklabels([f"{t}\n{51*t} rows" for t in xs], fontsize=9, color=INK)
ax.set_xlabel("tweets per user (users=100, follows=50 frozen)", color=MUT)
ax.set_ylabel("server-side p50 (ms)", color=MUT)
ax.set_xlim(0, max(xs) * 1.52)
ax.yaxis.grid(True, color=GRID, zorder=0); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
ax.tick_params(colors=MUT)
ax.set_title("load_feed scaling — server p50 vs tweets/user (stress axis, unpaginated feed)",
             fontsize=12.5, color=INK, pad=10)
fig.text(0.5, 0.015,
         "500 req/cell (300 @t200 in pre-fix sweep), x1, quiet, perf governor - warmup=100 (full cohort) - per-cohort PG DBs - "
         "leaf=JAC_LEAF_MATERIALIZE=Tweet - label = t200 p50 + marginal cost t20→t200 - 2026-07-30",
         ha="center", fontsize=7.4, color=MUT)
fig.tight_layout(rect=[0, 0.05, 1, 1])
fig.savefig(HERE / f"scale_sweep_slope_{PFX}.png", dpi=150, facecolor="white")
print("wrote scale_sweep_slope.png")
