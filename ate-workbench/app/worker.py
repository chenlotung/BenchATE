"""Per-instrument command queue, polling and session ownership."""

import heapq
import logging
import math
import time
import numpy as np
from itertools import count
from queue import PriorityQueue, Full, Empty
from dataclasses import replace
from datetime import datetime
from PySide6.QtCore import QThread, Signal

from app.models import DeviceState, ConnectionStatus, OutputState
from app.drivers.base import UnsupportedInstrument, SafetyError
from app.drivers import create_driver
from app.protocol import UnexpectedResponse

PRIORITY = {"disconnect": 0, "output_off": 1, "benchmark_cancel": 2,
            "limits": 3, "apply": 4, "output_on": 4, "remote": 4, "local": 4,
            "connect": 5, "test": 5, "monitor": 6, "screenshot": 8, "benchmark": 9, "fault": 9}


class CommandQueue:
    def __init__(self, capacity=64):
        self.queue = PriorityQueue(maxsize=capacity)
        self.sequence = count()

    def put(self, command):
        cancelled = 0
        if command.kind not in ("output_off", "disconnect") and self.queue.qsize() >= self.queue.maxsize-2:
            raise RuntimeError("Instrument command queue is full; slots reserved for OFF/disconnect")
        if command.kind == "output_off":
            # An older queued ON must never execute after a newer OFF.
            with self.queue.mutex:
                remaining = [item for item in self.queue.queue
                             if not (item[2].channel == command.channel and item[2].kind in ("apply", "output_on"))]
                cancelled = len(self.queue.queue) - len(remaining)
                self.queue.queue[:] = remaining
                heapq.heapify(self.queue.queue)
                self.queue.not_full.notify_all()
        try:
            self.queue.put_nowait((PRIORITY[command.kind], next(self.sequence), command))
        except Full:
            raise RuntimeError("Instrument command queue is full") from None
        return cancelled

    def get(self, timeout=.05):
        return self.queue.get(timeout=timeout)[2]

    def clear(self):
        from queue import Empty
        while True:
            try:
                self.queue.get_nowait()
            except Empty:
                return


log = logging.getLogger(__name__)


def advance_deadline(deadline, now, interval):
    """Next phase-aligned future tick; skip missed periods without queueing them."""
    return deadline + max(1, math.floor((now-deadline) / interval) + 1) * interval


