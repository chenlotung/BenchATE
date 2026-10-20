"""Supported-device discovery and application instrument management."""

import ipaddress
import logging
import re
from dataclasses import dataclass, field, replace
from PySide6.QtCore import QObject, Signal, Slot, QThread

from app.models import DeviceConfig, Command, DeviceState, ConnectionStatus
from app.drivers import DRIVERS, capabilities_for
from app.protocol import VisaService, scan_resources
from app.worker import InstrumentWorker
from app.data import DataManager
from app.config import save_devices


@dataclass
class DiscoveryReport:
    devices: list = field(default_factory=list)
    backend: str = ""
    ignored: int = 0
    failed: int = 0
    notes: list[str] = field(default_factory=list)

    def summary(self):
        return (f"Supported: {len(self.devices)} · Excluded: {self.ignored} · No response: {self.failed}"
                + (" · " + " / ".join(self.notes) if self.notes else ""))


def resource_key(resource):
    if resource.upper().startswith("DEMO::"):
        return resource.strip().upper()
    from pyvisa.rname import parse_resource_name
    return str(parse_resource_name(resource.strip())).upper()


def model_from_identity(identity):
    """Exact allowlist, including the legacy 6312A vendor+model first field."""
    parts = [p.strip().upper() for p in identity.strip().split(",")]
    if len(parts) < 2:
        return None
    vendor, model = parts[:2]
    legacy = re.fullmatch(r"CHROMA\s+(6312A)", vendor)
    if legacy:
        vendor, model = "CHROMA", legacy[1]
    vendors = {
        "CHROMA": "Chroma", "CHROMA ATE": "Chroma", "CHROMA ATE INC.": "Chroma",
        "RIGOL": "RIGOL", "RIGOL TECHNOLOGIES": "RIGOL", "TEKTRONIX": "Tektronix",
    }
    manufacturer = vendors.get(vendor)
    for key, (_, expected_vendor, models, connection) in DRIVERS.items():
        if manufacturer == expected_vendor and model in models:
            return key, manufacturer, model, connection
    # A generic 61500 reply cannot prove that the instrument is a 61512.
    return None


def compatible_transport(resource, driver):
    normalized = resource_key(resource)
    if DRIVERS[driver][3] == "USB":
        return normalized.startswith("USB") and normalized.endswith("::INSTR")
    if driver == "chroma_61512":
        return normalized.startswith("TCPIP") and normalized.endswith("::2101::SOCKET")
    return normalized.startswith("TCPIP") and normalized.endswith("::INST0::INSTR")


def lan_targets(scope_ip="", ac_ip=""):
    targets, notes = [], []
    for label, address, driver, suffix in (
        ("Scope", scope_ip, "tek_mso44b", "inst0::INSTR"),
        ("AC Source", ac_ip, "chroma_61512", "2101::SOCKET"),
    ):
        if not address.strip():
            notes.append(f"{label} skipped (blank IP)")
            continue
        try:
            ip = str(ipaddress.IPv4Address(address.strip()))
            targets.append((f"TCPIP0::{ip}::{suffix}", driver))
        except ValueError:
            notes.append(f"{label} skipped (invalid IPv4 address)")
    return targets, notes


