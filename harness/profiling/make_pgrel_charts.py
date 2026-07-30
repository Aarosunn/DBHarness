"""Generate pg-rel comparison PNGs from the quiet-2026-07-21 data files.
Chart 1: server-side latency (feed + profile), pg-rel vs baselines + mongo.
Chart 2: feed server span by cost pool (span-only), stacked.
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

D = Path("/home/aaron/Dev/Research/DatabaseResearch/DBHarness/results/profiles/quiet-2026-07-21")
OUT = Path("/home/aaron/Dev/Research/DatabaseResearch/DBHarness/results")
lat = json.load(open(D / "latency_medians.json"))
shares = json.load(open(D / "pool_shares.json"))
shares_fix = json.load(open(D / "pool_shares_pgrel_fix.json"))

# engine order + colorblind-safe (Tableau10) colors
ENGINES = [
    ("postgres",   "postgres\n(raw psycopg)",   "#4e79a7"),
    ("sqlalchemy", "sqlalchemy\n(ORM)",          "#76b7b2"),
    ("neo4j",      "neo4j\n(cypher)",            "#59a14f"),
    ("jacmongo",   "jac / mongo\n(all-opts)",    "#f28e2b"),
    ("pgrel",      "jac / pg-rel\n(all-opts)",   "#b07aa1"),
]
INK = "#1a1a1a"; MUT = "#666666"; GRID = "#dddddd"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.edgecolor": "#999", "axes.linewidth": 1.0})

# ---------- Chart 1: latency ----------
fig, axes = plt.subplots(1, 2, figsize=(12, 5.4))
for ax, wl, title in [(axes[0], "feed", "load_feed"), (axes[1], "profile", "get_profile")]:
    xs = range(len(ENGINES))
    p50 = [lat[f"{k}_{wl}"]["server"][0] for k, _, _ in ENGINES]
    p95 = [lat[f"{k}_{wl}"]["server"][1] for k, _, _ in ENGINES]
    p99 = [lat[f"{k}_{wl}"]["server"][2] for k, _, _ in ENGINES]
    cols = [c for _, _, c in ENGINES]
    ax.bar(xs, p50, color=cols, width=0.62, zorder=3)
    # p95 diamond, p99 triangle (offset right of bar center so labels stay clear)
    mx = [x + 0.0 for x in xs]
    ax.scatter(mx, p95, marker="D", s=34, color=INK, zorder=4)
    ax.scatter(mx, p99, marker="^", s=48, color=INK, zorder=4)
    ymax = max(p99) * 1.16
    for x, v in zip(xs, p50):
        if v > 0.13 * ymax:  # tall enough: label inside bar top (never hits markers)
            ax.text(x, v - 0.035*ymax, f"{v:g}", ha="center", va="top",
                    fontweight="bold", fontsize=10.5, color="white", zorder=5)
        else:  # short bar: label above the p99 marker
            ax.text(x, v + 0.11*ymax, f"{v:g}", ha="center", va="bottom",
                    fontweight="bold", fontsize=10.5, color=INK, zorder=5)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([lbl for _, lbl, _ in ENGINES], fontsize=9.2, color=INK)
    ax.set_ylabel("server-side p50 latency (ms)", color=MUT, fontsize=10)
    ax.set_title(f"{title}  ·  server span", fontsize=12.5, color=INK, pad=8)
    ax.set_ylim(0, max(p99) * 1.16)
    ax.yaxis.grid(True, color=GRID, zorder=0); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUT)

# pg-rel pre-fix annotation on feed panel
pre = 102.9; post = lat["pgrel_feed"]["server"][0]
axes[0].annotate(f"pre-fix {pre:g}", xy=(4, post), xytext=(4, pre),
                 ha="center", va="bottom", fontsize=8.5, color="#b07aa1",
                 arrowprops=dict(arrowstyle="->", color="#b07aa1", lw=1.2))
axes[0].scatter([4], [pre], marker="_", s=260, color="#b07aa1", zorder=4)

leg = [plt.Line2D([0],[0], marker="D", color="w", markerfacecolor=INK, markersize=7, label="p95"),
       plt.Line2D([0],[0], marker="^", color="w", markerfacecolor=INK, markersize=9, label="p99")]
axes[1].legend(handles=leg, loc="upper right", frameon=False, fontsize=9.5)
fig.suptitle("littleX server-side latency — jac pg-rel vs baselines",
             fontsize=15, fontweight="bold", color=INK, y=0.99, x=0.5)
fig.text(0.5, 0.015,
    "quiet single-box, powersave governor (ratios valid, absolutes inflated) · 500 req × 3 repeats (median) · oracle 400/400 · uniform_seed (100 users / 5000 tweets) · 2026-07-21",
    ha="center", fontsize=8, color=MUT)
fig.tight_layout(rect=[0, 0.04, 1, 0.96])
fig.savefig(OUT / "pgrel_latency_2026-07-21.png", dpi=150, facecolor="white")
print("wrote", OUT / "pgrel_latency_2026-07-21.png")

# ---------- Chart 2: feed pools (span-only) ----------
POOLS = [("topo", "Topology / index", "#1f77b4"), ("hyd", "Hydration / decode", "#2ca08c"),
         ("app", "App logic", "#e8a000"), ("sess", "Session / memory", "#1a7a1a"),
         ("db", "DB wait", "#4b3fa8"), ("other", "Other (in-span)", "#e05252")]
rows = []
for k, lbl, _ in ENGINES:
    stem = "jacrel_feed_fix" if k == "pgrel" else f"{'jacmongo' if k=='jacmongo' else k}_feed"
    src = shares_fix if k == "pgrel" else shares
    sh = src[stem]["shares"]
    p50 = lat[f"{k}_feed"]["server"][0]
    rows.append((lbl, {b: sh.get(b, 0) * p50 for b in [p[0] for p in POOLS]}, p50))

fig2, ax2 = plt.subplots(figsize=(11.5, 5.8))
ypos = range(len(rows))
for yi, (lbl, pool_ms, total) in zip(ypos, rows):
    left = 0
    for key, _, col in POOLS:
        w = pool_ms[key]
        if w <= 0: continue
        ax2.barh(yi, w, left=left, color=col, height=0.6, zorder=3,
                 edgecolor="white", linewidth=0.8)
        if w / max(r[2] for r in rows) > 0.045:
            ax2.text(left + w/2, yi, f"{w:.0f}" if w >= 10 else f"{w:.1f}",
                     ha="center", va="center", color="white", fontsize=8.5, fontweight="bold")
        left += w
    ax2.text(left + max(r[2] for r in rows)*0.01, yi, f"{total:g} ms",
             ha="left", va="center", color=INK, fontsize=10, fontweight="bold")
ax2.set_yticks(list(ypos))
ax2.set_yticklabels([r[0].replace("\n", " ") for r in rows], fontsize=10, color=INK)
ax2.invert_yaxis()
ax2.set_xlabel("server-side p50 attributed across cost pools (ms, span-only)", color=MUT, fontsize=10)
ax2.set_xlim(0, max(r[2] for r in rows) * 1.12)
ax2.xaxis.grid(True, color=GRID, zorder=0); ax2.set_axisbelow(True)
for s in ("top", "right", "left"): ax2.spines[s].set_visible(False)
ax2.tick_params(colors=MUT)
ax2.set_title("load_feed — server span by cost pool  (jac pg-rel dominated by DB-wait + SQL topology)",
              fontsize=12.5, color=INK, pad=10)
# legend above the plot (top rows are short bars, but place fully outside to avoid any overlap)
ax2.legend(handles=[Patch(facecolor=c, label=l) for _, l, c in POOLS],
           loc="upper center", bbox_to_anchor=(0.5, -0.13), frameon=False,
           fontsize=9.5, ncol=6, columnspacing=1.1, handlelength=1.3)
fig2.text(0.5, 0.015,
    "span-only denominator (gap/framework samples excluded) · pg-rel shown post-fix (-> → ->> for str-typed projected fields) · powersave · 2026-07-21",
    ha="center", fontsize=8, color=MUT)
fig2.tight_layout(rect=[0, 0.12, 1, 1])
fig2.savefig(OUT / "pgrel_pools_2026-07-21.png", dpi=150, facecolor="white")
print("wrote", OUT / "pgrel_pools_2026-07-21.png")
