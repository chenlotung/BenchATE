# NI-VISA 26.8 安裝與組件選擇（ATE Workbench）

> 歷史文件：此指南僅適用 main 的 NI-VISA 版本，不適用 codex/pyvisa-py-backend 分支。新分支請見 [pyvisa-py 通訊指南](PYVISA_PY_zh-TW.md)，發行包不附 NI 安裝器。

本指南對應你提供的 `ni-visa_26.8_online.exe`，適用於本專案 Windows 11 x64 可攜式版本。文件核對日期：2026-10-19。

## 先照這份清單選

在 NI Package Manager 的「Additional items you may wish to install」頁面，採用下列選擇。若某項已安裝、由相依套件自動帶入，或未獨立列出，不需另外尋找同名勾選框。

| 畫面項目／功能 | 本專案建議 | 用途 |
|---|---|---|
| NI-VISA / NI-VISA Runtime | **必要，保留** | 提供 PyVISA 使用的原生 VISA 通訊；成品需要 x64 library。 |
| NI-VISA Configuration Support | **勾選** | 讓 NI MAX 設定、檢查 VISA 資源；本指南的驗收流程會使用。 |
| NI Measurement & Automation Explorer（NI MAX） | **保留；若獨立列出則勾選** | 查看 USB 儀器、建立 LAN 資源及開啟測試面板。 |
| NI-VISA Interactive Control | **建議勾選** | 用測試工具單獨確認 `*IDN?`，方便區分驅動與程式問題。 |
| NI I/O Trace | **選用，建議初次安裝保留** | 追蹤 VISA 呼叫與 timeout；不影響程式基本執行。 |
| NI Certificates Installer、NI Package Manager，以及安裝器要求的共用 runtime／相依套件 | **保留預設／必要項目** | 交由安裝器處理相依性，不要強制取消必需項目。 |
| NI-VISA .NET Development Support / .NET Runtime | **不需主動加選** | 程式透過 PyVISA 呼叫原生 VISA，未使用 NI-VISA .NET API；若其他套件需要則保留。 |
| NI-VISA Support for LabVIEW、LabVIEW Runtime、LabWindows/CVI Support / Examples、C Examples | **不需主動加選** | 執行本專案不需要這些開發環境或範例；若為必要相依性則保留。 |
| NI-VISA Driver Development Wizard | **不需勾選** | 本專案不建立自訂 USB RAW／PXI VISA driver。 |
| NI-VISA Server / Remote Server | **不需勾選** | 本機直接連 USB 或儀器 LAN；MSO44B 的 VXI-11 server 位於儀器端，與此項不同。 |
| NI-488.2、NI PXI Platform Services、NI-Serial、Real-Time 支援 | **不需主動加選** | 目前使用 USBTMC、TCP Socket、VXI-11，沒有 GPIB／PXI／RT／ASRL 使用需求；必要相依性仍保留。 |

**建議組合：NI-VISA Runtime + Configuration Support / NI MAX + Interactive Control；I/O Trace 可一併保留。** 不必按 Select All，也不要 Deselect All 後漏掉 Configuration Support。

這是依本專案程式碼與 NI 官方功能文件整理的選擇表，並非宣稱已操作此安裝器的每一個畫面。線上套件清單會受已安裝軟體、語言及 NI feed 影響；項目名稱、排列與可選狀態以實際安裝畫面為準。

## 本次安裝檔的版本與身分

| 檢查項目 | 實際結果 |
|---|---|
| 檔案 | `installers/ni-visa_26.8_online.exe`（相對於解壓後的 ATEWorkbench 資料夾） |
| 大小 | 9,002,792 bytes |
| EXE FileVersion / ProductVersion | `26.8.0f128` |
| EXE ProductName | `NI Package Manager` |
| 內嵌安裝目標 | `ni-visa_26.8`，URI：`nipkg://store/1/install-item/ni-visa_26.8` |
| Windows Authenticode | 本機檢查為 `Valid`，簽署者為 National Instruments Corporation |
| SHA-256 | `00e3a6fe2d9609972983f44812fd33b468935480f82d6a98f27d4dd590b58e0f` |

