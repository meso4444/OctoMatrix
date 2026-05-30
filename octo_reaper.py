#!/usr/bin/env python3
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

    # 注入前先執行 1 回合 Ctrl+C 並等待 6 秒，後續交由 Router 補上第二發 Ctrl+C 強制打斷
    try:
        target = f"{session_name}:{agent_name}"
        agents = getattr(config, 'AGENTS', [])
        engine = next((a.get('engine', '').lower() for a in agents if a['name'] == agent_name), 'gemini')
        if engine == 'codex':
            res = subprocess.run(["tmux", "capture-pane", "-p", "-t", target], capture_output=True, text=True)
            lines = [line for line in res.stdout.split('\n') if line.strip()]
            if 'Working (' in '\n'.join(lines[-20:]):
                subprocess.run(["tmux", "send-keys", "-t", target, "C-c"])
                time.sleep(6)
        else:
            subprocess.run(["tmux", "send-keys", "-t", target, "C-c"])
            time.sleep(6)
    except Exception as e:
        print(f"[Reaper] 執行前置 Ctrl+C 失敗: {e}")

    # 注入指令給 Agent (隱性維護模式)
    inject_url = f"http://{router_host}:{router_port}/inject"
    payload = {
        "source": "reaper",
        "user_id": "system",
        "content": f"{SYS_PREFIX} 若有任務進行中，請先中斷任務，把當前任務狀態記錄到octo_cyberbrain/task_memo.txt。接著請使用參數模式執行 `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"語義大綱\" --keywords \"關鍵字\" --paths \"路徑\"` 來更新GHOST 狀態,不需發送訊息給用戶",
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
                        if time.time() - os.path.getmtime(flag_file) > polling_interval + 240:
                            print(f"[Reaper] 發現逾時 ({polling_interval + 240} 秒) 的空 Flag，強制接管寫入 READY_FOR_REAPER ({agent_name})")
                            with open(flag_file, 'w') as f:
                                f.write("READY_FOR_REAPER")
                            flag_content = "READY_FOR_REAPER"
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