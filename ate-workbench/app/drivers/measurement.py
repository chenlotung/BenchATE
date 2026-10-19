"""Power meter, multimeter and oscilloscope drivers."""

import uuid
from dataclasses import replace

from app.models import Capabilities, Measurement
from app.drivers.base import BaseInstrument, UnsupportedInstrument
from app.protocol import scalar, token, power_meter_batch, boolean, UnexpectedResponse, validate_png

class Chroma66205(BaseInstrument):
    identity_vendor = "CHROMA"
    identity_models = ("66205",)
    capabilities = Capabilities(measurements={"voltage": "V", "current": "A", "power": "W",
        "apparent_power": "VA", "power_factor": "", "frequency": "Hz"}, remote=True,
        notes="Cached FETCh batch; actual new hardware sample rate unverified. USB remote/local has no status query.")

    def read_measurements(self):
        period = scalar(self.io.query("MEAS:UPD?"))
        average = scalar(self.io.query("MEAS:AVER?"))
        mode = token(self.io.query("MEAS:MODE?"))
        values = power_meter_batch(self.io.query("FETC? V,I,W,VA,PF,FREQ"))
        # Manual defines these sentinels for returned measurement items. Preserve status, never plot as a measurement.
        measurements = {name: Measurement(None if value in (-1, -2, -3) else value, unit,
                         f"instrument_status_{value:g}" if value in (-1, -2, -3) else "valid")
                        for (name, unit), value in zip(self.capabilities.measurements.items(), values)}
        frame = self.frame("CH1", {}, mode=f"{mode}; average {average:g}", update_period=period,
            freshness=f"Cached fetch; configured update {period:g} s; new sample identity unavailable")
        return [replace(frame, measurements=measurements,
                        status="invalid" if any(m.value is None for m in measurements.values()) else "valid")]

    def set_remote(self, remote):
        self.io.write("SYST:REM" if remote else "SYST:LOC")
        return "Unknown (remote/local requested; no status query)"

    def safe_queries(self):
        return {**super().safe_queries(), "Configured update period": "MEAS:UPD?"}


class RigolDM3058E(BaseInstrument):
    identity_vendor = "RIGOL"
    identity_models = ("DM3058E",)
    functions = {
        "DCV": ("voltage", "V", ":MEAS:VOLT:DC?"), "ACV": ("voltage", "V", ":MEAS:VOLT:AC?"),
        "DCI": ("current", "A", ":MEAS:CURR:DC?"), "ACI": ("current", "A", ":MEAS:CURR:AC?"),
        "RESISTANCE": ("resistance", "Ω", ":MEAS:RES?"), "2WR": ("resistance", "Ω", ":MEAS:RES?"),
        "FRESISTANCE": ("resistance", "Ω", ":MEAS:FRES?"), "4WR": ("resistance", "Ω", ":MEAS:FRES?"),
        "FREQUENCY": ("frequency", "Hz", ":MEAS:FREQ?"), "FREQ": ("frequency", "Hz", ":MEAS:FREQ?"),
        "PERIOD": ("period", "s", ":MEAS:PER?"), "PERI": ("period", "s", ":MEAS:PER?"),
        "CAPACITANCE": ("capacitance", "F", ":MEAS:CAP?"), "CAP": ("capacitance", "F", ":MEAS:CAP?"),
        "DIODE": ("voltage", "V", ":MEAS:DIOD?")}
    capabilities = Capabilities(measurements={"voltage": "V", "current": "A", "resistance": "Ω",
        "frequency": "Hz", "period": "s", "capacitance": "F"},
        notes="RIGOL command set only. Function queried before/after reading. Unknown modes disabled.")

    def read_measurements(self):
        mode = token(self.io.query(":FUNC?"))
        if mode not in self.functions:
            raise UnsupportedInstrument(f"DMM function {mode} is not implemented; no unit inferred")
        name, _, command = self.functions[mode]
        # FUNC2:ON? has no response format in this revision. Do not guess a boolean.
        # Mode-specific queries are documented for single display only.
        value = scalar(self.io.query(command))
        if token(self.io.query(":FUNC?")) != mode:
            raise UnexpectedResponse("DMM function changed during read; value discarded")
        return [self.frame("CH1", {name: value}, mode=mode)]

    def safe_queries(self):
        return {**super().safe_queries(), "Measurement function": ":FUNC?"}


class TekMSO44B(BaseInstrument):
    identity_vendor = "TEKTRONIX"
    identity_models = ("MSO44B",)
    capabilities = Capabilities(screenshot=True,
        notes="VXI-11. PNG saved to unique temporary file on scope, read, then deleted. Does not change acquisition.")

    def read_measurements(self):
        return []  # No periodic scope I/O.

    def capture_screenshot(self):
        name = f"ate_capture_{uuid.uuid4().hex}.png"
        # Relative to scope's existing working directory; never change its CWD.
        self.io.write(f'SAVE:IMAGE "{name}"')
        if scalar(self.io.query("*OPC?")) != 1:
            raise UnexpectedResponse("Screenshot save did not complete")
        self.io.write(f'FILESYSTEM:READFILE "{name}"')
        image = validate_png(self.io.read_raw())
        # If transfer fails, leave the file for diagnosis; no further writes to a desynchronized session.
        self.io.write(f'FILESYSTEM:DELETE "{name}"')
        return image
