# Third-party dependencies

This distribution contains the following third-party software. Their license texts are retained under `licenses/` and with the corresponding runtime files.

| Package | Tested version | License metadata |
|---|---|---|
| PySide6 | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PySide6_Essentials | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PySide6_Addons | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| shiboken6 | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| pyqtgraph | 0.14.0 | MIT |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| PyVISA | 1.16.2 | See bundled license files (full package metadata) |
| pyvisa-py | 0.8.1 | MIT |
| PyUSB | 1.3.1 | BSD-3-Clause |
| libusb-package | 1.0.30.0 | Apache-2.0 for Python packaging code |
| libusb | 1.0.30 | LGPL-2.1-or-later; dynamically linked DLL, license under licenses/libusb/COPYING |
| importlib_resources | 7.1.0 | Apache-2.0 |
| PyInstaller | 6.22.3 | GPLv2-or-later with a special exception which allows to use PyInstaller to build and distribute non-free programs (including commercial ones) |

Python and Windows runtime DLL notices supplied with the runtime remain with their dependencies.

This pyvisa-py distribution does not contain or require NI-VISA. USB access still requires a compatible Windows device driver; see the [communication guide](docs/PYVISA_PY_zh-TW.md).

The unmodified libusb DLL is supplied by libusb-package and remains a separate dynamic library. Its corresponding upstream source is [libusb v1.0.30](https://github.com/libusb/libusb/tree/v1.0.30), available as a [source archive](https://github.com/libusb/libusb/archive/refs/tags/v1.0.30.tar.gz). Packaging source and build scripts are available from [libusb-package](https://github.com/pyocd/libusb-package).

See the included license texts for redistribution terms.
