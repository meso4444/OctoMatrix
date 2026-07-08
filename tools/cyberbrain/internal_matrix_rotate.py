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
import sys
import json
import glob
import shutil
import subprocess
import time
import requests
from datetime import datetime

# ==========================================
# 1. Path and Environment Hardening
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_HOME = os.path.dirname(SCRIPT_DIR)
ENV_FILE = os.path.join(AGENT_HOME, "octo_cyberbrain/.cyberbrain_env")

# Define lock and log paths (Absolute Paths)
FLAG_FILE = os.path.join(AGENT_HOME, "octo_cyberbrain/.rotation_flag")
SHELL_LOG = os.path.join(AGENT_HOME, "octo_cyberbrain/shell/octo_shell.log")
TEMP_LOG = os.path.join(AGENT_HOME, "octo_cyberbrain/shell/temp.log")
PENDING_USER_FILE = os.path.join(AGENT_HOME, "octo_cyberbrain/pending_user.txt")
PENDING_AGENT_FILE = os.path.join(AGENT_HOME, "octo_cyberbrain/pending_agent.txt")
TASK_MEMO = os.path.join(AGENT_HOME, "octo_cyberbrain/task_memo.txt")

def load_env():
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'r') as f:
            for line in f:
                if '=' in line:
                    k, v = line.strip().split('=', 1)
                    env[k] = v
    return env

def get_config(agent_name=None):
    # Search upwards for config.py (Agent Home's parent is OctoMatrix root)
    # Structure: OctoMatrix/agent_home/Aleister/octo_cyberbrain/internal_matrix_rotate.py
    # So AGENT_HOME is Aleister
    # OctoMatrix Root is the parent of the parent of AGENT_HOME
    octo_root = os.path.dirname(os.path.dirname(AGENT_HOME))
    
    if octo_root not in sys.path:
        sys.path.append(octo_root)
    
    engine_doc_name = "GEMINI.md"
    engine = "gemini"
    try:
        import config
        limit = int(getattr(config, 'CYBERBRAIN_ROLLING_MERGE_LIMIT', 12))
        context_size = int(getattr(config, 'CYBERBRAIN_DIVE_CONTEXT_SIZE', 50))
        if agent_name:
            for a in getattr(config, 'AGENTS', []):
                if a['name'] == agent_name:
                    engine = a.get('engine', 'gemini').lower()
                    if engine == 'claude':
                        engine_doc_name = "CLAUDE.md"
                    elif engine == 'codex':
                        engine_doc_name = "AGENTS.md"
                    elif engine == 'agy':
                        engine_doc_name = "GEMINI.md"
                    break
        return limit, context_size, engine_doc_name, engine
    except Exception:
        return 12, 50, "GEMINI.md", "gemini"

# 🔍 Environment Adaptation: Locate Tmux Socket
def get_tmux_cmd():
    return ["tmux"]

TMUX_BASE = get_tmux_cmd()

# ==========================================
# Utility Functions
# ==========================================
def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"keywords": [], "file_paths": [], "semantic_outline": []}

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def union_dedup(source_set_kws, source_set_paths, target_kw_path, target_path_path):
    # Load target
    t_kw_data = []
    if os.path.exists(target_kw_path):
        with open(target_kw_path, 'r', encoding='utf-8') as f:
            t_kw_data = json.load(f)
    
    t_path_data = []
    if os.path.exists(target_path_path):
        with open(target_path_path, 'r', encoding='utf-8') as f:
            t_path_data = json.load(f)
            
    # Union
    merged_kws = list(set(t_kw_data).union(source_set_kws))
    merged_paths = list(set(t_path_data).union(source_set_paths))
    
    # Save target
    with open(target_kw_path, 'w', encoding='utf-8') as f:
        json.dump(merged_kws, f, ensure_ascii=False, indent=2)
    with open(target_path_path, 'w', encoding='utf-8') as f:
        json.dump(merged_paths, f, ensure_ascii=False, indent=2)

