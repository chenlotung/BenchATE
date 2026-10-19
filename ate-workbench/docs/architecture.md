# 架構與執行邊界

## 原始碼結構

依目前程式規模整併後，`app/` 共有 19 個 Python 檔案、3 個套件目錄（包含 `app/` 本身）；原先為 35 個檔案、7 個套件目錄。合併 `core/` 與 `services/` 中相關的模組，將單一 Demo 實作併入 `drivers/`，並把 `gui/widgets/` 的兩個元件併為 `gui/widgets.py`。

```text
app/
  __init__.py
  main.py
  config.py
  models.py
  instruments.py
  worker.py
  data.py
  protocol.py
  drivers/
    __init__.py
    base.py
    power.py
    measurement.py
    mock.py
  gui/
    __init__.py
    main_window.py
    connection.py
    monitoring.py
    widgets.py
    themes.py
```

- `config.py`：設定檔、設備偏好與輪替記錄；不再拆成兩個微型 service。
- `instruments.py`：設備識別、掃描、清單與連線管理；掃描和加入設備的流程集中維護。
- `worker.py`：每台儀器的命令佇列、排程與 session 生命週期；`data.py` 負責資料緩衝及 CSV。
- `protocol.py`：VISA transport、SCPI 回應解析、PNG 完整性檢查，供 driver 使用，不依賴 Qt。
- `drivers/base.py`：共用介面與 DC Load 控制；`power.py` 集中 AC Source / DC Load；`measurement.py` 集中電力計、電表與示波器。各型號仍保留自己的 driver 類別及型號驗證。
- `drivers/mock.py`：明確啟用的 Demo 實作；driver 註冊與建構集中在 `drivers/__init__.py`。
- `gui/widgets.py`：設備卡片與趨勢圖；兩個頁面及主視窗各自保留，方便找對應的畫面。

`config/`、`tests/`、`scripts/`、`docs/` 與原廠 `datasheet/` 各有不同用途，保持分開。儀器手冊依型號存放，避免混淆來源。

## 通訊、執行緒與安全狀態

GUI 只呼叫單一 InstrumentManager，經由有界 PriorityQueue 交付命令。
每個實體 resource 僅允許一個 InstrumentWorker (QThread) 擁有 driver/session。
Scan & Connect 由獨立 ResourceScanner 背景執行 USB 枚舉及唯讀 *IDN? / 6312A *RDT?。Scope/AC 的 IP 欄位各自決定是否探測該 LAN 設備；空白時忽略 backend 枚舉到的 LAN 資源。
`instruments.py` 中的 discovery 流程嚴格比對 vendor、完整 model 及允許的 transport；只回傳合格設備。探測 session 先關閉，再由 InstrumentWorker 建立正式 session。已連線及正在連線的 resource 從掃描排除，避免第二個 session。
儲存設定只作偏好值，不在啟動時直接建立設備列；掃描辨識後才恢復名稱、timeout、polling 與安全限制值。掃描不恢復安全批准或輸出狀態。
Driver 不匯入 Qt；每筆操作完整執行，之後才執行下一個命令或輪詢。
6312A 的各個 channel 共用主機 driver，選台後恢復原選台，不建立模組 session。

輪詢使用 monotonic deadline，跳過逾期週期，不堆疊 polling 工作。
停止監控只停止週期讀取，不會修改實體輸出。切換頁面不建立或關閉連線。
通訊錯誤關閉失去同步的 session，保留最後有效資料並標示 Stale / Unknown。
重新連線由使用者操作，從不恢復輸出或重送控制命令。

DataManager 保存每設備/channel 最近 600 秒、至少 600 筆的有界 buffer。
CSV writer 使用獨立執行緒與有界 queue；queue 滿時回報錯誤，不默默丟資料。
牆上時間帶 timezone，monotonic 只供排程/過期判定；sample freshness 未驗證時顯示未知。

安全限制需使用者每次連線後明確批准；只持久化限制值，不持久化批准或 ON 狀態。
Apply 與 ON 使用當下回讀值/模式/輸出狀態檢查，不以 write 成功推定已生效。
Output OFF 是一般背景通訊命令，不能視作硬體緊急停止。

PyVISA ResourceManager 會在同一 backend 間共用；VisaBackendPool 使用 lease 計數，只在最後一個 scanner / instrument lease 釋放時關閉 RM。
每台儀器的 session 仍由各自 worker 建立及使用；pool lock 只涵蓋開啟/掃描/關閉等 backend 管理，不序列化不同儀器的查詢。

Output OFF 會取消同 channel 較舊但尚未執行的 ON / Apply。CommandQueue 保留 OFF / disconnect 名額；已在進行中的交易完成後才執行下一筆。
Worker shutdown 在目前 VISA 交易完成/timeout 後停止後續 I/O；不使用 QThread.terminate 強制中斷交易。

可攜式版本的 ROOT 為 sys.executable 所在資料夾，設定/記錄與 EXE 一起移動。
PyInstaller 建置明確排除其他工具的 PATH，避免誤收與 Windows Qt 不相容的同名 DLL；Python / Qt 依賴打包在 _internal。
