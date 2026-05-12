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
    import subprocess
    # Call matrix_notifier or the internal router API
    router_host = getattr(config, 'ROUTER_HOST', '127.0.0.1')
    router_port = getattr(config, 'ROUTER_PORT', 12210)
    session_name = getattr(config, 'TMUX_SESSION_NAME', 'chat_agent')

    # Create inject_block.lock for blocking
    agent_dir = os.path.join(base_dir, 'agent_home', agent_name)
    lock_file = os.path.join(agent_dir, 'octo_cyberbrain', 'inject_block.lock')
    os.makedirs(os.path.dirname(lock_file), exist_ok=True)
    open(lock_file, 'w').close()

    # Inject single Ctrl+C and wait 6s, letting Router inject the second Ctrl+C to interrupt stuck tasks
    try:
        target = f"{session_name}:{agent_name}"
        subprocess.run(["tmux", "send-keys", "-t", target, "C-c"])
        time.sleep(6)
    except Exception as e:
        print(f"[Reaper] Failed to execute pre-wake Ctrl+C: {e}")

    # Inject command to Agent (implicit maintenance mode)
    inject_url = f"http://{router_host}:{router_port}/inject"
    payload = {
        "source": "reaper",
        "user_id": "system",
        "content": "[System Prompt] If there is an ongoing task, please pause it and save the current task status to octo_cyberbrain/task_memo.txt. Then, please use parameter mode to execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"semantic outline\" --keywords \"keywords\" --paths \"paths\"` to update GHOST status, no need to send message to user",
        "metadata": {
            "target_agent": agent_name
        }
    }

    try:
        requests.post(inject_url, json=payload, timeout=5)
        print(f"[Reaper] Notified Agent: {agent_name} for implicit GHOST status update")
        return True
    except Exception as e:
        print(f"[Reaper] Failed to notify Agent {agent_name}: {e}")
        if os.path.exists(lock_file):
            try: os.remove(lock_file)
            except: pass
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
            
            if os.path.exists(shell_log):
                size = os.path.getsize(shell_log)
                if size >= threshold_bytes:
                    if not os.path.exists(flag_file):
                        try:
                            # Touch flag
                            os.makedirs(os.path.dirname(flag_file), exist_ok=True)
                            open(flag_file, 'w').close()
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

                    # 🚀 Fail-safe cleanup: If threshold not met, clear any residual inject_block.lock
                    lock_file = os.path.join(agent_dir, 'octo_cyberbrain', 'inject_block.lock')
                    if os.path.exists(lock_file):
                        try:
                            os.remove(lock_file)
                            print(f"[Reaper] Removed residual inject_block.lock ({agent_name})")
                        except FileNotFoundError:
                            pass
        
        time.sleep(polling_interval)

if __name__ == "__main__":
    main()