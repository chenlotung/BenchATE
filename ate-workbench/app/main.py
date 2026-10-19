import argparse
from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
import sys
import time

from PySide6.QtCore import QTimer, QObject
from PySide6.QtWidgets import QApplication

from app.instruments import InstrumentManager
from app.models import ConnectionStatus
from app.drivers.mock import demo_configs
from app.gui.main_window import MainWindow
from app.gui.themes import apply_theme
from app.config import ROOT, load_application, load_devices
from app.config import configure_logging


def private_memory_bytes():
    if sys.platform != "win32":
        return 0
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
            "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage",
            "PeakPagefileUsage", "PrivateUsage")]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    process = ctypes.windll.kernel32.GetCurrentProcess
    process.restype = wintypes.HANDLE
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    get_memory.restype = wintypes.BOOL
    ok = get_memory(process(), ctypes.byref(counters), counters.cb)
    return counters.PrivateUsage if ok else 0


class DemoRun(QObject):
    """Explicit CLI validation harness. Never enabled for real instruments."""
    def __init__(self, app, window, seconds, report):
        super().__init__(window)
        self.app, self.window, self.manager = app, window, window.manager
        self.seconds, self.report = seconds, Path(report)
        self.started = time.monotonic()
        self.started_at = datetime.now().astimezone().isoformat()
        code = hashlib.sha256()
        for path in sorted((ROOT/"app").rglob("*.py")):
            code.update(path.relative_to(ROOT).as_posix().encode())
            code.update(path.read_bytes())
        self.code_sha256 = code.hexdigest()
        if getattr(sys, "frozen", False) and (ROOT/"manifest.json").exists():
            self.code_sha256 = json.loads((ROOT/"manifest.json").read_text(encoding="utf-8")).get("app_source_sha256", "unavailable")
        self.previous = self.started
        self.max_heartbeat_gap = 0
        self.ticks = 0
        self.counts = {}
        self.errors = []
        self.memory = []
        self.screenshot_ok = False
        self.manager.data.updated.connect(self.frame)
        self.manager.error.connect(self.errors.append)
        self.manager.completed.connect(self.completed)
        self.manager.state_changed.connect(self.state)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.window.navigation.setCurrentRow(1)
        self.manager.data.csv.start(ROOT/"data"/f"demo_validation_{time.time_ns()}.csv")
        self.window.connection.scope_ip.setText("192.0.2.44")
        self.window.connection.ac_ip.setText("192.0.2.12")
        self.window.connection.scan_button.click()

    def frame(self, frame):
        key = f"{frame.device_id}/{frame.channel}"
        self.counts[key] = self.counts.get(key, 0) + 1

    def state(self, device_id, state):
        if state.status == ConnectionStatus.CONNECTED and not state.monitoring and device_id not in getattr(self, "started_ids", set()):
            if not hasattr(self, "started_ids"):
                self.started_ids = set()
            self.started_ids.add(device_id)
            caps = self.manager.capabilities(device_id)
            if caps.measurements:
                self.manager.send(device_id, "monitor", enabled=True)
            if caps.screenshot:
                self.manager.send(device_id, "screenshot")

    def completed(self, _, kind, result):
        if kind == "screenshot":
            self.screenshot_ok = bool(result["result"])

    def tick(self):
        now = time.monotonic()
        self.max_heartbeat_gap = max(self.max_heartbeat_gap, now-self.previous)
        self.previous = now
        self.ticks += 1
        elapsed = now-self.started
        if self.ticks % 100 == 0:
            self.memory.append({"elapsed_seconds": round(elapsed, 2), "private_bytes": private_memory_bytes()})
            self.save(elapsed, False)
        if elapsed >= self.seconds:
            self.timer.stop()
            self.window.refresh()
            self.report.parent.mkdir(parents=True, exist_ok=True)
            self.window.grab().save(str(self.report.with_suffix(".png")))
            self.save(elapsed, True)
            self.window.close()

    def save(self, elapsed, complete):
        self.report.parent.mkdir(parents=True, exist_ok=True)
        result = {"mode": "DEMO", "elapsed_seconds": round(elapsed, 3), "requested_seconds": self.seconds,
            "started_at": self.started_at, "app_source_sha256": self.code_sha256, "python_version": sys.version,
            "complete": complete, "heartbeat_count": self.ticks, "max_heartbeat_gap_seconds": round(self.max_heartbeat_gap, 3),
            "frame_counts": self.counts, "buffer_sizes": {f"{k[0]}/{k[1]}": len(v) for k,v in self.manager.data.buffers.items()},
            "worker_running": {k: w.isRunning() for k,w in self.manager.workers.items()},
            "errors": self.errors, "screenshot_received": self.screenshot_ok, "memory_samples": self.memory,
            "hardware_verified": False}
        self.report.write_text(json.dumps(result, indent=2), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="ATE Workbench")
    parser.add_argument("--demo", action="store_true", help="Explicit synthetic demo drivers; no VISA I/O")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--soak-seconds", type=float, default=0, help="Demo-only timed validation run (3600 = one hour)")
    parser.add_argument("--report", type=Path, default=ROOT/"docs/validation/demo_run.json")
    args = parser.parse_args(argv)
    if args.soak_seconds and not args.demo:
        parser.error("Timed validation runs require --demo")
    settings = load_application()
    configure_logging(ROOT/"logs/workbench.log", settings["communication"]["command_logging"])
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ATE Workbench")
    apply_theme(app, settings["application"]["theme"])
    config_path = args.config or ROOT/"config"/("instruments.demo.local.json" if args.demo else "instruments.local.json")
    manager = InstrumentManager(demo=args.demo, backend=settings["communication"]["visa_backend"], config_path=config_path)
    try:
        configs = load_devices(config_path)
        if not args.config and not args.demo and not config_path.exists():
            configs = load_devices(ROOT/"config/instruments.json")
        if not configs and args.demo:
            configs = demo_configs()
        manager.remember(configs)
    except Exception as exc:
        logging.exception("Configuration load failed")
        manager.data.csv.close()
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    try:
        window = MainWindow(manager, settings)
    except Exception:
        manager.data.csv.close()
        raise
    window.show()
    if args.soak_seconds:
        window.validation = DemoRun(app, window, args.soak_seconds, args.report)
    exit_code = app.exec()
    if args.soak_seconds and args.report.exists():
        result = json.loads(args.report.read_text(encoding="utf-8"))
        result["shutdown_workers_released"] = manager.stopped()
        result["shutdown_csv_released"] = not manager.data.csv.thread.is_alive()
        result["process_exit_code"] = exit_code
        args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return exit_code
