#!/usr/bin/env python3
import os
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
    
    # 建立 inject_block.lock 進行阻塞
    agent_dir = os.path.join(base_dir, 'agent_home', agent_name)
    lock_file = os.path.join(agent_dir, 'octo_cyberbrain', 'inject_block.lock')
    os.makedirs(os.path.dirname(lock_file), exist_ok=True)
    open(lock_file, 'w').close()

    # 注入指令給 Agent (隱性維護模式)
    inject_url = f"http://{router_host}:{router_port}/inject"
    payload = {
        "source": "reaper",
        "user_id": "system",
        "content": "【系統提示】請使用參數模式執行 `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"語義大綱\" --keywords \"關鍵字\" --paths \"路徑\"` 來更新GHOST 狀態,不需發送訊息給用戶",
        "metadata": {
            "target_agent": agent_name
        }
    }

    try:
        requests.post(inject_url, json=payload, timeout=5)
        print(f"[Reaper] 已通知 Agent: {agent_name} 進行隱性 GHOST 狀態更新")
    except Exception as e:
        print(f"[Reaper] 通知 Agent {agent_name} 失敗: {e}")
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
            
            if os.path.exists(shell_log):
                size = os.path.getsize(shell_log)
                if size >= threshold_bytes:
                    if not os.path.exists(flag_file):
                        try:
                            # Touch flag
                            os.makedirs(os.path.dirname(flag_file), exist_ok=True)
                            open(flag_file, 'w').close()
                            notify_agent(agent_name)
                        except Exception as e:
                            print(f"[Reaper] 建立 Flag 失敗 ({agent_name}): {e}")
                else:
                    if os.path.exists(flag_file):
                        try:
                            os.remove(flag_file)
                            print(f"[Reaper] 移除過期殘留 Flag ({agent_name})")
                        except FileNotFoundError:
                            pass
                    
                    # 🚀 防呆清除機制：如果未達門檻，清除可能殘留的 inject_block.lock
                    lock_file = os.path.join(agent_dir, 'octo_cyberbrain', 'inject_block.lock')
                    if os.path.exists(lock_file):
                        try:
                            os.remove(lock_file)
                            print(f"[Reaper] 移除殘留的 inject_block.lock ({agent_name})")
                        except FileNotFoundError:
                            pass
        
        time.sleep(polling_interval)

if __name__ == "__main__":
    main()