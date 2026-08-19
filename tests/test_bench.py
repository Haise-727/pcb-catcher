"""Virtual bench tests.

The bench exists to make hardware-dependent behaviour demonstrable without
hardware. That is only worth anything if the simulation actually moves the
things it claims to move, so these tests assert the *direction* of each effect
rather than exact values -- the model is stochastic, and pinning a mean to two
decimal places would make the suite flaky without making it stronger.

They also pin the guard that matters most: `locked` must leave demo behaviour
unchanged, so nobody discovers on demo day that adding realism broke the demo.
"""

from __future__ import annotations

import numpy as np
import pytest

from gerbereye import bench, capture, demo


@pytest.fixture()
def clean_frame() -> np.ndarray:
    """A board-like frame: mid-grey with high-contrast features to move."""
    frame = np.full((240, 320, 3), 90, dtype=np.uint8)
    frame[60:110, 80:150] = 230
    frame[150:190, 200:280] = 20
    return frame


def stability_of(profile_name: str, samples: int = 40) -> float:
    camera = demo.DemoCamera()
    camera.select_bench_profile(profile_name)
    camera.open()
    stats = capture.measure_frame_stability(camera, samples=samples)
    return stats["mean_deviation"]


# -- profile catalogue -----------------------------------------------------


def test_default_profile_is_the_working_bench():
    camera = demo.DemoCamera()
    assert camera.bench_profile == bench.DEFAULT_PROFILE
    assert camera.bench.profile.settings_locked is True


def test_unknown_profile_is_rejected():
    with pytest.raises(KeyError):
        bench.get_profile("no-such-bench")


def test_catalog_exposes_every_profile():
    names = {entry["name"] for entry in bench.profile_catalog()}
    assert names == set(bench.PROFILES)


# -- the model -------------------------------------------------------------


def test_apply_preserves_shape_and_dtype(clean_frame):
    out = bench.Bench().apply(clean_frame)
    assert out.shape == clean_frame.shape
    assert out.dtype == np.uint8


def test_consecutive_frames_are_not_identical(clean_frame):
    b = bench.Bench()
    assert not np.array_equal(b.apply(clean_frame), b.apply(clean_frame))


def test_source_frame_is_not_mutated(clean_frame):
    """The camera caches one decoded image per board and hands it to the bench
    on every read. Mutating it in place would accumulate noise across the whole
    session."""
    original = clean_frame.copy()
    bench.Bench(bench.get_profile("harsh")).apply(clean_frame)
    assert np.array_equal(clean_frame, original)


def test_exposure_drift_moves_frame_brightness(clean_frame):
    """The #35 failure mode: overall brightness changes between captures even
    though the board did not."""
    b = bench.Bench(bench.get_profile("unlocked"))
    means = [float(b.apply(clean_frame).mean()) for _ in range(40)]
    assert max(means) - min(means) > 2.0


def test_locked_profile_holds_brightness_steady(clean_frame):
    b = bench.Bench(bench.get_profile("locked"))
    means = [float(b.apply(clean_frame).mean()) for _ in range(40)]
    assert max(means) - min(means) < 1.0


# -- what the bench is for: the stability gate (#3, AC-006.2) --------------


def test_locked_bench_passes_the_stability_gate():
    assert stability_of("locked") < 2.0


def test_unlocked_bench_fails_the_stability_gate():
    """#35 reproduced. If this ever passes, the simulation has stopped
    demonstrating the thing it exists to demonstrate."""
    assert stability_of("unlocked") > 2.0


def test_severity_is_ordered():
    locked, unlocked, harsh = (stability_of(p) for p in ("locked", "unlocked", "harsh"))
    assert locked < unlocked < harsh


# -- capture state ---------------------------------------------------------


def test_degraded_profile_reports_degraded_capture_state():
    """The operator must see the same warning a real camera would raise."""
    camera = demo.DemoCamera()
    camera.select_bench_profile("unlocked")
    assert camera.state.settings_locked is False
    assert "exposure" in camera.state.degraded_reason


def test_returning_to_locked_clears_the_warning():
    camera = demo.DemoCamera()
    camera.select_bench_profile("harsh")
    camera.select_bench_profile("locked")
    assert camera.state.settings_locked is True
    assert camera.state.degraded_reason is None
