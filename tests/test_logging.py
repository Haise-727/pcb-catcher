"""Structured logging tests — issue #33, FR-027.

The requirement names three fields specifically: registration_residual_px,
per-stage duration, and component count. Those are what let you tell a latency
regression from an accuracy regression, so these tests assert they are present
rather than merely that logging happens.
"""

from __future__ import annotations

import json
import logging

import pytest

from gerbereye import config, logging_setup


@pytest.fixture()
def log_path(tmp_path, monkeypatch):
    """Point logging at a throwaway directory and force reconfiguration."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "GOLDEN_DIR", tmp_path / "golden")
    monkeypatch.setattr(config, "IMAGE_DIR", tmp_path / "images")
    monkeypatch.setattr(logging_setup, "_configured", False)

    logger = logging.getLogger(logging_setup.LOG_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    yield tmp_path / "gerbereye.jsonl"

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_each_record_is_one_json_object(log_path):
    """One object per line, so it greps and parses without a log library --
    which matters on a shop laptop where that is all the debugger has."""
    logging_setup.log_event("started", camera_index=0)
    logging_setup.log_event("stopped")

    records = read_lines(log_path)
    assert len(records) == 2
    assert records[0]["event"] == "started"
    assert records[0]["camera_index"] == 0
    assert all("ts" in r and "level" in r for r in records)


def test_inspection_record_carries_the_three_required_fields(log_path):
    """FR-027 names these specifically."""
    timer = logging_setup.StageTimer()
    with timer.stage("differencing"):
        pass

    logging_setup.log_inspection(
        inspection_id=7,
        board_type_id=1,
        verdict="fail",
        path_used="cad",
        component_count=19,
        region_count=3,
        timer=timer,
        registration_residual_px=1.234,
        registration_state="registered",
    )

    record = read_lines(log_path)[0]
    assert record["registration_residual_px"] == 1.234
    assert record["component_count"] == 19
    assert "differencing_ms" in record
    assert record["total_ms"] >= 0


def test_stage_timings_are_recorded_per_stage(log_path):
    timer = logging_setup.StageTimer()
    for stage in ("capture", "differencing", "registration", "naming", "persist"):
        with timer.stage(stage):
            pass

    durations = timer.as_dict()
    assert set(durations) == {
        "capture_ms", "differencing_ms", "registration_ms", "naming_ms", "persist_ms",
    }
    assert all(value >= 0 for value in durations.values())


def test_stage_duration_is_recorded_even_when_the_stage_raises():
    """A stage that failed slowly is exactly the one worth seeing in the log."""
    timer = logging_setup.StageTimer()
    with pytest.raises(ValueError):
        with timer.stage("registration"):
            raise ValueError("boom")

    assert "registration_ms" in timer.as_dict()


def test_missing_residual_is_logged_as_null_not_omitted(log_path):
    """The differencing-only path has no residual. The field must still be
    present, so a log consumer can distinguish 'no CAD path' from 'field
    dropped by an older build'."""
    logging_setup.log_inspection(
        board_type_id=1,
        verdict="pass",
        path_used="differencing",
        component_count=0,
        region_count=0,
        timer=logging_setup.StageTimer(),
        registration_residual_px=None,
    )
    record = read_lines(log_path)[0]
    assert "registration_residual_px" in record
    assert record["registration_residual_px"] is None


def test_unserialisable_values_do_not_break_logging(log_path):
    """A Path or numpy scalar in a field must not take the log down."""
    from pathlib import Path as P

    logging_setup.log_event("ingested", source=P("/tmp/board.gbr"))
    record = read_lines(log_path)[0]
    assert "board.gbr" in record["source"]


def test_warnings_are_recorded_at_warning_level(log_path):
    logging_setup.log_warning("capture_degraded", reason="driver refused manual mode")
    record = read_lines(log_path)[0]
    assert record["level"] == "WARNING"
    assert record["reason"] == "driver refused manual mode"
