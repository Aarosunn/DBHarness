"""
Merge per-condition ablation CSVs + baseline results into one ladder CSV,
then plot the full jac optimization ladder next to the baselines.

Reads the latest row of each per-condition file in results/csv/, writes
results/csv/ladder_merged.csv, renders results/plots/feed_ladder.png.

Usage:
    python plot_ladder.py
"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCRIPT_DIR = Path(__file__).resolve().parent
CSV_DIR = SCRIPT_DIR.parent / "results" / "csv"
MARK = "#1d1d20"

# jac ladder: sequential orange ramp, light -> dark = more optimization
LADDER = [
    ("no-GTI", "NOGTI_load_feed.csv", "#fcd9b0"),
    ("+GTI", "GTI_load_feed.csv", "#f9be7c"),
    ("+cross-root", "CROSSROOT_load_feed.csv", "#f5a54f"),
    ("+decode-cache", "DECODECACHE_load_feed.csv", "#f28e2b"),
    ("+PG-L3", "PG_load_feed.csv", "#d97612"),
    ("+N+1 fix", "N+1FIX_load_feed.csv", "#b45f0e"),
]
BASELINE_COLORS = {
    "postgres": "#4269d0",
    "sqlalchemy": "#0891b2",
    "neo4j": "#3ca951",
}


def last_row(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    return rows[-1]


def main():
    merged = []  # (label, color, row)
    for label, fname, color in LADDER:
        row = last_row(CSV_DIR / fname)
        merged.append((f"jac {label}", color, row))
    for row in csv.DictReader(open(CSV_DIR / "mvp_results.csv", newline="")):
        color = BASELINE_COLORS.get(row["engine"])
        if color:
            merged.append((row["engine"], color, row))

    out_csv = CSV_DIR / "ladder_merged.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["label"] + list(merged[0][2].keys()))
        for label, _, row in merged:
            w.writerow([label] + list(row.values()))
    print(f"wrote {out_csv}")

    labels = [m[0] for m in merged]
    colors = [m[1] for m in merged]
    p50 = [float(m[2]["p50_ms"]) for m in merged]
    p95 = [float(m[2]["p95_ms"]) for m in merged]
    p99 = [float(m[2]["p99_ms"]) for m in merged]

    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=150)
    x = range(len(labels))
    ax.bar(x, p50, width=0.6, color=colors, zorder=3, label="p50")
    ax.scatter(x, p95, marker="D", s=42, color=MARK, zorder=4, label="p95")
    ax.scatter(x, p99, marker="^", s=52, color=MARK, zorder=4, label="p99")
    for xi, v, hi in zip(x, p50, p99):  # label above the p99 marker, no collisions
        ax.annotate(
            f"{v:.1f}",
            (xi, max(v, hi)),
            textcoords="offset points",
            xytext=(0, 4),
            ha="center",
            fontsize=9,
            color="#3f3f46",
        )
    ax.set_xticks(list(x), labels, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("latency (ms)")
    ax.set_title(
        "feed — jac optimization ladder vs baselines (p50 bars; p95 ◆ / p99 ▲)",
        fontsize=11,
    )
    ax.grid(axis="y", color="#e4e4e7", linewidth=0.8, zorder=0)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    ax.set_ylim(0, max(p99) * 1.15)

    out_png = SCRIPT_DIR.parent / "results" / "plots" / "feed_ladder.png"
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_png)
    print(f"wrote {out_png}")


if __name__ == "__main__":
    main()