`26.8.0f128` 是這支 NI Package Installer 的檔案版本。此 EXE 內嵌目標確認為 `ni-visa_26.8`；**實際安裝的 NI-VISA runtime 與共用套件完整版本，仍須在安裝摘要及完成後的 NI Package Manager Installed 頁面核對**，不能把安裝器版本直接視為每個驅動 DLL 的版本。

這是 **online installer**，ZIP 內附的是原始線上安裝器，不是完整離線套件。安裝時需要連上 NI 套件來源；離線電腦請預先從 NI 官方下載頁使用 Install Offline 取得完整媒體。

## 安裝步驟

1. 解壓整份 release ZIP 到可寫入的資料夾，例如 `D:\LabTools\ATEWorkbench`。關閉 ATE Workbench 與其他正在使用儀器的程式。
2. 確認 Windows 11 x64、可使用管理員權限且可連上 NI 下載服務。若已有其他 VISA 實作，先記下目前使用的 backend 與版本，方便安裝後確認。
3. 執行 `installers\ni-visa_26.8_online.exe`，依 Windows 提示允許安裝。需要時先完成 NI Package Manager 安裝，再繼續 NI-VISA。
4. 在主產品與 Review 摘要確認目標是此安裝器指定的 NI-VISA；保留 NI-VISA runtime。若畫面有應用程式位元數選項，確保包含 **64-bit / x64**；同時安裝 x86 相依套件是正常情況。
5. 在 Additional items 頁面依上表勾選，尤其是 **NI-VISA Configuration Support**、NI MAX 與 Interactive Control。若只裝 runtime，程式可能能通訊，但缺少本指南使用的 MAX 設定／診斷功能。
6. 檢閱授權、下載大小與安裝摘要後完成安裝。若安裝器要求重新啟動，先重開機再接續驗收。
7. 在 NI Package Manager 的 Installed 頁面確認 NI-VISA runtime 與 Configuration Support 已安裝，記下實際版本。開啟 NI MAX 確認工具可正常使用。
8. 依下一節逐台確認儀器，再執行 `Start Real.cmd`。Demo 模式不需要 NI-VISA，不能用 Demo 成功來判斷驅動安裝完成。

不要因安裝器本身是 x86 bootstrapper 就改裝 32-bit ATE Workbench；要與本成品匹配的是最終安裝的 **x64 VISA library**。

## USB 與 Ethernet 要哪些功能

需要 **USB（USBTMC / USB488）** 與 **TCP/IP（Socket、VXI-11）**。若安裝畫面另有介面功能選項，保留 USB 與 TCP/IP；它們可能由 runtime 一併安裝，不一定是獨立勾選框。

| 儀器 | 本專案介面 | 安裝後確認 |
|---|---|---|
| Chroma 66205 | USB Device | 在 MAX 看到對應 USB VISA resource。 |
| RIGOL DM3058E | USB Device | 使用 USB Device 埠；必要時依 RIGOL 官方 driver／UltraSigma 指引處理裝置驅動。 |
| Chroma 6312A / 63106A | 主機選購 USB 通訊卡 | 連主機 USB，主機只建立一筆資源；63106A 模組不是獨立 USB 設備。 |
| Chroma 63210A | 遠端 USB Device | 不使用前面板的 USB Host 儲存埠。 |
| Chroma 61512 | LAN TCP Socket，port 2101 | 手動新增 `TCPIP0::192.168.1.101::2101::SOCKET`，IP 改為實機。 |
| Tektronix MSO44B | LAN VXI-11 | 在示波器啟用 VXI-11，使用 `TCPIP0::192.168.1.102::inst0::INSTR`，IP 改為實機。 |

