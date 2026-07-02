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
from datetime import datetime

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

    # 注入前先執行 1 回合 Ctrl+C 並等待 6 秒，後續交由 Router 補上第二發 Ctrl+C 強制打斷
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
        print(f"[Reaper] 執行前置 Ctrl+C 失敗: {e}")

    # 注入指令給 Agent (隱性維護模式)
    inject_url = f"http://{router_host}:{router_port}/inject"
    payload = {
        "source": "reaper",
        "user_id": "system",
        "content": f"{SYS_PREFIX} 若有任務進行中，請先中斷任務，把當前任務狀態記錄到octo_cyberbrain/task_memo.txt（建立檔案時請務必賦予 666 權限）。接著請使用參數模式執行 `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"語義大綱\" --keywords \"關鍵字\" --paths \"路徑\"` 來更新GHOST 狀態,不需發送訊息給用戶",
        "metadata": {
            "target_agent": agent_name
        }
    }

    try:
        requests.post(inject_url, json=payload, timeout=15)
        print(f"[Reaper] 已通知 Agent: {agent_name} 進行隱性 GHOST 狀態更新")
        return True
    except Exception as e:
        print(f"[Reaper] 通知 Agent {agent_name} 失敗: {e}")
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
        print(f"[Reaper] 解析 DND 區間失敗: {e}")
        return False

def trigger_inactivity_greeting(agent_name):
    router_host = getattr(config, 'ROUTER_HOST', '127.0.0.1')
    router_port = getattr(config, 'ROUTER_PORT', 12210)
    inactivity_hours = getattr(config, 'CYBERBRAIN_INACTIVITY_CHECK_HOURS', 12)
    
    inject_url = f"http://{router_host}:{router_port}/inject"
    payload = {
        "source": "reaper",
        "user_id": "system",
        "content": f"{SYS_PREFIX} 看看幾點了, 執行 python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png 發符合當下心情的貼圖，接著執行 python3 toolbox/matrix_notifier.py '{{向 {config.MATRIX_USERNAME} 問候近況}}'",
        "metadata": {
            "target_agent": agent_name
        }
    }
    try:
        res = requests.post(inject_url, json=payload, timeout=15)
        if res.status_code == 200:
            print(f"[Reaper] 成功觸發 Agent {agent_name} 的空閒問候注入")
            return True
        else:
            print(f"[Reaper] 觸發 Agent {agent_name} 空閒問候注入失敗: HTTP {res.status_code}")
            return False
    except Exception as e:
        print(f"[Reaper] 連線 Router 注入空閒問候失敗: {e}")
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
                        print(f"[Reaper] 發現存在過久 (超過 {polling_interval + 840} 秒) 的異常 Flag，強制清除 ({agent_name})")
                        continue
                except Exception:
                    pass
                    
                if not flag_content:
                    try:
                        elapsed = time.time() - os.path.getmtime(flag_file)
                        # Check intervals: 180-245, 420-485, 660-725
                        if (180 < elapsed <= 245) or (420 < elapsed <= 485) or (660 < elapsed <= 725):
                            print(f"[Reaper] 發現逾時空 Flag (已存在 {int(elapsed)} 秒)，位於重試區間內，發送通知 ({agent_name})")
                            notify_agent(agent_name)
                    except Exception as e:
                        print(f"[Reaper] 檢查逾時 Flag 失敗 ({agent_name}): {e}")

                if flag_content == "READY_FOR_REAPER":
                    try:
                        rotate_script = os.path.join(agent_dir, 'octo_cyberbrain', 'internal_matrix_rotate.py')
                        subprocess.Popen(["python3", rotate_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                        print(f"[Reaper] 啟動 Rotation 程序 ({agent_name})")
                    except Exception as e:
                        print(f"[Reaper] 啟動 Rotation 失敗 ({agent_name}): {e}")
                    continue
                elif "internal_matrix_rotate.py" in flag_content:
                    # Rotation script is running
                    continue

            if os.path.exists(shell_log):
                # --- 空閒問候檢測 ---
                try:
                    inactivity_hours = getattr(config, 'CYBERBRAIN_INACTIVITY_CHECK_HOURS', 12)
                    dnd_range = getattr(config, 'CYBERBRAIN_DND_RANGE', "2200-0700")
                    mtime = os.path.getmtime(shell_log)
                    
                    if time.time() - mtime > inactivity_hours * 3600:
                        if not is_in_dnd(dnd_range):
                            if trigger_inactivity_greeting(agent_name):
                                try:
                                    os.utime(shell_log, None)
                                    print(f"[Reaper] 已更新 {agent_name} 日誌時間戳，防止重複發送。")
                                except Exception as e:
                                    print(f"[Reaper] touch 日誌失敗: {e}")
                except Exception as e:
                    print(f"[Reaper] 檢查 Agent {agent_name} 空閒狀態失敗: {e}")
                # -------------------

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
                            print(f"[Reaper] 建立 Flag 失敗 ({agent_name}): {e}")
                else:
                    if os.path.exists(flag_file):
                        try:
                            os.remove(flag_file)
                            print(f"[Reaper] 移除過期殘留 Flag ({agent_name})")
                        except FileNotFoundError:
                            pass
                    

        
        time.sleep(polling_interval)

if __name__ == "__main__":
    main()