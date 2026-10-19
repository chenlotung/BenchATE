# Driver Capabilities

Capabilities 是 GUI 顯示與控制可用性的來源；真實 driver 不依賴 Qt。
以下是 Documented / Implemented 的軟體範圍，所有儀器皆未做 Hardware Verified。

| Driver | Measurements | Setpoints / modes | Output readback | Remote / Local | Screenshot |
|---|---|---|---|---|---|
| chroma_61512 | V RMS, A RMS, W, Hz | 0..300 V / 0.1 V；15..1500 Hz / 0.01 Hz；SINGLE/FIXED/AC | OUTP? | LAN 未確認，Disabled；Unknown | — |
| chroma_66205 | V, A, W, VA, PF, Hz；實際 MEAS mode 同時顯示 | 不改既有量測設定 | — | USB 請求支援；無實際狀態查詢，Unknown | — |
| rigol_dm3058e | Function 對應的 V/A/ohm/Hz/s/F | 不改 Function/trigger | — | 未確認，Disabled | — |
| chroma_6312a | 各 63106A 通道 V/A/W | CCL 0..12 A / 0.003 A；CCH 0..120 A / 0.03 A；L1=L2 | LOAD? per selected channel | USB 無已確認指令，Disabled | — |
| chroma_63210a | V/A/W | 下表三段 CC；L1=L2 | LOAD? | SYST:REM/LOC 請求；狀態 Unknown | — |
| tek_mso44b | 不參與週期數值輪詢 | — | — | 未確認，Disabled | 手動 PNG |

## 63210A 型號專屬範圍

| 完整型號 | CCL 最大值 / 解析度 | CCM 最大值 / 解析度 | CCH 最大值 / 解析度 | 手冊 PDF |
|---|---|---|---|---|
| 63210A-150-1000 | 100 A / 1 mA | 500 A / 5 mA | 1000 A / 10 mA | 25 / 1-5 |
| 63210A-600-700 | 70 A / 0.5 mA | 350 A / 2.5 mA | 700 A / 5 mA | 29 / 1-9 |
| 63210A-1200-400 | 40 A / 0.4 mA | 200 A / 2 mA | 400 A / 4 mA | 33 / 1-13 |

程式另查詢活動模式的 CURR:STAT:L1? MIN/MAX。不同型號的範圍不互相套用。
GUI 使用最細解析度輸入，driver 仍按實際所選 CC 檔位再次檢查，不默默捨入。

## 安全限制與狀態

- 沒有既有安全限制時，對話框預設為參數最小值到最小值，不預設硬體最大值。
- 保存軟體限制值，不保存使用者核可狀態。每次新連線重新批准。
- Output ON 使用實際回讀設定值，必須落在批准範圍及活動硬體範圍；需要明確確認。
- Apply 回讀不一致即報錯；Timeout 不重送，實際輸出狀態 Unknown。
- 6312A 的通道資料、輸出回讀與時間戳記分開；只有一個 mainframe worker。
- 兩個靜態負載 level 同時設成相同電流是 V1 的明確控制策略，不宣稱已查詢活動 A/B level。
- 不支援的 remote-state query 不會被猜測；送出 Remote 不等於確認 Remote。
- 量測新樣本識別與 SCPI 讀取頻率分開；66205 的設定更新週期不當作已驗證的新樣本速率。
