# ATE 自動化測試平台 — 完整開發需求 V1.0

## 0. 專案任務與執行原則

你是一位具備以下專業能力的資深軟體工程師：

- Python 3.11+
- PySide6 / Qt Widgets
- PyQtGraph
- PyVISA / VISA Backend
- SCPI 儀器通訊
- USBTMC、USB-Serial、Ethernet
- QThread / Signal / Slot
- 多儀器自動化測試系統
- 電源電子與實驗室量測儀器

請在目前 Codex 工作區中，建立一套適用於 Windows 11 的實驗桌 ATE（Automated Test Equipment）系統。

本專案用於公司內部研發及電源電子測試，必須能整合不同廠牌的儀器，提供統一的連線管理、即時監控、基本輸出控制及資料記錄功能。

**請實際建立、修改及測試程式碼，不要只提供設計方案、架構圖或虛擬碼。**

若工作區已經存在 Python 專案，優先沿用既有程式結構，避免不必要的重構。

若工作區為空白，建立完整新專案，暫用 `ate-workbench` 作為資料夾名稱，不需要先決定正式產品品牌名稱。

### 第一階段功能範圍

目前只實作兩個主要 GUI 子頁面：

1. Instrument Connection — 設備連線測試
2. Monitoring Dashboard — 監控與基本輸出控制

本階段不需要開發完整測試腳本編輯器、測試序列排程、Pass/Fail 測試流程或報表產生器。

但是必須將儀器 Driver、GUI、資料管理和測試控制邏輯分離，為未來增加這些功能保留擴充能力。

除非出現真正無法繼續的阻礙，否則請自行完成所有可以實作的部分，不要在每個階段停止等待確認。

---

# 1. 軟體技術架構

## 1.1 核心技術

| 功能 | 技術 |
|---|---|
| 程式語言 | Python 3.11 或更新相容版本 |
| 桌面 GUI | PySide6 |
| 即時趨勢圖 | PyQtGraph |
| 儀器通訊 | PyVISA |
| VISA Backend | NI-VISA 或相容 Backend |
| 背景執行 | QThread / QObject Worker |
| 訊息傳遞 | Qt Signal / Slot |
| 資料處理 | NumPy |
| 設定儲存 | JSON |
| 量測記錄 | CSV |
| Logging | Python logging |
| 單元測試 | pytest |
| 執行平台 | Windows 11 |

優先選擇穩定、維護成本低且授權允許公司內部使用的開源套件。

避免不必要的第三方依賴，不需要 Electron、Flask、Web Server 或前後端分離架構。

## 1.2 核心設計原則

1. GUI 不得直接操作 PyVISA。
2. 所有儀器 I/O 必須在背景 Worker 執行。
3. 每台實體儀器管理自己的 VISA Session。
4. 同一儀器的所有 SCPI 命令必須序列化執行。
5. 不同儀器之間允許並行操作。
6. 儀器 Driver 不依賴 GUI。
7. GUI 不得包含硬編碼的儀器 SCPI 指令。
8. 不得因為單台儀器斷線或 Timeout 導致整個 GUI 卡住。
9. 儀器設定值、量測值及狀態必須分開管理。
10. 不得使用模擬數據假冒真實儀器回應。

---

# 2. 儀器清單

目前實驗桌使用以下設備：

| 類型 | 廠牌 | 型號 | 通訊 |
|---|---|---|---|
| AC Source | Chroma | 61512 | Ethernet |
| Power Meter | Chroma | 66205 | USB |
| Multimeter | RIGOL | DM3058E | USB |
| DC Electronic Load | Chroma | 63106A / 6312A | USB |
| DC Electronic Load | Chroma | 63210A | USB |
| Oscilloscope | Tektronix | MSO44B | Ethernet |

此表為設備配置需求，實際通訊協定、連接埠、指令及量測能力必須根據原廠文件確認。

### 特殊注意事項

**Chroma 63106A / 6312A**

必須仔細確認：

- 6312A 是否為 Mainframe。
- 63106A 的模組與主機關係。
- 實際 USB 通訊介面位於哪個設備。
- Slot / Channel 的控制及查詢指令。
- Mainframe 與模組的識別方式。
- 每個 Channel 的電流設定範圍及限制。

不得直接假設兩個型號各自提供獨立 VISA Session。

**Chroma 63210A**

確認是否存在不同硬體、韌體或通訊介面版本，不能直接套用其他 Chroma DC Load 系列的指令。

**Tektronix MSO44B**

只需要支援基本連線與手動截圖。不需要在第一階段實作示波器的完整控制功能。

---

# 3. 通訊規格書管理 — 最高優先事項

**在建立任何儀器 Driver 之前，必須先確認對應的官方通訊規格。**

## 3.1 規格書來源優先順序

### 第一優先：Codex 工作區現有文件

搜尋整個工作區中與上述設備相關的：

- Programming Manual
- Remote Control Manual
- SCPI Command Reference
- Interface Manual
- User Manual
- USB / Ethernet Communication Manual

支援 PDF、Markdown、TXT、HTML 等格式。

需要實際讀取規格書內容，不可只依照檔名判斷。

如果規格書包含的內容足以支援目前功能，不需要再次從網路下載。

