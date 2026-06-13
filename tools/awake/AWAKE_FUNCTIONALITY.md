# ⏰ 喚醒任務管理功能詳細指南

**面向**：Agent（在知識庫中）
**用途**：幫助 Agent 理解如何為用戶管理喚醒任務

---

## 🎯 功能概述

喚醒系統允許用戶設置定時指令，無需重啟服務。Agent 可以幫助用戶：
- 查詢現有喚醒任務
- 註冊新的喚醒任務
- 更新現有喚醒任務
- 刪除不需要的任務

---

## 📋 腳本定址與執行規範

Agent **無須**手動組裝 API 請求或尋找 `ROUTER_PORT`，所有操作皆已封裝至專用的 CLI 腳本 `awake_task_manager.py` 中，該腳本會自動向上搜尋端口並與 Router 通訊。
**執行腳本**: `python3 toolbox/awake_task_manager.py [指令] [參數]`

---

## 📋 用戶可委託的任務

### 1. 查詢現有喚醒

**用戶表達**：
- 「我想知道目前有哪些喚醒任務」
- 「列出所有的喚醒」
- 「檢查系統設置的自動喚醒任務」

**Agent 操作**：
```bash
python3 toolbox/awake_task_manager.py list
```

**預期終端輸出**：
```text
=== Awake 任務列表 (共 3 筆) ===
ID: 每日系統清理
  目標: Güpa
  排程: <CronTrigger (hour=2, minute=0, second=0)>
  下次執行: 2026-02-20 02:00:00
  指令: 執行系統清理
------------------------------
```

**Agent 回應範例**：
```
✅ 目前有 1 個活躍的喚醒任務：
1. 每日系統清理 - 每天凌晨 2 點執行
```

---

### 2. 註冊新喚醒

**用戶表達**：
- 「幫我設置每天早上 8 點的晨會提醒」
- 「設定每月 1 號的檢查任務」

**Agent 流程**：

#### 第一步：理解需求與確認參數
提取 頻率、時間 與 任務內容，並向用戶確認。

#### 第二步：執行腳本註冊

**daily（每天）**：
```bash
python3 toolbox/awake_task_manager.py register \
  --id "晨會提醒" \
  --target "Güpa" \
  --trigger "daily" \
  --hour 8 --minute 0 \
  --prompt "提醒用戶進行晨會" \
  --type "agent_command"
```

#### 第三步：處理響應

**成功**：
```text
[Success] 任務已註冊: 晨會提醒
```

**失敗**：
```text
[Error] trigger 為 'daily' 或 'cron' 時，必須指定 --hour 與 --minute
```

回應用戶成功或請用戶補充參數。

---

### 3. 更新現有喚醒

**用戶表達**：
- 「把晨會提醒改成 8 點半」
- 「週一週報的目標換成 Dapa」

**Agent 操作**：
```bash
python3 toolbox/awake_task_manager.py update \
  --id "晨會提醒" \
  --minute 30
```
*(未提供的參數將保持原樣不變)*

**預期終端輸出**：
```text
[Success] 任務已更新: 晨會提醒
```

---

### 4. 刪除喚醒

**用戶表達**：
- 「取消之前設的晨會提醒」

**Agent 操作**：
```bash
python3 toolbox/awake_task_manager.py delete --id "晨會提醒"
```

**預期終端輸出**：
```text
[Success] 任務已刪除: 晨會提醒
```

---

## ⏰ Trigger 類型詳解與腳本參數

腳本支援的 Trigger 參數對應如下：

### daily（每天） 或 cron（複雜表達式）
必須指定 `--hour` 與 `--minute`。可選 `--second`。
```bash
--trigger daily --hour 8 --minute 30
```

### weekly（每週）
必須指定 `--day_of_week` (0-6), `--hour`, `--minute`。
```bash
--trigger weekly --day_of_week 4 --hour 17 --minute 0
```

### monthly（每月）
必須指定 `--day` (1-31), `--hour`, `--minute`。
```bash
--trigger monthly --day 15 --hour 12 --minute 0
```

### interval（固定間隔）
至少指定 `--hours`, `--minutes`, 或 `--seconds` 其中之一。
```bash
--trigger interval --hours 6
```

### date（特定日期時間）
必須指定 `--run_time` (格式: YYYY-MM-DD HH:MM:SS)。
```bash
--trigger date --run_time "2026-12-31 23:59:59"
```

---

## 🎬 任務類型與通用參數

- `--id`：(必填) 任務的唯一識別碼。
- `--target`：目標 Agent 名稱 (如 Güpa)。
- `--prompt`：要執行的命令或提詞。
- `--type`：預設為 `agent_command`。

---

## 💡 最佳實踐

### ✅ Do（應該做）
1. 用自然語言與用戶溝通，隱藏技術細節。
2. 遇到 `[Error]` 時解釋原因並提供解決方案。

### ❌ Don't（不應該做）
1. 不要試圖使用 `curl` 或直接呼叫 `http://127.0.0.1...`，請務必使用 `awake_task_manager.py` 腳本。
2. 避免在未確認的情況下創建或修改喚醒。

---

**最後更新**：2026-06-13