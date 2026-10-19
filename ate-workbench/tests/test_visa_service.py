from types import SimpleNamespace
import threading
import pytest

from app.protocol import VisaService, VisaBackendPool, scan_resources
from app.drivers.mock import demo_configs


def test_shared_visa_manager_scan_and_disconnect_do_not_close_other_devices(monkeypatch):
    class Session:
        resource_name = "FAKE"
        closed = False
        def close(self):
            self.closed = True
        def query(self, command):
            assert not self.closed
            return "reply"
    class Manager:
        visalib = "Fake native VISA backend"
        closed = False
        def open_resource(self, *_args, **_kwargs):
            return Session()
        def list_resources(self, query):
            assert query == "?*"
            return ("USB0::1::2::SN::INSTR",)
        def close(self):
            self.closed = True
    backend = Manager()
    calls = []
    def resource_manager(name):
        calls.append(name)
        return backend
    monkeypatch.setattr("pyvisa.ResourceManager", resource_manager)
    first, second = VisaService("test"), VisaService("test")
    first.open(demo_configs()[0])
    second.open(demo_configs()[1])
    resources, _ = scan_resources("test")
    assert len(resources) == 1 and not backend.closed
    first.close()
    assert not backend.closed and second.query("read") == "reply"
    second.close()
    assert backend.closed and len(calls) == 1
    assert "test" not in VisaBackendPool.managers


def test_transport_enforces_session_thread_ownership():
    service = VisaService()
    errors = []
    def other_thread():
        try:
            service.query("*IDN?")
        except Exception as exc:
            errors.append(exc)
    thread = threading.Thread(target=other_thread)
    thread.start()
    thread.join()
    assert isinstance(errors[0], RuntimeError)


def test_binary_read_disables_text_termination_and_restores_it():
    service = VisaService()
    class Session:
        read_termination = "\n"
        def read_raw(self):
            assert self.read_termination is None
            return b"\x89PNG\r\n\x1a\n"
    service.session = Session()
    assert service.read_raw().startswith(b"\x89PNG")
    assert service.session.read_termination == "\n"


def test_cancelled_worker_stops_before_the_next_scpi_command():
    service = VisaService(cancelled=lambda: True)
    with pytest.raises(InterruptedError):
        service.query("*IDN?")
    with pytest.raises(InterruptedError):
        service.write("OUTP ON")
