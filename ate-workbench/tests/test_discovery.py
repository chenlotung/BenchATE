from dataclasses import replace
import threading

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLineEdit, QPushButton

from app.instruments import InstrumentManager
from app.models import ConnectionStatus
from app.drivers.mock import demo_configs
from app.gui.connection import ConnectionPage, InstrumentDialog
from app.instruments import discover, model_from_identity, DiscoveryReport
from conftest import FakeVISA


@pytest.mark.parametrize("identity,driver", [
    ("Chroma ATE,61512,SN,1", "chroma_61512"),
    ("Chroma,66205,SN,1", "chroma_66205"),
    ("CHROMA 6312A,0,01.00,0", "chroma_6312a"),
    ("Chroma,63210A-150-1000,SN,1", "chroma_63210a"),
    ("Chroma,63210A-600-700,SN,1", "chroma_63210a"),
    ("Chroma,63210A-1200-400,SN,1", "chroma_63210a"),
    ("RIGOL TECHNOLOGIES,DM3058E,SN,1", "rigol_dm3058e"),
    ("TEKTRONIX,MSO44B,SN,1", "tek_mso44b"),
    ("Chroma ATE,61500,SN,1", None),
    ("Chroma ATE,61511,SN,1", None),
    ("Chroma,63210A,SN,1", None),
    ("Chroma,63210A-150-1000-OTHER,SN,1", None),
    ("Chroma,63106A,SN,1", None),
    ("RIGOL,DM3058,SN,1", None),
    ("TEKTRONIX,MSO46B,SN,1", None),
    ("OTHER,MSO44B,SN,1", None),
    ("OTHER,66205,SN,1", None),
    ("TEKTRONIX,MSO44B-OTHER,SN,1", None),
    ("bad reply", None),
])
def test_identification_exact_allowlist(identity, driver):
    match = model_from_identity(identity)
    assert (match[0] if match else None) == driver


def test_usb_scan_filters_unknowns_continues_timeout_and_discovers_installed_modules():
    resources = [f"USB0::1::2::{i}::INSTR" for i in range(5)]
    sessions = [
        FakeVISA({"*IDN?": "OTHER,UNKNOWN,SN,1"}),
        FakeVISA(fault=TimeoutError("no response")),
        FakeVISA({"*IDN?": "CHROMA 6312A,0,01.00,0", "*RDT?": "0,0,63106A,0"}),
        FakeVISA({"*IDN?": "RIGOL,DM3058E,SN,1"}),
        FakeVISA({"*IDN?": "Chroma,6312A,SN,1", "*RDT?": "63102A,0,0,0"}),
    ]
    pending = iter(sessions)
    report = discover(enumerate_resources=lambda _: (resources + ["ASRL1::INSTR", "USB0::1::2::RAW::RAW"], "fake"),
                      transport_factory=lambda: next(pending))
    assert [c.driver for c in report.devices] == ["chroma_6312a", "rigol_dm3058e"]
    assert report.devices[0].channels == ["CH3"]
    assert report.ignored == 2 and report.failed == 1
    assert all(io.closed for io in sessions)
    assert all(event[0] != "write" for io in sessions for event in io.events)


@pytest.mark.parametrize("scope_ip,ac_ip,expected", [
    ("", "", []), ("192.0.2.44", "", ["tek_mso44b"]),
    ("", "192.0.2.12", ["chroma_61512"]),
    ("192.0.2.44", "192.0.2.12", ["tek_mso44b", "chroma_61512"]),
])
def test_lan_fields_independent_and_blank_never_probes_enumerated_lan(scope_ip, ac_ip, expected):
    class Probe(FakeVISA):
        def open(self, config):
            self.responses["*IDN?"] = ("TEKTRONIX,MSO44B,SN,1" if "inst0" in config.resource
                                        else "Chroma ATE,61512,SN,1")
            return super().open(config)
    sessions = []
    def factory():
        sessions.append(Probe())
        return sessions[-1]
    report = discover(scope_ip=scope_ip, ac_ip=ac_ip, transport_factory=factory,
        enumerate_resources=lambda _: (["TCPIP0::192.0.2.99::INSTR", "TCPIP0::192.0.2.98::2101::SOCKET"], "fake"))
    assert [c.driver for c in report.devices] == expected
    assert len(sessions) == len(expected) and all(io.closed for io in sessions)


