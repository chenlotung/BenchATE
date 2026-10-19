"""Driver contract and shared DC-load control policy."""

from __future__ import annotations

import logging
import math
import re
import time
from contextlib import contextmanager

from app.models import Capabilities, Measurement, MeasurementFrame, OutputState
from app.protocol import UnexpectedResponse, scalar, token, boolean

log = logging.getLogger(__name__)


class UnsupportedInstrument(RuntimeError):
    pass


class SafetyError(ValueError):
    pass


class BaseInstrument:
    capabilities = Capabilities()
    identity_models: tuple[str, ...] = ()
    identity_vendor = ""

    def __init__(self, config, transport_factory):
        self.config = config
        self.transport_factory = transport_factory
        self.io = None
        self.identification = ""
        self.limits_approved = False
        self.last_identity_latency_ms = None

    def get_capabilities(self):
        return self.capabilities

    def connect(self):
        if self.io is not None:
            return self.identify()
        self.io = self.transport_factory()
        try:
            self.io.open(self.config)
            identity = self.identify()
            self.validate_identity(identity)
            self.identification = identity
            return identity
        except Exception:
            self.disconnect()
            raise

    def identify(self):
        start = time.perf_counter()
        reply = self.io.query("*IDN?").strip()
        self.last_identity_latency_ms = (time.perf_counter()-start)*1000
        return reply

    def validate_identity(self, identity):
        if self.identity_vendor not in identity.upper() or not any(
            re.search(rf"(?<![A-Z0-9]){re.escape(m)}(?![A-Z0-9-])", identity.upper())
            for m in self.identity_models
        ):
            raise UnsupportedInstrument(f"Driver/model mismatch: {identity}")

    def disconnect(self):
        self.limits_approved = False
        if self.io is not None:
            try:
                self.io.close()
            finally:
                self.io = None

    def get_connection_status(self):
        return self.io is not None

    @contextmanager
    def selected(self, channel):
        if channel not in self.config.channels:
            raise SafetyError(f"Unconfigured channel {channel}")
        yield

    def approve_limits(self, limits):
        if set(limits) != set(self.capabilities.setpoints):
            raise SafetyError("Approve a limit for every supported setpoint")
        for name, bounds in limits.items():
            p = self.capabilities.setpoints[name]
            if len(bounds) != 2 or not all(math.isfinite(float(v)) for v in bounds):
                raise SafetyError("Limits must contain two finite numbers")
            if not p.minimum <= bounds[0] <= bounds[1] <= p.maximum:
                raise SafetyError(f"Invalid {name} safety limits")
        self.config.safety_limits = {k: list(v) for k, v in limits.items()}
        self.limits_approved = True

    def validate_setpoints(self, values):
        if not self.limits_approved:
            raise SafetyError("Approve software safety limits for this connection first")
        if set(values) != set(self.capabilities.setpoints):
            raise SafetyError("Apply all supported setpoints together")
        for name, value in values.items():
            self.capabilities.setpoints[name].validate(value)
            lo, hi = self.config.safety_limits[name]
            if not lo <= value <= hi:
                raise SafetyError(f"{name} exceeds approved software limit {lo} .. {hi}")

    def frame(self, channel, values, **kwargs):
        return MeasurementFrame(self.config.device_id, self.config.model, channel,
            {k: Measurement(v, self.capabilities.measurements[k]) for k, v in values.items()}, **kwargs)

    def read_measurements(self):
        raise UnsupportedInstrument("Monitoring unavailable")

    def get_output_state(self):
        return OutputState.UNKNOWN

    def get_remote_state(self):
        return "Unknown"

    def get_setpoints(self):
        return {}

    def apply_settings(self, values, mode, confirmed_live=False):
        raise UnsupportedInstrument("Setpoints unavailable")

    def output_on(self):
        raise UnsupportedInstrument("Output unavailable")

    def output_off(self):
        raise UnsupportedInstrument("Output unavailable")

    def set_remote(self, remote):
        raise UnsupportedInstrument("Remote/local not documented for this interface")

    def capture_screenshot(self):
        raise UnsupportedInstrument("Screenshot unavailable")

    def check_readback(self, desired, actual):
        if set(desired) != set(actual) or any(
            not math.isclose(value, actual[name], rel_tol=0, abs_tol=self.capabilities.setpoints[name].resolution / 2 + 1e-9)
            for name, value in desired.items()
        ):
            raise UnexpectedResponse(f"Setpoint verification failed: requested={desired}, readback={actual}")

    def safe_queries(self):
        return {"Identification": "*IDN?"}


