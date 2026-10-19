import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from app.instruments import InstrumentManager
from app.drivers.mock import demo_configs
from app.gui.themes import apply_theme


@pytest.fixture
def manager(qtbot, qapp):
    apply_theme(qapp)
    manager = InstrumentManager(demo=True)
    for config in demo_configs():
        manager.add(config, persist=False)
    yield manager
    manager.begin_shutdown()
    qtbot.waitUntil(manager.stopped, timeout=10000)
    assert manager.data.csv.close()


class FakeVISA:
    def __init__(self, responses=None, fault=None):
        self.responses = responses or {}
        self.events = []
        self.closed = False
        self.fault = fault
        self.raw = b""

    def open(self, config):
        self.events.append(("open", config.resource))
        return self

    def query(self, command):
        self.events.append(("query", command))
        if self.fault:
            raise self.fault
        if command not in self.responses:
            raise AssertionError(f"Unexpected query: {command}")
        result = self.responses[command]
        if callable(result):
            return result()
        return result

    def write(self, command):
        self.events.append(("write", command))
        if self.fault:
            raise self.fault

    def read_raw(self):
        self.events.append(("binary", None))
        return self.raw

    def close(self):
        self.closed = True
        self.events.append(("close", None))
