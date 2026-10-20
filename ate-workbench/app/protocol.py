"""VISA transport, strict SCPI response parsing and PNG validation. No Qt dependencies."""

import logging
import threading
import math
import re
import struct
import zlib

from app.models import OutputState

log = logging.getLogger(__name__)


def python_backend(backend="@py"):
    # Empty values from older configuration files must not select native VISA.
    if backend not in (None, "", "@py"):
        raise ValueError("This branch requires pyvisa-py: set communication.visa_backend to @py")
    return "@py"


def packaged_usb_backend():
    import libusb_package
    path = libusb_package.get_library_path()
    if path is None or not path.is_file():
        raise RuntimeError("Bundled libusb library missing; restore the complete application folder")
    if libusb_package.get_libusb1_backend() is None:
        raise RuntimeError("Bundled libusb could not load; check the x64 runtime dependencies")
    return path


def usb_resources():
    # pyvisa-py 0.8 enumerates every interface before filtering list_resources().
    # Call only its USB INSTR enumerator: blank LAN fields must never broadcast.
    packaged_usb_backend()
    from pyvisa_py.usb import USBInstrSession
    return USBInstrSession.list_resources()


class VisaBackendPool:
    """PyVISA reuses RMs: closing one would otherwise close every device session.

    Leases cover scanner and instrument lifetimes. Only backend administration is
    locked; separate sessions can query concurrently in their owning workers.
    """
    lock = threading.RLock()
    managers = {}

    @classmethod
    def acquire(cls, backend):
        import pyvisa
        backend = python_backend(backend)
        with cls.lock:
            if backend not in cls.managers:
                try:
                    packaged_usb_backend()
                except Exception as exc:
                    # LAN remains usable if USB dependencies are damaged/missing.
                    log.warning("USB backend unavailable: %s", exc)
                cls.managers[backend] = [pyvisa.ResourceManager(backend), 0]
            entry = cls.managers[backend]
            entry[1] += 1
            return entry[0]

    @classmethod
    def release(cls, backend):
        backend = python_backend(backend)
        with cls.lock:
            entry = cls.managers[backend]
            entry[1] -= 1
            if entry[1] == 0:
                try:
                    entry[0].close()
                finally:
                    del cls.managers[backend]


class VisaService:
    def __init__(self, backend="@py", cancelled=None):
        self.backend = python_backend(backend)
        self.rm = None
        self.session = None
        self.owner = threading.get_ident()
        self.cancelled = cancelled

    def _check_owner(self):
        if threading.get_ident() != self.owner:
            raise RuntimeError("VISA session accessed outside owner thread")

    def open(self, config):
        self._check_owner()
        import pyvisa
        try:
            if config.resource.upper().startswith("USB"):
                packaged_usb_backend()
            self.rm = VisaBackendPool.acquire(self.backend)
            with VisaBackendPool.lock:
                self.session = self.rm.open_resource(config.resource, open_timeout=config.timeout_ms)
            self.session.timeout = config.timeout_ms
            self.session.read_termination = config.read_termination
            self.session.write_termination = config.write_termination
            self.session.chunk_size = 64 * 1024
            return self
        except Exception:
            self.close()
            raise

    def query(self, command):
        self._check_owner()
        if self.cancelled and self.cancelled():
            raise InterruptedError("Instrument worker is stopping")
        log.debug("%s QUERY %s", self.session.resource_name, command)
        return self.session.query(command)

    def write(self, command):
        self._check_owner()
        if self.cancelled and self.cancelled():
            raise InterruptedError("Instrument worker is stopping")
        log.info("%s WRITE %s", self.session.resource_name, command)
        return self.session.write(command)

    def read_raw(self):
        self._check_owner()
        # Binary image files can contain LF; never stop on a text terminator.
        previous = self.session.read_termination
        try:
            self.session.read_termination = None
            return self.session.read_raw()
        finally:
            self.session.read_termination = previous

    def close(self):
        self._check_owner()
        try:
            if self.session is not None:
                self.session.close()
        finally:
            self.session = None
            if self.rm is not None:
                try:
                    VisaBackendPool.release(self.backend)
                finally:
                    self.rm = None


def scan_resources(backend="@py"):
    backend = python_backend(backend)
    rm = VisaBackendPool.acquire(backend)
    try:
        with VisaBackendPool.lock:
            return list(usb_resources()), f"pyvisa-py (@py): {rm.visalib}"
    finally:
        VisaBackendPool.release(backend)


