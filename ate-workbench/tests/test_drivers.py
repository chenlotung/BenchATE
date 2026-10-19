from dataclasses import replace
import pytest

from app.models import DeviceConfig, OutputState, Parameter
from app.drivers.mock import demo_configs
from app.drivers import create_driver, capabilities_for
from app.drivers.base import SafetyError, UnsupportedInstrument
from app.drivers.power import Chroma61512
from app.drivers.power import Chroma6312A
from app.drivers.power import Chroma63210A
from app.drivers.measurement import Chroma66205
from app.drivers.measurement import RigolDM3058E
from app.protocol import UnexpectedResponse
from conftest import FakeVISA


@pytest.mark.parametrize("config", demo_configs(), ids=lambda c: c.driver)
def test_capabilities_and_connect_never_enable_output(config):
    driver = create_driver(config, demo=True)
    driver.connect()
    assert driver.get_capabilities() == driver.capabilities
    assert all(value == OutputState.OFF for value in driver.outputs.values())
    driver.disconnect()
    driver.connect()
    assert all(value == OutputState.OFF for value in driver.outputs.values())


def ac_driver():
    config = DeviceConfig("AC", "chroma_61512", "61512", "TCPIP0::192.0.2.1::2101::SOCKET")
    replies = {"*IDN?": "Chroma ATE,61512,SN,1.00", "INST:PHAS?": "SINGLE", "OUTP:MODE?": "FIXED",
        "OUTP:COUP?": "AC", "OUTP?": "OFF", "VOLT:RANG?": "LOW", "VOLT:LIM:AC?": "150",
        "FREQ:LIM?": "1500", "VOLT:AC?": "30", "FREQ?": "50", "SYST:ERR?": "No Error"}
    io = FakeVISA(replies)
    driver = Chroma61512(config, lambda: io)
    driver.connect()
    return driver, io


def test_real_connect_is_identity_only_and_closes_mismatch():
    driver, io = ac_driver()
    assert io.events == [("open", driver.config.resource), ("query", "*IDN?")]
    driver.disconnect()
    assert io.closed
    io = FakeVISA({"*IDN?": "RIGOL,DM3058E,SN,1"})
    with pytest.raises(UnsupportedInstrument):
        Chroma61512(driver.config, lambda: io).connect()
    assert io.closed


def test_generic_61500_requires_explicit_nameplate_confirmation():
    driver, _ = ac_driver()
    with pytest.raises(UnsupportedInstrument):
        driver.validate_identity("Chroma ATE,61500,SN,1")
    driver.config.model_confirmed = True
    driver.validate_identity("Chroma ATE,61500,SN,1")


def test_apply_reads_back_and_does_not_enable_output():
    driver, io = ac_driver()
    with pytest.raises(SafetyError):
        driver.apply_settings({"voltage": 30, "frequency": 50})
    driver.approve_limits({"voltage": [0, 50], "frequency": [45, 65]})
    actual = driver.apply_settings({"voltage": 30, "frequency": 50})
    assert actual == {"voltage": 30, "frequency": 50}
    assert [text for kind, text in io.events if kind == "write"] == ["VOLT:AC 30.0", "FREQ 50.00"]


def test_readback_mismatch_does_not_report_success():
    driver, io = ac_driver()
    driver.approve_limits({"voltage": [0, 50], "frequency": [45, 65]})
    io.responses["VOLT:AC?"] = "20"
    with pytest.raises(UnexpectedResponse):
        driver.apply_settings({"voltage": 30, "frequency": 50})


def test_software_range_and_live_changes_block_before_writes():
    driver, io = ac_driver()
    driver.approve_limits({"voltage": [0, 30], "frequency": [45, 65]})
    with pytest.raises((SafetyError, ValueError)):
        driver.apply_settings({"voltage": 40, "frequency": 50})
    assert not any(kind == "write" for kind, _ in io.events)
    io.responses["OUTP?"] = "ON"
    with pytest.raises(SafetyError):
        driver.apply_settings({"voltage": 30, "frequency": 50})
    assert not any(kind == "write" for kind, _ in io.events)


def test_output_requires_safe_readback_and_actual_state():
    driver, io = ac_driver()
    driver.approve_limits({"voltage": [0, 50], "frequency": [45, 65]})
    with pytest.raises(UnexpectedResponse):
        driver.output_on()  # fake instrument remains OFF
    assert ("write", "OUTP ON") in io.events
    assert driver.output_off() == OutputState.OFF


