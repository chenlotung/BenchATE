from dataclasses import replace
import threading
import time

import pytest
from pyvisa.errors import VisaIOError
from pyvisa.constants import StatusCode

from app.models import Command, ConnectionStatus, DeviceConfig, OutputState
from app.worker import InstrumentWorker, advance_deadline
from app.drivers.mock import DemoInstrument, demo_configs
from app.drivers.power import Chroma61512
from conftest import FakeVISA


def stop_worker(worker, qtbot):
    worker.requestInterruption()
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=10000)


@pytest.mark.parametrize("fault,status", [(VisaIOError(StatusCode.error_timeout), ConnectionStatus.TIMEOUT),
    (VisaIOError(StatusCode.error_connection_lost), ConnectionStatus.ERROR),
    (ConnectionError("USB disconnected"), ConnectionStatus.ERROR)])
def test_mock_visa_errors_release_session(fault, status, qtbot):
    cfg = DeviceConfig("AC", "chroma_61512", "61512", "TCPIP0::192.0.2.1::2101::SOCKET")
    io = FakeVISA(fault=fault)
    worker = InstrumentWorker(cfg, factory=lambda: Chroma61512(cfg, lambda: io))
    errors = []
    worker.state_changed.connect(lambda _, state: errors.append(state.status))
    worker.start()
    worker.submit(Command("connect"))
    try:
        qtbot.waitUntil(lambda: status in errors)
        assert io.closed
        assert worker.state.output == OutputState.UNKNOWN
        assert not worker.state.monitoring
        assert worker.commands.queue.empty()
    finally:
        stop_worker(worker, qtbot)


def test_same_instrument_serializes_queries_and_priority_controls(qtbot):
    config = demo_configs()[0]
    events = []
    class SlowDemo(DemoInstrument):
        def identify(self):
            events.append(("query_start", threading.get_ident()))
            time.sleep(.12)
            events.append(("query_end", threading.get_ident()))
            return super().identify()

        def output_off(self):
            events.append(("off", threading.get_ident()))
            return super().output_off()

    worker = InstrumentWorker(config, demo=True, factory=lambda: SlowDemo(config))
    worker.start()
    worker.submit(Command("connect"))
    try:
        qtbot.waitUntil(lambda: worker.state.status == ConnectionStatus.CONNECTED)
        worker.submit(Command("test"))
        qtbot.waitUntil(lambda: bool(events))
        worker.submit(Command("output_off"))
        qtbot.waitUntil(lambda: len(events) == 3)
        assert [e[0] for e in events] == ["query_start", "query_end", "off"]
        assert len({e[1] for e in events}) == 1
        assert events[0][1] != threading.get_ident()
    finally:
        stop_worker(worker, qtbot)


def test_output_on_requires_confirmation_and_fault_clear(qtbot):
    config = demo_configs()[0]
    worker = InstrumentWorker(config, demo=True)
    worker.start()
    worker.submit(Command("connect"))
    try:
        qtbot.waitUntil(lambda: worker.state.status == ConnectionStatus.CONNECTED)
        worker.submit(Command("output_on", payload={"confirmed": False}))
        qtbot.waitUntil(lambda: worker.state.control_fault)
        assert worker.driver.outputs["CH1"] == OutputState.OFF
        worker.submit(Command("test"))
        qtbot.waitUntil(lambda: not worker.state.control_fault)
        worker.submit(Command("limits", payload={"limits": {"voltage": [0, 30], "frequency": [45, 65]}}))
        qtbot.waitUntil(lambda: worker.state.limits_approved)
        worker.submit(Command("output_on", payload={"confirmed": True}))
        qtbot.waitUntil(lambda: worker.state.output == OutputState.ON)
        worker.submit(Command("disconnect"))
        qtbot.waitUntil(lambda: worker.state.status == ConnectionStatus.DISCONNECTED)
        assert worker.driver.outputs["CH1"] == OutputState.ON  # no unsolicited shutdown
        assert not worker.driver.limits_approved
        worker.submit(Command("connect"))
        qtbot.waitUntil(lambda: worker.state.status == ConnectionStatus.CONNECTED)
        assert worker.state.output == OutputState.UNKNOWN
    finally:
        stop_worker(worker, qtbot)


