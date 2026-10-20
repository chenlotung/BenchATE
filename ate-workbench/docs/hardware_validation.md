# 實機驗證清單

驗證狀態：**尚未進行任何實機測試**。執行者應填寫日期、序號、硬體型號、韌體、backend/driver 版本及測試結果。
僅經確認的命令可標記 Hardware Verified；不能以單元測試代替。

## 共用連線驗證

- [ ] `--check-backend` 顯示 pyvisa-py、USB/TCPIP 程式庫可載入；USB 裝置已綁定相容 WinUSB/libusb 驅動，記錄實際 driver provider、版本與硬體 ID，不以 NI MAX 測試代替。
- [ ] 掃描不改輸出、量測模式或 trigger；記錄連線本身是否導致前面板 remote。
- [ ] 按 Scan & Connect 自動辨識並連線；只列入支援型號，其他品牌或同品牌其他型號均排除；核對 model/serial/firmware 與 latency。
- [ ] Scope / AC Source IP 各自空白時跳過；兩欄空白仍可連 USB，backend 枚舉出的 LAN 資源不會繞過跳過規則。
- [ ] 重複掃描不重新開啟已連線設備的 session；某台識別 timeout 不影響其他合格設備加入。
- [ ] 切換兩個頁面不重連、不 reset；不同儀器 session 並行且單一儀器交易不交錯。
- [ ] 單台拔線或 Timeout 只影響該台，保留最後數據時間並顯示 Stale/Unknown。
- [ ] 重新連線不自動恢復輸出；每次重新批准安全限制。
- [ ] Benchmark 與輪詢協調，100 次結果包含 average/min/max/P95/timeout/error count。
- [ ] CSV 時間/單位/通道與儀器前面板一致；磁碟失敗有可見錯誤。

## Chroma 61512

- [ ] 確認 Ethernet TCP 2101 / LF、IDN 的實際格式；若只回通用 61500，掃描應排除並記錄硬體限制，不推定為 61512。
- [ ] 確認 SINGLE / FIXED / AC；不以程式主動改這些模式。
- [ ] 核對 FETC:VOLT:AC? / CURR:AC? / POW:AC? / FREQ? 與前面板。
- [ ] 使用本次 DUT 允許的低能量限制，批准電壓與頻率，再 Apply 並核對 readback。
- [ ] 明確操作 Output ON；確認實際 OUTP?，再操作 OFF；不得把命令成功當成實際已關閉。
- [ ] 記錄 LAN remote/local 的實際行為；本版無未確認指令可測。

## Chroma 66205

- [ ] 核對 USB 介面與 SYST:REM / LOC 行為，不把 request 當 actual state。
- [ ] 核對 FETC? V,I,W,VA,PF,FREQ 的順序、separator、header、單位及錯誤 sentinel。
- [ ] 記錄 MEAS:UPD? / AVER? / MODE?；確認不同 integration/averaging 下的行為，保留原設定。
- [ ] 說明實際硬體新樣本速率是否可觀察；沒有 sample ID 就維持 unverified。

## RIGOL DM3058E

- [ ] 確認 RIGOL command set、單顯示，記錄 :FUNC? 實際回應。
- [ ] 逐項核對 DCV / ACV / DCI / ACI / 2WR / 4WR 的值與單位。
- [ ] 手動改 Function 時，不把前一功能數據顯示為新單位。
- [ ] 檢查超量程表示及量測期間模式變動；雙顯示保留待驗證。

## Chroma 6312A / 63106A

- [ ] 確認 USB 選購介面在 mainframe，記錄 *IDN? / *RDT? inventory。
- [ ] 確認 slot 1 / 2 的 63106A 對應 CH1 / CH3；CHAN:ID? 型號一致。
- [ ] 不同通道以不同負載條件核對 V/I/P 與各自 LOAD?，不得混資料。
- [ ] 切換通道後恢復原選台，不修改其他通道；故障時 quarantine 而非繼續寫入。
- [ ] 核對 CCL/CCH 的 MAX/MIN、12A/120A 與 3mA/30mA 解析度。
- [ ] 負載 OFF 時套用 CC、L1/L2，相等 readback 後才明確 Load ON；再 Load OFF。

## Chroma 63210A

- [ ] 核對完整後綴、韌體與 USB device 埠；排除非 A 或 Slave 型號。
- [ ] 按完整型號核對 CCL/CCM/CCH 電流範圍與解析度、MIN/MAX 回讀。
- [ ] 核對 MODE、L1/L2、LOAD?、V/I/P 與 SCPI error response。
- [ ] Load ON 時拒絕 mode change；測試批准限制、設定回讀與輸出狀態。
- [ ] 記錄 SYST:REM/LOC request 與前面板實際行為；沒有狀態 query 維持 Unknown。

## Tektronix MSO44B

- [ ] 核對韌體、已啟用的 VXI-11、*IDN?；不由程式啟用 server。
- [ ] 手動觸發後 Capture Screenshot，確認 PNG 與當下螢幕相符。
- [ ] 檢查 PNG 完整傳輸及 UUID 暫存檔清除；不下載 waveform、不改 trigger/run/stop。
- [ ] 在等待 trigger 時測試 OPC timeout；其他儀器輪詢不受阻塞。

## 長時間測試

- [ ] 實機 1 小時穩定性測試：另外取得使用者授權的測試條件後執行並記錄。
- [ ] Demo 1 小時：本次依使用者要求略過，不標記通過。