def discover(*, backend="@py", scope_ip="", ac_ip="", excluded=(), cancelled=lambda: False,
             progress=lambda _message: None, enumerate_resources=None, transport_factory=None):
    report = DiscoveryReport()
    enumerate_resources = enumerate_resources or scan_resources
    transport_factory = transport_factory or (lambda: VisaService(backend, cancelled))
    excluded_keys = {resource_key(r) for r in excluded}
    if excluded_keys:
        report.notes.append(f"Existing sessions retained: {len(excluded_keys)}")
    candidates = []
    # Do not include backend-enumerated LAN devices: each blank LAN field must skip it.
    progress("Scanning USB VISA resources…")
    try:
        resources, report.backend = enumerate_resources(backend)
        if not resources:
            report.notes.append("No accessible USBTMC devices; check USB driver and other applications")
        for resource in resources:
            try:
                key = resource_key(resource)
                if key.startswith("USB") and key.endswith("::INSTR"):
                    candidates.append((resource, None))
            except ValueError:
                report.ignored += 1
    except Exception as exc:
        report.notes.append(f"VISA enumeration unavailable: {exc}")
    targets, notes = lan_targets(scope_ip, ac_ip)
    candidates.extend(targets)
    report.notes.extend(notes)
    seen = set(excluded_keys)
    for resource, expected_driver in candidates:
        if cancelled():
            break
        key = resource_key(resource)
        if key in seen:
            continue
        seen.add(key)
        progress(f"Identifying device {len(seen) - len(excluded_keys)}…")
        io = None
        detected = None
        closed = True
        try:
            config = DeviceConfig(name="Discovery", driver="", model="", resource=resource,
                                  timeout_ms=1000)
            io = transport_factory()
            io.open(config)
            identity = io.query("*IDN?").strip()
            match = model_from_identity(identity)
            if not match or (expected_driver and match[0] != expected_driver):
                report.ignored += 1
                continue
            driver, manufacturer, model, connection = match
            if not compatible_transport(resource, driver):
                report.ignored += 1
                continue
            channels = ["CH1"]
            if driver == "chroma_6312a":
                inventory = [part.strip().upper() for part in io.query("*RDT?").split(",")]
                channels = [f"CH{i+1}" for i in (0, 2) if i < len(inventory) and inventory[i] == "63106A"]
                if not channels:
                    report.ignored += 1
                    continue
            if not cancelled():
                detected = DeviceConfig(name=f"{manufacturer} {model}", driver=driver,
                    model=model, manufacturer=manufacturer, resource=resource,
                    connection=connection, channels=channels)
        except InterruptedError:
            break
        except Exception as exc:
            # A failing device must not hide other supported devices or stop the scan.
            logging.getLogger(__name__).warning("Discovery failed for %s: %s", resource, exc)
            report.failed += 1
        finally:
            if io is not None:
                try:
                    io.close()
                except Exception:
                    report.failed += 1
                    closed = False
        if detected is not None and closed and not cancelled():
            report.devices.append(detected)
    return report


def canonical_resource(resource):
    return resource_key(resource)


class ResourceScanner(QThread):
    result = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, backend="@py", parent=None, **options):
        super().__init__(parent)
        self.backend = backend
        self.options = options

    def run(self):
        try:
            report = discover(backend=self.backend, cancelled=self.isInterruptionRequested,
                              progress=self.progress.emit, **self.options)
            self.result.emit(report)
        except Exception as exc:
            self.failed.emit(f"VISA backend unavailable: {exc}")