class DCLoader(BaseInstrument):
    def get_output_state(self):
        return boolean(self.io.query("LOAD?"))

    def get_setpoints(self):
        return {"current": scalar(self.io.query("CURR:STAT:L1?")),
                "current_l2": scalar(self.io.query("CURR:STAT:L2?"))}

    def current_parameter(self, mode):
        raise NotImplementedError

    def _validate_current(self, value, mode):
        self.validate_setpoints({"current": value})
        self.current_parameter(mode).validate(value)
        maximum = scalar(self.io.query("CURR:STAT:L1? MAX"))
        minimum = scalar(self.io.query("CURR:STAT:L1? MIN"))
        if not minimum <= value <= maximum:
            raise SafetyError(f"Current exceeds instrument active range {minimum} .. {maximum}")

    def check_scpi_error(self):
        pass  # 6310A manual has no SYST:ERR?. Do not invent one.

    def apply_settings(self, values, mode, confirmed_live=False):
        self.validate_setpoints(values)
        if mode not in self.capabilities.modes:
            raise SafetyError("Unsupported CC range")
        old_mode = token(self.io.query("MODE?"))
        active = self.get_output_state()
        if active != OutputState.OFF and (not confirmed_live or old_mode != mode):
            raise SafetyError("Turn load OFF before changing mode; confirm changes to active current")
        # Reject hardware limits before a mode change or any setpoint write.
        self.current_parameter(mode).validate(values["current"])
        self.check_scpi_error()
        if old_mode != mode:
            self.io.write(f"MODE {mode}")
            if token(self.io.query("MODE?")) != mode:
                raise UnexpectedResponse("CC mode readback mismatch")
        self._validate_current(values["current"], mode)
        # Both static levels are explicitly controlled to avoid guessing active A/B level.
        for level in (1, 2):
            self.io.write(f"CURR:STAT:L{level} {values['current']:.6f}")
        self.check_scpi_error()
        actual = self.get_setpoints()
        self.check_readback(values, {"current": actual["current"]})
        self.check_readback(values, {"current": actual["current_l2"]})
        return actual

    def output_on(self):
        mode = token(self.io.query("MODE?"))
        if mode not in self.capabilities.modes:
            raise SafetyError("Load ON requires a documented static CC mode")
        actual = self.get_setpoints()
        for value in actual.values():
            self._validate_current(value, mode)
        if abs(actual["current"] - actual["current_l2"]) > 1e-8:
            raise SafetyError("Apply equal L1/L2 currents before enabling load")
        self.check_scpi_error()
        self.io.write("LOAD ON")
        self.check_scpi_error()
        state = self.get_output_state()
        if state != OutputState.ON:
            raise UnexpectedResponse("Load ON was not confirmed by readback")
        return state

    def output_off(self):
        self.io.write("LOAD OFF")
        state = self.get_output_state()
        if state != OutputState.OFF:
            raise UnexpectedResponse("Load OFF was not confirmed by readback")
        return state

    def read_measurements(self):
        frames = []
        for channel in self.config.channels:
            with self.selected(channel):
                values = {key: scalar(self.io.query(command)) for key, command in {
                    "voltage": "MEAS:VOLT?", "current": "MEAS:CURR?", "power": "MEAS:POW?"}.items()}
                frames.append(self.frame(channel, values, output=self.get_output_state(),
                    setpoints=self.get_setpoints(), mode=token(self.io.query("MODE?"))))
        return frames
