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
    *   `--level snapshot [--range START-END]`：讀取快照層級的聚合 GHOST，
        依新鮮度排序，1 為最新。**預設 `--range 1-30`**（GHOST 重置甦醒時
        的唯一自動化情境，用時間權重代理尚不存在的主題脈絡）；若預設範圍內
        找不到跟目前討論主題相關的關鍵字，可自行往回翻頁查找更早的關鍵字，
        例如 `--range 31-100`、找不到再 `--range 101-200`，判斷與翻頁節奏
        由 Agent 自主拿捏。範圍分頁的輸出**不做字母排序**（保留新鮮度順序）；
        建議每次分頁區塊維持在 30~100 左右，不要一次要太大範圍再整批塞進
        `dive_into_the_shell.py`。
    *   `--level monthly --month YYYY-MM`：精準讀取指定月份的月度歸併索引
        （必填，不支援「過去 N 個月」這種模糊範圍）。
    *   `--level yearly --year YYYY`：精準讀取指定年份的年度歸併索引（必填）。
    *   monthly／yearly 屬於冷記憶，沒有依主題篩選的能力，也刻意不做——
        篩選相關性本來就是 Agent 讀完清單後自己判斷的責任，維持字母排序方便
        人工瀏覽窄域關鍵字。
*   **執行範例**：
    *   *甦醒／一般脈絡重塑*：`python3 octo_cyberbrain/octo_ghost_reader.py --level snapshot`
    *   *找不到相關關鍵字時往回翻頁*：`python3 octo_cyberbrain/octo_ghost_reader.py --level snapshot --range 31-100`
    *   *精準查特定月份*：`python3 octo_cyberbrain/octo_ghost_reader.py --level monthly --month 2026-03`

---

## 3. 軀殼深潛：`dive_into_the_shell.py`

*   **用途**：對歷史終端日誌（Raw Logs）進行全文檢索。
*   **核心邏輯**：預設採用「最新優先 (Latest-First)」，保留最靠近現在的紀錄。
*   **參數說明**：
    *   `--keyword`：指定一個或多個搜尋標的（必填）。
    *   `--level`：指定搜尋深度 (`current`/`snapshot`/`monthly`/`yearly`)。
    *   `--level monthly --month YYYY-MM`／`--level yearly --year YYYY`：
        monthly／yearly 必須精準指定目標月份／年份（必填），只搜尋該單一
        封存檔，不會無條件掃描全部歷史封存檔。
    *   `--offset N`：**深度挖掘關鍵**。跳過最新的 N 行，翻閱更遠的歷史（分頁機制）。
    *   `-C`：指定上下文行數（預設 20）。
*   **執行範例**：
    *   *一般脈絡重塑*：`python3 octo_cyberbrain/dive_into_the_shell.py --level snapshot --keyword "重要事件"`
    *   *挖掘更深歷史*：`python3 octo_cyberbrain/dive_into_the_shell.py --level snapshot --keyword "重要事件" --offset 1000`
    *   *查特定月份*：`python3 octo_cyberbrain/dive_into_the_shell.py --level monthly --month 2026-03 --keyword "重要事件"`
*   **防護機制**：單次輸出限制為 1000 行，以防止 Token 爆炸。

---

## 4. 遺產遷移：`octo_ghost_legacy_converter.py`

*   **用途**：一次性將舊版 `.md` 格式的 Ghost 轉換為新版 `.json` 格式。
*   **執行方式**：`python3 octo_cyberbrain/octo_ghost_legacy_converter.py`
