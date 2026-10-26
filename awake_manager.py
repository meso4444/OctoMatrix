#!/usr/bin/env python3
# Copyright 2026 meso4444
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# awake_manager.py
# 負責處理定時任務

import os
import sys
import subprocess
import time
import yaml
import requests
import json
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
import threading

logger = logging.getLogger(__name__)

# 同時間多個喚醒任務整併:同一 target_agent 在緩衝時窗內到達的任務合成單則注入(只載入一次 SOP)
AWAKE_MERGE_WINDOW_SEC = 2          # 緩衝時窗(秒)
AWAKE_BATCH_MAX_BYTES = 8192        # 單批整併內容上限(UTF-8 bytes,不含 handle() 另外包上的 SOP);超過就按筆切批
AWAKE_INJECT_TIMEOUT_SEC = 30       # /inject 同步等待上限:AtomicInjector 全域鎖串行,第 n 筆約 2.5+5.4*(n-1) 秒
AWAKE_PROMPT_MAX_CHARS = 1000       # 單一任務 prompt 字數上限,只在註冊/更新時擋,既有超長任務照常執行


def _with_file_lock(fn):
    """序列化對 awake.yaml 的讀-改-寫(Flask 多執行緒與排程執行緒並行)"""
    def wrapper(self, *a, **k):
        with self._file_lock:
            return fn(self, *a, **k)
    return wrapper

# 導入配置
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from config import TMUX_SESSION_NAME, AWAKE_YAML_PATH, AGENTS, SYS_PREFIX
except ImportError:
    TMUX_SESSION_NAME = "ai_octomatrix"
    AWAKE_YAML_PATH = "awake.yaml"
    AGENTS = []

_WEEKDAY_ZH = {
    '0': '一', 'mon': '一',
    '1': '二', 'tue': '二',
    '2': '三', 'wed': '三',
    '3': '四', 'thu': '四',
    '4': '五', 'fri': '五',
    '5': '六', 'sat': '六',
    '6': '日', 'sun': '日',
}


def _weekday_label(day_of_week):
    return _WEEKDAY_ZH.get(str(day_of_week).strip().lower(), str(day_of_week))


def describe_schedule(original_task):
    """把註冊時的原始語義欄位(trigger類型+hour/minute/...)組成人話排程描述，
    供列表顯示用，不影響`trigger`欄位(APScheduler物件字串)原有的API行為。
    查不出對應規則時回傳None，呼叫端自行決定要不要退回原始字串。"""
    trigger_val = original_task.get('trigger')
    try:
        if trigger_val == 'daily':
            return f"每天 {int(original_task.get('hour', 0)):02d}:{int(original_task.get('minute', 0)):02d}"
        elif trigger_val == 'weekly':
            dow = _weekday_label(original_task.get('day_of_week', 0))
            return f"每週{dow} {int(original_task.get('hour', 0)):02d}:{int(original_task.get('minute', 0)):02d}"
        elif trigger_val == 'monthly':
            return f"每月{original_task.get('day', 1)}日 {int(original_task.get('hour', 0)):02d}:{int(original_task.get('minute', 0)):02d}"
        elif trigger_val == 'interval':
            h, m, s = int(original_task.get('hours', 0) or 0), int(original_task.get('minutes', 0) or 0), int(original_task.get('seconds', 0) or 0)
            parts = []
            if h: parts.append(f"{h}時")
            if m: parts.append(f"{m}分")
            if s and not (h or m): parts.append(f"{s}秒")
            return f"每隔 {''.join(parts)}" if parts else "每隔 60秒(預設)"
        elif trigger_val == 'date':
            return f"單次 {original_task.get('run_time', '?')}"
        elif trigger_val == 'cron':
            bits = []
            if original_task.get('day_of_week') is not None:
                bits.append(f"週{_weekday_label(original_task.get('day_of_week'))}")
            if original_task.get('day') is not None:
                bits.append(f"{original_task.get('day')}日")
            if original_task.get('hour') is not None and original_task.get('minute') is not None:
                bits.append(f"{int(original_task.get('hour')):02d}:{int(original_task.get('minute')):02d}")
            return " ".join(bits) if bits else None
    except (TypeError, ValueError):
        return None
    return None


