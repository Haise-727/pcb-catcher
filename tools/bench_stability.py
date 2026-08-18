"""Frame-stability bench check — the gate for issue #3.

    python tools/bench_stability.py [--samples 100]

Run this after the jig is fixed and the ring light is on, BEFORE anyone tunes a
threshold. Mean per-pixel deviation across static frames must sit below 2 grey
levels (AC-006.2). Above that, the camera is still auto-adjusting or the
lighting is drifting, and any threshold tuned against it stops being true the
moment conditions shift.

Illumination stability dominates the false-call rate more than any algorithm
choice downstream (RSK-02), which is why this is a gate and not a nice-to-have.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run directly from a clone with no install step: put the repo root on the
# path so `import gerbereye` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse

from gerbereye.capture import Camera, measure_frame_stability

# From AC-006.2: mean deviation on an 8-bit scale.
STABILITY_THRESHOLD = 2.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=100, help="frames to capture")
    args = parser.parse_args()

    camera = Camera()
    state = camera.open()
    if not state.connected:
        print(f"FAIL  no camera: {state.degraded_reason}")
        return 2

    if not state.settings_locked:
        # Not fatal, but the operator must know: with auto exposure still on,
        # a good result here says nothing about a real inspection.
        print(f"WARN  capture settings not locked -- {state.degraded_reason}")

    print(f"Capturing {args.samples} static frames. Do not touch the board or the light.")
    stats = measure_frame_stability(camera, samples=args.samples)
    camera.release()

    if stats["samples"] < 2:
        print("FAIL  captured too few frames to measure")
        return 2

    mean = stats["mean_deviation"]
    print(f"\n  frames captured   {int(stats['samples'])}")
    print(f"  mean deviation    {mean:.3f} grey levels")
    print(f"  max deviation     {stats['max_deviation']:.3f} grey levels")

    if mean < STABILITY_THRESHOLD:
        print(f"\nPASS  below {STABILITY_THRESHOLD} -- safe to tune thresholds.")
        return 0

    print(f"\nFAIL  at or above {STABILITY_THRESHOLD}. Fix this before tuning anything:")
    print("      - confirm exposure/focus/white-balance are locked to manual")
    print("      - block ambient light (window, overhead fluorescents)")
    print("      - check the ring light is not flickering on a dimmer circuit")
    print("      - confirm nothing is vibrating the jig")
    return 1


if __name__ == "__main__":
    sys.exit(main())
