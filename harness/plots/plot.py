"""
Plot the latest benchmark results as a latency bar chart.

Reads results/csv/results.csv (append-only, written by run.py), keeps the
LATEST row per (engine, workload), and renders one PNG per workload:
p50 bars + p95/p99 tick markers, saved to results/plots/<workload>_latency.png.

Default metric is the server-side in-handler span (server_* columns);
pass --metric client for the round-trip sanity view.

Usage:
    python plot.py [--input ../results/csv/results.csv] [--workload feed]
                   [--metric server|client]
"""

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: render straight to file
import matplotlib.pyplot as plt

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent.parent  # harness/plots/ -> DBHarness/
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
        "--name",
        default="results",
        help="experiment name: reads results/csv/<name>.csv, "
        "writes results/plots/<name>_<workload>...png",
    )
    parser.add_argument("--input", default=None, help="explicit CSV (overrides --name)")
    parser.add_argument("--workload", default="feed")
    parser.add_argument("--metric", choices=["server", "client"], default="server")
    parser.add_argument(
        "--yscale",
        choices=["auto", "linear", "log"],
        default="auto",
        help="auto = linear capped at 1.5x max p50 (off-scale p95/p99 annotated); "
        "linear = full range to max p99; log = log axis",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="output PNG (default results/plots/<name>_<workload>_latency.png)",
    )
    args = parser.parse_args()

    input_csv = args.input or str(REPO_DIR / "results" / "csv" / f"{args.name}.csv")
    rows = latest_rows(input_csv, args.workload)
    if not rows:
        raise SystemExit(f"no '{args.workload}' rows in {input_csv}")

    prefix = "server_" if args.metric == "server" else ""
    missing = [r["engine"] for r in rows if not r.get(f"{prefix}p50_ms")]
    if missing:
        raise SystemExit(
            f"no {args.metric}-side columns for {missing} - "
            f"re-run run.py (old-schema rows?)"
        )

    engines = [r["engine"] for r in rows]
    p50 = [float(r[f"{prefix}p50_ms"]) for r in rows]
    p95 = [float(r[f"{prefix}p95_ms"]) for r in rows]
    p99 = [float(r[f"{prefix}p99_ms"]) for r in rows]

    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=150)
    x = range(len(engines))

    colors = [ENGINE_COLORS.get(e, FALLBACK) for e in engines]
    ax.bar(x, p50, width=0.55, color=colors, zorder=3, label="p50")
    ax.scatter(x, p95, marker="D", s=42, color=MARK, zorder=4, label="p95")
    ax.scatter(x, p99, marker="^", s=52, color=MARK, zorder=4, label="p99")

    for xi, v in zip(x, p50):  # p50 label INSIDE the bar (markers sit above it)
        ax.annotate(
            f"{v:.1f}",
            (xi, v),
            textcoords="offset points",
            xytext=(0, -13),
            ha="center",
            va="bottom",
            fontsize=9,
            color="white",
            fontweight="bold",
        )

    ax.set_xticks(list(x), engines)
    ax.set_ylabel("latency (ms)")
    side = "server-side" if args.metric == "server" else "client round-trip"
    ax.set_title(
        f"{args.workload} — single-user {side} latency (p50 bars; p95 ◆ / p99 ▲)",
        fontsize=11,
    )
    ax.grid(axis="y", color="#e4e4e7", linewidth=0.8, zorder=0)  # recessive grid
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(frameon=False, fontsize=9, loc="upper center")
    if args.yscale == "log":
        ax.set_yscale("log")
        ax.set_ylim(min(p50) * 0.4, max(p99) * 1.6)
        ax.set_ylabel("latency (ms, log scale)")
    else:
        top = max(p99) * 1.15
        if args.yscale == "auto":
            top = min(top, max(p50) * 1.5)
        ax.set_ylim(0, top)
        # p95/p99 beyond the cap are clipped; print their values at the top edge
        for xi, vals in zip(x, zip(p95, p99)):
            clipped = [(m, v) for m, v in zip(("◆", "▲"), vals) if v > top]
            for i, (m, v) in enumerate(reversed(clipped)):
                ax.annotate(
                    f"{m} {v:.0f}",
                    (xi, top * (0.97 - 0.07 * i)),
                    ha="center",
                    va="top",
                    fontsize=7.5,
                    color=MARK,
                )

    prefix_out = "" if args.metric == "server" else "cl_"
    default_out = (
        REPO_DIR / "results" / "plots"
        / f"{prefix_out}{args.name}_{args.workload}_latency.png"
    )
    out = Path(args.output) if args.output else default_out
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