def backend_diagnostics():
    """Load packaged libraries without opening instrument sessions or sending SCPI."""
    result = {"backend": "@py", "ni_visa_required": False, "hardware_verified": False}
    rm = VisaBackendPool.acquire("@py")
    try:
        result["library_class"] = type(rm.visalib).__module__ + "." + type(rm.visalib).__name__
        result["tcpip_available"] = False
        from pyvisa import constants
        from pyvisa_py.sessions import Session
        available = dict(Session.iter_valid_session_classes())
        result["tcpip_available"] = all((constants.InterfaceType.tcpip, kind) in available
                                        for kind in ("SOCKET", "INSTR"))
        try:
            result["libusb_library"] = str(packaged_usb_backend())
            result["usb_available"] = (constants.InterfaceType.usb, "INSTR") in available
        except Exception as exc:
            result["usb_available"] = False
            result["usb_error"] = str(exc)
        result["usb_driver_requirement"] = "Device must already have a compatible WinUSB/libusb driver"
        result["passed"] = (result["library_class"].startswith("pyvisa_py.")
                            and result["tcpip_available"] and result["usb_available"])
        return result
    finally:
        VisaBackendPool.release("@py")


class UnexpectedResponse(ValueError):
    pass


def scalar(text: str) -> float:
    text = text.strip()
    # Documented Chroma header-on scalar response; only strip a SCPI header.
    if text.startswith(":"):
        parts = text.split(None, 1)
        if len(parts) != 2:
            raise UnexpectedResponse(f"Missing scalar: {text!r}")
        text = parts[1]
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text):
        raise UnexpectedResponse(f"Invalid numeric response: {text!r}")
    value = float(text)
    if not math.isfinite(value) or abs(value) >= 9e36:
        raise UnexpectedResponse("Overload / invalid numeric response")
    return value


def boolean(text: str) -> OutputState:
    value = text.strip().upper()
    if value in ("ON", "1", "+1", "TRUE"):
        return OutputState.ON
    if value in ("OFF", "0", "+0", "FALSE"):
        return OutputState.OFF
    raise UnexpectedResponse(f"Invalid boolean: {text!r}")


def token(text: str) -> str:
    return text.strip().strip('"').upper()


def power_meter_batch(text: str, labels=("V", "I", "W", "VA", "PF", "FREQ")) -> list[float]:
    text = re.sub(r"^:FETCH\s+", "", text.strip(), flags=re.I)
    parts = re.split(r"[,;]", text)
    if len(parts) != len(labels):
        raise UnexpectedResponse(f"Expected {len(labels)} values; received {len(parts)}")
    result = []
    for part, label in zip(parts, labels):
        part = part.strip()
        if re.match(r"^[A-Za-z]", part):
            match = re.fullmatch(r"([A-Za-z]+)\s+(.+)", part)
            if not match or match[1].upper() != label:
                raise UnexpectedResponse(f"Unexpected batch label {part!r}")
            part = match[2]
        result.append(scalar(part))
    return result


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


MAX_IMAGE_BYTES = 32 * 1024 * 1024


def validate_png(data: bytes) -> bytes:
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Screenshot exceeds 32 MiB")
    if data.startswith(b"#"):
        if len(data) < 2 or not data[1:2].isdigit() or data[1:2] == b"0":
            raise ValueError("Invalid or indefinite IEEE block")
        digits = int(data[1:2])
        if len(data) < 2 + digits or not data[2:2+digits].isdigit():
            raise ValueError("Incomplete binary header")
        length = int(data[2:2+digits])
        end = 2 + digits + length
        if len(data) < end or data[end:] not in (b"", b"\n", b"\r\n"):
            raise ValueError("Truncated binary block or unexpected trailing data")
        data = data[2+digits:end]
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("Expected PNG screenshot")
    offset, has_header, has_data = 8, False, False
    while offset + 12 <= len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset+4:offset+8]
        end = offset + 12 + length
        if end > len(data):
            raise ValueError("Truncated PNG chunk")
        body = data[offset+8:offset+8+length]
        expected = struct.unpack_from(">I", data, offset+8+length)[0]
        if zlib.crc32(kind+body) & 0xffffffff != expected:
            raise ValueError("PNG checksum mismatch")
        if kind == b"IHDR":
            if has_header or offset != 8 or length != 13:
                raise ValueError("Invalid PNG header")
            width, height = struct.unpack_from(">II", body)
            if not 0 < width <= 8192 or not 0 < height <= 8192 or width*height > 20_000_000:
                raise ValueError("Unsupported screenshot dimensions")
            has_header = True
        elif kind == b"IDAT":
            has_data = True
        elif kind == b"IEND":
            if length or not has_header or not has_data or data[end:] not in (b"", b"\n", b"\r\n"):
                raise ValueError("Invalid PNG end")
            return data[:end]
        offset = end
    raise ValueError("Incomplete PNG image")
