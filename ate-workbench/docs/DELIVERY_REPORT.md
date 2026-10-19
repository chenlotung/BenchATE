# ATE Workbench V1 交付報告

日期：2026-10-19（Asia/Taipei）。所有軟體測試使用 Demo / Mock VISA；沒有操作實體儀器。
依使用者後續要求，**跳過 1 小時測試**。短時間執行紀錄不代表 1 小時通過。

## A. 功能完成狀態

| 狀態 | 內容 |
|---|---|
| Completed | Python 分層專案、兩個 Qt Widgets 頁面、Dark/Light、一鍵 USB 掃描辨識並連線、確切型號 allowlist、Scope/AC 可選 IP（空白跳過）、已連線設備清單、背景連線/識別/benchmark、每實體儀器獨立 Worker、主機框共用 session、1 Hz 排程、V/A/W 趨勢、CSV、有界 buffer、Demo 與故障注入 |
| Completed | 軟體限制每次連線重新批准、Desired / Readback / Measurement 分離、Output ON 明確確認、OFF 取消舊 ON/Apply、通訊失敗 quarantine、Stale/Unknown、關閉時釋放資源 |
| Partially Completed | 各設備基本控制依已確認文件實作；61512 限 SINGLE/FIXED/AC；Remote/Local 僅支援明確有文件的介面，不能確認的狀態顯示 Unknown |
| Pending Hardware Verification | 全部真實設備的連線、回應格式、量測、輸出及截圖相容性；韌體差異與 USB remote 行為 |
| Blocked | 本機未偵測到 VISA native backend；未提供已連線實體設備供驗證。此限制不影響 Demo / Mock 測試 |
| Unsupported / Disabled in V1 | 未確認的 USB-Serial、LAN/USB 專用 remote 指令、RIGOL 雙顯示/未知模式、DC Load 非 CC 控制；不臆測指令 |
| Skipped at user request | 1 小時 Demo / 實機穩定性測試 |

## B. 儀器 Driver 狀態

| 儀器 | 文件 | 連線 | 監控 | 控制 | 實機驗證 |
|---|---|---|---|---|---|
| Chroma 61512 | 本地 v1.7 / 2021-03 | TCP Socket 2101，*IDN? | 快取 V/I/P/f | SINGLE/FIXED/AC 電壓/頻率與 Output，回讀及限制檢查；LAN Remote/Local 停用 | Pending |
| Chroma 66205 | 本地 v1.5 / 2025-04 | USB，*IDN? | 六項批次 FETCh，更新週期/平均次數/模式查詢 | USB Remote/Local request；actual state Unknown；不改量測配置 | Pending |
| RIGOL DM3058E | 官方 PDF，2021-11 | USB，*IDN? | 依 :FUNC? 取得單顯示讀值與正確單位 | 不改 Function/trigger | Pending |
| Chroma 6312A / 63106A | 本地 v2.0 / 2022-05 | 主機一個 USB session，inventory + module ID | CH1/CH3 個別 V/I/P、Load、readback | CCL/CCH、L1=L2、Load ON/OFF；USB Remote/Local 停用 | Pending |
| Chroma 63210A | 本地 v2.4 / 2025-03 | USB；嚴格比對完整三種型號後綴 | V/I/P、Load、readback | CCL/CCM/CCH、L1=L2、Load、Remote/Local request | Pending |
| Tektronix MSO44B | 本地 077189805 / 2026-09 | 已啟用 VXI-11，*IDN? | 不參與數值輪詢 | 手動 PNG、原生 save/read/delete、預覽；不改 trigger/acquire | Pending |

## C. 原廠文件取得結果

既有文件沿用 repo 根目錄的 `datasheet/`，不重複下載：

1. TC_61511_61512_UserManual_202103.pdf
2. TC_66205_UserManual_202504.pdf
3. TC_6310A_OperationProgrammingManual_202205.pdf
4. TC_63200A_OperationProgrammingManual_202503.pdf
5. 4-5-6-Series-MSO_Programmer_077189805.pdf

新增官方文件：`docs/instruments/rigol_dm3058e/Programming_Guide_DM3058.pdf`，由 RIGOL 官方產品頁的下載連結取得，PDF 封面及摘要明確適用 DM3058/DM3058E。

六組 `source.md` 均記錄版本、日期、來源、SHA-256、使用範圍。86 筆 SCPI 對照表記錄參數、回應、原始文件與 PDF/章節頁碼；來源連結與六份 checksum 均經本機檢查。
既有 Chroma 文件的原始下載網址未知，來源記錄維持「工作區提供」，不偽造直接下載網址。

尚未確認：61512 LAN remote/local、6312A USB remote/local、實際 remote state query、USB-Serial 組態、RIGOL 雙顯示狀態的回應格式、66205 硬體新樣本 ID。未確認的命令不送出。

