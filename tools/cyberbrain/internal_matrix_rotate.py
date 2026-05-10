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
# 1. 讀取環境變數落地檔
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
    # 上溯尋找 config.py
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if os.path.basename(base_dir) == 'agent_home':
        base_dir = os.path.dirname(base_dir)
    sys.path.append(base_dir)
    engine_doc_name = "GEMINI.md"
    try:
        import config
        limit = int(getattr(config, 'CYBERBRAIN_ROLLING_MERGE_LIMIT', 12))
        context_size = int(getattr(config, 'CYBERBRAIN_DIVE_CONTEXT_SIZE', 50))
        if agent_name:
            for a in getattr(config, 'AGENTS', []):
                if a['name'] == agent_name:
                    if a.get('engine', '').lower() == 'claude':
                        engine_doc_name = "CLAUDE.md"
                    elif a.get('engine', '').lower() == 'codex':
                        engine_doc_name = "AGENTS.md"
                    break
        return limit, context_size, engine_doc_name
    except Exception:
        return 12, 50, "GEMINI.md"

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

def main():
    env = load_env()
    AGENT_NAME = env.get("AGENT_NAME")
    TMUX_SESSION_NAME = env.get("TMUX_SESSION_NAME")
    
    if not AGENT_NAME or not TMUX_SESSION_NAME:
        print("❌ 無法取得 AGENT_NAME 或 TMUX_SESSION_NAME。中止重置。")
        sys.exit(1)

    TMUX_TARGET = f"{TMUX_SESSION_NAME}:{AGENT_NAME}"
    LIMIT, CONTEXT_SIZE, ENGINE_DOC_NAME = get_config(AGENT_NAME)
    TS = datetime.now().strftime("%Y-%m-%d_%H%M")
    MONTH_TS = datetime.now().strftime("%Y-%m")
    YEAR_TS = datetime.now().strftime("%Y")
    
    # ==========================================
    # Step 1: 物理中斷與零幹擾轉儲
    # ==========================================
    shell_log = "octo_cyberbrain/shell/octo_shell.log"
    temp_log = "octo_cyberbrain/shell/temp.log"
    
    if os.path.exists(shell_log):
        shutil.copy2(shell_log, temp_log)
    else:
        open(temp_log, 'w').close()
        
    # 強力中斷與清屏程序 (極致保險模式)
    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "C-c"])
    time.sleep(2.0) # 給予足夠時間中斷當前任務
    
    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "/clear"]) 
    time.sleep(1.5) # 等待字串完全輸入
    
    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
    time.sleep(0.5)
    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
    time.sleep(0.5)
    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"]) # 三重 Enter 保險
    
    print("⏳ 等待 CLI 執行 /clear 重置 (5s)...")
    time.sleep(5.0) # 預留充足時間讓 CLI 清理 Context 與畫面
    
    open(shell_log, 'w').close() # Instant clear
    
    flag_file = "octo_cyberbrain/.rotation_flag"
    if os.path.exists(flag_file):
        os.remove(flag_file)

    # ==========================================
    # Step 2: Shell 壓縮與 12 份滾動歸併
    # ==========================================
    zst_target = f"octo_cyberbrain/shell/octo_shell.log.{TS}.zst"
    try:
        subprocess.run(["zstd", "-T0", "--rm", temp_log, "-o", zst_target], stdout=subprocess.DEVNULL, check=True)
    except FileNotFoundError:
        print("⚠️ 找不到 zstd 指令，跳過壓縮，直接保存原始 log 檔案")
        os.rename(temp_log, f"octo_cyberbrain/shell/octo_shell.log.{TS}.bak")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ zstd 壓縮失敗: {e}")
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
    # Step 3: Ghost 蒸餾與 12 份滾動歸併
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

    # 重置 Active Ghost
    save_json(ghost_file, {"keywords": [], "file_paths": [], "semantic_outline": []})

    # ==========================================
    # Step 4: 靈魂重塑注入 (Neural Reset Injection)
    # ==========================================
    prompt = f"【系統提示】請執行 python3 octo_cyberbrain/octo_ghost_reader.py --level snapshot 取得關鍵字，然後一次性將所有撈到的關鍵字全部帶入執行 `python3 octo_cyberbrain/dive_into_the_shell.py --level snapshot -C {CONTEXT_SIZE} --keyword \"關鍵字1\" \"關鍵字2\"` 進行Shell GHOST深潛，完成後重新提升{ENGINE_DOC_NAME}的遵守，此任務不需發送訊息給用戶"

    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", prompt])
    time.sleep(2.0) # 長 Prompt 需要更長的輸入等待時間
    
    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
    time.sleep(0.5)
    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
    time.sleep(0.5)
    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"]) # 三重 Enter 保險

    # ==========================================
    # Step 5: 解鎖與積累指令注入 (Unlock and pending injection)
    # ==========================================
    lock_file = "octo_cyberbrain/inject_block.lock"
    pending_file = "octo_cyberbrain/pending_inject.txt"
    if os.path.exists(lock_file):
        os.remove(lock_file)
        
    if os.path.exists(pending_file):
        try:
            with open(pending_file, 'r', encoding='utf-8') as f:
                pending_content = f.read().strip()
                
            if pending_content:
                # 補上常規系統提示
                sys_prompt = f"\n\n【系統提示】此指令來自 Matrix 用戶，請先回用戶訊息再開始任務。任務開始前，若用戶所提及關 鍵字或任務缺少完整上下文脈絡時，主動進行關鍵字深潛shell紀錄，確認紀錄中是否有相關脈絡，若執行方向明確就執行，若有不明確就先暫停 任務並回訊用戶相關紀錄的recap向用戶確認方向，但禁止向用戶提及你做了shell深潛的相關操作; 任務完成後，完成以下 [SOP]:\n[Step 1 -  回報]：執行 `python3 toolbox/matrix_notifier.py` 將任務訊息或檔案發送給用戶並搭配Avatar emoji。\n[Step 2 - 收攝]：執行 `python3 octo_cyberbrain/octo_ghost_reader.py --level current` 收攝你的 GHOST 與記憶。\n[Step 3 - 刻印]：執行 `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"語義大綱\" --keywords \"關鍵字1,關鍵字2\" --paths \"/檔案路徑1,/檔案路徑2\"` 將本次任務狀態刻印 到GHOST。"
                final_message = pending_content + sys_prompt
                escaped = final_message.replace('!', '！').replace('$', '\\$')
                
                # 以不觸發 Ctrl+C 的方式一次性注入
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", escaped], check=True)
                time.sleep(1.0)
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                time.sleep(0.3)
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                print("📩 已將積累的用戶指令注入完成！")
            
            os.remove(pending_file)
        except Exception as e:
            print(f"❌ 處理積累指令時發生錯誤: {e}")

if __name__ == "__main__":
    main()
