# 🧠 電子腦 GHOST 系統操作手冊

本目錄存放所有與 Agent GHOST 系統相關的核心工具。Agent 應依據本手冊進行 GHOST 的寫入、讀取與深潛檢索。

---

## 1. GHOST 寫入：`octo_ghost_updater.py`

*   **用途**：這是 Agent 寫入語義大綱、關鍵字與檔案路徑的**唯一合法途徑**。
*   **執行模態**：
    *   **CLI 模式 (推薦 Agent 使用)**：透過參數一次性注入，徹底避免 EOF 錯誤。
        `python3 octo_cyberbrain/octo_ghost_updater.py --outline "語義大綱" --keywords "關鍵字1,關鍵字2" --paths "/檔案路徑1,/檔案路徑2"`
    *   **互動模式 (人類除錯)**：不帶參數執行，依提示輸入。
*   **關鍵職責**：Agent 必須主動且定期執行此工具，以確保任務脈絡不因系統重整而遺失。

---

## 2. 靈魂讀取：`octo_ghost_reader.py`

*   **用途**：讀取已結構化的 JSON GHOST 索引。
*   **參數說明**：
    *   `--level current`：讀取當前正在累積的 GHOST 狀態。
    *   `--level snapshot`：讀取快照層級的聚合 GHOST。
    *   `--level monthly --months N`：讀取過去 N 個月的月度歸併索引。
*   **執行範例**：`python3 octo_cyberbrain/octo_ghost_reader.py --level snapshot`

---

## 3. 軀殼深潛：`dive_into_the_shell.py`

*   **用途**：對歷史終端日誌（Raw Logs）進行全文檢索。
*   **核心邏輯**：預設採用「最新優先 (Latest-First)」，保留最靠近現在的紀錄。
*   **參數說明**：
    *   `--keyword`：指定一個或多個搜尋標的（必填）。
    *   `--level`：指定搜尋深度 (`current`/`snapshot`/`monthly`/`yearly`)。
    *   `--offset N`：**深度挖掘關鍵**。跳過最新的 N 行，翻閱更遠的歷史（分頁機制）。
    *   `-C`：指定上下文行數（預設 50）。
*   **執行範例**：
    *   *一般脈絡重塑*：`python3 octo_cyberbrain/dive_into_the_shell.py --level snapshot --keyword "重要事件"`
    *   *挖掘更深歷史*：`python3 octo_cyberbrain/dive_into_the_shell.py --level snapshot --keyword "重要事件" --offset 1000`
*   **防護機制**：單次輸出限制為 1000 行，以防止 Token 爆炸。

---

## 4. 遺產遷移：`octo_ghost_legacy_converter.py`

*   **用途**：一次性將舊版 `.md` 格式的 Ghost 轉換為新版 `.json` 格式。
*   **執行方式**：`python3 octo_cyberbrain/octo_ghost_legacy_converter.py`
