import pytest
from app.models import DeviceConfig
from app.drivers.mock import demo_png
from app.drivers.measurement import TekMSO44B
from app.protocol import validate_png
from conftest import FakeVISA


@pytest.mark.parametrize("framed", [False, True])
def test_complete_png_and_ieee_block(framed):
    png = demo_png()
    length = str(len(png)).encode()
    data = b"#"+str(len(length)).encode()+length+png+b"\n" if framed else png
    assert validate_png(data) == png


@pytest.mark.parametrize("mutation", [lambda b: b[:-4], lambda b: b[:40]+b"BAD"+b[43:],
    lambda b: b"#999"+b, lambda b: b"#0"+b, lambda b: b"not a png"])
def test_truncated_or_corrupt_screenshot_rejected(mutation):
    with pytest.raises(ValueError):
        validate_png(mutation(demo_png()))


def test_scope_capture_never_changes_trigger_or_acquisition():
    cfg = DeviceConfig("Scope", "tek_mso44b", "MSO44B", "TCPIP0::192.0.2.2::inst0::INSTR")
    io = FakeVISA({"*IDN?": "TEKTRONIX,MSO44B,SN,1", "*OPC?": "1"})
    io.raw = demo_png()
    driver = TekMSO44B(cfg, lambda: io)
    driver.connect()
    assert driver.capture_screenshot() == io.raw
    writes = [text for kind, text in io.events if kind == "write"]
    assert len(writes) == 3
    name = writes[0].split('"')[1]
    assert writes == [f'SAVE:IMAGE "{name}"', f'FILESYSTEM:READFILE "{name}"', f'FILESYSTEM:DELETE "{name}"']
    assert name.startswith("ate_capture_") and name.endswith(".png")
