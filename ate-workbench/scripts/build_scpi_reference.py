"""Rebuild the human-readable audit table from reviewed, model-specific manual evidence.

No network access and no instrument commands are executed by this script.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROWS = []
SOURCES = {
    "AC": ("Chroma", "61512", "../../datasheet/TC_61511_61512_UserManual_202103.pdf"),
    "PM": ("Chroma", "66205", "../../datasheet/TC_66205_UserManual_202504.pdf"),
    "MF": ("Chroma", "6312A / 63106A", "../../datasheet/TC_6310A_OperationProgrammingManual_202205.pdf"),
    "DC": ("Chroma", "63210A-150-1000 / 63210A-600-700 / 63210A-1200-400", "../../datasheet/TC_63200A_OperationProgrammingManual_202503.pdf"),
    "DMM": ("RIGOL", "DM3058E", "instruments/rigol_dm3058e/Programming_Guide_DM3058.pdf"),
    "SCOPE": ("Tektronix", "MSO44B", "../../datasheet/4-5-6-Series-MSO_Programmer_077189805.pdf"),
}


def add(source, function, command, parameters, response, page, tested=True, status=None):
    vendor, model, path = SOURCES[source]
    ROWS.append(dict(manufacturer=vendor, model=model, function=function, command=command,
        parameters=parameters, response=response, source=path, page=page,
        verification=status or ("Unit Tested (mock)" if tested else "Implemented"), hardware_verified=False))


for source, page in (("AC", "132 / 9-6"), ("PM", "103-104 / 14-7..8"), ("MF", "110-111 / 7-2..3"),
                     ("DC", "110 / 4-6"), ("DMM", "16 / 2-5"), ("SCOPE", "664")):
    add(source, "Identify", "*IDN?", "none", "Manufacturer/model/serial/firmware string; MF legacy format CHROMA 6312A,0,...", page)

for function, command, response, page in (
    ("Phase configuration", "INSTrument:PHASe?", "SINGLE or THREE", "135 / 9-9"),
    ("Selected phase", "INSTrument:NSELect?", "1, 2 or 3", "134 / 9-8"),
    ("Operating mode", "OUTPut:MODE?", "FIXED, LIST, PULSE, STEP, SYNTH or INTERHAR", "140 / 9-14"),
    ("Coupling", "OUTPut:COUPling?", "AC, DC or ACDC", "140 / 9-14"),
    ("AC voltage range", "VOLTage:RANGe?", "LOW, HIGH or AUTO", "143 / 9-17"),
    ("Instrument voltage limit", "VOLTage:LIMit:AC?", "NR2 V", "143 / 9-17"),
    ("Instrument frequency limit", "FREQuency:LIMit?", "NR2 Hz", "142 / 9-16"),
    ("Voltage setpoint readback", "VOLTage:AC?", "NR2 V", "142 / 9-16"),
    ("Frequency setpoint readback", "FREQuency?", "NR2 Hz", "142 / 9-16"),
    ("Output state readback", "OUTPut?", "ON or OFF", "139 / 9-13"),
    ("Command error", "SYSTem:ERRor?", "No Error / Data Format Error / Data Range Error / Too Many Errors / Execution Error", "133 / 9-7")):
    add("AC", function, command, "none", response, page, tested=function not in ("Selected phase",))
add("AC", "Select/restore monitored phase", "INSTrument:NSELect {phase}", "1..3; selection only, never changes phase configuration", "no response", "134 / 9-8", tested=False)
add("AC", "Set AC voltage", "VOLTage:AC {value}", "LOW 0..150 V; HIGH/AUTO 0..300 V; 0.1 V; approved software limit also required", "read back with VOLTage:AC?", "18 / 1-2; 142 / 9-16")
add("AC", "Set frequency", "FREQuency {value}", "15..1500 Hz; 0.01 Hz command precision; approved software limit", "read back with FREQuency?", "142 / 9-16")
for value in ("ON", "OFF"):
    add("AC", "Output control", f"OUTPut {value}", "ON requires confirmed safe readbacks, SINGLE phase/FIXED/AC; OFF never resets settings", "OUTPut? verifies outcome", "139 / 9-13")
for name, command, unit, page in (("Voltage RMS", "FETCh:VOLTage:AC?", "V", "138 / 9-12"),
    ("Current RMS", "FETCh:CURRent:AC?", "A", "136 / 9-10"),
    ("Active power", "FETCh:POWer:AC?", "W", "137 / 9-11"),
    ("Frequency", "FETCh:FREQuency?", "Hz", "136-137 / 9-10..11")):
    add("AC", name, command, "none; cached fetch does not trigger a new acquisition", f"NR2 {unit}", page, tested=False)
add("AC", "Remote/local over Ethernet", "SYSTem:REMote / SYSTem:LOCal", "Manual limits these commands to RS232; not sent over LAN", "No LAN remote status query established", "133 / 9-7", status="Unsupported (LAN); Pending Verification")

add("PM", "Six measurements, one fetch", "FETCh? V,I,W,VA,PF,FREQ", "V/I/W/VA/PF/FREQ tokens; up to 18 selected items", "6 NR2 values in requested order; comma or semicolon; optional :FETCH and item headers", "110-111 / 14-14..15")
add("PM", "Configured calculation period", "MEASure:UPDate?", "none", "NR2 seconds: 0.05,0.1,0.25,0.5,1,2,5,10", "121 / 14-25")
add("PM", "Averaging count", "MEASure:AVERage?", "none; no averaging changes", "NR1: 1,4,8,16,32,64", "121 / 14-25")
add("PM", "Measurement mode", "MEASure:MODE?", "none; mode left unchanged", "RMS, DC or VMEAN", "121 / 14-25")
for command in ("SYSTem:REMote", "SYSTem:LOCal"):
    add("PM", "Request remote/local", command, "USB only", "no response; actual state Unknown because no status query documented", "107-108 / 14-11..12", tested=False)

add("MF", "Module inventory", "*RDT?", "none; queried during connect", "Comma-separated module types; 0 = absent; configured slots must identify 63106A", "111 / 7-3")
add("MF", "Read current channel", "CHANnel?", "none", "NR1; mainframe 6312A addresses 1..4", "114 / 7-6")
add("MF", "Select/restore channel", "CHANnel {channel}", "Only configured 63106A at CH1 (slot 1) / CH3 (slot 2)", "no response", "44 / 2-4; 114 / 7-6")
add("MF", "Verify selected module", "CHANnel:ID?", "none", "CHROMA,63106A,0,firmware,PCB", "114-115 / 7-6..7")
add("MF", "Remote/local over USB", "CONFigure:REMote {ON|OFF}", "Manual limits command to RS232; never sent on USB", "No documented USB state query", "120 / 7-12", status="Unsupported (USB); Pending Verification")

for source, mode_page, load_page, current_page, measure_pages in (
    ("MF", "138 / 7-30", "132-133 / 7-24..25", "128 / 7-20", ("135 / 7-27", "136 / 7-28", "136 / 7-28")),
    ("DC", "112 / 4-8", "112 / 4-8", "123-124 / 4-19..20", ("164 / 4-60", "164 / 4-60", "164 / 4-60"))):
    modes = "CCL or CCH" if source == "MF" else "CCL, CCM or CCH"
    add(source, "Read operating mode", "MODE?", "none", "CRD operating mode; only static CC modes accepted for ON", mode_page)
    add(source, "Select static CC range", "MODE {mode}", modes + "; mode changes require load OFF", "MODE? verifies selection", mode_page, tested=False)
    add(source, "Actual load state", "LOAD?", "none", "MF: NR1 0/1; DC: CRD OFF/ON", load_page, tested=source == "DC")
    for value in ("ON", "OFF"):
        add(source, "Load control", f"LOAD {value}", "ON requires approval/explicit confirmation; L1=L2 and safe actual readbacks", "LOAD? verifies outcome", load_page, tested=False)
    for level in (1, 2):
        add(source, "CC current setpoint", f"CURRent:STATic:L{level} {{value}}", "A; V1 deliberately sets BOTH static L1 and L2 to same approved current", f"CURRent:STATic:L{level}? verifies setting", current_page, tested=source == "DC")
        add(source, "Static level readback", f"CURRent:STATic:L{level}?", "none", "NR2 A", current_page, tested=source == "DC")
    for limit in ("MIN", "MAX"):
        add(source, "Active range limit", f"CURRent:STATic:L1? {limit}", "Query only, not a set-to-MIN/MAX command", "NR2 A for active range", current_page, tested=source == "DC")
    for name, command, unit, page in zip(("Voltage", "Current", "Power"),
        ("MEASure:VOLTage?", "MEASure:CURRent?", "MEASure:POWer?"), ("V", "A", "W"), measure_pages):
        add(source, name, command, "none; selected channel only on MF", f"NR2 {unit}", page, tested=False)
add("DC", "Command error", "SYSTem:ERRor?", "none", '0,"No Error" or nonzero error', "173 / 4-69")
for command in ("SYSTem:REMote", "SYSTem:LOCal"):
    add("DC", "Request remote/local", command, "no parameters; does not change output settings", "no status query; display Unknown after request", "173 / 4-69", tested=False)

add("DMM", "Current primary function", ":FUNCtion?", "RIGOL command set; no mode changes", "DCV, ACV, DCI, ACI, RESISTANCE/2WR, FRESISTANCE/4WR, FREQUENCY/FREQ, PERIOD/PERI, CAPACITANCE/CAP, DIODE", "42 / 3-15")
for function, command, unit, page, tested in (
    ("DCV", ":MEASure:VOLTage:DC?", "V", "58-59 / 3-31..32", False),
    ("ACV", ":MEASure:VOLTage:AC?", "V", "61 / 3-34", True),
    ("DCI", ":MEASure:CURRent:DC?", "A", "63 / 3-36", True),
    ("ACI", ":MEASure:CURRent:AC?", "A", "65 / 3-38", False),
    ("2-wire resistance", ":MEASure:RESistance?", "ohm", "67 / 3-40", True),
    ("4-wire resistance", ":MEASure:FRESistance?", "ohm", "68 / 3-41", False),
    ("Frequency", ":MEASure:FREQuency?", "Hz", "69 / 3-42", False),
    ("Period", ":MEASure:PERiod?", "s", "71 / 3-44", False),
    ("Diode", ":MEASure:DIODe?", "V", "73 / 3-46", False),
    ("Capacitance", ":MEASure:CAPacitance?", "F", "73-74 / 3-46..47", False)):
    add("DMM", function, command, "Issue only if current :FUNC? matches; single display required", f"Scientific-notation scalar, {unit}", page, tested=tested)
add("DMM", "Dual display status", ":FUNCtion2:ON?", "No return format specified in this manual revision; not issued", "Unconfirmed", "51 / 3-24", status="Pending Verification")
add("DMM", "Freshness boolean (not issued)", ":MEASure?", "Does NOT return the measured scalar", "TRUE or FALSE", "58 / 3-31", status="Documented; not used")

add("SCOPE", "Save displayed screen", 'SAVe:IMAGe "{unique_name}.png"', "Unique ate_capture_UUID filename in current scope directory; no CWD/trigger/run changes", "no query form; writes PNG on instrument", "1171")
add("SCOPE", "Wait for save", "*OPC?", "Bounded by configured timeout; may also wait for existing pending acquisition", "ASCII 1 when pending OPC operations complete", "963; 1766")
add("SCOPE", "Transfer screenshot file", 'FILESystem:READFile "{unique_name}.png"', "Only the file just created by this capture", "File binary bytes; PNG signature/chunk CRC/IEND validated; optional definite block framing accepted", "625")
add("SCOPE", "Remove own temporary image", 'FILESystem:DELEte "{unique_name}.png"', "Only after successful full transfer; never delete arbitrary user files", "no response", "622")


def main():
    out = ROOT/"docs/SCPI_COMMAND_REFERENCE.md"
    lines = ["# SCPI Command Reference", "", "Reviewed 2026-10-19. PDF page numbers are 1-based; Chroma/RIGOL printed chapter pages are also listed.", "",
        "Short forms in code are the uppercase portions of the complete documented command forms below.",
        "Hardware Verified: **none**. Unit Tested means a mock session/parser test, never physical compatibility.", "",
        "Verification stages: Documented → Implemented → Unit Tested → Hardware Verified. Unsupported and Pending Verification remain unavailable.", "",
        "The application never issues reset/clear/trigger/mode changes on connection. VISA timeout quarantines the session and cancels queued controls; no automatic retries.", "",
        "| Manufacturer | Model | Function | SCPI Command | Parameters | Response | Source | Page | Verification |", "|---|---|---|---|---|---|---|---|---|"]
    for row in ROWS:
        source = f"[{Path(row['source']).name}]({row['source']})"
        cells = [row[k] for k in ("manufacturer", "model", "function", "command", "parameters", "response")]
        cells += [source, row["page"], row["verification"]]
        lines.append("| " + " | ".join(str(cell).replace("|", "/").replace("\n", " ") for cell in cells) + " |")
    lines += ["", "## Operational constraints", "",
        "- 61512: SINGLE-phase/FIXED/AC only for Apply/ON. Three-phase readout can select/restore configured phases; phase configuration is never changed. Voltage/range/limit read back before control. Generic 61500 IDN requires physical nameplate confirmation.",
        "- 6312A: USB interface belongs to the mainframe. Configured 63106A at CH1/CH3 verified via inventory and module ID. Restore previous selection after healthy transactions; after transport failure quarantine without more writes.",
        "- DC loads: both L1/L2 are deliberately set/read back to avoid guessing which static A/B level is active. Mode change while load ON is refused. Range/resolution and runtime MIN/MAX checks are independent of approved software safety limits.",
        "- 66205: configured update period and averaging are queried only. FETCh returns cached data. No sample identifier means actual new hardware sample rate remains unverified. Manual sentinel values -1/-2/-3 are marked invalid conservatively, including ambiguous negative power/PF values.",
        "- DM3058E: RIGOL command set and single-display mode. Unknown/continuity/sensor/dual-display modes are pending validation; no function or trigger changes are made to enable monitoring.",
        "- MSO44B: use an already-enabled VXI-11 server, firmware compatible with the supplied manual. OPC may timeout on a pending acquisition; no acquisition commands are sent to avoid that. Temporary files may remain after failed transfers, with UUID prefix for manual cleanup.",
        "- No unverified remote-state query is invented. A remote/local request without documented readback remains Unknown; disabled interface-specific commands are never substituted.", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    (ROOT/"docs/scpi_catalog.json").write_text(json.dumps(ROWS, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(ROWS)} model-specific command records")


if __name__ == "__main__":
    main()
