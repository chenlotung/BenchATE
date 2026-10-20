# pyvisa-py 通訊與 USB 使用說明

Windows x64 · ATE Workbench 0.1.0 pyvisa-py 版 · 2026-10-20

## 本版本的通訊方式

程式透過 PyVISA API 使用 pyvisa-py 的 `@py` 後端。ZIP 已包含 Python、pyvisa-py、PyUSB、libusb-package 與 x64 libusb DLL；執行時不下載套件，也不需要 NI-VISA、NI MAX、LabVIEW 或 Chroma SoftPanel。

請解壓整份 ZIP，保留 EXE 與 `_internal/` 的位置。此版本不附安裝程式、不安裝或更換 Windows 裝置驅動。Demo 模式完全不存取實體儀器。

## 網路儀器

| 儀器 | 連線方式 | 設定 |
|---|---|---|
| Chroma 61512 | TCP Socket，port 2101 | AC Source IP 填入實機 IPv4；不需要 NI-VISA。 |
| Tektronix MSO44B | VXI-11，inst0 | Scope IP 填入實機 IPv4，先在示波器啟用 VXI-11。 |

不需要網際網路，但電腦必須能連到儀器的區域網路。任一 IP 空白就跳過該台；兩欄空白仍可掃描 USB。本版只列舉 USB INSTR，沒有全網段或網路服務廣播搜尋。

## USB 的必要條件

打包 libusb DLL 可免去另外安裝通訊函式庫，但 Windows 仍必須已將儀器綁定至 PyUSB/libusb 相容的裝置驅動，例如 WinUSB。原有 NI USBTMC 驅動不保證能直接由本版本使用；NI MAX 看得到儀器也不代表 pyvisa-py 可以存取。

**若部署電腦沒有相容驅動，而且禁止安裝或變更驅動，本版本不能保證 USB 可用。** 不會自動以管理員權限安裝、替換或繞過系統驅動政策。驅動變更須由設備管理者評估，也可能影響原本的 VISA 工具。

| 儀器 | 專案內原廠手冊核對結果 |
|---|---|
| Chroma 66205 | §14.2，PDF 第 97 頁明列 USBTMC / USB488；原文的「不需其他驅動」以已有 NI-VISA USBTMC 支援為前提，不是 pyvisa-py 免驅保證。 |
| Chroma 6312A / 63106A | §2.6，PDF 第 48 頁說明主機 USB 為選購介面；此手冊未明列 USB class 或 Windows 驅動要求。需實機確認介面卡與描述資訊，63106A 模組不是獨立 USB 設備。 |
| Chroma 63210A | §3.3.5，PDF 第 71 頁說明後背板 USB Device 遠端控制；此手冊未明列 USBTMC 或 Windows 驅動要求，需實機確認。前面板 USB Host 用於儲存，不能用來連電腦。 |
| RIGOL DM3058E | 使用 USB Device 埠；需驗證實際裝置驅動是否相容 PyUSB/libusb。原廠工具能連線不等於此後端已通過驗證。 |

掃描只接受程式支援清單內、能以 USBTMC INSTR 存取並成功識別的完整型號。不支援 USB-Serial、USB RAW、GPIB 或未知介面卡，不猜測其他協定，也不自動改用 NI-VISA 或 Demo。

## 找不到設備時

1. 確認整個 `_internal/` 都已解壓；不要只複製 EXE。
2. USB 請確認資料線、Device / Remote 埠、介面卡及 Windows 現有驅動綁定；關閉可能占用儀器的其他軟體。零筆掃描結果不代表現場一定沒有儀器。
3. 網路請確認 IPv4、子網、儀器服務與防火牆；欄位空白會略過該台。
4. 查看 `logs/workbench.log`。程式失敗時不會重送輸出指令；確認實體狀態後再按 Scan & Connect。

可在命令提示字元執行 `ATEWorkbench.exe --check-backend`，結果寫入 `logs/backend_check.json`。它只檢查隨包程式庫是否能載入，不開啟儀器 session、不傳送 SCPI 指令；後端初始化可能讀取 USB 描述資訊，`passed` 不代表實機 USB 驅動、量測或輸出已驗證。

所有實機連線、控制及示波器截圖仍待硬體驗證。軟體測試和 Demo 不能代替實機測試。

## 參考資料

- [pyvisa-py 安裝與介面需求](https://pyvisa.readthedocs.io/projects/pyvisa-py/en/stable/installation.html)
- [libusb-package 原廠說明](https://github.com/pyocd/libusb-package)
- [Windows 自動載入 WinUSB 的設備條件](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/automatic-installation-of-winusb)

操作方式請先閱讀包內的 `README_PORTABLE.pdf`。
