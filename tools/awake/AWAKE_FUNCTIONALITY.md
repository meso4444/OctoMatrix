# ⏰ Wake-up Task Management Feature Detailed Guide

**Audience**: Agent (in knowledge base)
**Purpose**: Help Agent understand how to manage wake-up tasks for users

---

## 🎯 Feature Overview

The wake-up system allows users to set scheduled commands without needing to restart services. Agents can help users:
- Query existing wake-up tasks
- Register new wake-up tasks
- Delete unneeded tasks

---

## 📋 API Address Specification

Agents must read the `ROUTER_PORT` environment variable from `octo_cyberbrain/.cyberbrain_env` to construct requests.
**Base URL**: `http://127.0.0.1:${ROUTER_PORT}/awake/jobs`

---

## 📋 User-delegable Tasks

### 1. Query Existing Wake-ups

**User expressions**:
- "I want to know what wake-up tasks are currently set"
- "List all wake-ups"
- "Check the automatic wake-up tasks set by the system"

**Agent operation**:
```bash
curl -X GET http://127.0.0.1:${ROUTER_PORT}/awake/jobs
```

**Expected response**:
```json
{
  "status": "ok",
  "total": 3,
  "jobs": [
    {
      "id": "Daily system cleanup",
      "trigger": "<CronTrigger (hour=2, minute=0, second=0)>",
      "next_run_time": "2026-02-20 02:00:00"
    }
  ]
}
```

**Agent response example**:
```
✅ Currently there are 3 active wake-up tasks:
1. Daily system cleanup - Executes daily at 2:00 AM
2. Morning news - Executes daily at 8:00 AM
3. Friday weekly report - Executes every Friday at 5:00 PM
```

---

### 2. Register New Wake-up

**User expressions**:
- "Help me set a morning meeting reminder at 8 AM every day"
- "I want to automatically execute a task at 9 AM every Monday"
- "Set a check task on the 1st of each month"

**Agent process**:

#### Step 1: Understand requirements
Extract from user description:
- ⏰ **Frequency**: Daily / Weekly / Monthly / Custom
- 🕐 **Time**: Specific time (e.g., 8:00)
- 📝 **Content**: What task to execute

#### Step 2: Confirm parameters
Confirm with user to avoid misunderstanding:
```
Let me confirm, the wake-up task you want to set is:
- Frequency: Daily
- Time: 8:00 AM
- Task: Send morning meeting reminder
- Activate: Yes

Is this correct?
```

#### Step 3: Construct API request

Choose the corresponding trigger type based on frequency:

**daily (Every day)**:
```bash
curl -X POST http://127.0.0.1:${ROUTER_PORT}/awake/jobs/register \
  -H "Content-Type: application/json" \
  -d '{
    "id": "Morning meeting reminder",
    "type": "agent_command",
    "target_agent": "Güpa",
    "prompt": "Remind user to attend morning meeting",
    "trigger": "daily",
    "hour": 8,
    "minute": 0,
    "second": 0
  }'
```

**weekly (Every week)**:
```bash
curl -X POST http://127.0.0.1:${ROUTER_PORT}/awake/jobs/register \
  -H "Content-Type: application/json" \
  -d '{
    "id": "Monday report",
    "type": "agent_command",
    "target_agent": "Güpa",
    "prompt": "Generate this week report",
    "trigger": "weekly",
    "day_of_week": 0,
    "hour": 9,
    "minute": 0
  }'
```

**monthly (Every month)**:
```bash
curl -X POST http://127.0.0.1:${ROUTER_PORT}/awake/jobs/register \
  -H "Content-Type: application/json" \
  -d '{
    "id": "Monthly review",
    "type": "agent_command",
    "target_agent": "Güpa",
    "prompt": "Perform monthly review",
    "trigger": "monthly",
    "day": 1,
    "hour": 9,
    "minute": 0
  }'
```

#### Step 4: Handle response

**Success** (HTTP 200):
```json
{
  "status": "success",
  "message": "Wake-up task registered"
}
```

Response to user:
```
✅ Wake-up successfully configured!
Task name: Morning meeting reminder
Execution time: 8:00 AM every day
Next execution: Tomorrow at 8:00 AM
```

**Failure** (HTTP 400/500):
```json
{
  "status": "error",
  "message": "Missing required fields: hour, minute"
}
```

Response to user:
```
❌ Setting wake-up failed: Missing time parameters
Please tell me the specific time you want (e.g., 8:00 AM, 3:00 PM)
```

---

### 3. Delete Wake-up

**User expressions**:
- "Cancel the morning meeting reminder I set before"
- "Delete the Friday report task"
- "Stop the daily cleanup task"

**Agent process**:

#### Step 1: Confirm task ID
```
I found the following related tasks:
1. Morning meeting reminder - Every day at 8:00
2. Morning news - Every day at 8:00

Which one do you want to delete?
```

#### Step 2: Call API
```bash
curl -X DELETE http://127.0.0.1:${ROUTER_PORT}/awake/jobs/Morning%20meeting%20reminder
```

#### Step 3: Confirm result
Success:
```
✅ Wake-up task 'Morning meeting reminder' deleted
Execution will stop on next update
```

