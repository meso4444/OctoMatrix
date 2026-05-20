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
# 1. Path and Environment Hardening
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_HOME = os.path.dirname(SCRIPT_DIR)
ENV_FILE = os.path.join(AGENT_HOME, "octo_cyberbrain/.cyberbrain_env")

# Define lock and log paths (Absolute Paths)
LOCK_FILE = os.path.join(AGENT_HOME, "octo_cyberbrain/inject_block.lock")
FLAG_FILE = os.path.join(AGENT_HOME, "octo_cyberbrain/.rotation_flag")
SHELL_LOG = os.path.join(AGENT_HOME, "octo_cyberbrain/shell/octo_shell.log")
TEMP_LOG = os.path.join(AGENT_HOME, "octo_cyberbrain/shell/temp.log")
PENDING_FILE = os.path.join(AGENT_HOME, "octo_cyberbrain/pending_inject.txt")
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
    for f in [LOCK_FILE, FLAG_FILE]:
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
        
    if os.path.getsize(FLAG_FILE) > 0:
        print("⚠️ Detected an existing reset process (Flag is locked), skipping.")
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

        TMUX_TARGET = f"{TMUX_SESSION_NAME}:{AGENT_NAME}"
        LIMIT, CONTEXT_SIZE, ENGINE_DOC_NAME, ENGINE = get_config(AGENT_NAME)
        TS = datetime.now().strftime("%Y-%m-%d_%H%M")
        MONTH_TS = datetime.now().strftime("%Y-%m")
        YEAR_TS = datetime.now().strftime("%Y")
        
        # Select corresponding prompt markers based on engine (strict case-sensitive)
        if ENGINE == 'claude':
            prompt_markers = ['Claude']
        elif ENGINE == 'codex':
            prompt_markers = ['OpenAI']
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
        # 🚀 Hardening Means 1: Pre-wake (Force clear). [Ctrl+C] + [Enter] -> wait 6s -> [Ctrl+C] + [Enter]
        if ENGINE == 'codex':
            res = subprocess.run(TMUX_BASE + ["capture-pane", "-p", "-t", TMUX_TARGET], capture_output=True, text=True)
            lines = [line for line in res.stdout.split('\n') if line.strip()]
            if 'Working (' in '\n'.join(lines[-20:]):
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "C-c"])
        else:
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "C-c"])
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
        time.sleep(6.0)
        if ENGINE == 'codex':
            res = subprocess.run(TMUX_BASE + ["capture-pane", "-p", "-t", TMUX_TARGET], capture_output=True, text=True)
            lines = [line for line in res.stdout.split('\n') if line.strip()]
            if 'Working (' in '\n'.join(lines[-20:]):
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "C-c"])
        else:
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "C-c"])
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
        time.sleep(1.0)
        
        # 🚀 Hardening Means 2: Inject /clear command (only once)
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", "/clear"]) 
        
        cleared = False
        for i in range(100):
            # 🚀 Hardening Means 3: Continuously trigger Enter to trigger execution
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])

            time.sleep(3.0) # Wait 3 seconds to observe the result

            # Detect if reset was successful
            res = subprocess.run(TMUX_BASE + ["capture-pane", "-p", "-t", TMUX_TARGET], capture_output=True, text=True)
            screen = res.stdout
            if any(marker in screen for marker in prompt_markers):
                cleared = True
                print(f"✅ Attempt {i+1} successful! Detected {ENGINE} startup keyword.")
                break
            print(f"⚠️ Attempt {i+1} failed (CLI is busy), sending Enter again in 3 seconds...")
        
        if not cleared:
            print("⚠️ Timeout after 100 attempts, reset keyword not detected. Attempting ultimate fallback [Ctrl+C] -> 6s -> [Ctrl+C]...")
            if ENGINE == 'codex':
                res = subprocess.run(TMUX_BASE + ["capture-pane", "-p", "-t", TMUX_TARGET], capture_output=True, text=True)
                lines = [line for line in res.stdout.split('\n') if line.strip()]
                if 'Working (' in '\n'.join(lines[-20:]):
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "C-c"])
            else:
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "C-c"])
            time.sleep(6.0)
            if ENGINE == 'codex':
                res = subprocess.run(TMUX_BASE + ["capture-pane", "-p", "-t", TMUX_TARGET], capture_output=True, text=True)
                lines = [line for line in res.stdout.split('\n') if line.strip()]
                if 'Working (' in '\n'.join(lines[-20:]):
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "C-c"])
            else:
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "C-c"])
            time.sleep(3.0)
            res = subprocess.run(TMUX_BASE + ["capture-pane", "-p", "-t", TMUX_TARGET], capture_output=True, text=True)
            if any(marker in res.stdout for marker in prompt_markers):
                cleared = True
                print("✅ Ultimate fallback successful! Detected startup keyword.")
            else:
                print("❌ Ultimate fallback failed. Sending SOS message. Cancelling injection.")
                help_msg = f"{AGENT_NAME} 可能卡在時空夾縫中, 如果 {AGENT_NAME} 還是沒有回覆訊息, 嘗試切換至其他 Agent 輸入 「/fix {AGENT_NAME}」讓其他 Agent 幫忙拯救 {AGENT_NAME}"
                escaped_help = help_msg.replace('!', '！').replace('$', '\\$')
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", escaped_help])
                time.sleep(1.0)
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
                time.sleep(0.5)

        if not cleared:
            print("⚠️ Timeout after 100 attempts, reset keyword not detected. Cancelling injection.")
            if os.path.exists(TEMP_LOG):
                shutil.copy2(TEMP_LOG, SHELL_LOG)
                os.remove(TEMP_LOG)
            
            # Send recovery prompt to let Agent resume the previous task
            recovery_prompt = "[System Prompt] Maintenance timeout cancelled. Please check if octo_cyberbrain/task_memo.txt exists. If it does, read it and resume the interrupted task, then delete it after reading."
            escaped_rec = recovery_prompt.replace('!', '！').replace('$', '\\$')
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", escaped_rec])
            time.sleep(1.0)
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
            time.sleep(0.5)

            # Ensure accumulated user commands are not discarded
            if os.path.exists(PENDING_FILE):
                try:
                    with open(PENDING_FILE, 'r', encoding='utf-8') as f:
                        pending_content = f.read().strip()
                    if pending_content:
                        # Append normal system prompt
                        sys_prompt = "\n\n[System Prompt] This command is from Matrix user, please execute `python3 toolbox/matrix_notifier.py` to reply to the user first before starting the task. Before starting the task, if the keywords or task mentioned by the user lack complete context, actively perform keyword shell deep dive to confirm if there is relevant context in the records. If the execution direction is clear, execute it. If it is unclear, pause the task first and reply to the user with a recap of the relevant records to confirm the direction, but do not mention to the user that you performed shell deep dive related operations. After task completion, complete the following [SOP]:\n[Step 1 - Report]: Execute `python3 toolbox/matrix_notifier.py` to send task message or file to user with Avatar emoji.\n[Step 2 - Capture]: Execute `python3 octo_cyberbrain/octo_ghost_reader.py --level current` to capture your GHOST and memories.\n[Step 3 - Imprint]: Execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"Semantic Outline\" --keywords \"Keyword1,Keyword2\" --paths \"/FilePath1,/FilePath2\"` to imprint task status to GHOST."""
                        final_message = pending_content + sys_prompt
                        escaped = final_message.replace('!', '！').replace('$', '\\$')
                        
                        # Inject at once without triggering Ctrl+C
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", escaped], check=True)
                        time.sleep(1.0)
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                        time.sleep(0.3)
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                        print("📩 Pending user commands injected successfully!")
                    
                    os.remove(PENDING_FILE)
                except Exception as e:
                    print(f"❌ Error processing pending commands: {e}")
            
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
        # Step 4: Neural Reset Injection
        # ==========================================
        prompt = f"[System Prompt] Please execute python3 octo_cyberbrain/octo_ghost_reader.py --level snapshot to get keywords, then bring all retrieved keywords into a single execution of 'python3 octo_cyberbrain/dive_into_the_shell.py --level snapshot -C {CONTEXT_SIZE} --keyword \"Keyword1\" \"Keyword2\"' for Shell GHOST deep dive. Once complete, re-establish compliance with {ENGINE_DOC_NAME}. This task does not require sending messages to the user. Next, verify if octo_cyberbrain/task_memo.txt exists; if so, read it to resume the task and then delete task_memo.txt."

        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", prompt])
        time.sleep(2.0) # Longer prompt needs more input wait time
        
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
        time.sleep(0.5)
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
        time.sleep(0.5)
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"]) # Triple Enter safety

        # ==========================================
        # Step 5: Pending Injection
        # ==========================================
        if os.path.exists(PENDING_FILE):
            try:
                with open(PENDING_FILE, 'r', encoding='utf-8') as f:
                    pending_content = f.read().strip()
                    
                if pending_content:
                    # Append normal system prompt
                    sys_prompt = f"\n\n[System Prompt] This command is from Matrix user, please execute `python3 toolbox/matrix_notifier.py` to reply to the user first before starting the task. Before starting the task, if the keywords or task mentioned by the user lack complete context, actively perform keyword shell deep dive to confirm if there is relevant context in the records. If the execution direction is clear, execute it. If it is unclear, pause the task first and reply to the user with a recap of the relevant records to confirm the direction, but do not mention to the user that you performed shell deep dive related operations. After task completion, complete the following [SOP]:\n[Step 1 - Report]: Execute `python3 toolbox/matrix_notifier.py` to send task message or file to user with Avatar emoji.\n[Step 2 - Capture]: Execute `python3 octo_cyberbrain/octo_ghost_reader.py --level current` to capture your GHOST and memories.\n[Step 3 - Imprint]: Execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"Semantic Outline\" --keywords \"Keyword1,Keyword2\" --paths \"/FilePath1,/FilePath2\"` to imprint task status to GHOST."""
                    final_message = pending_content + sys_prompt
                    escaped = final_message.replace('!', '！').replace('$', '\\$')
                    
                    # Inject at once without triggering Ctrl+C
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", escaped], check=True)
                    time.sleep(1.0)
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                    time.sleep(0.3)
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                    print("📩 Pending user commands injected successfully!")
                
                os.remove(PENDING_FILE)
            except Exception as e:
                print(f"❌ Error processing pending commands: {e}")

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
