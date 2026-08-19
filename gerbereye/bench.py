"""Virtual bench — a simulated jig, ring light and sensor for demo mode.

The hardware chain (#2 jig, #35 exposure lock, #3 stability gate) cannot be
brought up on demand, which leaves a gap in what the station can *show*. Demo
mode already proves the pipeline runs without a camera, but it serves near
perfect frames, so the parts of the system that exist specifically to cope with
imperfect ones never do anything visible:

  - the frame-stability gate (AC-006.2 / #3) always passes trivially
  - the degraded-capture state (FR-006 A1 / #35) never lights up
  - threshold tuning (#9) has nothing to tune against

This module closes that gap by pushing the bundled board images through a
physically motivated model of a cheap USB webcam on a jig, with switchable
profiles standing in for bench conditions we cannot currently build.

**These numbers are simulated and must never be quoted as NFR results.**
`measure_frame_stability` against this bench verifies that the gate *works*; it
says nothing about what a real camera will do. Every payload that carries a
bench figure also carries `simulated: true` so a reader cannot mistake one for
the other. The real `Camera` class is untouched by this module.

Why it earns its place: RSK-02 identified illumination stability as the primary
control on the false-call rate — a bigger lever than any algorithm change
available to us. That claim is currently asserted in a document. Here it is
demonstrable in about four seconds, on a laptop, with no hardware.

Model, applied in the order the physics happens:

  1. **Board placement** — the operator drops the board into the jig by hand.
     Sub-pixel translation and a fraction of a degree of rotation, per capture.
  2. **Illumination field** — a ring light is brighter in the middle than at
     the edges. Static per profile, so it cancels in differencing; it is here
     so the registration path sees a realistic contrast gradient.
  3. **Exposure drift** — what auto-exposure does when the driver refuses
     manual control. A slow global gain cycle. This is #35, reproduced.
  4. **Read noise** — sensor noise, gaussian, per pixel per frame.

Drift is driven by a frame counter rather than the wall clock, so a stability
sweep of 50 reads covers a full cycle no matter how fast it samples, and the
same profile produces the same character of result every run.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class BenchProfile:
    """One set of bench conditions.

    Attributes are in physical units so the values can be argued about:
    grey levels, pixels, degrees, and fractional gain.
    """

    name: str
    label: str
    description: str
    # Gaussian sensor read noise, in grey levels.
    read_noise: float
    # Peak fractional deviation of the global gain. 0.05 means the frame
    # brightens and darkens by 5% as auto-exposure hunts.
    exposure_drift: float
    # Frames per full drift cycle.
    drift_period: int
    # Board placement scatter in the jig, one sigma.
    jitter_px: float
    jitter_deg: float
    # Radial falloff of the ring light at the frame corners, 0..1.
    vignette: float
    # What the capture subsystem reports in this condition.
    settings_locked: bool
    degraded_reason: str | None
    # What a human should conclude from selecting this profile.
    expectation: str


PROFILES: dict[str, BenchProfile] = {
    "locked": BenchProfile(
        name="locked",
        label="Jig locked",
        description=(
            "The bench as specified: board seated in the jig, diffused ring "
            "light, camera exposure/focus/white-balance held manual."
        ),
        read_noise=0.8,
        exposure_drift=0.0,
        drift_period=40,
        jitter_px=0.15,
        jitter_deg=0.02,
        vignette=0.05,
        settings_locked=True,
        degraded_reason=None,
        expectation="Stability passes. Good boards pass, seeded defects are found.",
    ),
    "unlocked": BenchProfile(
        name="unlocked",
        label="Exposure unlocked (#35)",
        description=(
            "The fault on the development laptop: the UVC driver refuses "
            "manual exposure, so the camera re-exposes between the golden "
            "capture and the live frame."
        ),
        read_noise=1.1,
        exposure_drift=0.055,
        drift_period=40,
        jitter_px=0.4,
        jitter_deg=0.06,
        vignette=0.07,
        settings_locked=False,
        degraded_reason="driver refused manual control of: auto-exposure, exposure",
        expectation=(
            "Stability fails the 2 grey-level gate. The station reports "
            "degraded rather than pretending its thresholds still hold."
        ),
    ),
    "harsh": BenchProfile(
        name="harsh",
        label="Uncontrolled shop light (CON-11)",
        description=(
            "Worst realistic case: overhead fluorescents, no enclosure, a jig "
            "the board moves in. What an MSME floor looks like before anyone "
            "has controlled the light."
        ),
        read_noise=2.4,
        exposure_drift=0.12,
        drift_period=32,
        jitter_px=1.6,
        jitter_deg=0.35,
        vignette=0.18,
        settings_locked=False,
        degraded_reason="uncontrolled ambient light; exposure and white balance drifting",
        expectation=(
            "Stability fails badly and false calls appear on a good board. "
            "This is RSK-02 made visible: fix the light before the algorithm."
        ),
    ),
}

DEFAULT_PROFILE = "locked"


def get_profile(name: str) -> BenchProfile:
    try:
        return PROFILES[name]
    except KeyError:
        raise KeyError(f"no bench profile named {name!r}") from None


def profile_catalog() -> list[dict]:
    """Profiles for the UI picker, in increasing order of severity."""
    return [
        {
            "name": p.name,
            "label": p.label,
            "description": p.description,
            "expectation": p.expectation,
            "settings_locked": p.settings_locked,
        }
        for p in PROFILES.values()
    ]


class Bench:
    """Applies a profile's optics and sensor model to a clean board image.

    Holds the drift phase and the cached illumination field. One instance per
    camera, because the phase is per-camera state.
    """

    def __init__(self, profile: BenchProfile | None = None) -> None:
        self._profile = profile or get_profile(DEFAULT_PROFILE)
        self._frame_count = 0
        self._rng = np.random.default_rng()
        self._field: np.ndarray | None = None
        self._field_shape: tuple[int, ...] | None = None

    @property
    def profile(self) -> BenchProfile:
        return self._profile

    def select(self, name: str) -> BenchProfile:
        """Switch conditions. Resets phase so the change is immediate."""
        self._profile = get_profile(name)
        self._frame_count = 0
        self._field = None
        self._field_shape = None
        return self._profile

    # -- the model ---------------------------------------------------------

    def _illumination_field(self, shape: tuple[int, ...]) -> np.ndarray:
        """Radial falloff standing in for ring-light geometry.

        Cached: the light does not move between frames, which is exactly why
        this term cancels in golden-board differencing. It is modelled anyway
        so the registration path sees a realistic contrast gradient rather than
        a flat field it will never meet in production.
        """
        if self._field is not None and self._field_shape == shape:
            return self._field

        height, width = shape[:2]
        ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
        cy, cx = (height - 1) / 2.0, (width - 1) / 2.0
        radius = np.sqrt(((xs - cx) / cx) ** 2 + ((ys - cy) / cy) ** 2)
        field = 1.0 - self._profile.vignette * np.clip(radius / math.sqrt(2.0), 0.0, 1.0)

        if len(shape) == 3:
            field = field[:, :, np.newaxis]
        self._field = field.astype(np.float32)
        self._field_shape = shape
        return self._field

    def _place_board(self, frame: np.ndarray) -> np.ndarray:
        """Sub-pixel translation and rotation — the board sitting in the jig."""
        p = self._profile
        if p.jitter_px <= 0 and p.jitter_deg <= 0:
            return frame

        height, width = frame.shape[:2]
        angle = float(self._rng.normal(0.0, p.jitter_deg))
        dx = float(self._rng.normal(0.0, p.jitter_px))
        dy = float(self._rng.normal(0.0, p.jitter_px))

        matrix = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), angle, 1.0)
        matrix[0, 2] += dx
        matrix[1, 2] += dy
        # BORDER_REPLICATE rather than a black border: a real camera sees more
        # bench beyond the board, not a void, and a hard black edge would hand
        # the differencing engine a defect that is not there.
        return cv2.warpAffine(
            frame, matrix, (width, height),
            flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE,
        )

    def _exposure_gain(self) -> float:
        """Global gain for this frame — auto-exposure hunting (#35)."""
        p = self._profile
        if p.exposure_drift <= 0:
            return 1.0
        phase = 2.0 * math.pi * (self._frame_count % p.drift_period) / p.drift_period
        return 1.0 + p.exposure_drift * math.sin(phase)

    def apply(self, frame: np.ndarray) -> np.ndarray:
        """Run one clean board image through the bench model."""
        p = self._profile
        self._frame_count += 1

        out = self._place_board(frame).astype(np.float32)
        out *= self._illumination_field(out.shape)
        out *= self._exposure_gain()
        if p.read_noise > 0:
            out += self._rng.normal(0.0, p.read_noise, out.shape)

        return np.clip(out, 0, 255).astype(np.uint8)
