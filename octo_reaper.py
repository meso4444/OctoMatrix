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
import requests

# Now in the same directory as config.py
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(base_dir)

import config

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
        if engine == 'codex':
            res = subprocess.run(["tmux", "capture-pane", "-p", "-t", target], capture_output=True, text=True)
            lines = [line for line in res.stdout.split('\n') if line.strip()]
            if 'Working (' in '\n'.join(lines[-20:]):
                subprocess.run(["tmux", "send-keys", "-t", target, "C-c", "Escape"])
                time.sleep(6)
        else:
            subprocess.run(["tmux", "send-keys", "-t", target, "C-c", "Escape"])
            time.sleep(6)
    except Exception as e:
        print(f"[Reaper] Failed to execute pre-wake Ctrl+C: {e}")

    # Inject command to Agent (implicit maintenance mode)
    inject_url = f"http://{router_host}:{router_port}/inject"
    payload = {
        "source": "reaper",
        "user_id": "system",
        "content": f"{SYS_PREFIX} If there is an ongoing task, please pause it and save the current task status to octo_cyberbrain/task_memo.txt. Then, please use parameter mode to execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"semantic outline\" --keywords \"keywords\" --paths \"paths\"` to update GHOST status, no need to send message to user",
        "metadata": {
            "target_agent": agent_name
        }
    }

    try:
        requests.post(inject_url, json=payload, timeout=15)
        print(f"[Reaper] Notified Agent: {agent_name} for implicit GHOST status update")
        return True
    except Exception as e:
        print(f"[Reaper] Failed to notify Agent {agent_name}: {e}")
        return False

def main():
    print("🐙 Global Reaper Daemon Started")
    while True:
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
                        print(f"[Reaper] Found abnormal Flag existing too long (> {polling_interval + 840}s), forcefully removed ({agent_name})")
                        continue
                except Exception:
                    pass
                    
                if not flag_content:
                    try:
                        elapsed = time.time() - os.path.getmtime(flag_file)
                        # Check intervals: 180-245, 420-485, 660-725
                        if (180 < elapsed <= 245) or (420 < elapsed <= 485) or (660 < elapsed <= 725):
                            print(f"[Reaper] Found empty Flag (exists for {int(elapsed)}s) in retry interval, resending notification ({agent_name})")
                            notify_agent(agent_name)
                    except Exception as e:
                        print(f"[Reaper] Failed to check timed out Flag ({agent_name}): {e}")

                if flag_content == "READY_FOR_REAPER":
                    try:
                        # Only responsible for triggering, internal script handles locking
                        rotate_script = os.path.join(agent_dir, 'octo_cyberbrain', 'internal_matrix_rotate.py')
                        subprocess.Popen(["python3", rotate_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                        print(f"[Reaper] Starting Rotation process ({agent_name})")
                    except Exception as e:
                        print(f"[Reaper] Failed to start Rotation ({agent_name}): {e}")
                    continue
                elif "internal_matrix_rotate.py" in flag_content:
                    # Rotation script is running, let it manage flags and logs
                    continue

            if os.path.exists(shell_log):
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
                            print(f"[Reaper] Failed to create Flag ({agent_name}): {e}")
                else:
                    if os.path.exists(flag_file):
                        try:
                            os.remove(flag_file)
                            print(f"[Reaper] Removed expired residual Flag ({agent_name})")
                        except FileNotFoundError:
                            pass
        
        time.sleep(polling_interval)

if __name__ == "__main__":
    main()