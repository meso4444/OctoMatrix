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

import os
from config import SYS_PREFIX

import subprocess
import sys
import time
import glob
import requests
from datetime import datetime

# Now in the same directory as config.py
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(base_dir)

import config
import logging
from logging.handlers import RotatingFileHandler

# Logs are kept in logs/ under the project root (created automatically at service start); fall back to /tmp only if it cannot be created
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
try:
    os.makedirs(LOG_DIR, mode=0o750, exist_ok=True)
except OSError:
    LOG_DIR = '/tmp'

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        RotatingFileHandler(os.path.join(LOG_DIR, 'octo_reaper.log'), maxBytes=2*1024*1024, backupCount=3, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_reaper_config():
    polling_interval = getattr(config, 'CYBERBRAIN_REAPER_POLLING_INTERVAL', 60)
    threshold_kb = getattr(config, 'CYBERBRAIN_ROTATION_THRESHOLD_KB', 70)
    return polling_interval, threshold_kb

def notify_agent(agent_name):
    # Call matrix_notifier or the internal router API
    router_host = getattr(config, 'ROUTER_HOST', '127.0.0.1')
    router_port = getattr(config, 'ROUTER_PORT', 12210)
    session_name = getattr(config, 'TMUX_SESSION_NAME', 'chat_agent')

    agent_dir = os.path.join(base_dir, 'agent_home', agent_name)

    # Inject single Ctrl+C and wait 6s, letting Router inject the second Ctrl+C to interrupt stuck tasks
    try:
        target = f"{session_name}:{agent_name}"
        agents = getattr(config, 'AGENTS', [])
        engine = next((a.get('engine', '').lower() for a in agents if a['name'] == agent_name), 'gemini')
        if engine == 'pi':
            # Pi needs no busy check and Ctrl-C does not apply; interrupt with Escape only
            subprocess.run(["tmux", "send-keys", "-t", target, "Escape"])
            time.sleep(6)
        elif engine == 'codex':
            res = subprocess.run(["tmux", "capture-pane", "-p", "-t", target], capture_output=True, text=True)
            lines = [line for line in res.stdout.split('\n') if line.strip()]
            if 'Working (' in '\n'.join(lines[-20:]):
                subprocess.run(["tmux", "send-keys", "-t", target, "C-c"])
                time.sleep(0.5)
                subprocess.run(["tmux", "send-keys", "-t", target, "Escape"])
                time.sleep(6)
        else:
            subprocess.run(["tmux", "send-keys", "-t", target, "C-c"])
            time.sleep(0.5)
            subprocess.run(["tmux", "send-keys", "-t", target, "Escape"])
            time.sleep(6)
    except Exception as e:
        logger.error(f"[Reaper] Failed to execute pre-wake Ctrl+C: {e}")

    # Inject command to Agent (implicit maintenance mode)
    inject_url = f"http://{router_host}:{router_port}/inject"
    payload = {
        "source": "reaper",
        "user_id": "system",
        "content": f"{SYS_PREFIX} If there is an ongoing task, please pause it and save the current task status to octo_cyberbrain/task_memo.txt. Then, please use parameter mode to execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"semantic outline\" --keywords \"keywords\" --paths \"paths\"` to update GHOST status, and execute `python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.webm` to send a sticker matching your current mood, then execute `python3 toolbox/matrix_notifier.py 'Scattered thought bubbles are merging into the focused sea... {{A reassuring greeting to ask {config.MATRIX_USERNAME} to wait a moment}}'`",
        "metadata": {
            "target_agent": agent_name
        }
    }

    try:
        requests.post(inject_url, json=payload, timeout=15)
        logger.info(f"[Reaper] Notified Agent: {agent_name} for implicit GHOST status update")
        return True
    except Exception as e:
        logger.error(f"[Reaper] Failed to notify Agent {agent_name}: {e}")
        return False

def is_in_dnd(dnd_str):
    if not dnd_str or '-' not in dnd_str:
        return False
    try:
        start_str, end_str = dnd_str.split('-')
        start_min = int(start_str[:2]) * 60 + int(start_str[2:])
        end_min = int(end_str[:2]) * 60 + int(end_str[2:])
        
        now = datetime.now()
        now_min = now.hour * 60 + now.minute
        
        if start_min <= end_min:
            return start_min <= now_min <= end_min
        else:
            return now_min >= start_min or now_min <= end_min
    except Exception as e:
        logger.error(f"[Reaper] Failed to parse DND range: {e}")
        return False

def trigger_inactivity_greeting(agent_name):
    router_host = getattr(config, 'ROUTER_HOST', '127.0.0.1')
    router_port = getattr(config, 'ROUTER_PORT', 12210)
    inactivity_hours = getattr(config, 'CYBERBRAIN_INACTIVITY_CHECK_HOURS', 12)
    
    inject_url = f"http://{router_host}:{router_port}/inject"
    payload = {
        "source": "reaper",
        "user_id": "system",
        "content": f"{SYS_PREFIX} Look what time it is, execute python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.webm to send a sticker matching your current mood, and then execute python3 toolbox/matrix_notifier.py '{{ask {config.MATRIX_USERNAME} about their recent status}}'",
        "metadata": {
            "target_agent": agent_name
        }
    }
    try:
        res = requests.post(inject_url, json=payload, timeout=15)
        if res.status_code == 200:
            logger.info(f"[Reaper] Successfully triggered idle greeting injection for Agent {agent_name}")
            return True
        else:
            logger.error(f"[Reaper] Failed to trigger idle greeting injection for Agent {agent_name}: HTTP {res.status_code}")
            return False
    except Exception as e:
        logger.error(f"[Reaper] Connection failed when injecting idle greeting to Router: {e}")
        return False

# Log cleanup: only touches rotated backups (*.log.N) in logs/; the active *.log is never deleted or truncated.
# 1) delete backups older than the retention days 2) if logs/ exceeds the size cap, delete the oldest backups first
LOG_RETENTION_DAYS = getattr(config, 'LOG_RETENTION_DAYS', 7)
LOG_MAX_TOTAL_MB = getattr(config, 'LOG_MAX_TOTAL_MB', 50)
LOG_CLEANUP_INTERVAL = 24 * 3600

def cleanup_logs():
    try:
        backups = [f for f in glob.glob(os.path.join(LOG_DIR, '*.log.*')) if os.path.isfile(f)]
        now = time.time()
        for f in list(backups):
            if now - os.path.getmtime(f) > LOG_RETENTION_DAYS * 86400:
                os.remove(f)
                backups.remove(f)
        total = sum(os.path.getsize(f) for f in glob.glob(os.path.join(LOG_DIR, '*.log*')) if os.path.isfile(f))
        for f in sorted(backups, key=os.path.getmtime):
            if total <= LOG_MAX_TOTAL_MB * 1024 * 1024:
                break
            total -= os.path.getsize(f)
            os.remove(f)
    except Exception as e:
        logger.error(f"[Reaper] Log cleanup failed: {e}")

def main():
    logger.info("🐙 Global Reaper Daemon Started")
    last_log_cleanup = 0
    while True:
        if time.time() - last_log_cleanup >= LOG_CLEANUP_INTERVAL:
            cleanup_logs()
            last_log_cleanup = time.time()
        polling_interval, threshold_kb = get_reaper_config()
        threshold_bytes = threshold_kb * 1024
        
        agents = getattr(config, 'AGENTS', [])
        
        for agent in agents:
            agent_name = agent['name']
            agent_dir = os.path.join(base_dir, 'agent_home', agent_name)
            shell_log = os.path.join(agent_dir, 'octo_cyberbrain', 'shell', 'octo_shell.log')
            flag_file = os.path.join(agent_dir, 'octo_cyberbrain', '.rotation_flag')
            
            if os.path.exists(flag_file):
                try:
                    with open(flag_file, 'r') as f:
                        flag_content = f.read().strip()
                except Exception:
                    flag_content = ""

                try:
                    if time.time() - os.path.getmtime(flag_file) > polling_interval + 840:
                        os.remove(flag_file)
                        logger.info(f"[Reaper] Found abnormal Flag existing too long (> {polling_interval + 840}s), forcefully removed ({agent_name})")
                        continue
                except Exception:
                    pass
                    
                if not flag_content:
                    try:
                        elapsed = time.time() - os.path.getmtime(flag_file)
                        # Check intervals: 180-245, 420-485, 660-725
                        if (180 < elapsed <= 245) or (420 < elapsed <= 485) or (660 < elapsed <= 725):
                            logger.info(f"[Reaper] Found empty Flag (exists for {int(elapsed)}s) in retry interval, resending notification ({agent_name})")
                            notify_agent(agent_name)
                    except Exception as e:
                        logger.error(f"[Reaper] Failed to check timed out Flag ({agent_name}): {e}")

                if flag_content == "READY_FOR_REAPER":
                    try:
                        # Only responsible for triggering, internal script handles locking
                        rotate_script = os.path.join(agent_dir, 'octo_cyberbrain', 'internal_matrix_rotate.py')
                        subprocess.Popen(["python3", rotate_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                        logger.info(f"[Reaper] Starting Rotation process ({agent_name})")
                    except Exception as e:
                        logger.error(f"[Reaper] Failed to start Rotation ({agent_name}): {e}")
                    continue
                elif "internal_matrix_rotate.py" in flag_content:
                    # Rotation script is running, let it manage flags and logs
                    continue

            if os.path.exists(shell_log):
                # --- Idle Inactivity Greeting Check ---
                try:
                    inactivity_hours = getattr(config, 'CYBERBRAIN_INACTIVITY_CHECK_HOURS', 12)
                    dnd_range = getattr(config, 'CYBERBRAIN_DND_RANGE', "2200-0700")
                    mtime = os.path.getmtime(shell_log)
                    
                    if time.time() - mtime > inactivity_hours * 3600:
                        if not is_in_dnd(dnd_range):
                            if trigger_inactivity_greeting(agent_name):
                                try:
                                    os.utime(shell_log, None)
                                    logger.info(f"[Reaper] Updated mtime of {agent_name} log to prevent duplicate greetings.")
                                except Exception as e:
                                    logger.error(f"[Reaper] Failed to touch log file: {e}")
                except Exception as e:
                    logger.error(f"[Reaper] Failed to check idle state for Agent {agent_name}: {e}")
                # --------------------------------------

                size = os.path.getsize(shell_log)
                if size >= threshold_bytes:
                    if not os.path.exists(flag_file):
                        try:
                            # Touch flag
                            os.makedirs(os.path.dirname(flag_file), exist_ok=True)
                            open(flag_file, 'w').close()
                            os.chmod(flag_file, 0o666)
                            success = notify_agent(agent_name)
                            if not success:
                                if os.path.exists(flag_file):
                                    try: os.remove(flag_file)
                                    except: pass
                        except Exception as e:
                            logger.error(f"[Reaper] Failed to create Flag ({agent_name}): {e}")
                else:
                    if os.path.exists(flag_file):
                        try:
                            os.remove(flag_file)
                            logger.info(f"[Reaper] Removed expired residual Flag ({agent_name})")
                        except FileNotFoundError:
                            pass
        
        time.sleep(polling_interval)

if __name__ == "__main__":
    main()