def test_benchmark_statistics_and_monitor_coordination(qtbot):
    cfg = demo_configs()[1]
    worker = InstrumentWorker(cfg, demo=True)
    results = []
    worker.completed.connect(lambda _, kind, payload: results.append((kind, payload)))
    worker.start()
    worker.submit(Command("connect"))
    try:
        qtbot.waitUntil(lambda: worker.state.status == ConnectionStatus.CONNECTED)
        worker.submit(Command("monitor", payload={"enabled": True}))
        worker.submit(Command("benchmark", payload={"query": "*IDN?", "count": 12}))
        qtbot.waitUntil(lambda: any(kind == "benchmark_result" for kind, _ in results))
        report = next(payload["result"] for kind, payload in results if kind == "benchmark_result")
        assert report["success_count"] == 12
        assert report["minimum_ms"] <= report["average_ms"] <= report["maximum_ms"]
        assert report["minimum_ms"] <= report["p95_ms"] <= report["maximum_ms"]
        assert report["timeout_count"] == report["error_count"] == 0
        assert worker.state.monitoring
    finally:
        stop_worker(worker, qtbot)


def test_deadline_skips_missed_periods_without_drift():
    assert advance_deadline(100, 100.2, 1) == 101
    assert advance_deadline(100, 103.9, 1) == 104
    assert advance_deadline(100, 101, 1) == 102


def test_default_one_hz_and_parallel_instrument_polling(manager, qtbot):
    ids = list(manager.configs)[:2]
    times = {device_id: [] for device_id in ids}
    manager.data.updated.connect(lambda frame: times[frame.device_id].append(frame.monotonic_time))
    for device_id in ids:
        assert manager.configs[device_id].poll_interval_ms == 1000
        manager.send(device_id, "connect")
    qtbot.waitUntil(lambda: all(manager.states[i].status == ConnectionStatus.CONNECTED for i in ids))
    for device_id in ids:
        manager.send(device_id, "monitor", enabled=True)
    qtbot.waitUntil(lambda: all(len(t) >= 4 for t in times.values()), timeout=6500)
    for readings in times.values():
        intervals = [b-a for a,b in zip(readings, readings[1:])]
        assert all(.80 < delta < 1.20 for delta in intervals)
    assert abs(times[ids[0]][0] - times[ids[1]][0]) < .3


def test_one_timeout_does_not_stop_other_workers(manager, qtbot):
    ids = list(manager.configs)[:2]
    for device_id in ids:
        manager.send(device_id, "connect")
    qtbot.waitUntil(lambda: all(manager.states[i].status == ConnectionStatus.CONNECTED for i in ids))
    for device_id in ids:
        manager.send(device_id, "monitor", enabled=True)
    qtbot.waitUntil(lambda: len(manager.data.latest) >= 2)
    other_frame = manager.data.latest[(ids[1], "CH1")]
    manager.send(ids[0], "fault", fault="timeout")
    qtbot.waitUntil(lambda: manager.states[ids[0]].status == ConnectionStatus.TIMEOUT, timeout=3000)
    assert (ids[0], "CH1") in manager.data.last_valid
    qtbot.waitUntil(lambda: manager.data.latest[(ids[1], "CH1")].monotonic_time > other_frame.monotonic_time)
    assert manager.states[ids[1]].monitoring


def test_mainframe_output_state_is_per_channel(manager, qtbot):
    device_id = "demo_chroma_6312a"
    manager.send(device_id, "connect")
    qtbot.waitUntil(lambda: manager.states[device_id].status == ConnectionStatus.CONNECTED)
    manager.send(device_id, "limits", limits={"current": [0, .9]})
    qtbot.waitUntil(lambda: manager.states[device_id].limits_approved)
    manager.send(device_id, "output_on", "CH3", confirmed=True)
    qtbot.waitUntil(lambda: manager.states[device_id].output_states.get("CH3") == OutputState.ON)
    manager.send(device_id, "monitor", enabled=True)
    qtbot.waitUntil(lambda: "CH1" in manager.states[device_id].output_states)
    assert manager.states[device_id].output_states == {"CH1": OutputState.OFF, "CH3": OutputState.ON}


def test_shutdown_releases_all_workers_and_session(manager, qtbot):
    for device_id in manager.configs:
        manager.send(device_id, "connect")
    qtbot.waitUntil(lambda: all(s.status == ConnectionStatus.CONNECTED for s in manager.states.values()))
    manager.begin_shutdown()
    qtbot.waitUntil(manager.stopped)
    assert all(not worker.driver.get_connection_status() for worker in manager.workers.values())
