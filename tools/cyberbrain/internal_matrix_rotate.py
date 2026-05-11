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
# 1. 定位與環境變數加固
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_HOME = os.path.dirname(SCRIPT_DIR)
ENV_FILE = os.path.join(AGENT_HOME, "octo_cyberbrain/.cyberbrain_env")

# 定義鎖檔路徑 (絕對路徑)
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
    # 上溯尋找 config.py (Agent Home 的上一層是 OctoMatrix root)
    # 結構: OctoMatrix/agent_home/Aleister/octo_cyberbrain/internal_matrix_rotate.py
    # 所以 AGENT_HOME 是 Aleister
    # OctoMatrix Root 是 AGENT_HOME 的上一層的上一層
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

# 🔍 環境自適應：自動定位 Tmux Socket
def get_tmux_cmd():
    return ["tmux"]

TMUX_BASE = get_tmux_cmd()

# ==========================================
# 工具函數
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
    # 🚀 統一清理 Flag 與 Lock，防止死鎖
    print("🧹 執行最後的清理程序...")
    for f in [LOCK_FILE, FLAG_FILE]:
        if os.path.exists(f):
            try:
                os.remove(f)
                print(f"   已移除: {f}")
            except Exception as e:
                print(f"   移除失敗 {f}: {e}")

