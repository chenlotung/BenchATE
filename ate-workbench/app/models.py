"""Shared device configuration, state and measurement types."""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import StrEnum

class ConnectionStatus(StrEnum):
    DISCONNECTED = "Disconnected"
    CONNECTING = "Connecting"
    CONNECTED = "Connected"
    ERROR = "Communication Error"
    TIMEOUT = "Timeout"
    UNSUPPORTED = "Unsupported"


class OutputState(StrEnum):
    ON = "ON"
    OFF = "OFF"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class Parameter:
    minimum: float
    maximum: float
    resolution: float
    unit: str
    decimals: int

    def validate(self, value: float) -> float:
        value = float(value)
        if not math.isfinite(value) or not self.minimum <= value <= self.maximum:
            raise ValueError(f"{value} outside {self.minimum} .. {self.maximum} {self.unit}")
        # Do not silently round a requested setpoint.
        steps = (value - self.minimum) / self.resolution
        if not math.isclose(steps, round(steps), abs_tol=1e-5, rel_tol=0):
            raise ValueError(f"Resolution is {self.resolution} {self.unit}")
        return value


@dataclass(frozen=True)
class Capabilities:
    measurements: dict[str, str] = field(default_factory=dict)
    setpoints: dict[str, Parameter] = field(default_factory=dict)
    modes: tuple[str, ...] = ()
    output: bool = False
    remote: bool = False
    screenshot: bool = False
    readback: bool = False
    notes: str = "Hardware not verified"



@dataclass
class DeviceConfig:
    name: str
    driver: str
    model: str
    resource: str
    manufacturer: str = ""
    device_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    connection: str = "USB"
    poll_interval_ms: int = 1000
    timeout_ms: int = 3000
    channels: list[str] = field(default_factory=lambda: ["CH1"])
    safety_limits: dict[str, list[float]] = field(default_factory=dict)
    read_termination: str | None = "\n"
    write_termination: str = "\n"
    model_confirmed: bool = False

    def __post_init__(self):
        if self.poll_interval_ms < 100 or not 100 <= self.timeout_ms <= 60000:
            raise ValueError("Polling >= 100 ms; timeout 100 .. 60000 ms")
        if not self.name.strip() or not self.device_id or not self.resource.strip():
            raise ValueError("Name, device ID and VISA resource are required")
        if not self.channels or len(set(self.channels)) != len(self.channels):
            raise ValueError("Channels must be nonempty and unique")

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Measurement:
    value: float | None
    unit: str
    validity: str = "valid"


@dataclass(frozen=True)
class MeasurementFrame:
    device_id: str
    model: str
    channel: str
    measurements: dict[str, Measurement]
    timestamp: datetime = field(default_factory=lambda: datetime.now().astimezone())
    monotonic_time: float = field(default_factory=time.monotonic)
    output: OutputState = OutputState.UNKNOWN
    remote: str = "Unknown"
    setpoints: dict[str, float] = field(default_factory=dict)
    mode: str = "Unknown"
    status: str = "valid"
    freshness: str = "Unverified hardware sample freshness"
    update_period: float | None = None



@dataclass
class DeviceState:
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    identification: str = ""
    latency_ms: float | None = None
    last_check: str = ""
    error: str = ""
    monitoring: bool = False
    actual_rate: float = 0.0
    overruns: int = 0
    output: OutputState = OutputState.UNKNOWN
    limits_approved: bool = False
    control_fault: bool = False
    output_states: dict[str, OutputState] = field(default_factory=dict)
    output_checked: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Command:
    kind: str
    channel: str = "CH1"
    payload: dict = field(default_factory=dict)
    created: float = field(default_factory=time.monotonic)
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
