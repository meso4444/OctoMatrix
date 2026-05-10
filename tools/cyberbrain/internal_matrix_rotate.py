#!/usr/bin/env python3
import os
import sys
import json
import glob
import shutil
import subprocess
import time
from datetime import datetime

# ==========================================
# 1. Read environment variable landing file
# ==========================================
ENV_FILE = "octo_cyberbrain/.cyberbrain_env"
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
    # Search up for config.py
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if os.path.basename(base_dir) == 'agent_home':
        base_dir = os.path.dirname(base_dir)
    sys.path.append(base_dir)
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
                    break
        return limit, context_size, engine_doc_name, engine
    except Exception:
        return 12, 50, "GEMINI.md", "gemini"


# 🔍 Environment adaptation: auto-locate Tmux Socket
def get_tmux_cmd():
    return ["tmux"]

TMUX_BASE = get_tmux_cmd()

# ==========================================
# Helper functions
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

def main():
    env = load_env()
    AGENT_NAME = env.get("AGENT_NAME")
    TMUX_SESSION_NAME = env.get("TMUX_SESSION_NAME")
    
    if not AGENT_NAME or not TMUX_SESSION_NAME:
        print("❌ Unable to get AGENT_NAME or TMUX_SESSION_NAME. Aborting rotation.")
        sys.exit(1)

    TMUX_TARGET = f"{TMUX_SESSION_NAME}:{AGENT_NAME}"
    LIMIT, CONTEXT_SIZE, ENGINE_DOC_NAME, ENGINE = get_config(AGENT_NAME)
    TS = datetime.now().strftime("%Y-%m-%d_%H%M")
    MONTH_TS = datetime.now().strftime("%Y-%m")
    YEAR_TS = datetime.now().strftime("%Y")

    # Choose markers based on engine (strict case-sensitive)
    if ENGINE == 'claude':
        prompt_markers = ['Claude']
    elif ENGINE == 'codex':
        prompt_markers = ['OpenAI']
    else:  # gemini
        prompt_markers = ['Gemini']

    # ==========================================
    # Step 1: Physical interruption and zero-disturbance dump
    # ==========================================
    shell_log = "octo_cyberbrain/shell/octo_shell.log"
    temp_log = "octo_cyberbrain/shell/temp.log"

    if os.path.exists(shell_log):
        shutil.copy2(shell_log, temp_log)
    else:
        open(temp_log, 'w').close()

    print(f"⏳ Injecting /clear and starting periodic Enter attempts (every 3s, up to 100 times)...")
    # 🚀 Strengthening Method 1: Pre-wakeup. Send Enter first to ensure CLI is active
    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])

    # 🚀 Strengthening Method 2: Inject /clear command (only once)
    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "/clear "]) 

    cleared = False
    for i in range(100):
        # 🚀 Strengthening Method 3: Continuously fire Enter to trigger execution
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])

        time.sleep(3.0) # Wait 3s to observe results

        # Check for reset success
        res = subprocess.run(TMUX_BASE + ["capture-pane", "-p", "-t", TMUX_TARGET], capture_output=True, text=True)
        screen = res.stdout
        if any(marker in screen for marker in prompt_markers):
            cleared = True
            print(f"✅ Attempt {i+1} successful! Detected {ENGINE} startup markers.")
            break
        print(f"⚠️ Attempt {i+1} failed (CLI busy), firing Enter again in 3 seconds...")

    if not cleared:
        print("⚠️ Timeout: Failed to detect reset markers after 100 attempts, canceling injection.")
        if os.path.exists(temp_log):
            shutil.copy2(temp_log, shell_log)
            os.remove(temp_log)
        
        flag_file = "octo_cyberbrain/.rotation_flag"
        if os.path.exists(flag_file):
            os.remove(flag_file)
            
        # Send recovery prompt to let Agent resume previous task
        recovery_prompt = "[System Prompt] System maintenance timed out and was canceled. Please confirm whether octo_cyberbrain/task_memo.txt exists. If it exists, read it to resume the interrupted task, and delete task_memo.txt after reading."
        escaped_rec = recovery_prompt.replace('!', '！').replace('$', '\\$')
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", escaped_rec])
        time.sleep(1.0)
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
        time.sleep(0.5)

        # Ensure accumulated user commands are not abandoned
        lock_file = "octo_cyberbrain/inject_block.lock"
        pending_file = "octo_cyberbrain/pending_inject.txt"
        if os.path.exists(lock_file):
            os.remove(lock_file)
            
        if os.path.exists(pending_file):
            try:
                with open(pending_file, 'r', encoding='utf-8') as f:
                    pending_content = f.read().strip()
                if pending_content:
                    sys_prompt = "\n\n[System Prompt]This command is from Matrix user, please reply to the user first before starting the task. Before starting the task, if the keywords mentioned by the user or the task lacks complete context, proactively perform a keyword dive into shell records to check if there is related context in the records. If the execution direction is clear, execute it. If it is unclear, pause the task first and reply to the user with a recap of the related records to confirm the direction with the user, but it is strictly prohibited to mention to the user that you performed shell dive related operations; After task completion, complete the following [SOP]:\n[Step 1 - Report]: Execute `python3 toolbox/matrix_notifier.py` to send task message or file to user with Avatar emoji.\n[Step 2 - Capture]: Execute `python3 octo_cyberbrain/octo_ghost_reader.py --level current` to capture your GHOST and memories.\n[Step 3 - Imprint]: Execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"Semantic Outline\" --keywords \"Keyword1,Keyword2\" --paths \"/FilePath1,/FilePath2\"` to imprint task status to GHOST."
                    final_message = pending_content + sys_prompt
                    escaped = final_message.replace('!', '！').replace('$', '\\$')
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", escaped], check=True)
                    time.sleep(1.0)
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                    time.sleep(0.3)
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                    print("📩 Successfully injected accumulated user commands!")
                os.remove(pending_file)
            except Exception as e:
                print(f"❌ Error processing accumulated commands: {e}")
                
        sys.exit(1)

    open(shell_log, 'w').close() # Instant clear
    
    flag_file = "octo_cyberbrain/.rotation_flag"
    if os.path.exists(flag_file):
        os.remove(flag_file)

    # ==========================================
    # Step 2: Shell compression and 12-snapshot rolling merge
    # ==========================================
    zst_target = f"octo_cyberbrain/shell/octo_shell.log.{TS}.zst"
    try:
        subprocess.run(["zstd", "-T0", "--rm", temp_log, "-o", zst_target], stdout=subprocess.DEVNULL, check=True)
    except FileNotFoundError:
        print("⚠️ zstd command not found, skipping compression, saving raw log file")
        os.rename(temp_log, f"octo_cyberbrain/shell/octo_shell.log.{TS}.bak")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ zstd compression failed: {e}")
        os.rename(temp_log, f"octo_cyberbrain/shell/octo_shell.log.{TS}.bak")
    
    # Check Snapshot count
    snaps = sorted(glob.glob("octo_cyberbrain/shell/octo_shell.log.*-*-*_*.zst"))
    if len(snaps) > LIMIT:
        oldest = snaps[0]
        monthly_target = f"octo_cyberbrain/shell/octo_shell.log.{MONTH_TS}.zst"
        with open(monthly_target, 'ab') as out_f, open(oldest, 'rb') as in_f:
            out_f.write(in_f.read())
        os.remove(oldest)
        
    # Check Monthly count
    months = sorted(glob.glob("octo_cyberbrain/shell/octo_shell.log.????-??.zst"))
    if len(months) > LIMIT:
        oldest = months[0]
        yearly_target = f"octo_cyberbrain/shell/octo_shell.log.{YEAR_TS}.zst"
        with open(yearly_target, 'ab') as out_f, open(oldest, 'rb') as in_f:
            out_f.write(in_f.read())
        os.remove(oldest)

    # ==========================================
    # Step 3: Ghost distillation and 12-snapshot rolling merge
    # ==========================================
    ghost_file = "octo_cyberbrain/ghost/octo_ghost.json"
    ghost_snap = f"octo_cyberbrain/ghost/octo_ghost.{TS}.json"
    
    if os.path.exists(ghost_file):
        shutil.copy2(ghost_file, ghost_snap)
    
    # Check Snapshot count
    g_snaps = sorted(glob.glob("octo_cyberbrain/ghost/octo_ghost.*-*-*_*.json"))
    if len(g_snaps) > LIMIT:
        oldest_snap = g_snaps[0]
        data = load_json(oldest_snap)
        kw_set = set(data.get("keywords", []))
        path_set = set(data.get("file_paths", []))
        
        m_kw_target = f"octo_cyberbrain/ghost/octo_ghost_kw.{MONTH_TS}.json"
        m_path_target = f"octo_cyberbrain/ghost/octo_ghost_path.{MONTH_TS}.json"
        union_dedup(kw_set, path_set, m_kw_target, m_path_target)
        os.remove(oldest_snap)
        
    # Check Monthly count
    m_kws = sorted(glob.glob("octo_cyberbrain/ghost/octo_ghost_kw.????-??.json"))
    if len(m_kws) > LIMIT:
        oldest_m_kw = m_kws[0]
        oldest_m_path = oldest_m_kw.replace("_kw.", "_path.")
        
        kw_set = set()
        if os.path.exists(oldest_m_kw):
            kw_set = set(load_json(oldest_m_kw))
        path_set = set()
        if os.path.exists(oldest_m_path):
            path_set = set(load_json(oldest_m_path))
            
        y_kw_target = f"octo_cyberbrain/ghost/octo_ghost_kw.{YEAR_TS}.json"
        y_path_target = f"octo_cyberbrain/ghost/octo_ghost_path.{YEAR_TS}.json"
        union_dedup(kw_set, path_set, y_kw_target, y_path_target)
        
        os.remove(oldest_m_kw)
        if os.path.exists(oldest_m_path):
            os.remove(oldest_m_path)

    # Reset Active Ghost
    save_json(ghost_file, {"keywords": [], "file_paths": [], "semantic_outline": []})

    # ==========================================
    # Step 4: Soul reincarnation injection (Neural Reset Injection)
    # ==========================================
    prompt = f"[System Prompt]Please execute python3 octo_cyberbrain/octo_ghost_reader.py --level snapshot to get keywords, then execute `python3 octo_cyberbrain/dive_into_the_shell.py --level snapshot -C {CONTEXT_SIZE} --keyword \"keyword1\" \"keyword2\"` in one go to perform Shell GHOST deep-dive, and re-promote adherence to {ENGINE_DOC_NAME} upon completion. This task does not need to send message to user. Then confirm whether octo_cyberbrain/task_memo.txt exists. If it exists, read it to resume the task, and delete task_memo.txt after reading."

    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", prompt])
    time.sleep(2.0) # Long prompt needs longer input wait time

    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
    time.sleep(0.5)
    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
    time.sleep(0.5)
    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"]) # Triple Enter insurance

    # ==========================================
    # Step 5: Unlock and pending injection
    # ==========================================
    lock_file = "octo_cyberbrain/inject_block.lock"
    pending_file = "octo_cyberbrain/pending_inject.txt"        
    if os.path.exists(pending_file):
        try:
            with open(pending_file, 'r', encoding='utf-8') as f:
                pending_content = f.read().strip()
                
            if pending_content:
                sys_prompt = f"\n\n[System Prompt]This command is from Matrix user, please reply to the user first before starting the task. Before starting the task, if the keywords mentioned by the user or the task lacks complete context, proactively perform a keyword dive into shell records to check if there is related context in the records. If the execution direction is clear, execute it. If it is unclear, pause the task first and reply to the user with a recap of the related records to confirm the direction with the user, but it is strictly prohibited to mention to the user that you performed shell dive related operations; After task completion, complete the following [SOP]:\n[Step 1 - Report]: Execute `python3 toolbox/matrix_notifier.py` to send task message or file to user with Avatar emoji.\n[Step 2 - Capture]: Execute `python3 octo_cyberbrain/octo_ghost_reader.py --level current` to capture your GHOST and memories.\n[Step 3 - Imprint]: Execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"Semantic Outline\" --keywords \"Keyword1,Keyword2\" --paths \"/FilePath1,/FilePath2\"` to imprint task status to GHOST."
                final_message = pending_content + sys_prompt
                escaped = final_message.replace('!', '！').replace('$', '\\$')
                
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", escaped], check=True)
                time.sleep(1.0)
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                time.sleep(0.3)
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                print("📩 Successfully injected accumulated user commands!")
            
            os.remove(pending_file)
        except Exception as e:
            print(f"❌ Error processing accumulated commands: {e}")

    if os.path.exists(lock_file):
        os.remove(lock_file)

if __name__ == "__main__":
    main()
