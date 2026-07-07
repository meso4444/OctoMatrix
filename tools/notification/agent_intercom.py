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

# Dynamically load project root directory into sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = _current_dir
for _ in range(5):
    if os.path.exists(os.path.join(_root_dir, 'config.py')):
        if _root_dir not in sys.path:
            sys.path.insert(0, _root_dir)
        break
    _root_dir = os.path.dirname(_root_dir)

try:
    from config import SYS_PREFIX
except ImportError:
    SYS_PREFIX = "[System Prompt]"

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

def main():
    parser = argparse.ArgumentParser(description="Agent-to-Agent communication sender")
    parser.add_argument("--target", required=True, help="Target Agent name")
    parser.add_argument("--message", required=True, help="Message or instruction to pass")
    args = parser.parse_args()

    router_url = f"{get_router_url()}/inter-agent/message"
    source_agent = get_source_agent()

    payload = {
        "source": source_agent,
        "target_agent": args.target,
        "message": args.message
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