class AwakeManager:
    def __init__(self, command_handler=None, image_manager=None):
        self.scheduler = BackgroundScheduler()
        self._file_lock = threading.RLock()
        self._pending = {}
        self._pending_lock = threading.Lock()
        self.awake_file = AWAKE_YAML_PATH
        self.load_jobs()

    def start(self):
        """啟動任務調度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("⏰ [Awake] 喚醒系統調度器已啟動")

    def load_jobs(self, jobs_data=None):
        """從 YAML 或傳入資料載入喚醒任務"""
        if jobs_data is not None:
            self.scheduler.remove_all_jobs()
            if isinstance(jobs_data, list):
                for task in jobs_data:
                    self._add_task_to_scheduler(task)
            return

        if not os.path.exists(self.awake_file):
            return
        
        try:
            with open(self.awake_file, 'r', encoding='utf-8') as f:
                jobs = yaml.safe_load(f) or []
            
            if isinstance(jobs, list):
                # 載入時清掉已過期的 date 任務(例如停機期間錯過的)，它們不會再被執行
                live = [t for t in jobs if not self._is_expired_date_task(t)]
                if len(live) != len(jobs):
                    with self._file_lock:
                        with open(self.awake_file, 'w', encoding='utf-8') as f:
                            yaml.dump(live, f, allow_unicode=True)
                    logger.info(f"[Awake] 載入時已清除 {len(jobs) - len(live)} 筆過期 date 任務")
                jobs = live
                self.scheduler.remove_all_jobs()
                for task in jobs:
                    self._add_task_to_scheduler(task)
        except Exception as e:
            logger.error(f"❌ 載入喚醒任務失敗: {e}")

    @staticmethod
    def _is_expired_date_task(task):
        if not isinstance(task, dict) or task.get('trigger') != 'date': return False
        run_time = task.get('run_time')
        try:
            if isinstance(run_time, str):
                run_time = datetime.strptime(run_time, "%Y-%m-%d %H:%M:%S")
            return run_time is not None and run_time < datetime.now()
        except Exception:
            return False

    def _add_task_to_scheduler(self, task):
        """將單個任務加入 apscheduler (含高階 Trigger 轉譯)"""
        if not isinstance(task, dict): return
        task_id = task.get('id') or task.get('name')
        trigger_type = task.get('trigger')
        if not task_id or not trigger_type: return

        try:
            if trigger_type == 'daily':
                trigger = CronTrigger(hour=task.get('hour', 0), minute=task.get('minute', 0), second=task.get('second', 0))
            elif trigger_type == 'weekly':
                trigger = CronTrigger(day_of_week=task.get('day_of_week', 0), hour=task.get('hour', 0), minute=task.get('minute', 0))
            elif trigger_type == 'monthly':
                trigger = CronTrigger(day=task.get('day', 1), hour=task.get('hour', 0), minute=task.get('minute', 0))
            elif trigger_type == 'interval':
                trigger = IntervalTrigger(hours=task.get('hours', 0), minutes=task.get('minutes', 0), seconds=task.get('seconds', 60))
            elif trigger_type == 'date':
                run_time = task.get('run_time')
                if isinstance(run_time, str):
                    run_time = datetime.strptime(run_time, "%Y-%m-%d %H:%M:%S")
                trigger = DateTrigger(run_date=run_time)
            else:
                trigger = CronTrigger(hour=task.get('hour'), minute=task.get('minute'), day_of_week=task.get('day_of_week'), day=task.get('day'))

            self.scheduler.add_job(
                self.execute_task,
                trigger,
                args=[task],
                id=task_id,
                replace_existing=True
            )
        except Exception as e:
            logger.error(f"❌ 新增任務 {task_id} 失敗: {e}")

    def execute_task(self, task):
        task_type = task.get('type', 'agent_command')
        if task_type == 'agent_command' and self._task_target_and_prompt(task):
            # 不直接注入:放進該 agent 的待發批次,時窗到期後整併送出;date 任務在批次送出後才移除
            self._enqueue(task)
        elif task.get('trigger') == 'date':
            # date 任務只會觸發一次:無可執行內容時也要移除,避免已過期的任務殘留
            self._remove_date_job(task)

    @_with_file_lock
    def _remove_date_job(self, task):
        task_id = task.get('id') or task.get('name')
        try:
            if not task_id or not os.path.exists(self.awake_file): return
            with open(self.awake_file, 'r', encoding='utf-8') as f:
                jobs = yaml.safe_load(f) or []
            if not isinstance(jobs, list): return
            # run_time 與本次執行的任務不同代表已被重新註冊/更新，不可誤刪
            keep = [t for t in jobs if not ((t.get('id') or t.get('name')) == task_id and str(t.get('run_time')) == str(task.get('run_time')))]
            if len(keep) == len(jobs): return
            with open(self.awake_file, 'w', encoding='utf-8') as f:
                yaml.dump(keep, f, allow_unicode=True)
            logger.info(f"[Awake] 已清除已執行的 date 任務: {task_id}")
        except Exception as e:
            logger.error(f"[Awake] 清除 date 任務失敗 ({task_id}): {e}")

    @staticmethod
    def _task_target_and_prompt(task):
        target_agent = task.get('target_agent') or task.get('agent')
        prompt = task.get('prompt') or task.get('command')
        if not target_agent or not prompt: return None
        return target_agent, prompt

    def _enqueue(self, task):
        target_agent, prompt = self._task_target_and_prompt(task)
        # prompt 自帶 [SOP] 框架的任務不併入:handle() 看到該字樣整則不包 SOP,併入會讓同批其他任務失去 SOP
        if '執行以下 [SOP]:' in prompt:
            self._send_batch(target_agent, [task], 1, 1)
            self._cleanup_date_tasks([task])
            return
        with self._pending_lock:
            batch = self._pending.get(target_agent)
            if batch is None:
                self._pending[target_agent] = [task]
                timer = threading.Timer(AWAKE_MERGE_WINDOW_SEC, self._flush, args=(target_agent,))
                timer.daemon = True
                timer.start()
            else:
                batch.append(task)

    def _flush(self, target_agent):
        with self._pending_lock:
            tasks = self._pending.pop(target_agent, [])
        if not tasks: return
        tasks.sort(key=lambda t: str(t.get('id') or t.get('name')))
        batches = self._split_batches(tasks)
        for idx, batch in enumerate(batches, 1):
            self._send_batch(target_agent, batch, idx, len(batches))
            self._cleanup_date_tasks(batch)

    @staticmethod
    def _split_batches(tasks):
        """按筆乾淨切分:依序貪婪裝入,超過單批上限就封口開新批,絕不切斷單筆;單筆本身超過上限時獨自成批"""
        batches, cur, cur_bytes = [], [], 300  # 300 bytes 預留批次標頭
        for t in tasks:
            prompt = t.get('prompt') or t.get('command')
            entry_bytes = len(f"[99] 任務 {t.get('id') or t.get('name')}: {prompt}\n".encode('utf-8'))
            if cur and cur_bytes + entry_bytes > AWAKE_BATCH_MAX_BYTES:
                batches.append(cur)
                cur, cur_bytes = [], 300
            cur.append(t)
            cur_bytes += entry_bytes
        if cur: batches.append(cur)
        return batches

    @staticmethod
    def _build_content(batch, idx, total):
        if len(batch) == 1 and total == 1:
            return f"(喚醒系統指令) {batch[0].get('prompt') or batch[0].get('command')}"
        lines = [f"[{n}] 任務 {t.get('id') or t.get('name')}: {t.get('prompt') or t.get('command')}" for n, t in enumerate(batch, 1)]
        if total == 1:
            head = f"(喚醒系統指令) 現在有 {len(batch)} 項同時到期的喚醒任務,請全部完成,完成後統一回報:"
        elif idx < total:
            head = f"(喚醒系統指令) 同時到期的喚醒任務共分 {total} 批,這是第 {idx}/{total} 批({len(batch)} 項),請全部完成;後面還有批次,待全部批次完成後再統一回報:"
        else:
            head = f"(喚醒系統指令) 同時到期的喚醒任務共分 {total} 批,這是最後一批(第 {idx}/{total} 批,{len(batch)} 項),請全部完成,完成後統一回報:"
        return head + "\n" + "\n".join(lines)

    def _send_batch(self, target_agent, batch, idx, total):
        from config import ROUTER_PORT
        ids = [t.get('id') or t.get('name') for t in batch]
        # 🚀 物理校準：強制使用 127.0.0.1 撥號
        url = f"http://127.0.0.1:{ROUTER_PORT}/inject"
        payload = {
            "source": "awake",
            "user_id": "system",
            "content": self._build_content(batch, idx, total),
            "metadata": {"target_agent": target_agent}
        }
        try:
            resp = requests.post(url, json=payload, timeout=AWAKE_INJECT_TIMEOUT_SEC)
            # /inject 不論成敗都回 HTTP 200,成功與否以 body 的 status 為準
            try:
                status = resp.json().get('status')
            except Exception:
                status = f"unparsable(HTTP {resp.status_code})"
            log = logger.info if status == 'success' else logger.error
            log(f"⏰ [Awake] 注入 target={target_agent} 第{idx}/{total}批 ids={ids} status={status}")
        except requests.exceptions.Timeout:
            logger.error(f"⏰ [Awake] 注入 target={target_agent} 第{idx}/{total}批 ids={ids} status=timeout(結果未知,router 可能仍已注入,不重試)")
        except Exception as e:
            logger.error(f"⏰ [Awake] 喚醒 Agent 失敗 (內部 API 錯誤) target={target_agent} 第{idx}/{total}批 ids={ids}: {e}")

    def _cleanup_date_tasks(self, batch):
        # date 任務只會觸發一次:批次送出後(不論成敗)逐筆從 awake.yaml 移除,避免已過期的任務殘留
        for t in batch:
            if t.get('trigger') == 'date':
                self._remove_date_job(t)

    @staticmethod
    def _check_prompt_length(task_data):
        prompt = task_data.get('prompt') or task_data.get('command') or ''
        if len(prompt) > AWAKE_PROMPT_MAX_CHARS:
            return {"status": "error", "message": f"prompt 過長: {len(prompt)} 字,上限 {AWAKE_PROMPT_MAX_CHARS} 字,請精簡後再註冊"}
        return None

    def _validate_job_data(self, task_data):
        allowed_fields = {'id', 'name', 'trigger', 'type', 'target_agent', 'agent', 'prompt', 'command', 'hour', 'minute', 'second', 'day_of_week', 'day', 'hours', 'minutes', 'seconds', 'run_time'}
        allowed_triggers = {'daily', 'weekly', 'monthly', 'interval', 'date', 'cron'}
        
        invalid_fields = [k for k in task_data.keys() if k not in allowed_fields]
        if invalid_fields:
            return {"status": "error", "message": f"包含無效的欄位: {', '.join(invalid_fields)}"}
            
        trigger_val = task_data.get('trigger')
        if not trigger_val or trigger_val not in allowed_triggers:
            return {"status": "error", "message": f"缺少或無效的必需欄位 trigger: {trigger_val}"}
            
        if not task_data.get('id') and not task_data.get('name'):
            return {"status": "error", "message": "缺少必需欄位: id"}
        if not task_data.get('target_agent') and not task_data.get('agent'):
            return {"status": "error", "message": "缺少必需欄位: target_agent"}
        if not task_data.get('prompt') and not task_data.get('command'):
            return {"status": "error", "message": "缺少必需欄位: prompt"}
            
        # Trigger-bound required fields validation
        trigger_reqs = {
            'daily': ['hour', 'minute'],
            'weekly': ['day_of_week', 'hour', 'minute'],
            'monthly': ['day', 'hour', 'minute'],
            'date': ['run_time'],
            'cron': ['hour', 'minute']
        }
        
        if trigger_val in trigger_reqs:
            missing = [f for f in trigger_reqs[trigger_val] if f not in task_data]
            if missing:
                return {"status": "error", "message": f"Trigger '{trigger_val}' 缺少關聯必需欄位: {', '.join(missing)}"}
        elif trigger_val == 'interval':
            if not any(k in task_data for k in ['hours', 'minutes', 'seconds']):
                return {"status": "error", "message": f"Trigger 'interval' 至少需要 hours, minutes, seconds 其中一個欄位"}
        return None

    @_with_file_lock
    def register_job(self, task_data):
        try:
            validation_error = self._validate_job_data(task_data) or self._check_prompt_length(task_data)
            if validation_error:
                return validation_error

            jobs = []
            if os.path.exists(self.awake_file):
                with open(self.awake_file, 'r', encoding='utf-8') as f:
                    jobs = yaml.safe_load(f) or []
            if not isinstance(jobs, list): jobs = []
            task_id = task_data.get('id') or task_data.get('name')
            jobs = [t for t in jobs if (t.get('id') or t.get('name')) != task_id]
            jobs.append(task_data)
            with open(self.awake_file, 'w', encoding='utf-8') as f:
                yaml.dump(jobs, f, allow_unicode=True)
            self._add_task_to_scheduler(task_data)
            return {"status": "success", "message": f"已註冊喚醒任務: {task_id}"}
        except Exception as e:
            logger.error(f"❌ [Awake] register_job 失敗: {e}")
            return {"status": "error", "message": f"註冊喚醒任務失敗: {e}"}

    @_with_file_lock
    def update_job(self, job_id, update_data):
        try:
            if not os.path.exists(self.awake_file):
                return {"status": "error", "message": "檔案不存在"}

            with open(self.awake_file, 'r', encoding='utf-8') as f:
                jobs = yaml.safe_load(f) or []

            target_job = None
            for job in jobs:
                if (job.get('id') or job.get('name')) == job_id:
                    target_job = job
                    break

            if not target_job:
                return {"status": "error", "message": f"找不到任務: {job_id}"}

            # Post-Merge Validation
            merged_job = target_job.copy()
            for k, v in update_data.items():
                if v is not None:
                    merged_job[k] = v

            # Remove empty string or None values that might have been passed to override
            merged_job = {k: v for k, v in merged_job.items() if v is not None}

            validation_error = self._validate_job_data(merged_job)
            # 字數上限只在這次更新動到 prompt 時檢查,既有超長任務改其他欄位(如時間)不受影響
            if not validation_error and ('prompt' in update_data or 'command' in update_data):
                validation_error = self._check_prompt_length(merged_job)
            if validation_error:
                return validation_error

            # Remove old job
            jobs = [t for t in jobs if (t.get('id') or t.get('name')) != job_id]
            jobs.append(merged_job)

            with open(self.awake_file, 'w', encoding='utf-8') as f:
                yaml.dump(jobs, f, allow_unicode=True)

            # Update Scheduler
            try:
                self.scheduler.remove_job(job_id)
            except:
                pass
            self._add_task_to_scheduler(merged_job)

            return {"status": "success", "message": f"已更新喚醒任務: {job_id}"}
        except Exception as e:
            logger.error(f"❌ [Awake] update_job 失敗: {e}")
            return {"status": "error", "message": f"更新喚醒任務失敗: {e}"}

    @_with_file_lock
    def delete_job(self, job_id):
        try:
            if not os.path.exists(self.awake_file): return {"status": "error", "message": "檔案不存在"}
            with open(self.awake_file, 'r', encoding='utf-8') as f:
                jobs = yaml.safe_load(f) or []
            new_jobs = [t for t in jobs if (t.get('id') or t.get('name')) != job_id]
            if len(new_jobs) == len(jobs): return {"status": "error", "message": f"找不到任務: {job_id}"}
            with open(self.awake_file, 'w', encoding='utf-8') as f:
                yaml.dump(new_jobs, f, allow_unicode=True)
            try: self.scheduler.remove_job(job_id)
            except: pass
            return {"status": "success", "message": f"已刪除喚醒任務: {job_id}"}
        except Exception as e:
            logger.error(f"❌ [Awake] delete_job 失敗: {e}")
            return {"status": "error", "message": f"刪除喚醒任務失敗: {e}"}

    def list_jobs(self):
        try:
            jobs_info = []
            for job in self.scheduler.get_jobs():
                original_task = job.args[0] if job.args else {}
                jobs_info.append({
                    "id": job.id,
                    "trigger": str(job.trigger),
                    "schedule_text": describe_schedule(original_task) or str(job.trigger),
                    "next_run_time": job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "None",
                    "target_agent": original_task.get('target_agent') or original_task.get('agent') or "未指定",
                    "prompt": original_task.get('prompt') or original_task.get('command') or "無指令"
                })
            return {"status": "ok", "total": len(jobs_info), "jobs": jobs_info}
        except Exception as e:
            logger.error(f"❌ [Awake] list_jobs 失敗: {e}")
            return {"status": "error", "message": f"列出喚醒任務失敗: {e}"}

