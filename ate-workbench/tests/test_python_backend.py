"""Exercise the real Python transport and packaged DLL, without lab equipment."""
from dataclasses import replace
from pathlib import Path
import socketserver
import threading

import pytest
import pyvisa

from app.drivers.mock import demo_configs
from app.protocol import (VisaService, VisaBackendPool, backend_diagnostics,
                          python_backend, scan_resources)


@pytest.mark.parametrize("setting", [None, "", "@py"])
def test_legacy_empty_backend_always_selects_python(setting):
    assert python_backend(setting) == "@py"


@pytest.mark.parametrize("setting", ["@ivi", "C:/Windows/System32/visa32.dll"])
def test_native_backend_is_rejected(setting):
    with pytest.raises(ValueError, match="pyvisa-py"):
        VisaService(setting)


def test_packaged_backend_registers_usb_and_lan_without_native_visa(monkeypatch):
    original = pyvisa.highlevel.get_wrapper_class
    def python_only(name):
        assert name == "py", "Native VISA must never be loaded"
        return original(name)
    monkeypatch.setattr(pyvisa.highlevel, "get_wrapper_class", python_only)
    monkeypatch.setenv("PYVISA_LIBRARY", "deliberately-missing.dll@ivi")
    result = backend_diagnostics()
    assert result["passed"] and result["library_class"].startswith("pyvisa_py.")
    assert result["usb_available"] and result["tcpip_available"]
    assert Path(result["libusb_library"]).is_file()
    assert not result["ni_visa_required"] and not VisaBackendPool.managers


def test_real_tcp_queries_fragmented_reply_and_timeout_without_usb(monkeypatch):
    received = []
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            while line := self.rfile.readline():
                received.append(line)
                if line == b"*IDN?\n":
                    self.request.sendall(b"Chroma,615")
                    self.request.sendall(b"12,LOOPBACK,1\n")
                # TIMEOUT? deliberately receives no response.
    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        config = replace(demo_configs()[0],
            resource=f"TCPIP0::127.0.0.1::{server.server_address[1]}::SOCKET", timeout_ms=200)
        def missing_usb():
            raise RuntimeError("USB dependency deliberately unavailable")
        monkeypatch.setattr("app.protocol.packaged_usb_backend", missing_usb)
        service = VisaService("")
        try:
            service.open(config)
            assert type(service.rm.visalib).__module__.startswith("pyvisa_py.")
            assert service.query("*IDN?") == "Chroma,61512,LOOPBACK,1"
            with pytest.raises(pyvisa.errors.VisaIOError) as exc:
                service.query("TIMEOUT?")
            assert exc.value.error_code == pyvisa.constants.StatusCode.error_timeout
        finally:
            service.close()
            server.shutdown()
            thread.join(timeout=3)
    assert received == [b"*IDN?\n", b"TIMEOUT?\n"]
    assert not VisaBackendPool.managers


def test_usb_scan_error_releases_shared_manager(monkeypatch):
    def unavailable():
        raise RuntimeError("Compatible USB driver missing")
    monkeypatch.setattr("app.protocol.usb_resources", unavailable)
    with pytest.raises(RuntimeError, match="driver missing"):
        scan_resources()
    assert not VisaBackendPool.managers


def test_vxi11_binary_transfer_uses_eom_and_preserves_embedded_newlines(monkeypatch):
    from pyvisa_py.protocols import vxi11
    payload = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 16
    events = []
    class Core:
        def __init__(self, host, port, timeout):
            assert host == "192.0.2.44"
            self.remaining = payload
        def create_link(self, *_args):
            return 0, 123, 0, 256
        def device_write(self, link, timeout, lock_timeout, flags, data):
            events.append(("write", data))
            return 0, len(data)
        def device_read(self, link, count, timeout, lock_timeout, flags, term_char):
            assert not flags & vxi11.OP_FLAG_TERMCHAR_SET
            chunk, self.remaining = self.remaining[:count], self.remaining[count:]
            return 0, (0 if self.remaining else vxi11.RX_END), chunk
        def destroy_link(self, link):
            events.append(("destroy", link))
        def close(self):
            events.append(("close",))
    monkeypatch.setattr("pyvisa_py.tcpip.Vxi11CoreClient", Core)
    config = replace(demo_configs()[-1], resource="TCPIP0::192.0.2.44::inst0::INSTR")
    service = VisaService()
    try:
        service.open(config)
        service.write('FILESYSTEM:READFILE "test.png"')
        assert service.read_raw() == payload
        assert service.session.read_termination == "\n"
    finally:
        service.close()
    assert events[0] == ("write", b'FILESYSTEM:READFILE "test.png"\n')
    assert events[-2:] == [("destroy", 123), ("close",)]
    assert not VisaBackendPool.managers
