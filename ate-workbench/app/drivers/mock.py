"""Explicit synthetic instruments for Demo mode and software validation."""

import math
import struct
import time
import zlib
import numpy as np
from dataclasses import replace

from app.models import DeviceConfig, OutputState
from app.drivers.base import BaseInstrument, SafetyError
from app.drivers import DRIVERS, capabilities_for
from app.protocol import PNG_SIGNATURE

def demo_png():
    width, height = 960, 480
    image = np.full((height, width, 3), (13, 22, 35), dtype=np.uint8)
    image[::48, :, :] = (37, 54, 72)
    image[:, ::96, :] = (37, 54, 72)
    x = np.arange(width)
    for phase, color, center in ((0, (47, 212, 184), 200), (1.1, (250, 193, 84), 270)):
        y = (center + 85 * np.sin(x / 45 + phase)).astype(int)
        for thick in (-1, 0, 1):
            image[y+thick, x] = color
    # A permanent bright demo stripe is also visible in the card's DEMO banner.
    image[:8, :] = (250, 193, 84)
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind+body) & 0xffffffff)
    raw = b"".join(b"\0" + row.tobytes() for row in image)
    return (PNG_SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class DemoInstrument(BaseInstrument):
    """Only reachable via explicit --demo mode; never a fallback from VISA failures."""
    def __init__(self, config):
        super().__init__(config, lambda: None)
        self.capabilities = replace(capabilities_for(config), remote=True)
        self.outputs = {ch: OutputState.OFF for ch in config.channels}
        self.settings = {ch: {k: (50.0 if k == "frequency" else 0.0) for k in self.capabilities.setpoints}
                         for ch in config.channels}
        self.modes = {ch: self.capabilities.modes[0] if self.capabilities.modes else "DCV"
                      for ch in config.channels}
        self.channel = config.channels[0]
        self.remote = "Local"
        self.fault = None
        self.connected = False

    def connect(self):
        self.connected = True
        self.limits_approved = False
        self.identification = f"DEMO,{self.config.model},{self.config.device_id},SIMULATION"
        return self.identification

    def identify(self):
        self._check()
        return self.identification

    def _check(self):
        time.sleep(.005)
        if self.fault:
            fault, self.fault = self.fault, None
            if fault == "timeout":
                raise TimeoutError("DEMO injected VISA timeout")
            raise ConnectionError("DEMO injected cable disconnect")
        if not self.connected:
            raise ConnectionError("DEMO disconnected")

    def disconnect(self):
        self.connected = False
        self.limits_approved = False
        # Physical output state survives disconnect, just as it can on a real instrument.

    def get_connection_status(self):
        return self.connected

    def selected(self, channel):
        from contextlib import contextmanager
        @contextmanager
        def context():
            if channel not in self.config.channels:
                raise SafetyError("Unconfigured channel")
            previous, self.channel = self.channel, channel
            try:
                yield
            finally:
                self.channel = previous
        return context()

    def get_output_state(self):
        self._check()
        return self.outputs[self.channel]

    def get_setpoints(self):
        self._check()
        return dict(self.settings[self.channel])

    def set_remote(self, remote):
        self._check()
        self.remote = "Remote" if remote else "Local"
        return self.remote

    def apply_settings(self, values, mode, confirmed_live=False):
        self._check()
        self.validate_setpoints(values)
        if self.outputs[self.channel] == OutputState.ON and not confirmed_live:
            raise SafetyError("Confirm live setpoint change")
        if self.capabilities.modes and mode not in self.capabilities.modes:
            raise SafetyError("Unsupported mode")
        if self.outputs[self.channel] == OutputState.ON and mode != self.modes[self.channel]:
            raise SafetyError("Turn output OFF before mode change")
        self.settings[self.channel] = dict(values)
        self.modes[self.channel] = mode
        return self.get_setpoints()

    def output_on(self):
        self._check()
        self.validate_setpoints(self.settings[self.channel])
        self.outputs[self.channel] = OutputState.ON
        return self.get_output_state()

    def output_off(self):
        self._check()
        self.outputs[self.channel] = OutputState.OFF
        return self.get_output_state()

    def read_measurements(self):
        self._check()
        if self.capabilities.screenshot:
            return []
        frames = []
        t = time.monotonic()
        for index, ch in enumerate(self.config.channels):
            settings = self.settings[ch]
            active = self.outputs[ch] == OutputState.ON
            v = (settings.get("voltage", 48.0) if active else 0.0) + .02*math.sin(t+index)
            i = settings.get("current", .25) if active else 0.0
            if not self.capabilities.output:
                v, i = 48 + .5*math.sin(t/5), .25 + .01*math.cos(t/4)
            values = {"voltage": v, "current": i, "power": v*i, "frequency": settings.get("frequency", 50),
                      "apparent_power": abs(v*i)*1.01, "power_factor": .99,
                      "resistance": 1000, "period": .02, "capacitance": 1e-6}
            frames.append(self.frame(ch, {k: values[k] for k in self.capabilities.measurements
                                        if self.config.driver != "rigol_dm3058e" or k == "voltage"},
                output=self.outputs[ch], remote=self.remote, setpoints=dict(settings), mode=self.modes[ch],
                freshness="DEMO synthetic sample - not hardware data"))
        return frames

    def benchmark_query(self, query):
        self._check()
        return self.identification

    def capture_screenshot(self):
        self._check()
        if not self.capabilities.screenshot:
            return super().capture_screenshot()
        return demo_png()


def demo_configs():
    configs = []
    for index, (key, (_, vendor, models, connection)) in enumerate(DRIVERS.items()):
        configs.append(DeviceConfig(name={"chroma_61512": "AC Source", "chroma_66205": "Power Meter",
            "rigol_dm3058e": "Multimeter", "chroma_6312a": "Modular DC Load",
            "chroma_63210a": "DC Load", "tek_mso44b": "Oscilloscope"}[key],
            driver=key, model=models[0], resource=f"DEMO::{index+1}", manufacturer=vendor,
            device_id=f"demo_{key}", connection=connection,
            channels=["CH1", "CH3"] if key == "chroma_6312a" else ["CH1"],
            safety_limits={"voltage": [0, 30], "frequency": [45, 65]} if key == "chroma_61512"
                          else {"current": [0, .9]} if "load" in key or key in ("chroma_6312a", "chroma_63210a") else {}))
    return configs