Failure:
```
❌ Deletion failed: Task named 'Morning meeting reminder' not found
Please check if the task name is correct
```

---

## 🔧 Complete API Endpoint Reference

### Query all tasks
```
GET http://127.0.0.1:${ROUTER_PORT}/awake/jobs
```

### Register new wake-up
```
POST http://127.0.0.1:${ROUTER_PORT}/awake/jobs/register
Content-Type: application/json
```

### Delete wake-up
```
DELETE http://127.0.0.1:${ROUTER_PORT}/awake/jobs/{job_id}
```

---

## ⏰ Trigger Type Details

### daily (Every day)
**When to use**: Need to execute at a fixed time every day

```json
{
  "trigger": "daily",
  "hour": 8,        // 0-23
  "minute": 0,      // 0-59
  "second": 0       // 0-59 (optional, default 0)
}
```

**Example**: Every day at 8:30 AM
```json
{
  "hour": 8,
  "minute": 30,
  "second": 0
}
```

---

### weekly (Every week)
**When to use**: Need to execute at a specific time on a specific day of the week

```json
{
  "trigger": "weekly",
  "day_of_week": 0,  // 0=Monday, 1=Tuesday, ..., 6=Sunday
  "hour": 9,
  "minute": 0
}
```

**Example**: Every Friday at 5:00 PM
```json
{
  "day_of_week": 4,
  "hour": 17,
  "minute": 0
}
```

---

### monthly (Every month)
**When to use**: Need to execute on a specific day of each month

```json
{
  "trigger": "monthly",
  "day": 1,         // 1-31 (1 = 1st of month)
  "hour": 9,
  "minute": 0
}
```

**Example**: 12:00 PM on the 15th of each month
```json
{
  "day": 15,
  "hour": 12,
  "minute": 0
}
```

---

### interval (Fixed interval)
**When to use**: Need to execute every N hours/minutes/seconds

```json
{
  "trigger": "interval",
  "hours": 6,       // Hours (optional)
  "minutes": 0,     // Minutes (optional)
  "seconds": 0      // Seconds (optional)
}
```

**Example**: Check every 6 hours
```json
{
  "hours": 6,
  "minutes": 0,
  "seconds": 0
}
```

---

### date (Specific Date and Time)
**When to use**: Need to execute once at a specific point in time in the future

```json
{
  "trigger": "date",
  "run_time": "2026-12-31 23:59:59"  // Format: YYYY-MM-DD HH:MM:SS
}
```

**Example**: Send Happy New Year at the end of 2026
```json
{
  "run_time": "2026-12-31 23:59:59"
}
```

---

### cron (Complex expression)
**When to use**: Need complex time logic

```json
{
  "trigger": "cron",
  "day_of_week": "0-4",  // Monday to Friday
  "hour": 9,
  "minute": 0
}
```

**Common usage**:
- `"0-4"` = Monday to Friday
- `"5,6"` = Saturday, Sunday
- `"1,15"` = 1st and 15th of each month
- `"L"` = Last day of month

---

## 🎬 Task Types

### agent_command (Agent command)
**Purpose**: Send commands to Agent at scheduled times

```json
{
  "type": "agent_command",
  "target_agent": "Güpa",
  "prompt": "Generate today's report"
}
```

At the specified time, the system will automatically send a command to the Agent's tmux window.

---

## 📝 Complete Workflow Example

**User requirement**: "I want to automatically generate a weekly report every Monday at 9 AM"

### Step 1: Agent confirms requirement
```
Let me confirm:
- Frequency: Every Monday
- Time: 9:00 AM
- Content: Automatically generate weekly report

Is this correct?
```

### Step 2: Construct request
```bash
curl -X POST http://127.0.0.1:${ROUTER_PORT}/awake/jobs/register \
  -H "Content-Type: application/json" \
  -d '{
    "id": "Monday weekly report generation",
    "type": "agent_command",
    "target_agent": "Güpa",
    "prompt": "Generate weekly report based on this week data",
    "trigger": "weekly",
    "day_of_week": 0,
    "hour": 9,
    "minute": 0
  }'
```

### Step 3: Confirm success
```
✅ Wake-up successfully configured!
Task: Monday weekly report generation
Frequency: Every Monday
Time: 9:00 AM
Next execution: This Monday at 9:00 AM
```

---

## 🛡️ Error Handling

### Common Errors

| Error Message | Cause | Solution |
|---------|------|--------|
| Missing required field | Missing id/type/trigger | Check all required fields are filled |
| Invalid trigger type | trigger is not one of the 5 supported types | Confirm using daily/weekly/monthly/cron/interval |
| agent_command requires target_agent | type is agent_command but missing target_agent | Add target_agent field |
| Wake-up task named X not found | Task does not exist when deleting | Query first to confirm task name |

---

## 💡 Best Practices

### ✅ Do
1. Communicate with users in natural language, hide technical details
2. Confirm user requirements before execution
3. Provide clear feedback on execution results
4. Explain reasons and provide solutions when errors occur

### ❌ Don't
1. Expose JSON format or API details to users
2. Assume users know trigger types
3. Create wake-ups without confirmation
4. Ignore error messages returned by API
5. Use unclear task names (e.g., "task1", "test")

---

**Last updated**: 2026-04-13