### 第二優先：官方網站

只有當工作區未提供對應文件，或現有文件缺少必要通訊資訊時，才透過網路搜尋。

官方來源優先：

- Chroma 官方文件與下載中心
- RIGOL 官方文件與下載中心
- Tektronix 官方文件與下載中心

禁止將不同型號或不同系列的指令直接視為相容。

如果只能找到相近型號的通訊手冊，必須先確認官方相容性聲明，否則只能作為待驗證參考。

### 第三優先：其他技術資料

僅在官方來源無法取得時，才參考其他可信技術資料。

必須明確標示其非官方來源，且不能將未驗證的指令視為正式支援。

---

## 3.2 網路文件下載與本地保存

從網路取得的官方通訊規格書，必須下載至本地專案。

建立以下目錄：

```text
docs/
└── instruments/
    ├── chroma_61512/
    ├── chroma_66205/
    ├── rigol_dm3058e/
    ├── chroma_6312a_63106a/
    ├── chroma_63210a/
    └── tek_mso44b/
```

每個資料夾內保存：

1. 官方通訊手冊原始文件。
2. `source.md`。
3. 規格書版本與日期。
4. 官方來源網址。
5. 下載日期。
6. SHA-256 Checksum。
7. 實際使用到的 SCPI 指令及頁碼。

如果文件已存在，沿用既有文件，不重複下載。

如果官方網站無法下載或授權條件不允許本地保存，記錄原因與網址，不得偽造官方文件。

不得把自行整理的 Markdown 假冒為下載到的原廠規格書。

---

## 3.3 SCPI 指令對照表

建立：

`docs/SCPI_COMMAND_REFERENCE.md`

對所有實際使用的指令記錄：

| 欄位 | 內容 |
|---|---|
| Manufacturer | 廠牌 |
| Model | 型號 |
| Function | 指令用途 |
| SCPI Command | 完整指令 |
| Parameters | 參數及範圍 |
| Response | 回應格式 |
| Source | 文件來源 |
| Page | 頁碼或章節 |
| Verification | 驗證狀態 |

驗證狀態應區分：

- Documented
- Implemented
- Unit Tested
- Hardware Verified
- Unsupported
- Pending Verification

文件中有記載不代表已完成實體硬體驗證。

禁止臆測 SCPI 指令、回傳格式或量測單位。

若通訊手冊缺少某項功能，暫停該功能實作或標記為 Pending Verification，不得讓 Codex 自行杜撰命令。

---

# 4. 軟體整體架構

建議採用以下架構：

```text
PySide6 Main Window
│
├── Instrument Connection
│
├── Monitoring Dashboard
│
├── Instrument Manager
│   ├── Driver Registry
│   ├── VISA Resource Manager
│   └── Device Configuration
│
├── Instrument Worker Manager
│   ├── AC Source Worker
│   ├── Power Meter Worker
│   ├── DMM Worker
│   ├── DC Load Worker
│   └── Oscilloscope Worker
│
├── Instrument Drivers
│   ├── Base Instrument
│   ├── Chroma 61512
│   ├── Chroma 66205
│   ├── RIGOL DM3058E
│   ├── Chroma 6312A / 63106A
│   ├── Chroma 63210A
│   └── Tektronix MSO44B
│
├── Data Manager
│   ├── Ring Buffer
│   ├── Timestamp
│   ├── Measurement Model
│   └── CSV Logger
│
└── Logging & Error Handling
```

Instrument Manager 必須是整個應用程式共用的單一管理實例。

連線頁面建立的 VISA Session，切換到監控頁面後必須繼續使用。

禁止因為切換頁面而重新連線、Reset 或重新初始化儀器。

---

# 5. GUI 主視窗

使用 PySide6 Qt Widgets 建立桌面應用程式。

## 5.1 視覺風格

採現代化工程測試軟體介面：

- 簡潔、專業。
- 支援 Dark / Light Theme，預設使用 Dark Theme。
- 清楚區分監控資訊與可操作控制項。
- 支援視窗尺寸調整。
- 儀器狀態容易辨識。
- 數值顯示採等寬數字或易讀字體。
- 避免過度動畫與裝飾。

所有介面文字優先使用英文技術術語，程式註解、README 與開發文件可以使用繁體中文。

## 5.2 主視窗排版

左側 Navigation Bar：

1. Instrument Connection
2. Monitoring Dashboard

右側顯示當前頁面。

底部 Status Bar：

- VISA Backend 狀態
- 已連線儀器數量
- 正在監控的儀器數量
- 最新系統錯誤
- 系統時間
- Real / Demo Mode

需要提供適當的錯誤提示，但不得以頻繁彈出視窗干擾正常量測。

---

# 6. 頁面一：Instrument Connection

此頁面負責儀器的搜尋、設定、連線、驗證及通訊效能測試。

## 6.1 儀器資源掃描

使用 PyVISA 列出可用的 VISA Resources。

支援：

- USBTMC
- 已確認可用的 USB-Serial
- 已存在的 TCPIP VISA Resources
- 手動輸入 Ethernet 儀器位址

提供以下操作：

- Refresh Resources
- Add Instrument
- Remove Instrument
- Connect
- Disconnect
- Test Connection
- Communication Benchmark

