"""
Plot the latest benchmark results as a latency bar chart.

Reads results/csv/results.csv (append-only, written by run.py), keeps the
LATEST row per (engine, workload), and renders one PNG per workload:
p50 bars + p95/p99 tick markers, saved to results/plots/<workload>_latency.png.

Usage:
    python plot.py [--input ../results/csv/results.csv] [--workload feed]
"""

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: render straight to file
import matplotlib.pyplot as plt

SCRIPT_DIR = Path(__file__).resolve().parent
MARK = "#1d1d20"  # p95/p99 markers: neutral ink, shape carries identity
ENGINE_ORDER = ["jaseci", "postgres", "sqlalchemy", "neo4j"]
# Fixed color per engine (validated: lightness/chroma/CVD pass; the sub-3:1
# contrast on orange/green is relieved by direct labels + x-axis names).
ENGINE_COLORS = {
    "jaseci": "#f28e2b",  # orange
    "postgres": "#4269d0",  # blue
    "sqlalchemy": "#0891b2",  # cyan
    "neo4j": "#3ca951",  # green
}
FALLBACK = "#9498a0"


def latest_rows(path, workload):
    """Latest row per engine for one workload (file is append-only)."""
    rows = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row["workload"] == workload:
                rows[row["engine"]] = row  # later rows overwrite earlier
    order = {e: i for i, e in enumerate(ENGINE_ORDER)}
    return sorted(rows.values(), key=lambda r: order.get(r["engine"], 99))


def main():
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[1])
    parser.add_argument(
        "--input", default=str(SCRIPT_DIR.parent / "results" / "csv" / "results.csv")
    )
    parser.add_argument("--workload", default="feed")
    parser.add_argument(
        "--output",
        default=None,
        help="output PNG (default results/plots/<workload>_latency.png)",
    )
    args = parser.parse_args()

    rows = latest_rows(args.input, args.workload)
    if not rows:
        raise SystemExit(f"no '{args.workload}' rows in {args.input}")

    engines = [r["engine"] for r in rows]
    p50 = [float(r["p50_ms"]) for r in rows]
    p95 = [float(r["p95_ms"]) for r in rows]
    p99 = [float(r["p99_ms"]) for r in rows]

    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=150)
    x = range(len(engines))

    colors = [ENGINE_COLORS.get(e, FALLBACK) for e in engines]
    ax.bar(x, p50, width=0.55, color=colors, zorder=3, label="p50")
    ax.scatter(x, p95, marker="D", s=42, color=MARK, zorder=4, label="p95")
    ax.scatter(x, p99, marker="^", s=52, color=MARK, zorder=4, label="p99")

    for xi, v in zip(x, p50):  # direct label the headline number only
        ax.annotate(
            f"{v:.1f}",
            (xi, v),
            textcoords="offset points",
            xytext=(0, 4),
            ha="center",
            fontsize=9,
            color="#3f3f46",
        )

    ax.set_xticks(list(x), engines)
    ax.set_ylabel("latency (ms)")
    ax.set_title(
        f"{args.workload} — single-user client latency (p50 bars; p95 ◆ / p99 ▲)",
        fontsize=11,
    )
    ax.grid(axis="y", color="#e4e4e7", linewidth=0.8, zorder=0)  # recessive grid
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    ax.set_ylim(0, max(p99) * 1.15)

    default_out = (
        SCRIPT_DIR.parent / "results" / "plots" / f"{args.workload}_latency.png"
    )
    out = Path(args.output) if args.output else default_out
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
