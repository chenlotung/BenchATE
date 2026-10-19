# Windows 11 安裝與執行

## 可攜式版本

1. 解壓整份 ZIP 到可寫入資料夾，如 `D:\LabTools\ATEWorkbench`。
2. 保留 `ATEWorkbench.exe`、`_internal/`、`config/` 的相對位置。不要直接在 ZIP 檢視器裡執行。
3. `Start Demo.cmd` 使用模擬設備；`ATEWorkbench.exe` 預設是真實模式。沒有 Python 安裝也能執行。
4. 設備設定分別存在 `config/instruments.local.json` 與 `config/instruments.demo.local.json`；不儲存輸出 ON 或安全批准狀態。
5. EXE 未簽章；包內 `manifest.json` 及 ZIP 同名 `.sha256` 可核對檔案完整性。
6. 先開啟 `README_PORTABLE.pdf`。Release 說明文件由 Markdown 原稿轉為 PDF；真正的文字授權檔、requirements 與機器讀取的設定檔保留原格式。

本機已解壓至另一個目錄測試可攜性，結果記錄於交付報告。沒有另一台乾淨 Windows VM，不能宣稱已跨電腦驗證。

## 原始碼版本

使用 python.org 的 Windows x64 CPython 3.11+，避免 MSYS2 的 Python 與 Windows Qt wheel 混用。
本機建立的環境是 `.venv-win`，使用 CPython 3.13.14。

```powershell
cd G:\Bench_ATE\ate-workbench
python -m venv .venv-win
.\.venv-win\Scripts\python.exe -m pip install -e ".[test,build]"
.\.venv-win\Scripts\python.exe main.py --demo
```

若 `python` 指到 MSYS2，改為明確的原生 Windows Python 路徑，例如本機：

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m venv .venv-win
```

可使用 `scripts/Install.ps1 -PythonExecutable 'C:\...\python.exe'`。所有 Python 套件只安裝到專案虛擬環境。

## VISA backend 與 USB 驅動

本 release 已附 `installers/ni-visa_26.8_online.exe`。請先看 [NI-VISA 26.8 組件勾選與安裝說明](NI_VISA_INSTALLATION_zh-TW.md)；ZIP 根目錄也有 `NI_VISA_INSTALLATION_zh-TW.pdf`。建議保留 NI-VISA Runtime、Configuration Support / NI MAX 與 Interactive Control；線上安裝器仍需要網路下載套件。

PyVISA 是前端，真實通訊仍需要 backend。Python 與原生 VISA DLL 必須位元數一致；本成品為 x64。
見 [PyVISA 安裝文件](https://pyvisa.readthedocs.io/en/stable/introduction/getting.html)。

安裝支援 Windows 11 x64 的 [NI-VISA](https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html)，依其安裝程式啟用所需 USBTMC / TCPIP 支援。
此系統不自動安裝全機驅動，也不把 NI-VISA 原生驅動偽裝成 EXE 內建依賴。

- Chroma 66205：USB Device 遠端介面；依手冊 USBTMC / USB488 與 VISA driver 設定。
- Chroma 6312A：確認主機背板有選購 USB 通訊卡；USB 在主機，不在 63106A 模組。
- Chroma 63210A：使用遠端 USB Device 連接埠，不能把前面板 USB Host 儲存埠當遠端介面。
- RIGOL DM3058E：使用 USB Device，必要時依 RIGOL 官方 UltraSigma / driver 指引設定。官方下載入口見該設備 `source.md`。
- USB-Serial：本版未確認這組設備的串列控制設定與介面相容性，停用 ASRL 資源指派，不猜 baud rate。

先使用 NI MAX 或原廠工具確認資源是否出現，再在應用程式按 Scan & Connect。
Windows 看得到 USB 裝置不代表已建立可用的 VISA resource。

## Ethernet

| 型號 | 協定 | 資源範例 | 依據 |
|---|---|---|---|
| Chroma 61512 | TCP Socket, port 2101 | `TCPIP0::192.168.1.101::2101::SOCKET` | 原手冊 PDF 128 / 9-2 |
| Tektronix MSO44B | 已啟用的 VXI-11 | `TCPIP0::192.168.1.102::inst0::INSTR` | 原手冊 VXI server 說明 PDF 1746 |

連線頁只保留 Scope IP 與 AC Source IP 兩欄。按 Scan & Connect 時先掃描 USB，再對有填 IPv4 的 LAN 設備查詢識別並自動連線；任一欄空白即跳過該設備，即使 VISA backend 已列舉到該 LAN 資源也不探測。兩欄都空白仍可掃描並連接支援的 USB 設備。
不需指定 USB driver / 型號 / resource；只允許 README 列出的完整型號，其他設備不列入設備表。掃描不進行整個 LAN 的位址搜尋。應用程式不會自行啟用示波器 server、修改 IP、切換 trigger 或使用假設的 5025 port。
MSO44B 截圖使用原手冊的 SAVE:IMAGE → OPC → READFILE → DELETE；需要目前儀器工作目錄可寫入。

## 常見錯誤

- **VISA backend unavailable / library not found**：確認安裝 backend、x64 DLL、驅動版本及 `config/application.json` 的 `visa_backend`（空字串使用 PyVISA 預設選擇）。
- **設備未列入**：核對 USB 驅動、完整型號及介面。63210A 需完整後綴。61512 若回報通用 61500 IDN，掃描無法確認確切型號，因此排除，不把同系列設備當成相容機種。
- **Scope / AC Source skipped**：空白 IP 會跳過該台；需連線時填有效 IPv4 再 Scan & Connect。無效 IP 會顯示跳過原因，USB 掃描仍繼續。
- **Timeout**：本版會關閉失去同步的 session，清空待執行控制並保留 Stale 值。查明位址、網路、防火牆、termination 後明確重新連線。
- **DMM no value**：確認 RIGOL command set、單顯示模式及所支援 Function；程式不會自行切換儀器模式。
- **Safety limits not approved**：每次連線均需 Review Safety Limits；Apply 不會自動啟用輸出。
- **CSV 已存在**：記錄器以新建檔案方式開啟，避免覆寫既有量測，請選擇新檔名。

記錄檔位於 `logs/workbench.log`，單檔 5 MiB、保留 3 份輪替；CSV 保存在使用者選擇的位置。
