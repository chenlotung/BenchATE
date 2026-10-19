# chroma_61512

- Source type: workspace-supplied manufacturer PDF; original download URL unknown, not independently authenticated.
- Original file: `../../../../datasheet/TC_61511_61512_UserManual_202103.pdf` (reuse; no duplicate download).
- Document revision/date: 1.7 / 2021-03 (PDF 3)
- Manufacturer entry point: https://www.chromaate.com/
- Download date: unknown (provided locally); inspected 2026-10-19.
- SHA-256: `0d86017ce4a7dab653ade47253ee13f6c4d85e8668c692b60ff3d46829efb097`
- Hardware verification: NOT performed.

TCP Socket port 2101; PDF 128 / 9-2. LF termination PDF 130. SYST:REM/LOC only RS232 (PDF 133), disabled for Ethernet. IDN may be generic 61500; explicit nameplate confirmation required. PHASE/coupling/selected phase read back before control.

Command/page audit: see ../../SCPI_COMMAND_REFERENCE.md.

V1 output controls require SINGLE phase / FIXED / AC. Three-phase controls are Pending Verification.