`list_resources()` 不能視為完整的 LAN 儀器搜尋機制，Ethernet 設備必須可以手動輸入 IP Address。

不要因為 USB 裝置出現在系統內，就直接判定其支援 VISA。

如需特定廠商 USB Driver，必須記錄所需驅動與安裝方式。

## 6.2 連線設備清單

使用 QTableView 顯示：

| 欄位 | 說明 |
|---|---|
| Device Name | 使用者自訂名稱 |
| Manufacturer | 製造商 |
| Model | 型號 |
| Connection | USB / Ethernet |
| VISA Resource | VISA 資源 |
| Identification | 儀器識別 |
| Status | 連線狀態 |
| Latency | 最近通訊延遲 |
| Last Check | 上次檢查時間 |
| Driver | Driver 支援狀態 |

狀態至少包含：

- Disconnected
- Connecting
- Connected
- Communication Error
- Timeout
- Unsupported

需要明確區分物理連線與應用層通訊是否成功。

---

## 6.3 Ethernet 設定

支援：

- IP Address
- 通訊協定
- Port（適用時）
- VISA Resource
- Timeout

根據儀器規格書選擇：

- VXI-11
- HiSLIP
- TCP Socket
- 其他已確認支援的協定

不得假設所有 LAN SCPI 儀器都使用 TCP 5025。

Chroma 61512 與 Tektronix MSO44B 必須分別確認實際通訊方式。

---

## 6.4 USB 設定

支援：

- VISA Resource 選擇。
- Instrument Driver 指派。
- USB Serial Number 辨識（若可取得）。
- Timeout 設定。
- Resource 重新掃描。

允許系統有多台相同型號儀器。

不得只使用 Model Name 作為設備唯一識別碼。

應盡量以 VISA Resource、Serial Number 及使用者設定 ID 建立穩定對應。

---

## 6.5 Test Connection

測試步驟：

1. 開啟 VISA Session。
2. 設定規格書要求的通訊參數。
3. 執行文件支援的設備識別查詢。
4. 接收回應。
5. 驗證型號與 Driver 的相容性。
6. 計算 Round-Trip Latency。
7. 顯示測試結果。
8. 記錄錯誤資訊。

如果儀器支援 `*IDN?`，可以使用。

若不支援，依照官方手冊選擇適當的唯讀查詢命令。

連線測試時不允許：

- 開啟輸出。
- 關閉輸出。
- 改變設定電壓。
- 改變設定電流。
- 執行 Reset。
- 清除使用者既有測試設定。
- 更改 Trigger 或量測模式。

單純連線測試必須維持非侵入式操作。

---

## 6.6 Communication Benchmark

提供可選的通訊效能測試功能。

執行使用者選擇的安全 SCPI Query，統計：

- Average Latency
- Minimum Latency
- Maximum Latency
- P95 Latency
- Timeout Count
- Error Count

測試次數可設定，預設 100 次。

Benchmark 不得自動執行。

必須清楚提示使用者測試會暫時增加儀器通訊負載。

若設備正在執行監控，Benchmark 必須與正常量測排程協調，不可同時對同一 Session 發送命令。

---

# 7. 頁面二：Monitoring Dashboard

此頁面同時負責：

1. 即時量測數值。
2. 量測趨勢曲線。
3. 基本輸出參數設定。
4. Output ON / OFF。
5. Remote / Local 狀態。
6. 示波器截圖。

監控及控制必須使用 Instrument Manager 中既有的 Session。

---

# 8. Monitoring Dashboard — 儀器卡片

每台儀器顯示獨立 Card。

卡片分成三個區域：

### A. Device Information

- Device Name
- Manufacturer
- Model
- Connection Status
- VISA Resource
- Remote / Local Status
- Last Update Time
- Actual Polling Rate

### B. Measurements

顯示該設備目前支援的量測資訊。

每項量測包含：

- Value
- Unit
- Timestamp
- Data Validity

### C. Controls

只對具有控制能力的設備顯示。

包括：

- Setpoint
- Mode
- Apply Settings
- Output ON / OFF
- Actual Output Status

需要區分：

- Desired Setpoint
- Applied / Readback Setpoint
- Actual Measurement

不得把使用者輸入但尚未 Apply 的數值顯示成已套用設定。

不得用最後一次發送的 Output ON 命令直接代表實際輸出狀態已經開啟。

---

# 9. 各儀器監控與控制功能

## 9.1 Chroma 61512 — AC Source

Connection：Ethernet

### Measurements

優先確認並提供：

- AC Output Voltage RMS
- AC Output Current RMS
- Active Power
- Output Frequency
- Output Status

實際功能及指令以官方文件為準。

### Controls

提供：

- Output Voltage Setpoint（Vac RMS）
- Output Frequency Setpoint（Hz）
- Apply Settings
- Output ON
- Output OFF
- Remote / Local 管理（若支援）

設定值必須符合原廠文件的電壓、頻率範圍及解析度。

若目前輸出已經開啟，修改 Voltage 或 Frequency 時，必須明確提醒這會改變實際輸出。

Output ON 前必須確認：

