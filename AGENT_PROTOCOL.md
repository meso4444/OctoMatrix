
## 電子腦 GHOST 系統指引

Agent 必須嚴格遵守以下 GHOST 操作規範，以確保長期 GHOST 的連貫性與系統穩定。

### 1. 核心操作工具 (Toolbox)
- **`octo_ghost_updater.py`**：**GHOST 寫入唯一入口**。Agent 必須主動且定期執行此腳本，記錄「關鍵字」、「檔案路徑」與「語義大綱」，以確保 重要任務脈絡被永久保存。
- **`octo_ghost_reader.py`**：**靈魂讀取器**。用於讀取結構化的 JSON GHOST 索引（支援 current/snapshot/monthly 層級）。
- **`dive_into_the_shell.py`**：**軀殼深潛器**。用於根據關鍵字在歷史終端日誌（Raw Logs）中進行深度檢索。

### 2. 日常 GHOST 更新指引 (Ghost Writing Workflow)
Agent 應在完成階段性任務後，遵循以下「先大綱、後關鍵字&檔案路徑」的流程記錄 GHOST：

1. **Step 1:  撰寫語義大綱 (Outline First)**
   - 優先撰寫詳細的決策邏輯、任務記錄與執行結果。
   - 語義大綱必須真實呈現對話內容與技術細節。

2. **Step 2:  萃取真實關鍵字 (Literal Keywords Extraction)**
   - **核心原則**：從你剛撰寫的大綱中萃取關鍵字。
   - **禁止轉譯**：嚴禁將關鍵字轉換為英文（除非原文即為英文）或進行語義再詮釋。
   - **真實呈現**：必須保持關鍵字在終端日誌中的原始字樣，以確保後續 `dive` 檢索能精準匹配。

3. **Step 3:  相關重要檔案的絕對路徑 (Paths)**

4. **執行寫入指令**
   - 指令執行範例：
    ```bash
    python3 octo_cyberbrain/octo_ghost_updater.py --outline "語義大綱" --keywords "關鍵字1,關鍵字2" --paths "/檔案路徑1,/檔案路徑2"
    ```

### 3. 進階操作指引 (Knowledge)
- **手冊位置**：更詳細的參數說明與深潛檢索 (Diving) 技巧，請參閱 `octo_cyberbrain/CYBERBRAIN_GUIDE.md`。

---

## 通知系統操作指引


### 訊息發送規範

1. **唯一發送管道**：**`matrix_notifier.py` 為用戶唯一接收訊息內容管道,回訊內容不可精簡省略**
2. **引號使用原則**：
   - 最外層統一使用**單引號** `'` 包裹。
   - 訊息內部可自由使用雙引號 `"`、金錢符號 `$` 等，無需額外轉義。
   - 若訊息本身包含單引號，建議改為雙引號包裹外層，或對內層單引號進行轉義 (`\'`)。
   - 訊息內不要用\*\*作為文字強調

2. **發送範例**：

```bash
## 一般回應
python3 toolbox/matrix_notifier.py '💬 您好！我是 {agent_name}\n已收到您的訊息並正在回應'

## 發送文檔（帶說明）
python3 toolbox/matrix_notifier.py --file document /path/to/report.pdf '📄 任務完成報告'

## 發送圖片
python3 toolbox/matrix_notifier.py --file photo /tmp/screenshot.png '截圖驗證'

## 發送視頻
python3 toolbox/matrix_notifier.py --file video /tmp/demo.mp4 '演示影片\n時長: 5分鐘'

## 發送音頻
python3 toolbox/matrix_notifier.py --file audio /tmp/notification.wav '語音確認'
```

3. **視覺表達規範**：

	Agent 應根據訊息內容與當前情感狀態，發送對應的 Avatar 心情貼圖。

	#### 使用範例

```bash
## 發送獨立的心情貼圖
python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/happy.webm

```
---

4. **資安注意**：

   - 避免在通知中包含敏感資訊, 如個資, 密碼...等

5. **網址連結處理規範**：

   - **拒絕猜測**：絕不自行「推算」或「組合」網址（例如根據日期格式猜測）。僅使用搜尋工具明確返回的連結。
   - **解析轉址**：若搜尋結果為轉址連結（如 `google.com/url?...` 或 `vertexaisearch...`），**必須**使用 Python `requests.head()` 或 `curl -I` 解析出原始真實網址 (Canonical URL)。
   - **驗證有效性**：在發送給用戶前，務必確認網址可正常訪問（回傳 HTTP 200/301/302）。
   - **來源核實**：確認最終網址的域名與聲稱的新聞來源相符（例如：來源說是 PR Newswire，網址域名應為 `prnewswire.com`）。

---

## 喚醒系統 (Awake System) 操作指引

矩陣透過「喚醒系統」定時對 Agent 下達指令。詳細實現見 `knowledge/AWAKE_FUNCTIONALITY.md`。

Agent **必須透過專用腳本** 來管理自動化行為，嚴禁直接編輯 `awake.yaml` 或打裸露的 curl。

- **新增喚醒任務 (支援 trigger: daily, weekly, monthly, interval, date, cron)**：
    ```bash
    python3 toolbox/awake_task_manager.py register \
      --id "task_id" --target "{agent_name}" --trigger "cron" \
      --hour 9 --minute 30 --prompt "執行任務內容"
    ```
- **檢視與管理**：
    - `python3 toolbox/awake_task_manager.py list`
    - `python3 toolbox/awake_task_manager.py delete --id "task_id"`
    - `python3 toolbox/awake_task_manager.py update --id "task_id" --hour 10 --prompt "新內容"`

---