def main():
    if not os.path.exists(FLAG_FILE):
        print(f"⚠️ 找不到 Rotation Flag ({FLAG_FILE})，中止程序。")
        sys.exit(0)
        
    if os.path.getsize(FLAG_FILE) > 0:
        print("⚠️ 偵測到已有重置進程正在執行 (Flag 已鎖定)，跳過本次啟動。")
        sys.exit(0)
    
    try:
        # 寫入語義化鎖定標記，防止重複啟動
        with open(FLAG_FILE, 'w') as f:
            f.write("移交 internal_matrix_rotate.py")
        
        env = load_env()
        AGENT_NAME = env.get("AGENT_NAME")
        TMUX_SESSION_NAME = env.get("TMUX_SESSION_NAME")
        
        if not AGENT_NAME or not TMUX_SESSION_NAME:
            print(f"❌ 無法取得 AGENT_NAME 或 TMUX_SESSION_NAME (來源: {ENV_FILE})。中止重置。")
            sys.exit(1)

        TMUX_TARGET = f"{TMUX_SESSION_NAME}:{AGENT_NAME}"
        LIMIT, CONTEXT_SIZE, ENGINE_DOC_NAME, ENGINE = get_config(AGENT_NAME)
        TS = datetime.now().strftime("%Y-%m-%d_%H%M")
        MONTH_TS = datetime.now().strftime("%Y-%m")
        YEAR_TS = datetime.now().strftime("%Y")
        
        # 根據引擎選擇對應的提示符 (嚴格大小寫)
        if ENGINE == 'claude':
            prompt_markers = ['Claude']
        elif ENGINE == 'codex':
            prompt_markers = ['OpenAI']
        else:  # gemini
            prompt_markers = ['Gemini']

        # ==========================================
        # Step 1: 物理中斷與零幹擾轉儲
        # ==========================================
        if os.path.exists(SHELL_LOG):
            shutil.copy2(SHELL_LOG, TEMP_LOG)
        else:
            open(TEMP_LOG, 'w').close()
            
        print(f"⏳ 注入 /clear 並開始週期性嘗試 Enter (每 3 秒一次，共 100 次)...")
        # 🚀 強化手段 1: 前置喚醒。先發送 Enter 確保 CLI 處於活動狀態
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
        
        # 🚀 強化手段 2: 注入 /clear 指令 (僅一次)
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "/clear"]) 
        
        cleared = False
        for i in range(100):
            # 🚀 強化手段 3: 持續擊發 Enter 試圖觸發執行
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])

            time.sleep(3.0) # 等待 3 秒觀察結果

            # 檢測是否重置成功
            res = subprocess.run(TMUX_BASE + ["capture-pane", "-p", "-t", TMUX_TARGET], capture_output=True, text=True)
            screen = res.stdout
            if any(marker in screen for marker in prompt_markers):
                cleared = True
                print(f"✅ 第 {i+1} 次嘗試成功！偵測到 {ENGINE} 啟動關鍵字。")
                break
            print(f"⚠️ 第 {i+1} 次嘗試失敗 (CLI 忙碌中)，3 秒後續發 Enter...")
        
        if not cleared:
            print("⚠️ 逾時 100 次嘗試仍未偵測到重置關鍵字，取消注入。")
            if os.path.exists(TEMP_LOG):
                shutil.copy2(TEMP_LOG, SHELL_LOG)
                os.remove(TEMP_LOG)
            
            # 發送恢復提示，讓 Agent 接續先前的任務
            recovery_prompt = "[System Prompt] Maintenance timeout cancelled. Please check if octo_cyberbrain/task_memo.txt exists. If it does, read it and resume the interrupted task, then delete it after reading."
            escaped_rec = recovery_prompt.replace('!', '！').replace('$', '\\$')
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", escaped_rec])
            time.sleep(1.0)
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
            time.sleep(0.5)

            # 確保積累的用戶指令不會被拋棄
            if os.path.exists(PENDING_FILE):
                try:
                    with open(PENDING_FILE, 'r', encoding='utf-8') as f:
                        pending_content = f.read().strip()
                    if pending_content:
                        sys_prompt = "\n\n[System Prompt] This command is from Matrix user, please reply to the user first before starting the task. Before starting the task, if the keywords or task mentioned by the user lack complete context, actively perform keyword shell deep dive to confirm if there is relevant context in the records. If the execution direction is clear, execute it. If it is unclear, pause the task first and reply to the user with a recap of the relevant records to confirm the direction, but do not mention to the user that you performed shell deep dive related operations. After task completion, complete the following [SOP]:\n[Step 1 - Report]: Execute `python3 toolbox/matrix_notifier.py` to send task message or file to user with Avatar emoji.\n[Step 2 - Capture]: Execute `python3 octo_cyberbrain/octo_ghost_reader.py --level current` to capture your GHOST and memories.\n[Step 3 - Imprint]: Execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"Semantic Outline\" --keywords \"Keyword1,Keyword2\" --paths \"/FilePath1,/FilePath2\"` to imprint task status to GHOST."
                        final_message = pending_content + sys_prompt
                        escaped = final_message.replace('!', '！').replace('$', '\\$')
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", escaped], check=True)
                        time.sleep(1.0)
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                        time.sleep(0.3)
                        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                        print("📩 Pending user commands injected successfully!")
                    os.remove(PENDING_FILE)
                except Exception as e:
                    print(f"❌ Error processing pending commands: {e}")
            
            # 這裡不需手動清理，交由 finally 處理
            sys.exit(1)
        
        open(SHELL_LOG, 'w').close() # Instant clear
        
        # ==========================================
        # Step 2: Shell 壓縮與 12 份滾動歸併
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
        # Step 3: Ghost 蒸餾與 12 份滾動歸併
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

        # 重置 Active Ghost
        save_json(ghost_file, {"keywords": [], "file_paths": [], "semantic_outline": []})

        # ==========================================
        # Step 4: 靈魂重塑注入 (Neural Reset Injection)
        # ==========================================
        prompt = f"[System Prompt] Please execute python3 octo_cyberbrain/octo_ghost_reader.py --level snapshot to get keywords, then bring all retrieved keywords into a single execution of 'python3 octo_cyberbrain/dive_into_the_shell.py --level snapshot -C {CONTEXT_SIZE} --keyword \"Keyword1\" \"Keyword2\"' for Shell GHOST deep dive. Once complete, re-establish compliance with {ENGINE_DOC_NAME}. This task does not require sending messages to the user. Next, verify if octo_cyberbrain/task_memo.txt exists; if so, read it to resume the task and then delete task_memo.txt."

        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", prompt])
        time.sleep(2.0) # 長 Prompt 需要更長的輸入等待時間
        
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
        time.sleep(0.5)
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
        time.sleep(0.5)
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"]) # 三重 Enter 保險

        # ==========================================
        # Step 5: 積累指令注入 (Pending injection)
        # ==========================================
        if os.path.exists(PENDING_FILE):
            try:
                with open(PENDING_FILE, 'r', encoding='utf-8') as f:
                    pending_content = f.read().strip()
                    
                if pending_content:
                    # 補上常規系統提示
                    sys_prompt = f"\n\n[System Prompt] This command is from Matrix user, please reply to the user first before starting the task. Before starting the task, if the keywords or task mentioned by the user lack complete context, actively perform keyword shell deep dive to confirm if there is relevant context in the records. If the execution direction is clear, execute it. If it is unclear, pause the task first and reply to the user with a recap of the relevant records to confirm the direction, but do not mention to the user that you performed shell deep dive related operations. After task completion, complete the following [SOP]:\n[Step 1 - Report]: Execute `python3 toolbox/matrix_notifier.py` to send task message or file to user with Avatar emoji.\n[Step 2 - Capture]: Execute `python3 octo_cyberbrain/octo_ghost_reader.py --level current` to capture your GHOST and memories.\n[Step 3 - Imprint]: Execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"Semantic Outline\" --keywords \"Keyword1,Keyword2\" --paths \"/FilePath1,/FilePath2\"` to imprint task status to GHOST."
                    final_message = pending_content + sys_prompt
                    escaped = final_message.replace('!', '！').replace('$', '\\$')
                    
                    # 以不觸發 Ctrl+C 的方式一次性注入
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", escaped], check=True)
                    time.sleep(1.0)
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                    time.sleep(0.3)
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                    print("📩 Pending user commands injected successfully!")
                
                os.remove(PENDING_FILE)
            except Exception as e:
                print(f"❌ 處理積累指令時發生錯誤: {e}")

    except BaseException as e:
        # 捕捉包含 SystemExit 在內的所有異常，確保清理執行
        if isinstance(e, SystemExit):
            if e.code == 0: # 正常退出不報錯
                pass
            else:
                print(f"❌ 程序因 sys.exit({e.code}) 中止")
        else:
            print(f"❌ 重置過程中發生異常: {e}")
    finally:
        cleanup()