def test_wrong_lan_model_and_wrong_transport_not_admitted():
    sessions = iter([FakeVISA({"*IDN?": "TEKTRONIX,MSO44B,SN,1"}),
                     FakeVISA({"*IDN?": "Chroma,66205,SN,1"})])
    report = discover(scope_ip="192.0.2.44", enumerate_resources=lambda _: (["USB0::1::2::SN::INSTR"], "fake"),
                      transport_factory=lambda: next(sessions))
    assert not report.devices and report.ignored == 2


def test_invalid_lan_ip_still_scans_usb_and_does_not_open_lan():
    session = FakeVISA({"*IDN?": "Chroma ATE,66205,SN,1"})
    report = discover(scope_ip="not an ip", ac_ip="999.0.0.1",
        enumerate_resources=lambda _: (["USB0::1::2::SN::INSTR"], "fake"), transport_factory=lambda: session)
    assert len(report.devices) == 1
    assert sum("invalid IPv4" in note for note in report.notes) == 2
    assert session.events[0][1].startswith("USB")


def test_active_session_and_resource_alias_excluded_from_probe():
    alias = "USB0::1::2::SN::0::INSTR"
    report = discover(excluded=["USB::1::2::SN::INSTR"],
        enumerate_resources=lambda _: ([alias, alias], "fake"),
        transport_factory=lambda: pytest.fail("Active session must never be probed"))
    assert not report.devices


def test_cancel_stops_next_identification_and_closes_probe():
    cancelled = [False]
    def identity():
        cancelled[0] = True
        return "RIGOL,DM3058E,SN,1"
    session = FakeVISA({"*IDN?": identity})
    report = discover(cancelled=lambda: cancelled[0],
        enumerate_resources=lambda _: (["USB0::1::2::1::INSTR", "USB0::1::2::2::INSTR"], "fake"),
        transport_factory=lambda: session)
    assert not report.devices and session.closed
    assert sum(event[0] == "open" for event in session.events) == 1


@pytest.fixture
def scan_manager(qtbot):
    manager = InstrumentManager(demo=True)
    yield manager
    manager.begin_shutdown()
    qtbot.waitUntil(manager.stopped, timeout=10000)
    assert manager.data.csv.close()


def test_one_click_blank_ips_connects_only_usb_and_repeat_keeps_sessions(scan_manager, qtbot):
    page = ConnectionPage(scan_manager)
    qtbot.addWidget(page)
    assert len(page.findChildren(QLineEdit)) == 2
    assert not {"Add Instrument", "Connect", "Refresh Resources"} & {b.text() for b in page.findChildren(QPushButton)}
    page.scan_button.click()
    qtbot.waitUntil(lambda: len(scan_manager.states) == 4 and
                   all(s.status == ConnectionStatus.CONNECTED for s in scan_manager.states.values()))
    assert all(c.connection == "USB" for c in scan_manager.configs.values())
    workers = dict(scan_manager.workers)
    page.scan_button.click()
    assert scan_manager.workers == workers
    assert page.model.rowCount() == 4
    assert "blank IP" in page.resource_label.text()
    page.scope_ip.setText("192.0.2.44")
    page.scan_button.click()
    qtbot.waitUntil(lambda: len(scan_manager.states) == 5 and
                   all(s.status == ConnectionStatus.CONNECTED for s in scan_manager.states.values()))
    assert not any(c.driver == "chroma_61512" for c in scan_manager.configs.values())


