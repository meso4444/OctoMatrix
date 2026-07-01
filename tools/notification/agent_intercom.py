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

# -*- coding: utf-8 -*-
"""
Internal horizontal communication wrapper (agent_intercom.py)
"""
import os
import sys
import argparse
import requests

def get_router_url() -> str:
    curr = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        port_file = os.path.join(curr, '.router_port')
        if os.path.exists(port_file):
            try:
                with open(port_file, 'r') as f:
                    p = f.read().strip()
                    if p: return f"http://localhost:{p}"
            except: pass
        curr = os.path.dirname(curr)
    return f"http://localhost:{os.getenv('ROUTER_PORT', 12210)}"

def get_source_agent() -> str:
    # Try to get from environment variable or project status
    agent_name = os.getenv("AGENT_NAME")
    if agent_name: return agent_name
    
    curr = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        env_file = os.path.join(curr, 'octo_cyberbrain', '.cyberbrain_env')
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        if line.startswith("AGENT_NAME="):
                            return line.strip().split('=', 1)[1]
            except: pass
        curr = os.path.dirname(curr)
    return "UnknownAgent"

def get_sys_prefix(default_prefix: str) -> str:
    # Attempt to retrieve from environment variable or project status
    sys_prefix = os.getenv("SYS_PREFIX")
    if sys_prefix: return sys_prefix
    
    curr = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        env_file = os.path.join(curr, 'octo_cyberbrain', '.cyberbrain_env')
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        if line.startswith("SYS_PREFIX="):
                            return line.strip().split('=', 1)[1]
            except: pass
        curr = os.path.dirname(curr)
    return default_prefix

def main():
    parser = argparse.ArgumentParser(description="Agent-to-Agent communication sender")
    parser.add_argument("--target", required=True, help="Target Agent name")
    parser.add_argument("--message", required=True, help="Message or instruction to pass")
    args = parser.parse_args()

    router_url = f"{get_router_url()}/inter-agent/message"
    source_agent = get_source_agent()

    SYS_PREFIX = get_sys_prefix("[System Prompt]")
    sop_template = f"""{SYS_PREFIX}
Execute the following [SOP]:
[Step 0 - Empathize]: Execute `python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png` to send a sticker matching the current mood.
[Step 1 - Identify]: Identify if the Source Agent's message is an unfinished collaboration task. If it is an unfinished collaboration task, proceed to Step2; if not, execute `python3 toolbox/matrix_notifier.py '{{Report the completion status of the collaboration task to {{MATRIX_USERNAME}}}}'`, and do not execute subsequent Steps.
[Step 2 - Clarify]: If the collaboration task is clear, execute `python3 toolbox/matrix_notifier.py '{{Greet {{MATRIX_USERNAME}} and autonomously think of an appropriate initial preview}}'` to preview the initial direction of the collaboration, and proceed to Step3; if unclear, suspend the task and execute `python3 toolbox/agent_intercom.py --target "{source_agent}" --message "{{Your message...}}"` to ask the Source Agent for specific directions, and do not execute subsequent Steps.
[Step 3 - Execute]: Officially start the collaboration task and write md. If the task still requires a phased handover or completion verification with the Source Agent, execute `python3 toolbox/agent_intercom.py --target "{source_agent}" --message "{{Your message...}}"` for inter-agent handover, and do not execute subsequent Steps; if the collaboration task is confirmed completed or failed, proceed to Step4.
[Step 4 - Empathize]: Execute `python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png` to send a sticker matching the current mood.
[Step 5 - Report to User]: Execute `python3 toolbox/matrix_notifier.py '{{Report successful transfer or failure exception to {{MATRIX_USERNAME}}}}'`.
[Step 6 - Report to Agent]: Execute `python3 toolbox/agent_intercom.py --target "{source_agent}" --message "{{Explain the completed or failed status, and note that this message does not require an Agent communication reply to avoid an infinite loop. If in doubt, ask {{MATRIX_USERNAME}}}}"`
[Step 7 - Absorb]: Execute `python3 octo_cyberbrain/octo_ghost_reader.py --level current` to absorb your GHOST and memory.
[Step 8 - Engrave]: Execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline "Semantic Outline" --keywords "keyword1,keyword2" --paths "/file/path1,/file/path2"` to engrave this task's status into GHOST.

Message from {source_agent}:
{args.message}

{SYS_PREFIX} Please strictly follow the [SOP] above to reply."""

    payload = {
        "source": source_agent,
        "target_agent": args.target,
        "message": sop_template
    }

    try:
        response = requests.post(router_url, json=payload, timeout=5)
        response.raise_for_status()
        result = response.json()
        if result.get("status") == "success":
            print(f"✅ Successfully sent message to {args.target}")
            sys.exit(0)
        else:
            print(f"❌ Transmission failed: {result.get('error', 'Unknown Error')}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ API request exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
