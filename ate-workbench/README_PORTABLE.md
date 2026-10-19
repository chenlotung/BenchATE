# ATE Workbench 可攜式版本

Windows 11 x64 · 版本 0.1.0

## 開始使用

1. 將整份 ZIP 解壓到可寫入資料夾。保留 `ATEWorkbench.exe`、`_internal/`、`config/` 的相對位置，不需要另外安裝 Python。
2. 使用模擬設備時開啟 `Start Demo.cmd`；連接實體儀器時開啟 `Start Real.cmd` 或 `ATEWorkbench.exe`。
3. 連線頁只保留 **Scope IP (MSO44B)** 與 **AC Source IP (61512)**。任一欄留白就跳過該台 LAN 儀器；兩欄都空白也能掃描 USB。
4. 按 **Scan & Connect**，自動辨識並連線支援清單內的設備。其他品牌或其他型號不列入設備表。Demo 模式填入有效 IPv4 只會模擬 LAN 設備，不會存取網路。
5. 在 Monitoring Dashboard 按 **Start Monitoring** 或 **Start All**。控制輸出前，先檢閱並批准本次連線的安全限制。

掃描與連線不會 reset 或啟用輸出。通訊失敗後，請確認實體設備狀態，再手動掃描重新連線；Output OFF 不能作為實體緊急停止。

## 真實儀器需要 NI-VISA

ZIP 已包含原始線上安裝程式 `installers/ni-visa_26.8_online.exe`，仍需在電腦上另行安裝；需要網路與管理員權限。它不是完整離線安裝包，也不是可直接從 ZIP 載入的原生 VISA 驅動。

依 [NI-VISA 安裝與組件選擇](docs/NI_VISA_INSTALLATION_zh-TW.md) 完成安裝，再測試實機連線。Demo 模式不需要 NI-VISA。

## 支援的設備

| 設備 | 連線方式 | 使用範圍 |
|---|---|---|
| Chroma 61512 | AC Source IP，TCP 2101 | AC 電壓 / 頻率、V/I/P/f、輸出控制；控制限 SINGLE / FIXED / AC。只回報通用 61500 型號時不列入。 |
| Chroma 66205 | USB 自動掃描 | 電壓、電流、功率、視在功率、功率因數、頻率。 |
| RIGOL DM3058E | USB 自動掃描 | 依儀器目前功能讀值；使用 RIGOL 指令集與單顯示模式。 |
| Chroma 6312A / 63106A | 主機 USB 自動掃描 | 自動辨識 CH1 / CH3 的 63106A；主機共用一筆連線，支援靜態 CC 負載。 |
| Chroma 63210A | USB 自動掃描 | 完整型號限 150-1000、600-700、1200-400；靜態 CC 負載。 |
| Tektronix MSO44B | Scope IP，VXI-11 | 手動取得螢幕截圖；先在儀器啟用 VXI-11。 |

## 監控、控制與儲存

- 設備清單顯示連線狀態、識別與延遲。重複按 Scan & Connect 會沿用已連線設備；斷線後可再掃描連線。
- 預設每秒更新一次量測。停止監控或暫停圖表不會關閉實體輸出；重新連線不會恢復先前的輸出指令。
- **Review Safety Limits**：每次連線後重新核可電壓 / 頻率 / 電流限制。**Apply Settings** 套用設定後請核對回讀值；啟用輸出另按 **Output ON / Load ON** 並確認。
- DC 負載套用電流時同時設定 L1 / L2；切換負載模式前先關閉負載。輸出與量測無法確認時顯示 Unknown / Stale，請核對儀器前面板。
- **Start CSV Logging**：選擇新的 CSV 檔案路徑；既有檔案不會覆寫。**Capture Screenshot** 取得 MSO44B 畫面。
- 設定、CSV 與記錄分別位於 `config/`、`data/`、`logs/`。請將整個資料夾一起移動，並使用可寫入的位置。

## 找不到設備時

1. 真實模式先依 [NI-VISA 安裝指南](docs/NI_VISA_INSTALLATION_zh-TW.md) 安裝 x64 VISA 與正確的 USB 驅動；Demo 模式不需要安裝。
2. USB 請接儀器的 Device / Remote 埠，確認資料線與原廠驅動；儀器前面板的 USB 儲存埠通常不能作為遠端通訊埠。
3. Scope / AC Source 請填入實機 IPv4；空白會跳過該台。確認電腦與儀器網路可達，Scope 已啟用 VXI-11。
4. 確認完整型號在上表內。其他型號不會列入設備清單；Timeout 後查明連接狀態，再按 Scan & Connect。
5. 需要查閱通訊錯誤時，開啟 `logs/workbench.log`。首次使用真實設備時，請以允許的低能量條件核對量測、設定與輸出狀態。
