import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

INK="#1a1a1a"; MUT="#666"; GRID="#ddd"
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":11,"axes.edgecolor":"#999"})

# pool -> (label, color) fixed order; shares in % of each arm's active samples
POOLS = [
    ("serialize",    "Serialize (objects→JSON)", "#4e79a7"),
    ("build_object", "Object build (anchor+Permission+archetype)", "#e15759"),
    ("visit_dispatch","Visit dispatch (kernel)",  "#b07aa1"),
    ("bson_decode",  "BSON decode (fetch)",       "#f28e2b"),
    ("uuid",         "UUID intern",               "#edc948"),
    ("mongo_plan",   "Mongo cursor/plan",         "#76b7b2"),
    ("db_wait",      "DB wait (socket)",          "#59a14f"),
    ("other",        "Other runtime + framework", "#9c9c9c"),
]
anchor = {"serialize":40.1,"build_object":24.3,"visit_dispatch":9.3,"bson_decode":4.5,
          "uuid":5.3,"mongo_plan":4.9,"db_wait":2.0,"other":9.6}
leaf   = {"serialize":38.7,"build_object":0.0,"visit_dispatch":0.5,"bson_decode":18.3,
          "uuid":9.9,"mongo_plan":9.9,"db_wait":7.9,"other":14.8}
counts = {  # raw sample counts for the eliminated-pools panel
    "Object build\n(__init__/<string>, Permission,\ndeserialize_projected)": (60, 0),
    "Reflective serialize\n(_serialize_attrs dir() scan)":                  (65, 0),
    "Visit dispatch\n(osp kernel, node descs)":                             (23, 1),
}

fig = plt.figure(figsize=(13.2, 7.0))
gs = fig.add_gridspec(1, 2, width_ratios=[1.25, 1], wspace=0.30,
                      left=0.135, right=0.975, top=0.80, bottom=0.30)

# ---- panel A: composition shares ----
ax = fig.add_subplot(gs[0])
arms = [("anchor path\nload_feed (objects)", anchor), ("leaf path\nload_feed_leaf (dicts)", leaf)]
for yi, (lbl, sh) in enumerate(arms):
    left = 0
    for k, plab, col in POOLS:
        w = sh[k]
        if w <= 0: continue
        ax.barh(yi, w, left=left, color=col, height=0.52, zorder=3,
                edgecolor="white", linewidth=1.0)
        if w >= 4:
            ax.text(left+w/2, yi, f"{w:.0f}%", ha="center", va="center",
                    color="white", fontsize=9.5, fontweight="bold", zorder=4)
        left += w
ax.set_yticks([0,1]); ax.set_yticklabels([a[0] for a in arms], fontsize=10.5, color=INK)
ax.invert_yaxis(); ax.set_xlim(0, 100)
ax.set_xlabel("share of active profiler samples (%)", color=MUT, fontsize=10)
ax.set_title("Where each arm spends its CPU", fontsize=12, color=INK, pad=8)
ax.xaxis.grid(True, color=GRID, zorder=0); ax.set_axisbelow(True)
for s in ("top","right","left"): ax.spines[s].set_visible(False)
ax.tick_params(colors=MUT)
ax.legend(handles=[Patch(facecolor=c, label=l) for _,l,c in POOLS],
          loc="upper center", bbox_to_anchor=(0.5,-0.26), frameon=False,
          fontsize=8.4, ncol=2, columnspacing=1.2, handlelength=1.2)

# ---- panel B: eliminated pools, raw samples ----
ax2 = fig.add_subplot(gs[1])
labels = list(counts); a_vals = [counts[k][0] for k in labels]; b_vals = [counts[k][1] for k in labels]
y = range(len(labels)); h = 0.34
ax2.barh([i-h/2 for i in y], a_vals, height=h, color="#e15759", zorder=3, label="anchor path")
ax2.barh([i+h/2 for i in y], b_vals, height=h, color="#59a14f", zorder=3, label="leaf path")
for i,(av,bv) in enumerate(zip(a_vals,b_vals)):
    ax2.text(av+1, i-h/2, str(av), va="center", fontsize=10, fontweight="bold", color=INK)
    ax2.text(bv+1, i+h/2, str(bv), va="center", fontsize=10, fontweight="bold", color="#2a7a2a")
ax2.set_yticks(list(y)); ax2.set_yticklabels(labels, fontsize=8.8, color=INK)
ax2.invert_yaxis()
ax2.set_xlabel("profiler samples (300 dumps/arm, same window)", color=MUT, fontsize=9.5)
ax2.set_title("The object tax the leaf path eliminates", fontsize=12, color=INK, pad=8)
ax2.xaxis.grid(True, color=GRID, zorder=0); ax2.set_axisbelow(True)
for s in ("top","right","left"): ax2.spines[s].set_visible(False)
ax2.tick_params(colors=MUT)
ax2.legend(loc="lower right", frameon=False, fontsize=9)

fig.suptitle("Leaf materialization (JAC_LEAF_MATERIALIZE) — feed served as projected dicts, no Tweet objects",
             fontsize=14, fontweight="bold", color=INK, y=0.97)
fig.text(0.5, 0.965, "", ha="center")
fig.text(0.135, 0.855, "Same boot, interleaved A/B, output byte-identical (5 users × 2550 tweets) · client p50 ratio 0.59× (159.5→93.8 ms, busy box — ratio valid, absolutes not)",
         ha="left", fontsize=9.5, color=MUT)
fig.text(0.5, 0.012, "jittered py-spy dump-loop · 300 dumps/arm · 247 vs 191 active stacks · busy machine: shares within-arm valid; fixed-cost pools (BSON/DB wait) inflate in the faster arm by construction · 2026-07-29",
         ha="center", fontsize=7.8, color=MUT)
fig.savefig("/home/aaron/Dev/Research/DatabaseResearch/DBHarness/results/leaf_pools_2026-07-29.png", dpi=150, facecolor="white")
print("wrote leaf_pools_2026-07-29.png")