- 設備已連線。
- Driver 已確認支援。
- 設定值符合軟體安全限制。
- 控制命令沒有待處理的異常。
- 使用者已明確確認啟用輸出。

不得因為 Apply Settings 自動 Output ON。

---

## 9.2 Chroma 66205 — Power Meter

Connection：USB

### Measurements

優先提供：

- Voltage RMS
- Current RMS
- Active Power
- Apparent Power
- Power Factor
- Frequency

其他參數可以依規格書的支援情況增加。

必須確認：

- Measurement Update Rate。
- Data Fetch / Measure 指令差異。
- 是否有 Integration / Averaging 設定。
- 量測通道或 Element 對應。
- 是否有多筆數據批次查詢方式。

不能假設每次 SCPI 回應都代表新的測量樣本。

### Controls

本階段不需要輸出控制。

若有必要的量測模式配置，可以預留 Driver API，但不主動改變現有量測設定。

---

## 9.3 RIGOL DM3058E — Multimeter

Connection：USB

### Measurements

支援讀取：

- Current Measurement Value
- Measurement Function
- Unit
- Measurement Status

依照實際模式顯示：

- DC Voltage
- AC Voltage
- DC Current
- AC Current
- Resistance
- 其他規格書支援的模式

不得預設量測數值一定代表電壓。

### Controls

第一階段僅以量測監控為主。

如能安全查詢目前 Function，優先顯示實際量測模式。

切換 Function 暫時不列為必要功能，除非已能完整確認其控制行為。

---

## 9.4 Chroma 63106A / 6312A — DC Electronic Load

Connection：USB

### Measurements

- Input Voltage
- Load Current
- Input Power
- Load Status

### Controls

- Mainframe / Slot / Channel Selection
- CC Mode
- Load Current Setpoint（A）
- Apply Settings
- Load ON
- Load OFF
- Current Setpoint Readback
- Actual Load Status

必須先確認 Mainframe 與 Module 的正確通訊架構。

如果一個主機有多個負載模組，各 Channel 的資料及設定必須完全獨立。

不得因為切換 Slot 或 Channel 而意外修改其他通道。

切換 CC Mode 是否會改變當前負載行為，必須依手冊確認。若可能影響正在運作的負載，需提供確認機制。

---

## 9.5 Chroma 63210A — DC Electronic Load

Connection：USB

### Measurements

- Input Voltage
- Load Current
- Input Power
- Load Status

### Controls

- CC Mode
- Current Setpoint（A）
- Apply Settings
- Load ON
- Load OFF
- Setpoint Readback
- Actual Load Status

此階段只要求 Constant Current Mode。

不必實作：

- CV
- CR
- CP
- Dynamic Load
- Sequence Mode
- Transient Mode

但 Driver 設計應預留後續新增 Mode 的能力。

---

## 9.6 Tektronix MSO44B — Oscilloscope

Connection：Ethernet

### Monitoring

本階段只顯示：

- Connection Status
- Instrument Identification
- Capture Screenshot
- Screenshot Preview
- Last Capture Time

### Screenshot

需求是直接觀看示波器觸發後的畫面。

優先使用原廠 SCPI Screenshot 功能取得 PNG。

若不支援 PNG，可以使用規格書支援的其他圖片格式，例如 JPG。

禁止為了截圖需求而下載完整 Raw Waveform 後重新繪製。

圖片處理流程：

1. 使用者按下 Capture Screenshot。
2. 背景 Worker 發送原廠截圖指令。
3. 讀取完整圖片二進位資料。
4. 檢查資料格式及完整性。
5. 將圖片資料傳回 GUI。
6. GUI 使用 QImage / QPixmap 顯示。
7. 保存最後一次擷取時間。

如果設備支援在記憶體內直接回傳圖片，優先使用，不需要先寫入本地硬碟。

示波器不參與一般 1 Hz 數據輪詢。

不需要額外設定示波器 Trigger、Acquire、Run/Stop 或改變其他既有操作狀態。

---

# 10. Remote / Local Mode 管理

因為部分儀器透過 Remote Control 後，前面板按鍵會被鎖定，因此 Monitoring Dashboard 必須具備足夠的基本控制功能。

## 10.1 Remote Mode

必須確認各儀器：

- 如何進入 Remote Mode。
- 是否有 Remote Status Query。
- 如何返回 Local Mode。
- USB 與 Ethernet 是否有不同的 Remote 管理方式。
- Remote Mode 是否限制前面板按鍵操作。

不得假設所有儀器都有共用的 `SYST:REM` 或 `SYST:LOC` 指令。

必須以原廠文件為準。

## 10.2 進入 Remote Mode 的原則

1. 單純掃描設備不應改變其操作模式。
2. 連線測試不應開啟輸出或修改設定。
3. 若 VISA 連線本身會使儀器進入 Remote Mode，必須記錄及顯示這個行為。
4. 使用者執行控制操作時，若必須進入 Remote Mode，才依照原廠規範切換。
5. Remote/Local 切換不得自行改變輸出設定。
6. 返回 Local 不代表需要先 Output OFF。
7. Disconnect 不得無條件 Reset 或關閉輸出。

若不能確認當前狀態，顯示 Unknown，不得自行猜測。