def test_three_phase_coupling_blocks_unintended_cross_channel_writes():
    driver, io = ac_driver()
    driver.approve_limits({"voltage": [0, 50], "frequency": [45, 65]})
    io.responses.update({"INST:PHAS?": "THREE", "INST:COUP?": "ALL", "INST:EDIT?": "ALL"})
    with pytest.raises(SafetyError):
        driver.apply_settings({"voltage": 30, "frequency": 50})
    assert not any(kind == "write" for kind, _ in io.events)


def test_6312_inventory_and_selected_channel_restored_even_on_error():
    cfg = DeviceConfig("Load", "chroma_6312a", "6312A", "USB0::1::2::SN::INSTR", channels=["CH1", "CH3"])
    io = FakeVISA({"*IDN?": "CHROMA 6312A,0,1.00,0", "*RDT?": "63106A,0,63106A,0",
                   "CHAN?": "1", "CHAN:ID?": "CHROMA,63106A,0,1,0"})
    driver = Chroma6312A(cfg, lambda: io)
    driver.connect()
    assert not any(kind == "write" for kind, _ in io.events)
    with pytest.raises(RuntimeError):
        with driver.selected("CH3"):
            raise RuntimeError("Simulated transaction error")
    assert [cmd for kind, cmd in io.events if kind == "write"] == ["CHAN 3", "CHAN 1"]
    io.responses["CHAN:ID?"] = "CHROMA,63102A,0,1,0"
    with pytest.raises(UnsupportedInstrument):
        with driver.selected("CH3"):
            pass
    assert io.events[-1] == ("write", "CHAN 1")


@pytest.mark.parametrize("model,mode,maximum,resolution", [
    ("63210A-150-1000", "CCL", 100, .001), ("63210A-600-700", "CCM", 350, .0025),
    ("63210A-1200-400", "CCH", 400, .004)])
def test_variant_current_ranges_from_manual(model, mode, maximum, resolution):
    cfg = DeviceConfig("Load", "chroma_63210a", model, "USB0::1::2::SN::INSTR")
    driver = Chroma63210A(cfg, lambda: None)
    assert driver.current_parameter(mode).maximum == maximum
    assert driver.current_parameter(mode).resolution == resolution
    with pytest.raises(UnsupportedInstrument):
        driver.validate_identity("Chroma,63210A,SN,1")


def test_63210_apply_both_levels_and_require_readback():
    cfg = DeviceConfig("Load", "chroma_63210a", "63210A-150-1000", "USB0::1::2::SN::INSTR")
    io = FakeVISA({"*IDN?": "Chroma,63210A-150-1000,SN,1", "MODE?": "CCL", "LOAD?": "OFF",
        "CURR:STAT:L1?": ".5", "CURR:STAT:L2?": ".5", "CURR:STAT:L1? MAX": "100",
        "CURR:STAT:L1? MIN": "0", "SYST:ERR?": '0,"No Error"'})
    driver = Chroma63210A(cfg, lambda: io)
    driver.connect()
    driver.approve_limits({"current": [0, 1]})
    assert driver.apply_settings({"current": .5}, "CCL") == {"current": .5, "current_l2": .5}
    writes = [cmd for kind, cmd in io.events if kind == "write"]
    assert writes == ["CURR:STAT:L1 0.500000", "CURR:STAT:L2 0.500000"]
    io.responses["CURR:STAT:L2?"] = "2"
    with pytest.raises(SafetyError):
        driver.output_on()
    assert ("write", "LOAD ON") not in io.events


def test_power_meter_invalid_sentinel_and_cached_freshness():
    cfg = DeviceConfig("Meter", "chroma_66205", "66205", "USB0::1::2::SN::INSTR")
    io = FakeVISA({"*IDN?": "Chroma ATE,66205,SN,1", "MEAS:UPD?": "2", "MEAS:AVER?": "16",
        "MEAS:MODE?": "RMS", "FETC? V,I,W,VA,PF,FREQ": "230,1,-3,240,.95,50"})
    driver = Chroma66205(cfg, lambda: io)
    driver.connect()
    frame = driver.read_measurements()[0]
    assert frame.measurements["power"].value is None
    assert frame.status == "invalid" and frame.update_period == 2
    assert "Cached" in frame.freshness
    assert not any(kind == "write" for kind, _ in io.events)


@pytest.mark.parametrize("mode,query,name,unit", [
    ("DCI", ":MEAS:CURR:DC?", "current", "A"), ("ACV", ":MEAS:VOLT:AC?", "voltage", "V"),
    ("RESISTANCE", ":MEAS:RES?", "resistance", "Ω")])
