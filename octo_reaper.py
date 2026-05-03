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

    # Inject command to Agent (implicit maintenance mode)
    inject_url = f"http://{router_host}:{router_port}/inject"
    payload = {
        "source": "reaper",
        "user_id": "system",
        "content": "【System Prompt】Please use parameter mode to execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"semantic outline\" --keywords \"keywords\" --paths \"paths\"` to update GHOST status, no need to send message to user",
        "metadata": {
            "target_agent": agent_name
        }
    }

    try:
        requests.post(inject_url, json=payload, timeout=5)
        print(f"[Reaper] Notified Agent: {agent_name} for implicit GHOST status update")
    except Exception as e:
        print(f"[Reaper] Failed to notify Agent {agent_name}: {e}")
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