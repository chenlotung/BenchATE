# ATE Workbench

Windows 11 / Python 3.11+ 的桌面儀器連線、監控與基本輸出控制平台。GUI 使用 PySide6 Qt Widgets，趨勢圖使用 PyQtGraph。
本版僅提供 Instrument Connection 與 Monitoring Dashboard 兩個頁面。

本分支 `codex/pyvisa-py-backend` 使用 **PyVISA → pyvisa-py (@py)**，不載入 NI-VISA。USB 透過 PyUSB 與隨包 libusb DLL；Windows 必須已有相容的裝置驅動。原本 NI-VISA 版本保留在 main。

## 直接使用可攜式版本

[下載 pyvisa-py Windows x64 發行 ZIP](https://github.com/chenlotung/BenchATE/raw/refs/heads/codex/pyvisa-py-backend/ate-workbench/releases/ATEWorkbench-0.1.0-pyvisa-py-windows-x64.zip) · [SHA-256 校驗檔](releases/ATEWorkbench-0.1.0-pyvisa-py-windows-x64.zip.sha256)

ZIP 與校驗檔均保存在 repo 的 `releases/`。解壓縮後保留整個 `ATEWorkbench` 資料夾。

- `ATEWorkbench.exe` 或 `Start Real.cmd`：Real Mode，初始設備清單為空，不自動連線或啟用輸出。
- `Start Demo.cmd`：明確標示 DEMO MODE；按 Scan & Connect 連線模擬設備，再 Start Monitoring。Scope / AC Source 的 IP 留白時同樣跳過；填入任意有效 IPv4 可模擬這兩台，不會存取網路。
- 不需另外安裝 Python。`_internal` 內是 EXE 必需的 Python、Qt 與其他依賴，請與 EXE 一起移動。
- `config/`、`data/`、`logs/` 與 EXE 同層；請解壓到可寫入的資料夾。
- 已包含 pyvisa-py、PyUSB 與 libusb DLL，不需要安裝 NI-VISA。LAN 只需儀器區域網路可達；USB 仍需要已綁定相容 WinUSB/libusb 驅動，見 [通訊指南](docs/PYVISA_PY_zh-TW.md)。
- Release 是使用者發行包，只附快速操作、通訊與 USB 說明、授權 PDF；先看 `README_PORTABLE.pdf`。不包含 NI 安裝器、原始碼、架構、SCPI 表、原廠通訊手冊、測試或交付報告。

## 在目前工作區執行原始碼

已建立並測試原生 Windows Python 虛擬環境 `.venv-win`：

```powershell
cd G:\Bench_ATE\ate-workbench
.\.venv-win\Scripts\python.exe main.py --demo
```

Real Mode：

```powershell
.\.venv-win\Scripts\python.exe main.py
```

其他電腦可執行 `scripts/Install.ps1` 建立環境，或使用原生 Windows Python 3.11+：

```powershell
python -m venv .venv-win
.\.venv-win\Scripts\python.exe -m pip install -e ".[test]"
.\.venv-win\Scripts\python.exe main.py --demo
```

目前驗證環境為 Windows 11 x64、CPython 3.13.14；其他 Python 版本未在本機實測。

## 操作流程

1. **Instrument Connection**：只保留 **Scope IP (MSO44B)** 與 **AC Source IP (61512)** 兩個手動 IP 欄位。可分別留白；留白就跳過該台 LAN 設備，USB 掃描照常。
2. 按 **Scan & Connect**，自動掃描 USBTMC、查詢識別、比對原先支援的確切型號，再加入設備表格並連線。不需要指定 USB driver、型號或 VISA resource；不在清單內的設備不列入。表格保留連線狀態、完整識別、資源、延遲及最後檢查時間。
3. 有填 IP 時才探測對應設備：61512 固定 TCP Socket 2101 / LF；MSO44B 使用 VXI-11 inst0，須先在示波器啟用 VXI-11。空白欄位不會探測 VISA backend 列舉到的 LAN 資源，也不會廣域搜尋 LAN。
4. 6312A 只建立一筆主機設備，自動從 *RDT? 選取 CH1 / CH3 上的 63106A；其他模組不加入。掃描只做識別與 inventory 查詢，不 reset、不改量測模式或輸出。通用 61500 識別不足以證明是 61512，會被排除。重複掃描沿用已連線 session；斷線後按 Scan & Connect 明確重新連線。
5. **Monitoring Dashboard**：Start Monitoring / Start All，預設每設備 1000 ms。切換頁面沿用同一連線。
6. 控制前按 **Review Safety Limits**，核可本次連線的限制；Apply Settings 後檢查獨立的 Applied / Readback。DC Load 的 Apply 明確同時設定 L1/L2 為相同 CC 電流。
7. Output ON / Load ON 另行確認；不使用未套用的輸入值。模式切換需先 Load OFF；已啟用輸出的設定變更會要求確認。
8. Stop Monitoring 只停止週期查詢。Disconnect / 關閉程式釋放連線，保留實體儀器原有輸出狀態。
9. Capture Screenshot 手動取得 MSO44B 畫面；不擷取 raw waveform、不改 trigger/acquisition。
10. Start CSV Logging 選擇新的 CSV 路徑。圖表 Pause display 不會停止採集或記錄。

Actual Output、Remote、設定回讀與量測值各自管理。無法確認的狀態顯示 Unknown；過期量測保留最後有效值與 timestamp 並標示 Stale。
Output OFF 是一般通訊操作，不能當成實體緊急停止。

## 支援範圍

| 設備 | 本版功能 | 限制 |
|---|---|---|
| Chroma 61512 | LAN 識別、V/I/P/f、設定電壓/頻率、Output 回讀與控制 | SINGLE / FIXED / AC；三相控制待驗證；LAN Remote/Local 無已確認方法 |
| Chroma 66205 | USB 識別、六項批次 fetch、更新週期/平均次數查詢、USB Remote/Local 請求 | 實際新硬體樣本速率未驗證；Remote 實際狀態 Unknown |
| RIGOL DM3058E | USB 識別、依實際 Function 讀值及單位 | RIGOL command set、單顯示；雙顯示/continuity/sensor 待驗證 |
| Chroma 6312A / 63106A | 主機 inventory、CH1/CH3、多通道 V/I/P、CCL/CCH、L1/L2、Load 回讀 | 只支援辨識為 63106A 的模組；USB Remote/Local 指令未確認 |
| Chroma 63210A | 三種完整型號、V/I/P、CCL/CCM/CCH、L1/L2、Load、Remote/Local 請求 | 需型號後綴 150-1000 / 600-700 / 1200-400；不套用非 A 系列 |
| Tektronix MSO44B | VXI-11 識別、手動 PNG 預覽 | 依手冊適用韌體；先在儀器建立暫存圖片；OPC 可能等待既有擷取 |

所有實機相容性均為 **Pending Hardware Verification**。缺少 VISA backend 會回報錯誤，絕不切換為 Demo 資料。

`communication.visa_backend` 為 `@py`；舊設定的空字串也正規化為 `@py`，不自動選擇本機 NI-VISA。指定原生 DLL 或 `@ivi` 會回報設定錯誤。USB 掃描直接使用 pyvisa-py USB INSTR 枚舉，避免一般 list_resources 在過濾前搜尋 LAN；這個介面整合以 pyvisa-py 0.8.x 為範圍，升版需重測。

## 原始碼配置

程式集中在 `app/`，只保留 `drivers/` 與 `gui/` 兩個子套件。設備管理與掃描在 `instruments.py`，佇列與背景執行在 `worker.py`，低階通訊在 `protocol.py`；設定、型別及資料處理各自保留一個檔案。
原先 35 個 Python 檔案、7 個套件目錄已整併為 19 個檔案、3 個套件目錄；各型號 driver 類別及 GUI / 通訊邊界保留。完整目錄與責任分配見 [架構](docs/architecture.md)。

## 測試與重現

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv-win\Scripts\python.exe -m pytest -q --basetemp=tmp/pytest-local --junitxml=docs/validation/pytest.xml
.\.venv-win\Scripts\python.exe main.py --demo --soak-seconds 20 --report docs/validation/smoke.json
Remove-Item Env:QT_QPA_PLATFORM
```

測試不會啟用真實儀器輸出。Mock VISA 與 Demo 驗證軟體行為，不能代替實機驗證。
**依使用者後續要求，跳過 1 小時測試。** 詳細結果見 [交付報告](docs/DELIVERY_REPORT.md)。

## 重建可攜式 ZIP

```powershell
.\.venv-win\Scripts\python.exe -m pip install -e ".[build]"
.\.venv-win\Scripts\python.exe scripts/build_portable.py
```

建置後使用 EXE 自身的 `--demo --soak-seconds 20 --report PATH` 可在不依賴 Python 的情況執行短測試。
成品為 Windows x64 的資料夾型 EXE；未簽署程式碼簽章。
PDF 轉換只在建置時使用 ReportLab、Markdown parser 及 Windows 微軟正黑體，使用者執行 EXE 不需要安裝這些工具。只更新文件可執行 `scripts/build_portable.py --refresh-only`；同樣會轉換 PDF 並重建 manifest / ZIP。
執行 `scripts/validate_release_documents.py` 可檢查使用者發行白名單、PDF 內容與連結、ZIP 校驗碼；加上 `--poppler C:\path\to\pdftoppm.exe` 可產生逐頁預覽，保存在 `tmp/pdfs/release_review/`。

## 文件

- [安裝指南](docs/installation.md)
- [pyvisa-py 通訊、USB 條件與函式庫檢查](docs/PYVISA_PY_zh-TW.md)
- [架構](docs/architecture.md)
- [SCPI 指令、參數、頁碼、驗證階段](docs/SCPI_COMMAND_REFERENCE.md)
- [Capabilities 與軟體安全限制](docs/capabilities.md)
- [實機驗證清單](docs/hardware_validation.md)
- [已知限制](docs/KNOWN_LIMITATIONS.md)
- [依賴授權及版本](THIRD_PARTY_NOTICES.md)

原始手冊沿用 repo 根目錄 `datasheet/`；新增 RIGOL 官方 PDF 保存在 `docs/instruments/rigol_dm3058e/`。
各設備的 `source.md` 記錄來源、版本、日期、SHA-256 與使用範圍。
