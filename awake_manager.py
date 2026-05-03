#!/usr/bin/env python3
# awake_manager.py
# Responsible for handling scheduled tasks
# 【Physical Hardened Version】: Fix 0.0.0.0 dial error and data transmission

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

# Import configuration
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from config import TMUX_SESSION_NAME, AWAKE_YAML_PATH, AGENTS
except ImportError:
    TMUX_SESSION_NAME = "ai_octomatrix"
    AWAKE_YAML_PATH = "awake.yaml"
    AGENTS = []

class AwakeManager:
    def __init__(self, command_handler=None, image_manager=None):
        self.scheduler = BackgroundScheduler()
        self.awake_file = AWAKE_YAML_PATH
        self.load_jobs()

    def start(self):
        """Start task scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            print("⏰ [Awake] Awake system scheduler started")

    def load_jobs(self, jobs_data=None):
        """Load awake tasks from YAML or passed data"""
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
                self.scheduler.remove_all_jobs()
                for task in jobs:
                    self._add_task_to_scheduler(task)
        except Exception as e:
            print(f"❌ Failed to load awake tasks: {e}")

    def _add_task_to_scheduler(self, task):
        """Add single task to apscheduler (with advanced Trigger translation)"""
        if not isinstance(task, dict): return
        task_id = task.get('id') or task.get('name')
        trigger_type = task.get('trigger', 'cron')
        if not task_id: return

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
            print(f"❌ Failed to add task {task_id}: {e}")

    def execute_task(self, task):
        task_type = task.get('type', 'agent_command')
        if task_type == 'agent_command':
            self._execute_agent_command(task)

    def _execute_agent_command(self, task):
        from config import ROUTER_PORT
        target_agent = task.get('target_agent') or task.get('agent')
        prompt = task.get('prompt') or task.get('command')
        if not target_agent or not prompt: return

        # 🚀 Physical calibration: Force use of 127.0.0.1 dial
        url = f"http://127.0.0.1:{ROUTER_PORT}/inject"
        payload = {
            "source": "awake",
            "user_id": "system",
            "content": f"【Awake System Command】{prompt}",
            "metadata": {"target_agent": target_agent}
        }
        try:
            requests.post(url, json=payload, timeout=5)
            print(f"⏰ [Awake] Successfully awakened Agent: {target_agent}")
        except Exception as e:
            print(f"⏰ [Awake] Failed to awaken Agent (Internal API error): {e}")

    def register_job(self, task_data):
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
        return {"status": "success", "message": f"Registered awake task: {task_id}"}

    def delete_job(self, job_id):
        if not os.path.exists(self.awake_file): return {"status": "error", "message": "File does not exist"}
        with open(self.awake_file, 'r', encoding='utf-8') as f:
            jobs = yaml.safe_load(f) or []
        new_jobs = [t for t in jobs if (t.get('id') or t.get('name')) != job_id]
        if len(new_jobs) == len(jobs): return {"status": "error", "message": f"Task not found: {job_id}"}
        with open(self.awake_file, 'w', encoding='utf-8') as f:
            yaml.dump(new_jobs, f, allow_unicode=True)
        try: self.scheduler.remove_job(job_id)
        except: pass
        return {"status": "success", "message": f"Deleted awake task: {job_id}"}

    def list_jobs(self):
        jobs_info = []
        for job in self.scheduler.get_jobs():
            original_task = job.args[0] if job.args else {}
            jobs_info.append({
                "id": job.id,
                "trigger": str(job.trigger),
                "next_run_time": job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "None",
                "prompt": original_task.get('prompt') or original_task.get('command') or "No command"
            })
        return {"status": "ok", "total": len(jobs_info), "jobs": jobs_info}
