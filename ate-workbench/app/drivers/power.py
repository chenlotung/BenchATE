"""Chroma AC source and DC loads; each model retains its own driver."""

import re
from contextlib import contextmanager
from pyvisa.errors import VisaIOError

from app.models import Capabilities, Parameter, OutputState
from app.drivers.base import BaseInstrument, SafetyError, UnsupportedInstrument, DCLoader
from app.protocol import scalar, boolean, token, UnexpectedResponse

class Chroma61512(BaseInstrument):
    identity_vendor = "CHROMA"
    identity_models = ("61512",)
    capabilities = Capabilities(
        measurements={"voltage": "V", "current": "A", "power": "W", "frequency": "Hz"},
        setpoints={"voltage": Parameter(0, 300, 0.1, "V", 1),
                   "frequency": Parameter(15, 1500, 0.01, "Hz", 2)},
        modes=("FIXED",), output=True, readback=True,
        notes="TCP socket 2101. Controls require SINGLE phase / FIXED / AC. LAN remote/local state is unknown.")

    def validate_identity(self, identity):
        if "CHROMA" in identity.upper() and ",61500," in identity.upper():
            if not self.config.model_confirmed or self.config.model != "61512":
                raise UnsupportedInstrument("Generic 61500 IDN: confirm physical 61512 nameplate in configuration")
        else:
            super().validate_identity(identity)

    @contextmanager
    def selected(self, channel):
        if channel not in self.config.channels or channel not in ("CH1", "CH2", "CH3"):
            raise SafetyError("Invalid AC phase")
        phase = token(self.io.query("INST:PHAS?"))
        if phase == "SINGLE":
            if channel != "CH1":
                raise SafetyError("Single-phase configuration supports CH1 only")
            yield
            return
        if phase != "THREE":
            raise UnexpectedResponse(f"Unknown phase configuration {phase}")
        previous = int(scalar(self.io.query("INST:NSEL?")))
        target = int(channel[-1])
        if previous not in (1, 2, 3):
            raise UnexpectedResponse("Invalid selected phase")
        if previous != target:
            self.io.write(f"INST:NSEL {target}")
        restore = True
        try:
            yield
        except (VisaIOError, TimeoutError, ConnectionError, InterruptedError):
            restore = False
            raise
        finally:
            if restore and previous != target:
                self.io.write(f"INST:NSEL {previous}")

    def _control_context(self):
        if token(self.io.query("OUTP:MODE?")) != "FIXED":
            raise SafetyError("Select FIXED mode on instrument first")
        if token(self.io.query("OUTP:COUP?")) != "AC":
            raise SafetyError("Select AC coupling on instrument first")
        if token(self.io.query("INST:PHAS?")) != "SINGLE":
            raise SafetyError("V1 controls require SINGLE phase; three-phase output interlocks are pending validation")

    def get_setpoints(self):
        return {"voltage": scalar(self.io.query("VOLT:AC?")), "frequency": scalar(self.io.query("FREQ?"))}

    def get_output_state(self):
        return boolean(self.io.query("OUTP?"))

    def _check_range(self, values):
        selected_range = token(self.io.query("VOLT:RANG?"))
        if selected_range not in ("LOW", "HIGH", "AUTO"):
            raise UnexpectedResponse("Unknown AC voltage range")
        limit = 150 if selected_range == "LOW" else 300
        if values["voltage"] > min(limit, scalar(self.io.query("VOLT:LIM:AC?"))):
            raise SafetyError("Voltage exceeds current instrument range/limit")
        if values["frequency"] > scalar(self.io.query("FREQ:LIM?")):
            raise SafetyError("Frequency exceeds instrument limit")

    def _check_error(self):
        reply = self.io.query("SYST:ERR?").strip()
        if reply.upper() != "NO ERROR":
            raise UnexpectedResponse(f"SCPI error: {reply}")

    def apply_settings(self, values, mode="FIXED", confirmed_live=False):
        self.validate_setpoints(values)
        self._control_context()
        if mode != "FIXED":
            raise SafetyError("Only FIXED AC control supported")
        if self.get_output_state() != OutputState.OFF and not confirmed_live:
            raise SafetyError("Confirm live output changes first")
        self._check_range(values)
        self._check_error()
        self.io.write(f"VOLT:AC {values['voltage']:.1f}")
        self.io.write(f"FREQ {values['frequency']:.2f}")
        self._check_error()
        actual = self.get_setpoints()
        self.check_readback(values, actual)
        return actual

    def output_on(self):
        self._control_context()
        values = self.get_setpoints()
        self.validate_setpoints(values)
        self._check_range(values)
        self._check_error()
        self.io.write("OUTP ON")
        self._check_error()
        state = self.get_output_state()
        if state != OutputState.ON:
            raise UnexpectedResponse("Output ON was not confirmed by readback")
        return state

    def output_off(self):
        self.io.write("OUTP OFF")
        state = self.get_output_state()
        if state != OutputState.OFF:
            raise UnexpectedResponse("Output OFF was not confirmed by readback")
        return state

    def read_measurements(self):
        result = []
        for ch in self.config.channels:
            with self.selected(ch):
                values = {name: scalar(self.io.query(cmd)) for name, cmd in {
                    "voltage": "FETC:VOLT:AC?", "current": "FETC:CURR:AC?",
                    "power": "FETC:POW:AC?", "frequency": "FETC:FREQ?"}.items()}
                result.append(self.frame(ch, values, output=self.get_output_state(),
                    setpoints=self.get_setpoints(), mode=token(self.io.query("OUTP:MODE?"))))
        return result