本版未開放 ASRL 指派；USB-to-Serial 不能直接當作上述 USBTMC 資源。GPIB-USB 轉接器則屬 GPIB，若日後使用 NI GPIB 硬體需要相容的 NI-488.2，不能只靠 USBTMC 支援。

## 安裝後的驗收

1. USB：用可傳資料的線連接 USB Device 埠，確認 Windows 裝置管理員沒有驅動錯誤，再到 NI MAX → My System → Devices and Interfaces 找 USB VISA resource。
2. LAN：確認電腦與儀器的 IP／子網及服務設定。可在 MAX 依上表建立資源並測試；應用程式只需填入 Scope IP 或 AC Source IP。欄位空白會跳過該台，不會搜尋整個 LAN。
3. 在 NI MAX 的 VISA Test Panel／Interactive Control 開啟對應資源，依儀器設定 termination 後只查詢 `*IDN?`，確認回覆與機身型號一致。61512 使用 2101，勿改用未經手冊確認的 5025。
4. 關閉測試面板，避免占用同一資源。開啟 `Start Real.cmd` → Instrument Connection；需要連線 Scope / AC Source 時分別填入 IPv4，然後按 **Scan & Connect**。USB 設備會自動掃描辨識，只加入支援型號，不必指定 driver 或 VISA resource。
5. 看到正確識別、Connected 與 latency，接著 Start Monitoring，確認量測更新。僅查詢即可完成連線驗收，不需 Output ON／Load ON。

## 常見問題

- **程式找不到 VISA library**：確認已安裝 x64 VISA runtime 並依安裝器要求重開機。`config/application.json` 的 `communication.visa_backend` 預設空字串，交由 PyVISA 選擇；若有多家 VISA 並存，先確認實際載入來源，必要時指定已確認的 NI x64 VISA DLL 完整路徑。JSON 中的路徑反斜線需寫成 `\\`；不要把 NI-VISA 產品名稱當成 PyVISA backend 代號。
- **MAX 看不到資源**：先確認 **NI-VISA Configuration Support** 有裝。若是 USB，再查實體連接埠、線材、USB 通訊卡及原廠驅動；Windows 看得到裝置不等於已建立 VISA resource。可透過 NI Package Manager 修改 NI-VISA 補裝組件。
- **LAN timeout**：確認 IP、2101 Socket 或 VXI-11 協定、儀器 server、termination 與允許的防火牆規則。VXI-11 不只使用單一固定 TCP port；不要把停用整個防火牆當作正常安裝步驟。
- **MSO44B 查詢可用但截圖 timeout／程式異常**：NI 官方記錄 NI-VISA 2026.x 的 VXI-11 bounded-read 問題，可能影響分段讀取或二進位截圖。請核對實際安裝的 runtime 版本是否已修正，並測試實機截圖。可記錄 NI I/O Trace，依 NI 官方問題文件／修正資訊處理；`*IDN?` 成功不代表截圖傳輸一定正常。

## 官方文件

- [NI-VISA 官方下載／Install Offline](https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html)
- [NI：Configuration Support 與 MAX 資源偵測](https://knowledge.ni.com/KnowledgeArticleDetails?id=kA00Z000000P6soSAC&l=en-US)
- [NI：NI-VISA 功能與作業系統相容性](https://www.ni.com/en/support/documentation/compatibility/17/ni-visa-features-and-operating-system-compatibility.html)
- [NI：.NET 支援安裝說明](https://knowledge.ni.com/KnowledgeArticleDetails?id=kA00Z000000P9fESAS&l=en-US)
- [NI：GPIB-USB-HS 需要 NI-488.2](https://knowledge.ni.com/KnowledgeArticleDetails?id=kA0VU000000CFT70AO&l=en-US)
- [NI：NI-VISA 2026.x VXI-11 讀取問題](https://knowledge.ni.com/KnowledgeArticleDetails?id=kA0VU000000F5CH0A0&l=en-US)
- [PyVISA：安裝與原生 VISA library](https://pyvisa.readthedocs.io/en/stable/introduction/getting.html)
