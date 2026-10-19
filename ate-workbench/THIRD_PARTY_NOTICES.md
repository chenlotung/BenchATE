# Third-party dependencies

Package metadata from the tested environment. License texts are retained in the portable ZIP under `licenses/`. Instrument PDFs retain manufacturer copyright; they are documentation, not software dependencies.

| Package | Tested version | License metadata |
|---|---|---|
| PySide6 | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PySide6_Essentials | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PySide6_Addons | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| shiboken6 | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| pyqtgraph | 0.14.0 | MIT |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| PyVISA | 1.16.2 | See bundled license files (full package metadata) |
| PyInstaller | 6.22.3 | GPLv2-or-later with a special exception which allows to use PyInstaller to build and distribute non-free programs (including commercial ones) |

Runtime imports use Qt Core/Gui/Widgets and PyQtGraph; no web server or browser runtime is needed by this application. The Python runtime and Windows runtime DLL notices supplied by packaging tools remain with their dependencies.

The portable ZIP also carries the user-supplied, unmodified National Instruments online installer `installers/ni-visa_26.8_online.exe`. NI-VISA is installed separately through NI Package Manager and remains subject to the NI license terms displayed by its installer. It is not part of the application's Python dependencies. See `docs/NI_VISA_INSTALLATION_zh-TW.md` for the installer identity, checksum, component selection and internet requirements.

Build tool license metadata does not change the license of the project source. See the actual included license texts for redistribution terms.