class InstrumentWorker(QThread):
    state_changed = Signal(str, object)
    frame_ready = Signal(object)
    completed = Signal(str, str, object)
    failed = Signal(str, str)

    def __init__(self, config, *, demo=False, backend="", factory=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.demo = demo
        self.backend = backend
        self.factory = factory
        self.commands = CommandQueue()
        self.state = DeviceState()
        self.driver = None
        self.interval = config.poll_interval_ms / 1000
        self.deadline = 0.0
        self.last_poll = None
        self.benchmark = None

    def submit(self, command):
        cancelled = self.commands.put(command)
        if cancelled:
            self.completed.emit(self.config.device_id, "controls_cancelled", {
                "channel": command.channel, "result": f"Output OFF cancelled {cancelled} pending control(s)"})

    def publish(self):
        self.state.limits_approved = bool(self.driver and self.driver.limits_approved)
        self.state_changed.emit(self.config.device_id, replace(self.state, output_states=dict(self.state.output_states),
                                                             output_checked=dict(self.state.output_checked)))

    def run(self):
        try:
            self.driver = self.factory() if self.factory else create_driver(self.config, demo=self.demo,
                backend=self.backend, cancelled=self.isInterruptionRequested)
            while not self.isInterruptionRequested():
                try:
                    command = self.commands.get(.01 if self.benchmark else .04)
                except Empty:
                    command = None
                if self.isInterruptionRequested():
                    break
                try:
                    if command:
                        self.execute(command)
                    elif self.benchmark:
                        self.benchmark_step()
                    elif self.state.monitoring and time.monotonic() >= self.deadline:
                        started = time.monotonic()
                        self.poll()
                        ended = time.monotonic()
                        if ended - started > self.interval:
                            self.state.overruns += 1
                            log.warning("Polling overrun %s %.3fs", self.config.device_id, ended-started)
                        self.deadline = advance_deadline(self.deadline, ended, self.interval)
                        self.publish()
                except Exception as exc:
                    if self.isInterruptionRequested():
                        break
                    if isinstance(exc, SafetyError):
                        # User validation errors do not imply a lost physical connection.
                        self.state.control_fault = True
                        self.state.error = str(exc)
                        self.failed.emit(self.config.device_id, str(exc))
                        self.publish()
                    else:
                        self.communication_error(exc)
        except Exception as exc:
            self.state.status = ConnectionStatus.UNSUPPORTED
            self.state.error = str(exc)
            self.failed.emit(self.config.device_id, str(exc))
        finally:
            if self.driver:
                try:
                    self.driver.disconnect()
                except Exception:
                    log.exception("Failed to release VISA session")
            self.state.status = ConnectionStatus.DISCONNECTED
            self.state.monitoring = False
            self.state.output = OutputState.UNKNOWN
            self.state.output_states = {}
            self.publish()

    def communication_error(self, exc):
        from pyvisa.errors import VisaIOError
        from pyvisa.constants import StatusCode
        timeout = isinstance(exc, TimeoutError) or (
            isinstance(exc, VisaIOError) and exc.error_code == StatusCode.error_timeout)
        self.state.status = (ConnectionStatus.UNSUPPORTED if isinstance(exc, UnsupportedInstrument)
                             else ConnectionStatus.TIMEOUT if timeout else ConnectionStatus.ERROR)
        self.state.monitoring = False
        self.state.output = OutputState.UNKNOWN
        self.state.output_states = {}
        self.state.control_fault = True
        self.state.error = f"{type(exc).__name__}: {exc}"
        if self.benchmark:
            self.benchmark["timeouts" if timeout else "errors"] += 1
            self.finish_benchmark(aborted=True)
        try:
            self.driver.disconnect()
        except Exception:
            log.exception("Session close failed after communication error")
        self.commands.clear()  # Never replay a queued control after losing synchronization.
        self.failed.emit(self.config.device_id, self.state.error)
        log.warning("%s %s", self.config.device_id, self.state.error)
        self.publish()

    def execute(self, command):
        kind, payload = command.kind, command.payload
        if kind not in ("disconnect", "output_off") and time.monotonic()-command.created > 15:
            raise SafetyError("Command expired; repeat explicitly")
        if kind in ("connect", "test"):
            self.state.status = ConnectionStatus.CONNECTING
            self.publish()
            start = time.perf_counter()
            identity = self.driver.connect() if not self.driver.get_connection_status() else self.driver.identify()
            if not self.demo:
                self.driver.validate_identity(identity)
            self.state.identification = identity
            self.state.latency_ms = (self.driver.last_identity_latency_ms
                if self.driver.last_identity_latency_ms is not None else (time.perf_counter()-start)*1000)
            self.state.last_check = datetime.now().astimezone().isoformat(timespec="seconds")
            self.state.status = ConnectionStatus.CONNECTED
            self.state.error = ""
            self.state.control_fault = False
            self.last_poll = None
            result = identity
        elif kind == "disconnect":
            self.state.monitoring = False
            if self.benchmark:
                self.finish_benchmark(aborted=True)
            self.driver.disconnect()
            self.state.status = ConnectionStatus.DISCONNECTED
            self.state.output = OutputState.UNKNOWN
            self.state.output_states = {}
            self.commands.clear()
            result = "Session released; output was not modified"
        else:
            if self.state.status != ConnectionStatus.CONNECTED:
                raise SafetyError("Connect the instrument first")
            if kind == "monitor":
                self.state.monitoring = bool(payload["enabled"]) and bool(self.driver.capabilities.measurements)
                self.deadline = time.monotonic()
                result = self.state.monitoring
            elif kind == "benchmark_cancel":
                self.finish_benchmark(aborted=True)
                result = "Benchmark cancelled"
            elif kind == "benchmark":
                if self.benchmark:
                    raise SafetyError("Benchmark already running")
                query = payload["query"]
                if query not in self.driver.safe_queries().values():
                    raise SafetyError("Only driver-whitelisted read-only queries are allowed")
                count = int(payload.get("count", 100))
                if not 1 <= count <= 10000:
                    raise SafetyError("Benchmark count must be 1 .. 10000")
                self.benchmark = {"query": query, "count": count, "latencies": [], "errors": 0, "timeouts": 0}
                result = "Benchmark started; polling paused for this instrument"
            elif kind == "fault" and self.demo:
                self.driver.fault = payload["fault"]
                result = "Fault armed for next transaction"
            elif kind == "limits":
                self.driver.approve_limits(payload["limits"])
                result = {"limits": self.config.safety_limits}
            elif kind in ("remote", "local"):
                result = self.driver.set_remote(kind == "remote")
            elif kind == "screenshot":
                result = self.driver.capture_screenshot()
            elif kind in ("apply", "output_on", "output_off"):
                if kind == "output_on" and self.state.control_fault:
                    raise SafetyError("Resolve the control fault and Test Connection before enabling output")
                with self.driver.selected(command.channel):
                    if kind == "apply":
                        result = self.driver.apply_settings(payload["values"], payload["mode"], payload.get("confirmed_live", False))
                    elif kind == "output_on":
                        if payload.get("confirmed") is not True:
                            raise SafetyError("Explicit output enable confirmation is required")
                        result = self.driver.output_on()
                        self.state.output = result
                        self.state.output_states[command.channel] = result
                        self.state.output_checked[command.channel] = time.monotonic()
                    else:
                        result = self.driver.output_off()
                        self.state.output = result
                        self.state.output_states[command.channel] = result
                        self.state.output_checked[command.channel] = time.monotonic()
                if kind == "apply":
                    self.state.control_fault = False
            else:
                raise SafetyError(f"Unsupported operation {kind}")
        self.completed.emit(self.config.device_id, kind, {"channel": command.channel, "result": result})
        self.publish()

    def poll(self):
        now = time.monotonic()
        frames = self.driver.read_measurements()
        if self.last_poll is not None:
            self.state.actual_rate = 1/(now-self.last_poll)
        self.last_poll = now
        for frame in frames:
            self.state.output_states[frame.channel] = frame.output
            self.state.output_checked[frame.channel] = frame.monotonic_time
            self.frame_ready.emit(frame)
        if frames:
            self.state.output = frames[-1].output

    def benchmark_step(self):
        start = time.perf_counter()
        if self.demo:
            self.driver.benchmark_query(self.benchmark["query"])
        else:
            self.driver.io.query(self.benchmark["query"])
        self.benchmark["latencies"].append((time.perf_counter()-start)*1000)
        if len(self.benchmark["latencies"]) >= self.benchmark["count"]:
            self.finish_benchmark()

    def finish_benchmark(self, aborted=False):
        benchmark, self.benchmark = self.benchmark, None
        if not benchmark:
            return
        latencies = benchmark["latencies"]
        result = {"average_ms": float(np.mean(latencies)) if latencies else None,
                  "minimum_ms": min(latencies) if latencies else None,
                  "maximum_ms": max(latencies) if latencies else None,
                  "p95_ms": float(np.percentile(latencies, 95)) if latencies else None,
                  "success_count": len(latencies), "requested_count": benchmark["count"],
                  "timeout_count": benchmark["timeouts"], "error_count": benchmark["errors"], "aborted": aborted}
        self.deadline = time.monotonic() + self.interval
        self.completed.emit(self.config.device_id, "benchmark_result", {"result": result})
