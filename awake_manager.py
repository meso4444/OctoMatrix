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
# Responsible for handling scheduled tasks

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
    from config import TMUX_SESSION_NAME, AWAKE_YAML_PATH, AGENTS, SYS_PREFIX
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
            print(f"❌ Failed to add task {task_id}: {e}")

    def execute_task(self, task):
        task_type = task.get('type', 'agent_command')
        if task_type == 'agent_command':
            self._execute_agent_command(task)

    def _execute_agent_command(self, task):
        from config import ROUTER_PORT, SYS_PREFIX
        target_agent = task.get('target_agent') or task.get('agent')
        prompt = task.get('prompt') or task.get('command')
        if not target_agent or not prompt: return

        # 🚀 Physical calibration: Force use of 127.0.0.1 dial
        url = f"http://127.0.0.1:{ROUTER_PORT}/inject"
        payload = {
            "source": "awake",
            "user_id": "system",
            "content": f"(Awake System Command) {prompt}",
            "metadata": {"target_agent": target_agent}
        }
        try:
            requests.post(url, json=payload, timeout=5)
            print(f"⏰ [Awake] Successfully awakened Agent: {target_agent}")
        except Exception as e:
            print(f"⏰ [Awake] Failed to awaken Agent (Internal API error): {e}")

    def _validate_job_data(self, task_data):
        allowed_fields = {'id', 'name', 'trigger', 'type', 'target_agent', 'agent', 'prompt', 'command', 'hour', 'minute', 'second', 'day_of_week', 'day', 'hours', 'minutes', 'seconds', 'run_time'}
        allowed_triggers = {'daily', 'weekly', 'monthly', 'interval', 'date', 'cron'}
        
        invalid_fields = [k for k in task_data.keys() if k not in allowed_fields]
        if invalid_fields:
            return {"status": "error", "message": f"Invalid fields detected: {', '.join(invalid_fields)}"}
            
        trigger_val = task_data.get('trigger')
        if not trigger_val or trigger_val not in allowed_triggers:
            return {"status": "error", "message": f"Missing or invalid required field trigger: {trigger_val}"}
            
        if not task_data.get('id') and not task_data.get('name'):
            return {"status": "error", "message": "Missing required field: id"}
        if not task_data.get('target_agent') and not task_data.get('agent'):
            return {"status": "error", "message": "Missing required field: target_agent"}
        if not task_data.get('prompt') and not task_data.get('command'):
            return {"status": "error", "message": "Missing required field: prompt"}
            
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
                return {"status": "error", "message": f"Trigger '{trigger_val}' is missing bound required fields: {', '.join(missing)}"}
        elif trigger_val == 'interval':
            if not any(k in task_data for k in ['hours', 'minutes', 'seconds']):
                return {"status": "error", "message": f"Trigger 'interval' requires at least one of hours, minutes, or seconds"}
        return None

    def register_job(self, task_data):
        validation_error = self._validate_job_data(task_data)
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
        return {"status": "success", "message": f"Registered awake task: {task_id}"}

    def update_job(self, job_id, update_data):
        if not os.path.exists(self.awake_file):
            return {"status": "error", "message": "File does not exist"}
            
        with open(self.awake_file, 'r', encoding='utf-8') as f:
            jobs = yaml.safe_load(f) or []
            
        target_job = None
        for job in jobs:
            if (job.get('id') or job.get('name')) == job_id:
                target_job = job
                break
                
        if not target_job:
            return {"status": "error", "message": f"Task not found: {job_id}"}
            
        # Post-Merge Validation
        merged_job = target_job.copy()
        for k, v in update_data.items():
            if v is not None:
                merged_job[k] = v
                
        # Remove empty string or None values that might have been passed to override
        merged_job = {k: v for k, v in merged_job.items() if v is not None}
                
        validation_error = self._validate_job_data(merged_job)
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
        
        return {"status": "success", "message": f"Updated awake task: {job_id}"}

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
                "target_agent": original_task.get('target_agent') or original_task.get('agent') or "Unspecified",
                "prompt": original_task.get('prompt') or original_task.get('command') or "No command"
            })
        return {"status": "ok", "total": len(jobs_info), "jobs": jobs_info}
