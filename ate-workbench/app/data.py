"""Bounded measurement history and background CSV logging."""

import csv
import threading
from collections import deque
from pathlib import Path
from queue import Queue, Full, Empty
from PySide6.QtCore import QObject, Signal, Slot

class CSVLogger(QObject):
    error = Signal(str)
    changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue = Queue(maxsize=10000)
        self.enabled = False
        self.closing = threading.Event()
        self.thread = threading.Thread(target=self._run, name="CSV writer", daemon=False)
        self.thread.start()

    def start(self, path):
        if self.enabled:
            raise ValueError("CSV logging already active")
        self.queue.put_nowait(("start", Path(path)))
        self.enabled = True

    def stop(self):
        if self.enabled:
            self.enabled = False
            self.queue.put_nowait(("stop", None))

    def append(self, frame):
        if self.enabled:
            try:
                self.queue.put_nowait(("frame", frame))
            except Full:
                self.enabled = False
                self.error.emit("CSV queue full; logging stopped, at least one frame not recorded")

    def close(self):
        self.request_close()
        self.thread.join(timeout=10)
        return not self.thread.is_alive()

    def request_close(self):
        self.enabled = False
        self.closing.set()

    def _run(self):
        stream = writer = None
        try:
            while True:
                try:
                    kind, item = self.queue.get(timeout=.1)
                except Empty:
                    if self.closing.is_set():
                        return
                    continue
                try:
                    if kind in ("start", "stop", "close") and stream:
                        stream.close()
                        stream = writer = None
                    if kind == "start":
                        item.parent.mkdir(parents=True, exist_ok=True)
                        stream = item.open("x", newline="", encoding="utf-8-sig")
                        writer = csv.writer(stream)
                        writer.writerow(["Timestamp", "Device ID", "Device Model", "Channel", "Measurement Name",
                                         "Value", "Unit", "Data Status", "Freshness"])
                        stream.flush()
                        self.changed.emit(str(item))
                    elif kind == "frame" and writer:
                        for name, measurement in item.measurements.items():
                            writer.writerow([item.timestamp.isoformat(), item.device_id, item.model, item.channel, name,
                                             measurement.value, measurement.unit, measurement.validity, item.freshness])
                        stream.flush()
                    elif kind == "stop":
                        self.changed.emit("Stopped")
                    elif kind == "close":
                        return
                except Exception as exc:
                    self.enabled = False
                    self.error.emit(f"CSV error: {exc}")
                    if stream:
                        stream.close()
                        stream = writer = None
                finally:
                    self.queue.task_done()
        finally:
            if stream:
                stream.close()


class DataManager(QObject):
    updated = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.buffers = {}
        self.latest = {}
        self.last_valid = {}
        self.csv = CSVLogger(self)

    @Slot(object)
    def accept(self, frame):
        key = (frame.device_id, frame.channel)
        buffer = self.buffers.setdefault(key, deque(maxlen=6000))
        buffer.append(frame)
        while buffer and frame.monotonic_time-buffer[0].monotonic_time > 600:
            buffer.popleft()
        self.latest[key] = frame
        if frame.status == "valid":
            self.last_valid[key] = frame
        self.csv.append(frame)
        self.updated.emit(frame)

    def remove(self, device_id):
        for mapping in (self.buffers, self.latest, self.last_valid):
            for key in [k for k in mapping if k[0] == device_id]:
                del mapping[key]