---

# 11. 基本輸出控制及安全機制

本 ATE 系統會控制實際電源及電子負載，因此必須確保操作行為可預期。

## 11.1 Setpoint 輸入

使用適當的 Qt 數值輸入元件，例如 QDoubleSpinBox。

必須依據 Driver Capabilities 設定：

- Minimum
- Maximum
- Resolution
- Unit
- Decimal Places
- Channel

除了儀器硬體範圍外，還需支援使用者可設定的 Software Safety Limits。

例如某 AC Source 可以輸出高電壓，但本次測試只允許 0～220 Vac，程式應使用較嚴格的軟體限制。

軟體安全限制不得預設為硬體最大值，且首次 Output ON 前必須明確取得使用者認可的限制。

## 11.2 Apply Settings

設定操作流程：

1. 檢查輸入值。
2. 檢查設備連線。
3. 檢查控制權限及 Remote 狀態。
4. 確認 Mode / Channel。
5. 送出設定命令。
6. 讀取儀器 Setpoint Readback（若支援）。
7. 比較設定值與回讀值。
8. 更新 GUI。
9. 記錄操作結果。

不能只因為 `write()` 沒有丟出例外，就認定設定已成功。

如果儀器不支援 Setpoint Readback，顯示 Unverified。

## 11.3 Output ON / OFF

Output ON 與 Output OFF 必須提供獨立按鈕。

要求：

- 禁止連線完成後自動 Output ON。
- 禁止程式啟動時自動恢復輸出。
- Output ON 需要使用者明確操作。
- AC Source Output ON 需要確認。
- Output OFF 應能快速操作。
- 不得將 Output OFF 按鈕宣稱為緊急停止功能。
- 命令送出後盡可能回讀實際狀態。
- 若通訊失敗，實際輸出狀態顯示 Unknown。

即使 GUI 失去連線，也不代表實體設備已經停止輸出。

禁止在通訊 Timeout 後未經確認就自動重送可能造成狀態變更的命令。

---

# 12. 數據採集頻率 — 第一階段固定以 1 Hz 為目標

## 12.1 預設採集設定

所有一般數值監控設備：

**Polling Rate = 1 Hz**

也就是：

```text
Polling Interval = 1000 ms
```

GUI 數值顯示與趨勢圖同樣以約 1 Hz 更新。

不同儀器允許有獨立 Polling Interval，但預設均為 1000 ms。

示波器截圖不納入 1 Hz Polling。

## 12.2 區分三種頻率

必須清楚區分：

1. Instrument Measurement Update Rate
2. SCPI Polling Rate
3. GUI Refresh Rate

GUI 更新頻率不代表儀器真的取得新量測數據。

如果 Power Meter 實際內部量測更新速度低於 1 Hz，必須顯示實際可取得的新樣本速率。

不可以將重複讀取的值直接標示為新的硬體量測樣本。

若儀器不提供樣本更新識別或時間戳記，則只能確定 SCPI 讀取頻率，不得宣稱已驗證內部採樣頻率。

## 12.3 Polling 排程

要求：

- 每台儀器有自己的輪詢排程。
- 每輪量測收集所有啟用且支援的參數。
- 優先使用原廠支援的批次查詢方式。
- 不允許同一台儀器重疊輪詢。
- 使用單調時鐘安排週期，避免查詢耗時造成持續時間漂移。
- 查詢時間過長時記錄 Polling Overrun。
- 當前輪未完成時，不得累積大量過期輪詢任務。
- 設定操作可以優先於監控輪詢處理。

---

# 13. PyQtGraph 即時趨勢圖

在 Monitoring Dashboard 加入趨勢圖區域。

至少支援：

- Voltage Trend
- Current Trend
- Power Trend

圖表基本要求：

1. 使用 PyQtGraph。
2. X 軸使用實際時間。
3. Y 軸使用正確工程單位。
4. 可以選擇儀器及 Channel。
5. 可以選擇顯示的 Measurement。
6. 可以啟用或停用曲線。
7. 支援 Auto Range。
8. 支援暫停畫面更新。
9. 預設顯示最近 60 秒。
10. 可切換最近 10 分鐘。

不同物理量不得混在同一 Y 軸而沒有區分單位。

暫停圖表不代表停止數據擷取，除非使用者明確要求停止監控。

---

# 14. 資料管理與儲存

## 14.1 Data Model

建立統一的 Measurement Data Model。

建議使用 Python Dataclass 或其他具型別的資料結構。

每筆資料至少包含：

```python
{
    "device_id": "dc_load_01",
    "channel": "CH1",
    "timestamp": "2026-10-19T12:00:00+08:00",
    "measurements": {
        "voltage": {
            "value": 48.5,
            "unit": "V"
        },
        "current": {
            "value": 10.0,
            "unit": "A"
        },
        "power": {
            "value": 485.0,
            "unit": "W"
        }
    },
    "status": "valid"
}
```

上述數值只是資料格式示例，不是實際儀器回應。

除了牆上時鐘時間，內部排程與時間差計算應採用 monotonic clock。

## 14.2 Ring Buffer

每台設備保存最近至少 10 分鐘的數據。

