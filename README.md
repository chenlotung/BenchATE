# BenchATE

Windows 11 實驗桌 ATE 平台。程式碼、安裝方式與測試資料位於 [ate-workbench](ate-workbench/README.md)。

- 原始儀器文件：`datasheet/`
- SCPI 指令依據：`ate-workbench/docs/SCPI_COMMAND_REFERENCE.md`
- 本分支 `codex/pyvisa-py-backend` 改用 pyvisa-py、PyUSB 與隨包 libusb DLL，不需要 NI-VISA；原本 NI-VISA 版本保留在 main。
- 可攜式發行包：[下載 pyvisa-py Windows x64 ZIP](https://github.com/chenlotung/BenchATE/raw/refs/heads/codex/pyvisa-py-backend/ate-workbench/releases/ATEWorkbench-0.1.0-pyvisa-py-windows-x64.zip) · [SHA-256 校驗檔](ate-workbench/releases/ATEWorkbench-0.1.0-pyvisa-py-windows-x64.zip.sha256)
- [通訊與 USB 使用說明](ate-workbench/docs/PYVISA_PY_zh-TW.md)；LAN 可免裝 NI-VISA，USB 仍需要 Windows 已有相容裝置驅動。新版 ZIP 不附 NI 安裝器。
- 預設 Real Mode；`--demo` 明確啟用模擬設備，兩種模式的設備設定分開保存。