class Chroma6312A(DCLoader):
    identity_vendor = "CHROMA"
    identity_models = ("6312A",)
    capabilities = Capabilities(measurements={"voltage": "V", "current": "A", "power": "W"},
        setpoints={"current": Parameter(0, 120, 0.003, "A", 3)}, modes=("CCL", "CCH"),
        output=True, readback=True,
        notes="One USB session per mainframe; only verified 63106A modules at CH1/CH3. Applies L1 and L2.")

    def connect(self):
        identity = super().connect()
        try:
            inventory = self.io.query("*RDT?").split(",")
            if any(ch not in ("CH1", "CH3") for ch in self.config.channels):
                raise UnsupportedInstrument("63106A on 6312A uses channel 1 or 3 (slot 1 or 2)")
            for ch in self.config.channels:
                index = int(ch[2:]) - 1
                if index >= len(inventory) or inventory[index].strip().upper() != "63106A":
                    raise UnsupportedInstrument(f"{ch}: inventory does not identify 63106A")
            return identity
        except Exception:
            self.disconnect()
            raise

    @contextmanager
    def selected(self, channel):
        if channel not in self.config.channels or channel not in ("CH1", "CH3"):
            raise SafetyError("Unconfigured 63106A channel")
        previous = int(scalar(self.io.query("CHAN?")))
        if not 1 <= previous <= 4:
            raise SafetyError("Invalid current mainframe channel")
        target = int(channel[2:])
        if previous != target:
            self.io.write(f"CHAN {target}")
        restore = True
        try:
            identity = self.io.query("CHAN:ID?").upper()
            if not re.search(r"\b63106A\b", identity):
                raise UnsupportedInstrument("Selected module is not 63106A")
            yield
        except (VisaIOError, TimeoutError, ConnectionError, InterruptedError):
            restore = False  # Do not send any more commands to a desynchronized session.
            raise
        finally:
            if restore and previous != target:
                self.io.write(f"CHAN {previous}")

    def current_parameter(self, mode):
        if mode == "CCL":
            return Parameter(0, 12, 0.003, "A", 3)
        if mode == "CCH":
            return Parameter(0, 120, 0.03, "A", 3)
        raise SafetyError("Unsupported 63106A CC range")


class Chroma63210A(DCLoader):
    identity_vendor = "CHROMA"
    identity_models = ("63210A-150-1000", "63210A-600-700", "63210A-1200-400")
    ranges = {"63210A-150-1000": ((100, .001), (500, .005), (1000, .01)),
              "63210A-600-700": ((70, .0005), (350, .0025), (700, .005)),
              "63210A-1200-400": ((40, .0004), (200, .002), (400, .004))}

    def __init__(self, config, transport_factory):
        super().__init__(config, transport_factory)
        if config.model not in self.ranges:
            raise UnsupportedInstrument("Select full 63210A variant; bare 63210A is ambiguous")
        maximum = self.ranges[config.model][-1][0]
        step = self.ranges[config.model][0][1]
        self.capabilities = Capabilities(measurements={"voltage": "V", "current": "A", "power": "W"},
            setpoints={"current": Parameter(0, maximum, step, "A", 4)}, modes=("CCL", "CCM", "CCH"),
            output=True, remote=True, readback=True,
            notes="Exact A-series variant required. Applies both L1/L2. Remote state cannot be queried.")

    def validate_identity(self, identity):
        super().validate_identity(identity)
        if identity.split(",")[1].strip().upper() != self.config.model:
            raise UnsupportedInstrument("Configured 63210A variant does not match IDN")

    def current_parameter(self, mode):
        if mode not in self.capabilities.modes:
            raise SafetyError("Unsupported CC mode")
        maximum, step = self.ranges[self.config.model][self.capabilities.modes.index(mode)]
        return Parameter(0, maximum, step, "A", 3)

    def check_scpi_error(self):
        response = self.io.query("SYST:ERR?").strip()
        if not response.startswith('0,'):
            raise UnexpectedResponse(f"SCPI error: {response}")

    def set_remote(self, remote):
        self.io.write("SYST:REM" if remote else "SYST:LOC")
        self.check_scpi_error()
        return "Unknown (remote/local requested; no status query)"
