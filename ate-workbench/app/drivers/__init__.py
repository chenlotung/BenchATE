"""Supported drivers and explicit Real/Demo driver construction."""

from app.drivers.power import Chroma61512, Chroma6312A, Chroma63210A
from app.drivers.measurement import Chroma66205, RigolDM3058E, TekMSO44B

DRIVERS = {
    "chroma_61512": (Chroma61512, "Chroma", ("61512",), "Ethernet"),
    "chroma_66205": (Chroma66205, "Chroma", ("66205",), "USB"),
    "rigol_dm3058e": (RigolDM3058E, "RIGOL", ("DM3058E",), "USB"),
    "chroma_6312a": (Chroma6312A, "Chroma", ("6312A",), "USB"),
    "chroma_63210a": (Chroma63210A, "Chroma", tuple(Chroma63210A.ranges), "USB"),
    "tek_mso44b": (TekMSO44B, "Tektronix", ("MSO44B",), "Ethernet"),
}


def capabilities_for(config):
    cls = DRIVERS[config.driver][0]
    return cls(config, lambda: None).get_capabilities()


def create_driver(config, *, demo=False, backend="@py", transport_factory=None, cancelled=None):
    if demo:
        from app.drivers.mock import DemoInstrument
        return DemoInstrument(config)
    from app.protocol import VisaService
    return DRIVERS[config.driver][0](config, transport_factory or (lambda: VisaService(backend, cancelled)))