在 1 Hz 條件下，每個量測項目至少可保存 600 筆資料。

使用固定長度 Buffer，避免長時間執行後記憶體持續增加。

## 14.3 CSV Logging

支援將量測數據儲存至 CSV。

資料至少包含：

- Timestamp
- Device ID
- Device Model
- Channel
- Measurement Name
- Value
- Unit
- Data Status

避免在 GUI 主執行緒直接執行大量硬碟寫入。

記錄資料時應保留真實量測時間，不得以 GUI 重繪時間代替。

---

# 15. 多執行緒與通訊排程

## 15.1 每台儀器獨立 Worker

建議使用 QObject Worker 搭配 QThread。

每台實體儀器維持獨立工作單元。

例如：

```text
Instrument Manager
│
├── Chroma 61512 Worker
├── Chroma 66205 Worker
├── RIGOL DM3058E Worker
├── Chroma 6312A Worker
├── Chroma 63210A Worker
└── Tektronix MSO44B Worker
```

若一台 Mainframe 管理多個 Channel，應共用對應的實體通訊 Worker，而不是每個 Channel 建立一個可能互相衝突的 VISA Session。

## 15.2 Command Queue

每台儀器應維持自己的 Command Queue。

區分：

- Monitoring Queries
- Setpoint Configuration
- Output Control
- Remote / Local Control
- Screenshot
- Connection Check

操作指令原則上高於一般監控輪詢。

但實際 SCPI Query / Response 交易必須完整結束，才能處理下一條命令。

禁止不同 Thread 同時操作相同的 VISA Session。

## 15.3 Timeout 與錯誤處理

必須處理：

- VISA Timeout
- USB Disconnect
- Ethernet Disconnect
- SCPI Error
- Unexpected Response
- Invalid Measurement
- Resource Busy
- Device Not Found

要求：

- 單台儀器異常不能中斷其他設備。
- 錯誤發生時保留最後有效數據及時間戳記。
- 過期數據標示為 Stale。
- Output State 無法確認時標示 Unknown。
- 控制命令不能無限制自動重試。
- 重新連線不得自動重新開啟輸出。
- 關閉程式時要妥善停止 Worker 並釋放 VISA Session。

---

# 16. 儀器 Driver API

建立共用 BaseInstrument。

建議介面：

```python
class BaseInstrument:
    def connect(self): ...
    def disconnect(self): ...
    def identify(self): ...

    def get_capabilities(self): ...
    def get_connection_status(self): ...

    def read_measurements(self): ...
    def get_output_state(self): ...
    def get_remote_state(self): ...

    def get_setpoints(self): ...
    def set_voltage(self, value): ...
    def set_current(self, value): ...
    def set_frequency(self, value): ...
    def set_mode(self, mode): ...

    def output_on(self): ...
    def output_off(self): ...
```

針對示波器：

```python
def capture_screenshot(self): ...
```

這些只是共用的 API 設計方向。

不要求所有儀器都支援全部方法。

每台儀器必須透過 Capabilities 告訴 GUI：

- 支援哪些 Measurements。
- 支援哪些 Setpoints。
- 支援哪些 Modes。
- 是否支援 Output ON/OFF。
- 是否支援 Remote/Local。
- 是否支援 Screenshot。
- 是否支援 Setpoint Readback。
- 各參數的有效設定範圍。

不支援的功能在 GUI 中應隱藏或 Disabled。

---

# 17. Real Mode 與 Demo Mode

為了允許在沒有全部實體設備的開發電腦上進行 GUI 測試，必須提供兩種模式。

## 17.1 Real Instrument Mode

實際透過 PyVISA 與設備通訊。

所有數值必須來自真實設備。

當設備斷線或查詢失敗時，不允許自動使用模擬數據代替。

## 17.2 Demo Mode

建立模擬儀器 Driver。

模擬：

- 設備連線。
- 電壓、電流、功率變化。
- Output ON/OFF。
- Setpoint 設定。
- Remote/Local 狀態。
- Timeout。
- Disconnect。
- Screenshot Preview。

畫面必須明確顯示 DEMO MODE。

Demo Mode 可以用來測試功能及 GUI，但不能作為硬體通訊相容性的驗證結果。

---

# 18. 建議專案資料夾結構

```text
ate-workbench/
│
├── main.py
├── pyproject.toml
├── requirements.txt
├── README.md
├── .gitignore
│
├── app/
│   ├── __init__.py
│   │
│   ├── gui/
│   │   ├── main_window.py
│   │   ├── connection_page.py
│   │   ├── monitoring_page.py
│   │   ├── themes/
│   │   └── widgets/
│   │       ├── device_card.py
│   │       ├── measurement_display.py
│   │       ├── setpoint_control.py
│   │       ├── output_control.py
│   │       └── trend_plot.py
│   │
│   ├── core/
│   │   ├── instrument_manager.py
│   │   ├── instrument_worker.py
│   │   ├── command_queue.py
│   │   ├── data_manager.py
│   │   ├── measurement_buffer.py
│   │   └── models.py
│   │
│   ├── drivers/
│   │   ├── base.py
│   │   ├── chroma_61512.py
│   │   ├── chroma_66205.py
│   │   ├── rigol_dm3058e.py
│   │   ├── chroma_6312a.py
│   │   ├── chroma_63210a.py
│   │   └── tek_mso44b.py
│   │
│   ├── services/
│   │   ├── visa_service.py
│   │   ├── config_service.py
│   │   ├── screenshot_service.py
│   │   └── logging_service.py
│   │
│   └── demo/
│       ├── mock_instruments.py
│       └── demo_data.py
│
├── config/
│   ├── instruments.json
│   └── application.json
│
├── docs/
│   ├── instruments/
│   ├── SCPI_COMMAND_REFERENCE.md
│   ├── architecture.md
│   └── hardware_validation.md
│
├── logs/
├── data/
└── tests/
    ├── test_drivers.py
    ├── test_scpi_parser.py
    ├── test_instrument_manager.py
    ├── test_worker.py
    ├── test_polling.py
    └── test_gui.py
```

