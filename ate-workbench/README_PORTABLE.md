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

## 文件與資料

- [完整操作說明](README.md)
- [Windows 安裝指南](docs/installation.md)
- [實機驗證清單](docs/hardware_validation.md)
- [已知限制](docs/KNOWN_LIMITATIONS.md)
- [SCPI 指令與手冊頁碼](docs/SCPI_COMMAND_REFERENCE.md)

Release 的說明文件以 PDF 提供，原廠 PDF 手冊保留原檔。專案中的 Markdown 原稿持續用於維護。

設定、CSV 與記錄分別位於 `config/`、`data/`、`logs/`。請保留整個資料夾一起移動。

目前所有實機相容性仍待驗證；1 小時測試依使用者要求跳過。EXE 尚未簽署程式碼簽章。