class InstrumentManager(QObject):
    changed = Signal()
    state_changed = Signal(str, object)
    completed = Signal(str, str, object)
    error = Signal(str)
    resources_ready = Signal(object, str)
    scan_changed = Signal(bool)
    scan_progress = Signal(str)

    def __init__(self, *, demo=False, backend="@py", config_path=None, parent=None):
        super().__init__(parent)
        self.demo, self.backend, self.config_path = demo, backend, config_path
        self.configs, self.states, self.workers = {}, {}, {}
        self.retired = []
        self.scanners = []
        self.resources = []
        self.known_configs = {}
        self.scanning = False
        self.scan_summary = ""
        self.pending_connections = set()
        self.data = DataManager(self)
        self.data.csv.error.connect(self.error)
        self.closing = False

    def capabilities(self, device_id):
        caps = capabilities_for(self.configs[device_id])
        return replace(caps, remote=True) if self.demo else caps

    def add(self, config, persist=True):
        if self.closing:
            raise ValueError("Application is closing")
        if config.driver not in DRIVERS or config.model not in DRIVERS[config.driver][2]:
            raise ValueError("Unknown driver/model combination")
        if self.demo != config.resource.upper().startswith("DEMO::"):
            raise ValueError("Real and Demo resource configurations cannot be mixed")
        normalized = canonical_resource(config.resource)
        if not self.demo:
            connection = DRIVERS[config.driver][3]
            if connection == "USB" and not (normalized.startswith("USB") and normalized.endswith("::INSTR")):
                raise ValueError("Driver requires a USBTMC VISA resource; serial support is pending verification")
            if connection == "Ethernet" and not normalized.startswith("TCPIP"):
                raise ValueError("Driver requires a TCPIP VISA resource")
            if config.driver == "chroma_61512" and not normalized.endswith("::SOCKET"):
                raise ValueError("61512 requires a TCP Socket resource, documented port 2101")
            if config.driver == "tek_mso44b" and not normalized.endswith("::INSTR"):
                raise ValueError("MSO44B requires an INSTR resource for enabled VXI-11")
        if config.device_id in self.configs or any(canonical_resource(c.resource) == normalized for c in self.configs.values()):
            raise ValueError("Duplicate device ID or physical VISA resource; use channels on one mainframe")
        if config.driver == "chroma_6312a" and any(ch not in ("CH1", "CH3") for ch in config.channels):
            raise ValueError("63106A on 6312A supports CH1 / CH3 (slot 1 / 2)")
        if config.driver not in ("chroma_6312a", "chroma_61512") and config.channels != ["CH1"]:
            raise ValueError("This driver supports CH1 only")
        self.configs[config.device_id] = config
        self.states[config.device_id] = DeviceState()
        if persist:
            self.save()
        self.changed.emit()

    def save(self):
        self.known_configs.update({canonical_resource(c.resource): c for c in self.configs.values()})
        if self.config_path:
            save_devices(self.config_path, self.known_configs.values())

    def remember(self, configs):
        """Saved preferences are not proof of a discovered/connected instrument."""
        self.known_configs = {canonical_resource(c.resource): c for c in configs
            if c.driver in DRIVERS and c.model in DRIVERS[c.driver][2]
            and self.demo == c.resource.upper().startswith("DEMO::")}

    def remove(self, device_id):
        if self.scanning:
            raise ValueError("Wait for discovery to finish before removing or editing devices")
        state = self.states[device_id]
        if device_id in self.pending_connections or state.status in (ConnectionStatus.CONNECTED, ConnectionStatus.CONNECTING):
            raise ValueError("Disconnect the instrument before removing it")
        worker = self.workers.pop(device_id, None)
        if worker:
            if worker.isRunning():
                worker.requestInterruption()
                self.retired.append(worker)
            else:
                worker.deleteLater()
        self.data.remove(device_id)
        self.known_configs.pop(canonical_resource(self.configs[device_id].resource), None)
        self.configs.pop(device_id)
        self.states.pop(device_id)
        self.save()
        self.changed.emit()

    def send(self, device_id, kind, channel="CH1", **payload):
        if self.closing:
            return
        if self.scanning and kind in ("connect", "test"):
            self.error.emit("Wait for discovery to finish before testing a connection.")
            return
        if device_id not in self.workers or not self.workers[device_id].isRunning():
            worker = InstrumentWorker(self.configs[device_id], demo=self.demo, backend=self.backend, parent=self)
            worker.state_changed.connect(self._state)
            worker.frame_ready.connect(self.data.accept)
            worker.completed.connect(self._complete)
            worker.failed.connect(self._failed)
            worker.finished.connect(self._worker_finished)
            self.workers[device_id] = worker
            worker.start()
        if kind in ("connect", "test"):
            self.pending_connections.add(device_id)
        try:
            self.workers[device_id].submit(Command(kind, channel, payload))
        except Exception:
            self.pending_connections.discard(device_id)
            raise

    @Slot(str, object)
    def _state(self, device_id, state):
        if device_id in self.states and self.sender() is self.workers.get(device_id):
            self.states[device_id] = state
            if state.status != ConnectionStatus.CONNECTING:
                self.pending_connections.discard(device_id)
            self.state_changed.emit(device_id, state)

    @Slot(str, str, object)
    def _complete(self, device_id, kind, result):
        if self.sender() is not self.workers.get(device_id):
            return
        if kind == "limits":
            self.configs[device_id].safety_limits = result["result"]["limits"]
            self.save()
        self.completed.emit(device_id, kind, result)

    @Slot(str, str)
    def _failed(self, device_id, message):
        self.error.emit(f"{self.configs[device_id].name if device_id in self.configs else device_id}: {message}")

    @Slot()
    def _worker_finished(self):
        worker = self.sender()
        if worker in self.retired:
            self.retired.remove(worker)
            worker.deleteLater()

    def scan(self, *, scope_ip="", ac_ip=""):
        if self.closing or self.scanning or any(s.isRunning() for s in self.scanners):
            return
        self.scanning = True
        self.scan_changed.emit(True)
        if self.demo:
            from app.drivers.mock import demo_configs
            # Same optional-LAN selection in Demo, without any VISA/network access.
            targets, notes = lan_targets(scope_ip, ac_ip)
            enabled_lan = {driver for _, driver in targets}
            configs = [c for c in demo_configs() if c.connection == "USB"
                       or c.driver in enabled_lan]
            report = DiscoveryReport(devices=configs, backend="DEMO simulated backend", notes=notes)
            self._resources(report)
            return
        # Active sessions are never opened or queried by a second scanner session.
        excluded = [c.resource for key, c in self.configs.items()
                    if key in self.pending_connections
                    or self.states[key].status in (ConnectionStatus.CONNECTED, ConnectionStatus.CONNECTING)]
        scanner = ResourceScanner(self.backend, self, scope_ip=scope_ip, ac_ip=ac_ip, excluded=excluded)
        scanner.result.connect(self._resources)
        scanner.failed.connect(self._scan_failed)
        scanner.progress.connect(self.scan_progress)
        scanner.finished.connect(self._scanner_finished)
        self.scanners.append(scanner)
        scanner.start()

    @Slot()
    def _scanner_finished(self):
        scanner = self.sender()
        if scanner in self.scanners:
            self.scanners.remove(scanner)
        scanner.deleteLater()

    @Slot(str)
    def _scan_failed(self, message):
        self.scanning = False
        self.scan_changed.emit(False)
        self.scan_summary = message
        self.scan_progress.emit(message)
        self.error.emit(message)

    @Slot(object)
    def _resources(self, report):
        self.scanning = False
        if self.closing:
            return
        existing = {canonical_resource(c.resource): c for c in self.configs.values()}
        self.resources = [c.resource for c in report.devices]
        for detected in report.devices:
            key = canonical_resource(detected.resource)
            if key in existing:
                config = existing[key]
                if config.driver != detected.driver or config.model != detected.model:
                    if self.states[config.device_id].status in (ConnectionStatus.CONNECTED, ConnectionStatus.CONNECTING):
                        continue
                    self.remove(config.device_id)
                else:
                    state = self.states[config.device_id]
                    if state.status not in (ConnectionStatus.CONNECTED, ConnectionStatus.CONNECTING):
                        # A stopped worker holds an old channel inventory; replace it.
                        if config.channels != detected.channels:
                            self.remove(config.device_id)
                            detected = replace(config, channels=detected.channels)
                        else:
                            self.send(config.device_id, "connect")
                            continue
                    else:
                        continue
            saved = self.known_configs.get(key)
            if saved and (saved.driver, saved.model) == (detected.driver, detected.model):
                detected = replace(saved, channels=detected.channels)
            try:
                self.add(detected, persist=False)
                self.send(detected.device_id, "connect")
            except ValueError as exc:
                self.error.emit(str(exc))
        self.save()
        self.scan_summary = report.summary()
        self.resources_ready.emit(self.resources, report.backend or "VISA unavailable")
        self.scan_progress.emit(self.scan_summary)
        self.scan_changed.emit(False)

    def begin_shutdown(self):
        self.closing = True
        for worker in [*self.workers.values(), *self.retired, *self.scanners]:
            worker.requestInterruption()

    def stopped(self):
        return all(not worker.isRunning() for worker in [*self.workers.values(), *self.retired, *self.scanners])
