"""Live ArUco detection check — the acceptance test for issue #5.

    python tools/detect_markers.py

Opens the camera and prints, once per second, which markers are visible and how
much their detected centres jitter between frames. Press Ctrl-C to stop.

Acceptance criteria for #5 are met when all four markers report found across
consecutive samples and jitter stays around a pixel or less. Jitter above a few
pixels means the homography will wander, which moves every projected component
box and lands defect names on the wrong parts.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run directly from a clone with no install step: put the repo root on the
# path so `import gerbereye` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import time

import numpy as np

from gerbereye.capture import Camera
from gerbereye.inspector import DEFAULT_MARKER_POSITIONS_MM
from gerbereye.pipeline import registration

EXPECTED_IDS = sorted(DEFAULT_MARKER_POSITIONS_MM)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=20, help="samples before exiting")
    args = parser.parse_args()

    camera = Camera()
    state = camera.open()
    if not state.connected:
        print(f"FAIL  no camera: {state.degraded_reason}")
        return 2

    print(f"Expecting markers {EXPECTED_IDS}. Ctrl-C to stop.\n")
    history: dict[int, list[np.ndarray]] = {}

    try:
        for sample in range(args.samples):
            frame = camera.read()
            if frame is None:
                print("  no frame")
                time.sleep(1)
                continue

            detected = registration.detect_markers(frame)
            for marker_id, centre in detected.items():
                history.setdefault(marker_id, []).append(centre)

            found = sorted(detected)
            missing = [i for i in EXPECTED_IDS if i not in detected]

            result = registration.compute_homography(DEFAULT_MARKER_POSITIONS_MM, detected)
            residual = f"{result.residual_px:.2f}px" if result.residual_px is not None else "n/a"

            status = "OK  " if not missing else "MISS"
            print(
                f"[{sample + 1:3}/{args.samples}] {status} found={found} "
                f"missing={missing} state={result.state.value} residual={residual}"
            )
            time.sleep(1)
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        camera.release()

    print("\nJitter (std dev of detected centre, pixels):")
    unstable = []
    for marker_id in sorted(history):
        points = np.array(history[marker_id])
        if len(points) < 2:
            continue
        jitter = float(points.std(axis=0).max())
        flag = "" if jitter <= 1.5 else "   <-- too noisy"
        if jitter > 1.5:
            unstable.append(marker_id)
        print(f"  ID {marker_id}: {jitter:.2f}px{flag}")

    missing_overall = [i for i in EXPECTED_IDS if i not in history]
    if missing_overall:
        print(f"\nFAIL  never detected: {missing_overall}")
        print("      - check the markers are fully inside the frame and in focus")
        print("      - reprint larger if the camera sits far from the jig")
        print("      - avoid glare from the ring light directly on the paper")
        return 1
    if unstable:
        print(f"\nWARN  jitter above 1.5px on {unstable} — homography will wander.")
        return 1

    print("\nPASS  all markers detected and stable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