def test_dmm_uses_actual_function_and_units(mode, query, name, unit):
    cfg = DeviceConfig("DMM", "rigol_dm3058e", "DM3058E", "USB0::1::2::SN::INSTR")
    io = FakeVISA({"*IDN?": "RIGOL,DM3058E,SN,1", ":FUNC?": mode, query: "1.234e-2"})
    driver = RigolDM3058E(cfg, lambda: io)
    driver.connect()
    frame = driver.read_measurements()[0]
    assert frame.measurements[name].unit == unit
    assert frame.measurements[name].value == .01234
    assert not any(kind == "write" for kind, _ in io.events)


def test_nonfinite_limits_and_unapproved_reconnect():
    driver = create_driver(demo_configs()[0], demo=True)
    driver.connect()
    with pytest.raises(SafetyError):
        driver.approve_limits({"voltage": [0, float("nan")], "frequency": [45, 65]})
    driver.approve_limits({"voltage": [0, 30], "frequency": [45, 65]})
    driver.disconnect()
    driver.connect()
    assert not driver.limits_approved


def test_resolution_cannot_silently_round():
    with pytest.raises(ValueError):
        Parameter(0, 12, .003, "A", 3).validate(.5)


def test_real_ac_monitor_uses_fetch_and_preserves_configuration():
    driver, io = ac_driver()
    io.responses.update({"FETC:VOLT:AC?": "30", "FETC:CURR:AC?": ".25",
                         "FETC:POW:AC?": "7.5", "FETC:FREQ?": "50"})
    frame = driver.read_measurements()[0]
    assert frame.measurements["power"].value == 7.5
    assert frame.measurements["current"].unit == "A"
    assert frame.output == OutputState.OFF
    assert not any(kind == "write" for kind, _ in io.events)


def test_mainframe_monitor_keeps_channel_measurements_separate():
    cfg = DeviceConfig("Load", "chroma_6312a", "6312A", "USB0::1::2::SN::INSTR", channels=["CH1", "CH3"])
    current = [1]
    io = FakeVISA({"*IDN?": "CHROMA 6312A,0,1.00,0", "*RDT?": "63106A,0,63106A,0",
        "CHAN?": lambda: str(current[0]), "CHAN:ID?": "CHROMA,63106A,0,1,0", "MODE?": "CCL",
        "LOAD?": "0", "CURR:STAT:L1?": "0", "CURR:STAT:L2?": "0", "MEAS:VOLT?": lambda: str(10*current[0]),
        "MEAS:CURR?": lambda: str(current[0]), "MEAS:POW?": lambda: str(10*current[0]**2)})
    original_write = io.write
    def write(command):
        original_write(command)
        if command.startswith("CHAN "):
            current[0] = int(command.split()[1])
    io.write = write
    driver = Chroma6312A(cfg, lambda: io)
    driver.connect()
    frames = driver.read_measurements()
    assert [f.channel for f in frames] == ["CH1", "CH3"]
    assert [f.measurements["voltage"].value for f in frames] == [10, 30]
    assert current[0] == 1
    assert all(command.startswith("CHAN ") for kind, command in io.events if kind == "write")


def test_unknown_dmm_function_never_infers_voltage_unit():
    cfg = DeviceConfig("DMM", "rigol_dm3058e", "DM3058E", "USB0::1::2::SN::INSTR")
    io = FakeVISA({"*IDN?": "RIGOL,DM3058E,SN,1", ":FUNC?": "SENSOR"})
    driver = RigolDM3058E(cfg, lambda: io)
    driver.connect()
    with pytest.raises(UnsupportedInstrument):
        driver.read_measurements()


def test_mainframe_timeout_does_not_send_restoration_commands():
    cfg = DeviceConfig("Load", "chroma_6312a", "6312A", "USB0::1::2::SN::INSTR", channels=["CH3"])
    io = FakeVISA({"*IDN?": "CHROMA 6312A,0,1.00,0", "*RDT?": "0,0,63106A,0", "CHAN?": "1", "CHAN:ID?": "CHROMA,63106A,0,1,0"})
    driver = Chroma6312A(cfg, lambda: io)
    driver.connect()
    with pytest.raises(TimeoutError):
        with driver.selected("CH3"):
            raise TimeoutError("Late response may still arrive")
    assert [command for kind, command in io.events if kind == "write"] == ["CHAN 3"]