可依實際實作需求微調，但須保留模組化分層設計。

所有從網路下載的官方通訊文件必須確實保存在工作區的 `docs/instruments/` 目錄。

---

# 19. 設定檔設計

建立 `config/application.json`。

預設包含：

```json
{
  "application": {
    "theme": "dark",
    "default_mode": "real"
  },
  "acquisition": {
    "default_poll_interval_ms": 1000,
    "gui_refresh_interval_ms": 1000,
    "buffer_duration_seconds": 600,
    "polling_overrun_warning": true
  },
  "communication": {
    "default_timeout_ms": 3000,
    "auto_reconnect": false,
    "command_logging": true
  },
  "monitoring": {
    "default_trend_window_seconds": 60,
    "max_trend_window_seconds": 600
  }
}
```

上述為軟體預設值。

儀器特殊 Timeout、Terminator、Resource、Polling Interval 應儲存在各設備設定中。

Timeout 及通訊格式仍以設備規格書為準。

## 19.1 instruments.json

需支援保存：

- Device ID
- Device Name
- Manufacturer
- Model
- Driver Name
- VISA Resource
- Connection Type
- Polling Interval
- Timeout
- Channel Configuration
- Software Safety Limits

不得在設定檔內保存不必要的帳號密碼。

重新啟動應用程式可以恢復設備清單與設定，但不得自動恢復 Output ON 狀態。

---

# 20. 自動化測試要求

使用 pytest 撰寫必要測試。

至少包含：

1. Driver Capabilities 測試。
2. SCPI Response Parser 測試。
3. Measurement 單位與格式測試。
4. VISA Timeout 模擬。
5. USB / Ethernet 斷線模擬。
6. QThread Worker 生命週期測試。
7. 多儀器並行輪詢。
8. 同一儀器命令序列化。
9. 1 Hz Polling 排程測試。
10. Ring Buffer 測試。
11. Output ON/OFF 狀態管理。
12. Setpoint 範圍檢查。
13. Remote / Local 狀態管理。
14. GUI 與 Driver 隔離測試。
15. Screenshot Binary Data 處理。
16. CSV 資料儲存。
17. 程式關閉時資源釋放。

必要時使用 Mock VISA Session，避免測試依賴實體儀器。

測試程式不能在未知硬體狀態下自動開啟真實儀器輸出。

---

# 21. 第一階段驗收標準

## 21.1 GUI

- 程式可正常啟動。
- 兩個頁面可以切換。
- Dark Theme 正常。
- 多台設備卡片可以同時顯示。
- GUI 不會因為 VISA Timeout 卡住。
- 數字及曲線以約 1 Hz 更新。
- 可顯示每個設備的最後更新時間。
- 可顯示通訊異常及資料失效狀態。

## 21.2 儀器連線

- 能列出可用 USB VISA Resources。
- 可以手動新增 Ethernet 設備。
- 可以執行 Connection Test。
- 可以讀取支援的設備識別資訊。
- 可以顯示 Round-Trip Latency。
- 可以保存儀器連線設定。
- 單一設備連線失敗不影響其他設備。

## 21.3 儀器監控

- 所有支援設備能按照 Driver Capabilities 顯示量測參數。
- 目標 Polling Rate 為 1 Hz。
- 各設備的數據互不混淆。
- 數據具備時間戳記。
- 可繪製電壓、電流及功率趨勢。
- 長時間執行後 Buffer 不會無限制成長。

## 21.4 基本控制

- AC Source 能設定輸出電壓及頻率。
- DC Load 能設定 CC 負載電流。
- Output ON/OFF 能獨立操作。
- 能區分設定值與量測值。
- Remote Mode 下能使用已支援的 GUI 控制功能。
- 不支援的控制功能會 Disabled。
- 超出安全限制時禁止下發設定。
- 不因為連線或重新啟動程式而自動開啟輸出。

以上控制驗收僅在原廠規格書確認支援的設備上實施。

## 21.5 示波器

- 可以建立 Ethernet 通訊。
- 可以執行手動 Capture Screenshot。
- 可以顯示擷取圖片。
- 不需要讀取 Raw Waveform。
- Screenshot 操作不影響其他設備監控。
- 不改變原有示波器 Trigger 設定。

## 21.6 長時間穩定性

Demo Mode 需能連續運作至少 1 小時。

測試期間確認：

