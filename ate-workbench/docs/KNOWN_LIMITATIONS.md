# 已知限制

1. **所有硬體均 Pending Hardware Verification**。本分支使用 pyvisa-py，不載入本機 NI-VISA；沒有以本程式連接實體儀器，Mock / Demo 與 localhost 通訊測試不代表硬體相容。
2. **1 小時穩定性測試依使用者後續要求略過**。曾啟動的短暫執行保留原始數據，但不能標記為 1 小時通過。
3. 61512 控制限定 SINGLE phase、FIXED、AC；三相讀取可選擇/恢復 phase，三相輸出控制尚未建立完整 interlock。
4. 61512 以 Ethernet 使用時，不傳送僅限 RS232 的 SYST:REM/LOC。6312A USB 同樣不使用僅限 RS232 的 CONF:REM。
5. 支援的 Remote/Local request 若無原廠狀態查詢，實際狀態保持 Unknown。USB/VISA 連線可能使部分前面板進入 remote；實際行為需個別驗證。
6. RIGOL 僅支援 RIGOL command set 的單顯示模式；FUNC2:ON? 在此手冊沒有足夠回傳格式，暫不實作雙顯示。Continuity / sensor 模式也不猜單位。
7. 66205 FETCh 是快取數據；沒有 sample ID，不能辨識每次是否為新樣本。手冊的 -1/-2/-3 sentinel 與部分負值可能有歧義，本版保守標示 invalid，保留最後有效量測。
8. 6312A 掃描時從 inventory 自動選出 CH1/CH3 的 63106A 模組；沒有可確認的 63106A 就不加入。其他模組與非 A 系列不視為相容。
9. DC Load Apply 同時修改 L1/L2 為相同值；不支援獨立 A/B level、動態負載、測試序列或非 CC 模式。
10. MSO44B 先寫入儀器工作目錄的 UUID PNG，再下載和刪除；失敗時可能保留暫存檔供人工檢查。OPC 可能等待既有未完成的擷取，會依 timeout 中止，不改 trigger。
11. 單筆 SCPI query 進行中無法立刻取消；程式關閉會在該交易完成/timeout 後停止下一筆 I/O。Output OFF 不是硬體緊急停止。
12. 設定由多筆 SCPI 命令構成，通訊中斷可能只套用部分設定。程式不自動回滾或重送；必須查驗儀器後重新連線。
13. 圖表只繪製 V/A/W，分開 Y 軸；其餘量測顯示於卡片與 CSV。支援單一設備/channel、多種量測選擇與曲線開關。
14. 尚未在另一台乾淨的 Windows 11 電腦或 VM 實測。可攜性驗證是在本機解壓到不同路徑後直接執行 EXE。
15. 沒有 MSI、數位簽章、測試腳本編輯器、Pass/Fail 排程或報表產生器；這些不在本階段範圍。
16. 自動掃描只接受確切型號；61500 系列通用識別無法證明是 61512，因此不加入設備表。原始 driver 的明確銘牌確認能力不會由掃描自動啟用。
17. LAN 僅探測 Scope / AC Source 欄位中填入的 IPv4；空白欄位會跳過該台。USB 依 VISA 枚舉，非 USBTMC、其他 LAN 機種及其他品牌/型號不列入；不做整個 LAN 搜尋。
18. USB 使用 PyUSB/libusb，必須已有相容的 Windows 裝置驅動。隨包 DLL 不會安裝或綁定系統驅動；原有 NI USBTMC 驅動不保證相容。6312A 與 63210A 的本地手冊未明列 USBTMC class 或 Windows 驅動要求，須確認實機描述資訊與介面卡。