## D. 測試與可攜式交付

- 自動化測試：**112 passed**；JUnit：`docs/validation/pytest.xml`。
- 最終驗收（2026-10-19）：本地 commit 前重新執行完整測試、原始碼 / EXE 短測與 release 校驗，全部通過。彙整：`docs/validation/final_verification.json`。
- 原始碼結構整併：`app/` 的 35 個 Python 檔案 / 7 個套件目錄收斂為 19 個檔案 / 3 個套件目錄；63 個類別與函式的 AST 比對一致（只更新匯入路徑），另修正設定模組搬移後的專案根目錄定位。原始證據：`docs/validation/source_structure.json`。
- 測試涵蓋 parser/單位、model/capabilities、範圍/解析度、readback mismatch、主機框通道隔離、VISA timeout/斷線、1 Hz 與多設備、同 session 序列化、queue 安全、RM lease、binary PNG、CSV、buffer、GUI 分層、頁面共用 session、Worker/CSV 關閉。
- 新增掃描測試：確切 vendor/model 過濾、通用型號排除、未知設備不列入、timeout 後繼續、63106A inventory、兩個 IP 獨立留白/無效處理、已列舉 LAN 不繞過空白欄位、一鍵自動連線、重複掃描維持原 session、保存偏好只在辨識後恢復、背景掃描心跳與取消。Mock native VISA 完整走過「probe 關閉 → 正式連線 → 重掃不開第二個 session」。
- 原始碼 Demo 一鍵掃描連線短測：**20.036 秒**，6 組設備/channel 各 20–20 筆；無錯誤，截圖收到，Worker/CSV 釋放成功；GUI 心跳最長間隔 0.125 秒。
- GUI 實際畫面：`connection_dark.png`、`connection_light.png`、`dashboard_dark.png`、`scope_preview.png`，均位於 `docs/validation/`。
- Windows x64 可攜式資料夾與 ZIP 已建立；內含 EXE、Python DLL、Qt、PyQtGraph、NumPy、PyVISA、預設設定、使用 / 安裝 PDF 及依賴授權檔。
- Release 改為使用者發行包：只含 EXE / 依賴、預設設定、啟動捷徑、NI-VISA 安裝程式、快速使用 / NI-VISA 安裝 PDF 及必要授權。架構、原始碼、SCPI 表、原廠通訊手冊、測試 / 交付報告與截圖只留在專案；以白名單及乾淨 staging 目錄打包，避免更新文件時夾帶舊檔。
- 解壓後 EXE 一鍵掃描連線驗證 **Passed**：20.004 秒、6 組設備/channel 各 20 筆、GUI 心跳最長間隔 0.127 秒、無錯誤、PNG 收到、Worker/CSV 全部釋放、exit code 0。使用不同的含中文/空白路徑，從 PATH 移除 Python，ZIP CRC 與 manifest 全部 SHA-256 通過。原始證據：`docs/validation/portable_smoke.json`。
- Release PDF 驗證：22 份 PDF（2 份使用 / 安裝指南，其餘為必要授權）檢查通過、3 個本地 PDF 連結有效。確認開發文件與通訊手冊均未放入 ZIP，逐頁預覽無缺字、裁切或空白頁。記錄：`docs/validation/release_pdf_checks.json`。
- 未在另一台乾淨 Windows VM 驗證；不宣稱硬體相容或跨機環境已完成測試。
- 1 小時測試：依使用者要求 **Skipped**；保留的中斷紀錄不視為通過。

可攜式包：`releases/ATEWorkbench-0.1.0-windows-x64.zip`。同名 `.sha256` 為 ZIP 校驗碼；`manifest.json` 為包內各檔案 SHA-256。
ZIP 與 `.zip.sha256` 均納入 Git repo，README 提供直接下載連結；建置暫存、虛擬環境及解壓執行目錄仍不納入。
解壓後執行 `Start Demo.cmd`；`ATEWorkbench.exe` / `Start Real.cmd` 預設 Real Mode。

## E. 優先實機驗證

1. 安裝 x64 NI-VISA 或相容 backend，確認 USBTMC / VXI-11 資源與實際儀器完整型號、序號、韌體。
2. Scope / AC Source 可分別輸入 IP，留白跳過；按 Scan & Connect，核對確切型號過濾、IDN、termination、量測回應與單位；確認 6312A 的 slot/channel/inventory。
3. 以低能量 DUT 條件明確批准軟體限制，逐台驗證 AC voltage/frequency、CC L1/L2、readback、Output/Load ON/OFF。
4. 檢查 Timeout/拔線後的實體輸出與前面板狀態；軟體 Unknown 不代表實體已停止輸出。
5. 對 MSO44B 確認 VXI-11、PNG、OPC 行為與暫存檔清理；另記錄真實設備穩定性結果。
