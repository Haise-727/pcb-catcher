"""Inspection latency benchmark — the measurement harness for #38.

    python tools/bench_latency.py --runs 200
    GERBEREYE_DEMO=1 python tools/bench_latency.py --runs 200

NFR-001 requires p95 trigger-to-result at or below 5.0s and p99 at or below
10.0s, measured over 200 consecutive inspections and reported as a histogram
rather than a mean. A mean hides exactly the tail the requirement is about.

Two important caveats on what this measures:

  - It times the server-side inspection path only. Browser render and network
    are excluded, so the real operator-perceived latency is slightly higher.
  - Run under GERBEREYE_DEMO it reads bundled images rather than a camera, so
    capture time is not representative. **A demo-mode run is not an NFR-001
    result** — it verifies the harness and catches pipeline regressions. The
    real figure needs the reference bench (#2, #3) and a real camera.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run directly from a clone with no install step.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import statistics
import time

from gerbereye import config, db, demo, inspector
from gerbereye.capture import Camera

# From NFR-001.
TARGET_P95_MS = 5000.0
TARGET_P99_MS = 10000.0


def percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile.

    Deliberately not interpolated: with 200 samples an interpolated p99 invents
    a number between two real observations, and the requirement is about
    observed behaviour.
    """
    if not values:
        return float("nan")
    ordered = sorted(values)
    index = min(int(round(fraction * len(ordered) + 0.5)) - 1, len(ordered) - 1)
    return ordered[max(index, 0)]


def histogram(values: list[float], buckets: int = 12, width: int = 44) -> str:
    """Text histogram. The requirement asks for the distribution, not a mean."""
    if not values:
        return "  (no samples)"
    low, high = min(values), max(values)
    if high - low < 1e-9:
        return f"  all {len(values)} samples at {low:.1f} ms"

    size = (high - low) / buckets
    counts = [0] * buckets
    for value in values:
        index = min(int((value - low) / size), buckets - 1)
        counts[index] += 1

    peak = max(counts)
    lines = []
    for i, count in enumerate(counts):
        start = low + i * size
        bar = "#" * int(round(count / peak * width)) if peak else ""
        lines.append(f"  {start:7.1f} ms | {bar:<{width}} {count}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=200, help="inspections to time")
    parser.add_argument("--board-type-id", type=int, default=None)
    parser.add_argument("--warmup", type=int, default=5, help="untimed runs first")
    args = parser.parse_args()

    demo_mode = demo.demo_enabled()
    config.ensure_dirs()
    conn = db.connect()
    try:
        board_types = db.list_board_types(conn)
        if not board_types:
            print("FAIL  no board types. Run: python tools/seed_demo.py")
            return 2
        board_type_id = args.board_type_id or board_types[0]["id"]
        board = next((b for b in board_types if b["id"] == board_type_id), None)
        if board is None:
            print(f"FAIL  no board type {board_type_id}")
            return 2

        camera = demo.DemoCamera() if demo_mode else Camera()
        state = camera.open()
        if not state.connected:
            print(f"FAIL  capture unavailable: {state.degraded_reason}")
            return 2

        print(f"Board type   #{board_type_id} — {board['name']}")
        print(f"Components   {board['component_count']} inspected, {board['dnp_count']} DNP excluded")
        print(f"Source       {'demo images' if demo_mode else 'live camera'}")
        print(f"Runs         {args.runs} (after {args.warmup} warmup)\n")

        # Warmup: the first inspection pays for lazy imports and OS file cache,
        # and including it would skew the tail it is meant to measure.
        for _ in range(args.warmup):
            inspector.run_inspection(conn, camera, board_type_id, persist=False)

        timings: list[float] = []
        for run in range(args.runs):
            if demo_mode:
                camera.next_board()
            started = time.perf_counter()
            inspector.run_inspection(conn, camera, board_type_id, persist=False)
            timings.append((time.perf_counter() - started) * 1000.0)

            if (run + 1) % 50 == 0:
                print(f"  {run + 1}/{args.runs} …")

        p95 = percentile(timings, 0.95)
        p99 = percentile(timings, 0.99)

        print("\nDistribution")
        print(histogram(timings))

        print("\nSummary")
        print(f"  min     {min(timings):8.1f} ms")
        print(f"  median  {statistics.median(timings):8.1f} ms")
        print(f"  mean    {statistics.fmean(timings):8.1f} ms")
        print(f"  p95     {p95:8.1f} ms   target <= {TARGET_P95_MS:.0f}")
        print(f"  p99     {p99:8.1f} ms   target <= {TARGET_P99_MS:.0f}")
        print(f"  max     {max(timings):8.1f} ms")

        within = p95 <= TARGET_P95_MS and p99 <= TARGET_P99_MS
        print(f"\n{'PASS' if within else 'FAIL'}  NFR-001 targets "
              f"{'met' if within else 'NOT met'}")

        if demo_mode:
            print("\nNOTE  Demo mode reads bundled images, so capture time is not")
            print("      representative. This is not an NFR-001 result -- it verifies")
            print("      the harness and catches pipeline regressions. The real figure")
            print("      needs the reference bench and a real camera (#2, #3).")
        return 0 if within else 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