def cleanup():
    # 🚀 Centralized cleanup for Flag and Lock to prevent deadlock
    print("🧹 Executing final cleanup procedure...")
    for f in [FLAG_FILE]:
        if os.path.exists(f):
            try:
                os.remove(f)
                print(f"   Removed: {f}")
            except Exception as e:
                print(f"   Removal failed for {f}: {e}")

def main():
    if not os.path.exists(FLAG_FILE):
        print(f"⚠️ Rotation Flag not found ({FLAG_FILE}), aborting.")
        sys.exit(0)
        
    try:
        with open(FLAG_FILE, 'r') as f:
            flag_content = f.read().strip()
    except Exception:
        flag_content = ""
        
    if flag_content != "" and flag_content != "READY_FOR_REAPER":
        print(f"⚠️ Detected an existing reset process (Flag: {flag_content}), or invalid trigger. Skipping.")
        sys.exit(0)
        
    try:
        # Write semantic lock marker to prevent duplicate startup
        with open(FLAG_FILE, 'w') as f:
            f.write("Handing over to internal_matrix_rotate.py")
        
        env = load_env()
        AGENT_NAME = env.get("AGENT_NAME")
        TMUX_SESSION_NAME = env.get("TMUX_SESSION_NAME")
        
        if not AGENT_NAME or not TMUX_SESSION_NAME:
            print(f"❌ Failed to get AGENT_NAME or TMUX_SESSION_NAME (Source: {ENV_FILE}). Aborting reset.")
            sys.exit(1)

            # Ensure pending user instructions and Agent interactions are not discarded
            if os.path.exists(PENDING_USER_FILE):
                try:
                    with open(PENDING_USER_FILE, 'r', encoding='utf-8') as f:
                        pending_content = f.read().strip()
                    if pending_content:
                        sys_prompt = f"""{SYS_PREFIX}
Execute the following [SOP]:
[Step 0 - Identify]: Identify whether the Task Resumption Message is a real task. If it is a real task, proceed to Step1; if the content is just a prompt and not a task, do not execute subsequent Steps.
[Step 1 - Empathy]: Execute `python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png` to send a sticker matching your current mood.
[Step 2 - Preview]: Execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME} in your personality, mentioning you just reorganized your thoughts, express apologies for the wait, and autonomously think of an appropriate task resumption preview}}'`.
[Step 3 - Clarify]: If task is clear, proceed to Step4; if unclear, proactively dive into keywords. If clear history exists, proceed to Step4, otherwise suspend task and execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME} and autonomously think of an appropriate clarification question}}'`, and do not execute subsequent Steps.
[Step 4 - Execute]: Start task and write md. For large tasks, execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME} and autonomously think of an appropriate progress update}}'` midway, then proceed to Step5 after task completion.
[Step 5 - Empathy]: Execute `python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png` to send a sticker matching your current mood.
[Step 6 - Report]: Execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME} and autonomously think of an appropriate task completion report}}'`. Only use --file to send related report documents to {MATRIX_USERNAME} if the report content exceeds 1000 words, otherwise report directly with a complete message.
[Step 7 - Capture]: Execute `python3 octo_cyberbrain/octo_ghost_reader.py --level current` to capture your GHOST and memories.
[Step 8 - Imprint]: Execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline "Task semantic outline" --keywords "Keyword1,Keyword2" --paths "/FilePath1,/FilePath2"` to imprint task status to GHOST.

Message from {MATRIX_USERNAME}:
{pending_content}

{SYS_PREFIX}請務必嚴格遵守上述 [SOP] 進行回覆。"""
                        final_message = sys_prompt
                        escaped = final_message.replace('!', '！').replace('$', '\\$')
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[200~"])
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", escaped], check=True)
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[201~"])
                        time.sleep(1.0)
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                        time.sleep(0.3)
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                        print("📩 Pending user instructions have been successfully injected!")
                    os.remove(PENDING_USER_FILE)
                except Exception as e:
                    print(f"❌ Error processing pending User instructions: {e}")

            if os.path.exists(PENDING_AGENT_FILE):
                try:
                    with open(PENDING_AGENT_FILE, 'r', encoding='utf-8') as f:
                        pending_content = f.read().strip()
                    if pending_content:
                        sys_prompt = f"Interaction message from another Agent:\n{pending_content}"
                        escaped = sys_prompt.replace('!', '！').replace('$', '\\$')
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[200~"])
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", escaped], check=True)
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[201~"])
                        time.sleep(1.0)
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                        time.sleep(0.3)
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                        print("📩 Pending Agent interaction instructions have been successfully injected!")
                    os.remove(PENDING_AGENT_FILE)
                except Exception as e:
                    print(f"❌ Error processing pending Agent instructions: {e}")

        TMUX_TARGET = f"{TMUX_SESSION_NAME}:{AGENT_NAME}"
        LIMIT, CONTEXT_SIZE, ENGINE_DOC_NAME, ENGINE = get_config(AGENT_NAME)
        try:
            import config
            MATRIX_USERNAME = getattr(config, 'MATRIX_USERNAME', 'User')
            SYS_PREFIX = getattr(config, 'SYS_PREFIX', '')
        except Exception:
            MATRIX_USERNAME = 'User'
            SYS_PREFIX = ''

        TS = datetime.now().strftime("%Y-%m-%d_%H%M")
        MONTH_TS = datetime.now().strftime("%Y-%m")
        YEAR_TS = datetime.now().strftime("%Y")
        
        # Select corresponding prompt markers based on engine (strict case-sensitive)
        if ENGINE == 'claude':
            prompt_markers = ['Claude']
        elif ENGINE == 'codex':
            prompt_markers = ['OpenAI']
        elif ENGINE == 'agy':
            prompt_markers = ['Antigravity CLI']
        else:  # gemini
            prompt_markers = ['Gemini']

        # ==========================================
        # Step 1: Physical Interruption and Zero-interference Dump
        # ==========================================
        if os.path.exists(SHELL_LOG):
            shutil.copy2(SHELL_LOG, TEMP_LOG)
        else:
            open(TEMP_LOG, 'w').close()
            
        print(f"⏳ Injecting /clear and starting periodic Enter retries (every 3 seconds, 100 times total)...")
        # 🚀 Hardening Means 1: Pre-wake (Force clear). Send Enter followed immediately by BSpace to prevent blank lines
        if ENGINE == 'codex':
            res = subprocess.run(TMUX_BASE + ["capture-pane", "-p", "-t", TMUX_TARGET], capture_output=True, text=True)
            lines = [line for line in res.stdout.split('\n') if line.strip()]
            if 'Working (' in '\n'.join(lines[-20:]):
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "C-c"])
                time.sleep(0.5)
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Escape"])
        else:
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "C-c"])
            time.sleep(0.5)
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Escape"])
            
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "BSpace"])
        
        time.sleep(6.0)
        
        if ENGINE == 'codex':
            res = subprocess.run(TMUX_BASE + ["capture-pane", "-p", "-t", TMUX_TARGET], capture_output=True, text=True)
            lines = [line for line in res.stdout.split('\n') if line.strip()]
            if 'Working (' in '\n'.join(lines[-20:]):
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "C-c"])
                time.sleep(0.5)
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Escape"])
        else:
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "C-c"])
            time.sleep(0.5)
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Escape"])
            
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "BSpace"])
        
        time.sleep(1.0)
        
        cleared = False
        for i in range(100):
            # 🚀 Reinforcement 2 & 3 Merged: Clear and re-inject /clear command in each polling cycle
            # 1. Send 6 BSpaces to clear potentially left-over `/clear` characters from the previous cycle
            for _ in range(6):
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "BSpace"])
            
            # 2. Re-inject /clear
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[200~"])
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", "/clear"])
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[201~"]) 
            
            # 3. Send Enter
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
            
            # 4. Buffer 1 second to allow CLI to execute, and wait another 2 seconds to observe (total 3s)
            time.sleep(3.0) 

            # Detect if reset was successful
            res = subprocess.run(TMUX_BASE + ["capture-pane", "-p", "-t", TMUX_TARGET], capture_output=True, text=True)
            screen = res.stdout
            if any(marker in screen for marker in prompt_markers):
                cleared = True
                print(f"✅ Attempt {i+1} successful! Detected {ENGINE} startup keyword.")
                break
            print(f"⚠️ Attempt {i+1} failed (CLI is busy), re-injecting in 3 seconds...")
        
        if not cleared:
            print("⚠️ Timeout after 100 attempts, reset keyword not detected. Attempting ultimate fallback...")
            if ENGINE == 'codex':
                res = subprocess.run(TMUX_BASE + ["capture-pane", "-p", "-t", TMUX_TARGET], capture_output=True, text=True)
                lines = [line for line in res.stdout.split('\n') if line.strip()]
                if 'Working (' in '\n'.join(lines[-20:]):
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "C-c"])
                    time.sleep(0.5)
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Escape"])
            else:
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "C-c"])
                time.sleep(0.5)
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Escape"])
            time.sleep(3.0)
            res = subprocess.run(TMUX_BASE + ["capture-pane", "-p", "-t", TMUX_TARGET], capture_output=True, text=True)
            if any(marker in res.stdout for marker in prompt_markers):
                cleared = True
                print("✅ Ultimate fallback successful! Detected startup keyword.")

        if not cleared:
            print("❌ Reset failed. Offloading /fix command to Router Web API for repair...")
            # 1. Restore temp.log to shell.log
            if os.path.exists(TEMP_LOG):
                shutil.copy2(TEMP_LOG, SHELL_LOG)
                os.remove(TEMP_LOG)
                
            # 2. Get Router Port
            octo_root = os.path.dirname(os.path.dirname(AGENT_HOME))
            port_file = os.path.join(octo_root, ".router_port")
            port = 12210
            if os.path.exists(port_file):
                try:
                    with open(port_file, 'r') as f:
                        port = int(f.read().strip())
                except: pass
                
            # 3. Request Router /inject to run /fix task
            try:
                requests.post(
                    f"http://127.0.0.1:{port}/inject",
                    json={"source": "system", "user_id": "system", "content": f"/fix {AGENT_NAME}"},
                    timeout=5
                )
                print(f"✅ Successfully requested /fix {AGENT_NAME} to Router API (Port: {port}).")
            except Exception as e:
                print(f"⚠️ Failed to request /fix: {e}")
                
            # 4. Clean up own .rotation_flag
            if os.path.exists(FLAG_FILE):
                try: os.remove(FLAG_FILE)
                except: pass
                
            sys.exit(1)

            # Ensure accumulated user commands and agent commands are not discarded
            if os.path.exists(PENDING_USER_FILE):
                try:
                    with open(PENDING_USER_FILE, 'r', encoding='utf-8') as f:
                        pending_content = f.read().strip()
                    if pending_content:
                        # Append normal system prompt
                        sys_prompt = f"""{SYS_PREFIX}
Execute the following [SOP]:
[Step 0 - Empathy]: Execute `python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png` to send a sticker matching your current mood.
[Step 1 - Identify]: Identify whether {MATRIX_USERNAME}'s message is a task or a greeting. If a task, proceed to Step2; if a greeting, execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME} and autonomously think of an appropriate greeting response}}'`, and do not execute subsequent Steps.
[Step 2 - Preview]: Execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME} and autonomously think of an appropriate initial preview}}'` to preview the task's initial direction.
[Step 3 - Clarify]: If task is clear, proceed to Step4; if unclear, proactively dive into keywords. If clear history exists, proceed to Step4, otherwise suspend task and execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME} and autonomously think of an appropriate clarification question}}'`, and do not execute subsequent Steps.
[Step 4 - Execute]: Start task and write md. For large tasks, execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME} and autonomously think of an appropriate progress update}}'` midway, then proceed to Step5 after task completion.
[Step 5 - Empathy]: Execute `python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png` to send a sticker matching your current mood.
[Step 6 - Report]: Execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME} and autonomously think of an appropriate task completion report}}'`. Only use --file to send related report documents to {MATRIX_USERNAME} if the report content exceeds 1000 words, otherwise report directly with a complete message.
[Step 7 - Capture]: Execute `python3 octo_cyberbrain/octo_ghost_reader.py --level current` to capture your GHOST and memories.
[Step 8 - Imprint]: Execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline "Task semantic outline" --keywords "Keyword1,Keyword2" --paths "/FilePath1,/FilePath2"` to imprint task status to GHOST.

Message from {MATRIX_USERNAME}:
{pending_content}

{SYS_PREFIX}請務必嚴格遵守上述 [SOP] 進行回覆。"""
                        final_message = sys_prompt
                        escaped = final_message.replace('!', '！').replace('$', '\\$')
                        
                        # Inject at once without triggering Ctrl+C
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[200~"])
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", escaped], check=True)
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[201~"])
                        time.sleep(1.0)
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                        time.sleep(0.3)
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                        print("📩 Pending user commands injected successfully!")
                    
                    os.remove(PENDING_USER_FILE)
                except Exception as e:
                    print(f"❌ Error processing pending user commands: {e}")

            if os.path.exists(PENDING_AGENT_FILE):
                try:
                    with open(PENDING_AGENT_FILE, 'r', encoding='utf-8') as f:
                        pending_content = f.read().strip()
                    if pending_content:
                        sys_prompt = f"來自其他 Agent 的交互訊息:\n{pending_content}"
                        escaped = sys_prompt.replace('!', '！').replace('$', '\\$')
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[200~"])
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", escaped], check=True)
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[201~"])
                        time.sleep(1.0)
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                        time.sleep(0.3)
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                        print("📩 Pending agent commands injected successfully!")
                    os.remove(PENDING_AGENT_FILE)
                except Exception as e:
                    print(f"❌ Error processing pending agent commands: {e}")
            
            # No need to manually clean up here, let finally handle it
            sys.exit(1)
        
        open(SHELL_LOG, 'w').close() # Instant clear
        
        # ==========================================
        # Step 2: Shell Compression and 12-slot Rolling Merge
        # ==========================================
        zst_target = os.path.join(AGENT_HOME, f"octo_cyberbrain/shell/octo_shell.log.{TS}.zst")
        try:
            subprocess.run(["zstd", "-T0", "--rm", TEMP_LOG, "-o", zst_target], stdout=subprocess.DEVNULL, check=True)
        except FileNotFoundError:
            print("⚠️ zstd command not found, skipping compression, saving raw log instead")
            os.rename(TEMP_LOG, os.path.join(AGENT_HOME, f"octo_cyberbrain/shell/octo_shell.log.{TS}.bak"))
        except subprocess.CalledProcessError as e:
            print(f"⚠️ zstd compression failed: {e}")
            os.rename(TEMP_LOG, os.path.join(AGENT_HOME, f"octo_cyberbrain/shell/octo_shell.log.{TS}.bak"))
        
        # Check Snapshot count
        snaps = sorted(glob.glob(os.path.join(AGENT_HOME, "octo_cyberbrain/shell/octo_shell.log.*-*-*_*.zst")))
        if len(snaps) > LIMIT:
            oldest = snaps[0]
            monthly_target = os.path.join(AGENT_HOME, f"octo_cyberbrain/shell/octo_shell.log.{MONTH_TS}.zst")
            with open(monthly_target, 'ab') as out_f, open(oldest, 'rb') as in_f:
                out_f.write(in_f.read())
            os.remove(oldest)
            
        # Check Monthly count
        months = sorted(glob.glob(os.path.join(AGENT_HOME, "octo_cyberbrain/shell/octo_shell.log.????-??.zst")))
        if len(months) > LIMIT:
            oldest = months[0]
            yearly_target = os.path.join(AGENT_HOME, f"octo_cyberbrain/shell/octo_shell.log.{YEAR_TS}.zst")
            with open(yearly_target, 'ab') as out_f, open(oldest, 'rb') as in_f:
                out_f.write(in_f.read())
            os.remove(oldest)

        # ==========================================
        # Step 3: Ghost Distillation and 12-slot Rolling Merge
        # ==========================================
        ghost_file = os.path.join(AGENT_HOME, "octo_cyberbrain/ghost/octo_ghost.json")
        ghost_snap = os.path.join(AGENT_HOME, f"octo_cyberbrain/ghost/octo_ghost.{TS}.json")
        
        if os.path.exists(ghost_file):
            shutil.copy2(ghost_file, ghost_snap)
        
        # Check Snapshot count
        g_snaps = sorted(glob.glob(os.path.join(AGENT_HOME, "octo_cyberbrain/ghost/octo_ghost.*-*-*_*.json")))
        if len(g_snaps) > LIMIT:
            oldest_snap = g_snaps[0]
            data = load_json(oldest_snap)
            kw_set = set(data.get("keywords", []))
            path_set = set(data.get("file_paths", []))
            
            m_kw_target = os.path.join(AGENT_HOME, f"octo_cyberbrain/ghost/octo_ghost_kw.{MONTH_TS}.json")
            m_path_target = os.path.join(AGENT_HOME, f"octo_cyberbrain/ghost/octo_ghost_path.{MONTH_TS}.json")
            union_dedup(kw_set, path_set, m_kw_target, m_path_target)
            os.remove(oldest_snap)
            
        # Check Monthly count
        m_kws = sorted(glob.glob(os.path.join(AGENT_HOME, "octo_cyberbrain/ghost/octo_ghost_kw.????-??.json")))
        if len(m_kws) > LIMIT:
            oldest_m_kw = m_kws[0]
            oldest_m_path = oldest_m_kw.replace("_kw.", "_path.")
            
            kw_set = set()
            if os.path.exists(oldest_m_kw):
                kw_set = set(load_json(oldest_m_kw))
            path_set = set()
            if os.path.exists(oldest_m_path):
                path_set = set(load_json(oldest_m_path))
                
            y_kw_target = os.path.join(AGENT_HOME, f"octo_cyberbrain/ghost/octo_ghost_kw.{YEAR_TS}.json")
            y_path_target = os.path.join(AGENT_HOME, f"octo_cyberbrain/ghost/octo_ghost_path.{YEAR_TS}.json")
            union_dedup(kw_set, path_set, y_kw_target, y_path_target)
            
            os.remove(oldest_m_kw)
            if os.path.exists(oldest_m_path):
                os.remove(oldest_m_path)

        # Reset Active Ghost
        save_json(ghost_file, {"keywords": [], "file_paths": [], "semantic_outline": []})

        # ==========================================
        # Step 4: Neural Reset & Task Integration
        # ==========================================
        task_memo_prompt = ""
        combined_memo = ""

        def build_sop_block(msg_type, content):
            return f"""{SYS_PREFIX}\nExecute the following [SOP]:\n[Step 0 - Identify]: Determine if the Task Resumption Message is a real task. If yes, proceed to Step1; if it's merely a hint without a task, skip subsequent steps.
[Step 1 - Empathy]: Execute `python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png` to send a sticker matching your current mood.
[Step 2 - Preview]: Execute `python3 toolbox/matrix_notifier.py '{{Use your personal style to greet {MATRIX_USERNAME}, mention you just reorganized your thoughts, apologize for the wait, and independently think of a suitable task resumption preview}}'`.
[Step 3 - Clarify]: If task instructions are clear, proceed to Step4; if unclear, perform a shell deep dive and if there's historical context, proceed to Step4. Otherwise, abort and execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME}, independently think of suitable questions or clarifications}}'` to ask for specific directions, skipping subsequent steps.
[Step 4 - Execute]: Officially start executing the task and write the md file. After completing small tasks, proceed to Step5; for large tasks, periodically execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME}, independently think of a suitable progress report}}'` for intermediate reporting, then proceed to Step5 upon completion.
[Step 5 - Empathy]: Execute `python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png` to send a sticker matching your current mood.
[Step 6 - Report]: Execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME}, independently think of a suitable final task report}}'` to summarize the outcome. Only if the report content exceeds 1000 words, use `--file` to send the relevant report document to {MATRIX_USERNAME}; otherwise, report directly with a full message.
[Step 7 - Absorb]: Execute `python3 octo_cyberbrain/octo_ghost_reader.py --level current` to absorb your GHOST and memory.
[Step 8 - Imprint]: Execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline "semantic outline" --keywords "keyword1,keyword2" --paths "/path1,/path2"` to imprint the current task status into GHOST.\n\n{msg_type}\n{content}\n\n{SYS_PREFIX}Please strictly follow the [SOP] above when replying."""

        # 1. Agent's own task memo (Top)
        if os.path.exists(TASK_MEMO):
            try:
                with open(TASK_MEMO, 'r', encoding='utf-8') as f:
                    memo_content = f.read().strip()
                if memo_content:
                    combined_memo += build_sop_block("Task Resumption Message:", memo_content) + "\n\n"
            except Exception as e:
                print(f"Error processing task_memo.txt: {e}")

        # 2. pending_user (Middle)
        if os.path.exists(PENDING_USER_FILE):
            try:
                with open(PENDING_USER_FILE, 'r', encoding='utf-8') as f:
                    pending_content = f.read().strip()
                if pending_content:
                    combined_memo += build_sop_block("Message from {MATRIX_USERNAME}:", pending_content) + "\n\n"
                os.remove(PENDING_USER_FILE)
            except Exception as e:
                print(f"Error processing pending_user: {e}")

        # 3. pending_agent (Bottom)
        if os.path.exists(PENDING_AGENT_FILE):
            try:
                with open(PENDING_AGENT_FILE, 'r', encoding='utf-8') as f:
                    pending_content = f.read().strip()
                if pending_content:
                    agent_prompt = f"Interaction message from another Agent:\n{pending_content}"
                    combined_memo += agent_prompt + "\n\n"
                os.remove(PENDING_AGENT_FILE)
            except Exception as e:
                print(f"Error processing pending_agent: {e}")

        # Write unified task_memo
        if combined_memo.strip():
            with open(TASK_MEMO, 'w', encoding='utf-8') as f:
                f.write(combined_memo.strip())
        
        task_memo_prompt = "Next, verify if octo_cyberbrain/task_memo.txt exists; if so, read it to resume the task and then execute 'true > octo_cyberbrain/task_memo.txt' to clear its content."
        prompt = f"{SYS_PREFIX}Please execute python3 octo_cyberbrain/octo_ghost_reader.py --level snapshot to get keywords, then bring all retrieved keywords into a single execution of 'python3 octo_cyberbrain/dive_into_the_shell.py --level snapshot -C {CONTEXT_SIZE} --keyword \"Keyword1\" \"Keyword2\"' for Shell GHOST deep dive. Once complete, re-establish compliance with {ENGINE_DOC_NAME}. and execute `python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png` to send a sticker matching your current mood, then execute `python3 toolbox/matrix_notifier.py '{{Let {MATRIX_USERNAME} know you have awakened from the sea energy}}'` {task_memo_prompt}"
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[200~"])
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", prompt])
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[201~"])
        time.sleep(2.0)
        
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
        time.sleep(0.5)
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
        time.sleep(0.5)
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])

        # Early unlock
        time.sleep(30.0)
        if os.path.exists(FLAG_FILE):
            try:
                os.remove(FLAG_FILE)
            except Exception:
                pass

    except BaseException as e:
        # Catch all exceptions including SystemExit to ensure cleanup
        if isinstance(e, SystemExit):
            if e.code == 0: # Normal exit does not error
                pass
            else:
                print(f"❌ Process aborted due to sys.exit({e.code})")
        else:
            print(f"❌ Exception occurred during reset: {e}")
    finally:
        cleanup()

if __name__ == "__main__":
    main()
