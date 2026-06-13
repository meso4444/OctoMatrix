# ⏰ Wake-up Task Management Feature Detailed Guide

**Audience**: Agent (in knowledge base)
**Purpose**: Help Agent understand how to manage wake-up tasks for users

---

## 🎯 Feature Overview

The wake-up system allows users to set scheduled commands without needing to restart services. Agents can help users:
- Query existing wake-up tasks
- Register new wake-up tasks
- Update existing wake-up tasks
- Delete unneeded tasks

---

## 📋 User-delegable Tasks

### 1. Query Existing Wake-ups

**User expressions**:
- "I want to know what wake-up tasks are currently set"
- "List all wake-ups"

**Agent operation**:
```bash
python3 toolbox/awake_task_manager.py list
```

**Expected terminal output**:
```text
=== Awake 任務列表 (共 1 筆) ===
ID: Daily system cleanup
  目標: Güpa
  排程: <CronTrigger (hour=2, minute=0, second=0)>
  下次執行: 2026-02-20 02:00:00
  指令: Execute system cleanup
------------------------------
```

**Agent response example**:
```
✅ Currently there is 1 active wake-up task:
1. Daily system cleanup - Executes daily at 2:00 AM
```

---

### 2. Register New Wake-up

**User expressions**:
- "Help me set a morning meeting reminder at 8 AM every day"

**Agent process**:

#### Step 1: Understand requirements & Confirm parameters
Extract frequency, time, and content, then confirm with the user.

#### Step 2: Execute script to register

**daily (Every day)**:
```bash
python3 toolbox/awake_task_manager.py register \
  --id "Morning meeting reminder" \
  --target "Güpa" \
  --trigger "daily" \
  --hour 8 --minute 0 \
  --prompt "Remind user to attend morning meeting" \
  --type "agent_command"
```

#### Step 3: Handle response

**Success**:
```text
[Success] 任務已註冊: Morning meeting reminder
```

**Failure**:
```text
[Error] trigger 為 'daily' 或 'cron' 時，必須指定 --hour 與 --minute
```

Respond to the user with success or ask for the missing parameters.

---

### 3. Update Existing Wake-up

**User expressions**:
- "Change the morning meeting reminder to 8:30"
- "Change the target of the Monday report to Dapa"

**Agent operation**:
```bash
python3 toolbox/awake_task_manager.py update \
  --id "Morning meeting reminder" \
  --minute 30
```
*(Parameters not provided will remain unchanged)*

**Expected terminal output**:
```text
[Success] 任務已更新: Morning meeting reminder
```

---

### 4. Delete Wake-up

**User expressions**:
- "Cancel the morning meeting reminder I set before"

**Agent operation**:
```bash
python3 toolbox/awake_task_manager.py delete --id "Morning meeting reminder"
```

**Expected terminal output**:
```text
[Success] 任務已刪除: Morning meeting reminder
```

---

## ⏰ Trigger Type Details & Script Parameters

The trigger parameters supported by the script correspond as follows:

### daily (Every day)
Must specify `--hour` and `--minute`. Optional `--second`.
```bash
--trigger daily --hour 8 --minute 30
```

### weekly (Every week)
Must specify `--day_of_week` (0-6), `--hour`, `--minute`.
```bash
--trigger weekly --day_of_week 4 --hour 17 --minute 0
```

### monthly (Every month)
Must specify `--day` (1-31), `--hour`, `--minute`.
```bash
--trigger monthly --day 15 --hour 12 --minute 0
```

### interval (Fixed interval)
Must specify at least one of `--hours`, `--minutes`, or `--seconds`.
```bash
--trigger interval --hours 6
```

### date (Specific Date and Time)
Must specify `--run_time` (Format: YYYY-MM-DD HH:MM:SS).
```bash
--trigger date --run_time "2026-12-31 23:59:59"
```

### cron (Complex expression)
Used for complex scheduling logic. Can combine `--hour`, `--minute`, `--day_of_week`, `--day` and supports range and list expressions.
**Common usage**:
- `--day_of_week "0-4"` = Monday to Friday
- `--day "1,15"` = 1st and 15th of each month

---

## 🎬 Task Types & Common Parameters

- `--id`: (Required) Unique identifier for the task.
- `--target`: Target Agent name (e.g., Güpa).
- `--prompt`: Command or prompt to execute.
- `--type`: Defaults to `agent_command`.

---

## 💡 Best Practices

### ✅ Do
1. Communicate with users in natural language, hide technical details.
2. Explain the reason and provide solutions when encountering `[Error]`.

### ❌ Don't
1. Do not attempt to use `curl` or directly call `http://127.0.0.1...`, always use the `awake_task_manager.py` script.
2. Avoid creating or modifying wake-ups without confirmation.

---

**Last updated**: 2026-06-13