def test_saved_configs_not_listed_without_discovery_and_preferences_retained(scan_manager, qtbot):
    known = [replace(c, name="Custom " + c.model, poll_interval_ms=1234) for c in demo_configs()]
    scan_manager.remember(known)
    assert not scan_manager.configs
    scan_manager.scan()
    qtbot.waitUntil(lambda: all(s.status == ConnectionStatus.CONNECTED for s in scan_manager.states.values()))
    assert len(scan_manager.configs) == 4
    assert all(c.name.startswith("Custom") and c.poll_interval_ms == 1234 for c in scan_manager.configs.values())
    dialog = InstrumentDialog(scan_manager, next(iter(scan_manager.configs.values())))
    qtbot.addWidget(dialog)
    assert [w for w in dialog.findChildren(QLineEdit) if w.objectName() != "qt_spinbox_lineedit"] == [dialog.name]


def test_real_scan_stays_background_and_shutdown_cancels_it(qtbot, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    options = []
    def fake_discover(**kwargs):
        options.append(kwargs)
        entered.set()
        while not kwargs["cancelled"]() and not release.wait(.005):
            pass
        return DiscoveryReport(backend="fake")
    monkeypatch.setattr("app.instruments.discover", fake_discover)
    manager = InstrumentManager()
    try:
        manager.scan(scope_ip="192.0.2.44")
        qtbot.waitUntil(entered.is_set)
        assert manager.scanning
        manager.scan()  # cannot start an overlapping scanner
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        qtbot.waitUntil(lambda: bool(heartbeat))
        manager.begin_shutdown()
        qtbot.waitUntil(manager.stopped, timeout=3000)
        assert len(options) == 1 and options[0]["scope_ip"] == "192.0.2.44"
        assert not manager.configs
    finally:
        release.set()
        manager.begin_shutdown()
        qtbot.waitUntil(manager.stopped, timeout=3000)
        manager.data.csv.close()


def test_real_scan_identifies_closes_probe_then_connects_and_keeps_one_session(qtbot, monkeypatch, tmp_path):
    resource = "USB0::1::2::SUPPORTED::INSTR"
    unknown = "USB0::1::2::OTHER::INSTR"
    opened, active, native = [], {}, []
    class Session:
        def __init__(self, name):
            self.resource_name = name
            assert active.get(name, 0) == 0, "Overlapping physical sessions"
            active[name] = 1
            opened.append(name)
        def query(self, query):
            assert query == "*IDN?"
            return "RIGOL,DM3058E,SN,1" if self.resource_name == resource else "OTHER,UNKNOWN,SN,1"
        def close(self):
            active[self.resource_name] -= 1
    class Backend:
        visalib = "Mock Python VISA"
        def list_resources(self, _query):
            return [resource, unknown]
        def open_resource(self, name, **_kwargs):
            return Session(name)
        def close(self):
            assert not any(active.values())
    def rm(_backend):
        native.append(Backend())
        return native[-1]
    monkeypatch.setattr("pyvisa.ResourceManager", rm)
    monkeypatch.setattr("app.protocol.usb_resources", lambda: [resource, unknown])
    manager = InstrumentManager(config_path=tmp_path/"devices.json")
    try:
        # A saved record is not admitted when enumeration no longer finds it.
        manager.remember([replace(demo_configs()[1], resource="USB0::1::2::MISSING::INSTR")])
        manager.scan()
        qtbot.waitUntil(lambda: len(manager.states) == 1 and
            next(iter(manager.states.values())).status == ConnectionStatus.CONNECTED)
        assert [c.model for c in manager.configs.values()] == ["DM3058E"]
        assert opened.count(resource) == 2  # closed probe followed by lasting worker session
        assert active[resource] == 1 and active[unknown] == 0
        worker = next(iter(manager.workers.values()))
        qtbot.waitUntil(lambda: not manager.scanners)
        manager.scan()
        qtbot.waitUntil(lambda: not manager.scanning and not manager.scanners)
        assert opened.count(resource) == 2
        assert next(iter(manager.workers.values())) is worker
        assert len(manager.configs) == 1
    finally:
        manager.begin_shutdown()
        qtbot.waitUntil(manager.stopped, timeout=5000)
        manager.data.csv.close()
    assert not any(active.values())
