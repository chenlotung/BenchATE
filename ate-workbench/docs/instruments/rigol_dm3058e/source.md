# RIGOL DM3058 / DM3058E

- Manufacturer PDF, Nov. 2021, downloaded 2026-10-19.
- Product source: https://www.rigolna.com/products/digital-multimeters/dm3000/dm3058E/
- Official download link: https://beyondmeasure.rigoltech.com/acton/attachment/1579/f-003f/1/-/-/-/-/file.pdf
- Redirect CDN: https://cdn-aorpci9.actonsoftware.com/acton/cdna/1579/f-003f/1/3/Programming%20Guide_DM3058.pdf
- SHA-256: `491ecf0c32aab51216811a332f3b2470890b4f138c15bbb9103592c561150014`
- Local original: Programming_Guide_DM3058.pdf
- PDF explicitly covers both DM3058 and DM3058E (cover, summary).
- Driver uses RIGOL command mode (not Agilent/Fluke emulation). No command-mode changes.
- USB device interface. The original NI-VISA version used VISA/UltraSigma setup; the pyvisa-py branch uses PyUSB/libusb and requires an already compatible Windows USB driver binding. Compatibility is pending hardware verification.
- :FUNC? (PDF 42) and single-display mode-specific :MEAS queries (PDF 58-74). :MEAS? is boolean freshness, NOT a value. :FUNC2:ON? (PDF 51) has no documented return format in this revision; dual display is Pending Verification and not queried.
- Hardware verification: NOT performed.

Command/page audit: see ../../SCPI_COMMAND_REFERENCE.md.