- 無 GUI 凍結。
- 無 Worker Thread 異常。
- 無持續性的記憶體增長。
- 無未處理例外。
- 資料更新與時間戳記正常。
- 可正常關閉程式。

實體設備的 1 小時穩定性測試必須另外記錄，不能以 Demo Mode 測試代替。

---

# 22. 實作順序

請按照以下順序完成。

### Phase 1 — Workspace Inspection

1. 檢查現有專案。
2. 搜尋通訊規格書。
3. 檢查 Python 與 VISA 環境。
4. 確認可用文件及缺少的內容。

### Phase 2 — Documentation

1. 讀取現有官方文件。
2. 搜尋缺少的官方通訊手冊。
3. 下載並保存至本地。
4. 建立 SCPI Command Reference。
5. 建立各儀器 Capabilities 清單。

### Phase 3 — Core Architecture

1. 建立 PyVISA Service。
2. 建立 BaseInstrument。
3. 建立 Instrument Manager。
4. 建立 Worker / Command Queue。
5. 建立 Measurement Data Model。

### Phase 4 — Instrument Drivers

依官方通訊規格書實作各設備 Driver。

優先完成：

1. Chroma 61512
2. Chroma 66205
3. RIGOL DM3058E
4. Chroma 6312A / 63106A
5. Chroma 63210A
6. Tektronix MSO44B

若某設備缺少文件，不要因此中止其他設備的實作。

### Phase 5 — Instrument Connection GUI

完成：

- VISA Resource Scan
- Add Instrument
- Connect / Disconnect
- Test Connection
- Communication Benchmark
- Device Configuration

### Phase 6 — Monitoring Dashboard GUI

完成：

- Instrument Cards
- Measurement Displays
- 1 Hz Polling
- PyQtGraph Trends
- Setpoint Controls
- Remote / Local Management
- Output ON/OFF
- Screenshot Preview

### Phase 7 — Demo & Tests

完成：

- Demo Instrument Drivers
- Mock VISA Tests
- GUI Tests
- Polling Tests
- Command Queue Tests
- Safety Checks
- Long-Run Test

### Phase 8 — Documentation & Delivery

完成：

- README
- Installation Guide
- Architecture Document
- SCPI Reference
- Hardware Verification Checklist
- Known Limitations
- Test Results

---

# 23. 最終交付要求

完成後，請提供：

1. 可執行的完整 Python 專案。
2. 完整的 PySide6 GUI。
3. Instrument Connection 頁面。
4. Monitoring Dashboard 頁面。
5. 所有已確認規格的儀器 Driver。
6. PyQtGraph 量測趨勢圖。
7. 基本 Remote Output Controls。
8. 示波器 Screenshot 功能。
9. 1 Hz 資料採集機制。
10. Demo Mode。
11. 自動化測試。
12. 工作區通訊規格書整理及本地下載結果。
13. Windows 11 安裝與執行說明。

最後以繁體中文整理：

### A. 功能完成狀態

區分：

- Completed
- Partially Completed
- Pending Hardware Verification
- Blocked
- Unsupported

### B. 儀器 Driver 狀態

建立表格：

| 儀器 | 文件 | 連線 | 監控 | 控制 | 實機驗證 |
|---|---|---|---|---|---|

### C. 官方文件取得結果

列出：

- 原本已存在工作區的文件。
- 從網路搜尋取得的文件。
- 已下載至本地的文件。
- 缺少的文件。
- 無法確認的 SCPI 指令。

### D. 測試結果

列出：

- 自動化測試通過數量。
- Demo Mode 驗證結果。
- GUI 啟動及運作結果。
- 1 Hz Polling 測試結果。
- 尚未進行的實體儀器測試。

### E. 下一步建議

列出最優先需要進行的實際硬體驗證項目。

---

# 24. 最重要的開發限制

1. **所有 SCPI 指令必須依照工作區規格書或可信官方通訊文件。**
2. **缺少通訊文件時才上網搜尋，並將取得的官方文件下載保存至本地。**
3. **不可猜測 SCPI 指令、通訊參數、量測回應或輸出狀態。**
4. **儀器 I/O 不得阻塞 GUI 主執行緒。**
5. **同一儀器只能由自己的 Worker 序列化操作。**
6. **數值採集與 GUI 更新預設均為 1 Hz。**
7. **AC Source 必須支援基本電壓／頻率及 Output 控制。**
8. **DC Load 必須支援 CC 電流設定與 Load ON/OFF。**
9. **示波器只需要手動 Screenshot，不需要 Raw Waveform。**
10. **不允許連線、初始化或重新連線後自動開啟輸出。**
11. **GUI 必須區分 Setpoint、Actual Measurement 與 Actual Output State。**
12. **Demo Mode 與 Real Mode 必須完全區分。**
13. **無法進行實機驗證時，不得宣稱已完成硬體測試。**
14. **本階段只建立兩個主要功能頁面，不擴充不必要的功能。**
15. **遇到部分儀器文件或通訊問題時，應繼續完成其他可實作功能，最後集中列出阻礙與待驗證事項。**

請現在開始檢查 Codex 工作區，依上述階段直接完成可運作的第一版 ATE 系統。