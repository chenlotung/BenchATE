import csv
from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest
from app.models import MeasurementFrame, Measurement
from app.data import DataManager
from app.config import save_devices, load_devices
from app.drivers.mock import demo_configs


def test_ten_minute_buffer_is_bounded_without_channel_mixing(qapp):
    manager = DataManager()
    try:
        for i in range(7200):
            manager.accept(MeasurementFrame("a", "load", "CH1", {"current": Measurement(float(i), "A")}, monotonic_time=float(i)))
        manager.accept(MeasurementFrame("a", "load", "CH3", {"current": Measurement(3, "A")}, monotonic_time=7200))
        assert len(manager.buffers[("a", "CH1")]) == 601
        assert manager.latest[("a", "CH1")].measurements["current"].value == 7199
        assert manager.latest[("a", "CH3")].measurements["current"].value == 3
        assert len(manager.buffers[("a", "CH1")]) <= 6000
    finally:
        assert manager.csv.close()


def test_csv_preserves_measurement_time_units_and_invalid_status(tmp_path, qapp):
    manager = DataManager()
    path = tmp_path/"values.csv"
    manager.csv.start(path)
    frame = MeasurementFrame("dev", "66205", "CH1", {"voltage": Measurement(123, "V"),
        "power": Measurement(None, "W", "instrument_status_-3")}, timestamp=datetime(2026, 10, 19, tzinfo=timezone.utc), status="invalid")
    manager.accept(frame)
    assert manager.csv.close()
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    assert len(rows) == 2
    assert rows[0]["Timestamp"] == frame.timestamp.isoformat()
    assert rows[0]["Value"] == "123" and rows[0]["Unit"] == "V"
    assert rows[1]["Value"] == "" and rows[1]["Data Status"] == "instrument_status_-3"


def test_config_roundtrip_never_persists_output_or_approval(tmp_path):
    path = tmp_path/"instruments.json"
    configs = demo_configs()
    save_devices(path, configs)
    assert [c.to_dict() for c in load_devices(path)] == [c.to_dict() for c in configs]
    raw = path.read_text()
    assert "limits_approved" not in raw
    assert "output_state" not in raw


def test_invalid_sample_preserves_last_valid(qapp):
    manager = DataManager()
    try:
        valid = MeasurementFrame("dev", "66205", "CH1", {"voltage": Measurement(230, "V")})
        invalid = replace(valid, measurements={"voltage": Measurement(None, "V", "invalid")}, status="invalid")
        manager.accept(valid)
        manager.accept(invalid)
        assert manager.last_valid[("dev", "CH1")] is valid
        assert manager.latest[("dev", "CH1")] is invalid
    finally:
        manager.csv.close()
