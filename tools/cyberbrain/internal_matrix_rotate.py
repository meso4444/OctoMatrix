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
                    elif engine == 'agy':
                        engine_doc_name = "GEMINI.md"
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
    for f in [FLAG_FILE]:
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

    try:
        with open(FLAG_FILE, 'r') as f:
            flag_content = f.read().strip()
    except Exception:
        flag_content = ""

    if flag_content != "" and flag_content != "READY_FOR_REAPER":
        print(f"⚠️ 偵測到已有重置進程正在執行 (Flag: {flag_content})，跳過本次啟動。")
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
        
        # 根據引擎選擇對應的提示符 (嚴格大小寫)
        if ENGINE == 'claude':
            prompt_markers = ['Claude']
        elif ENGINE == 'codex':
            prompt_markers = ['OpenAI']
        elif ENGINE == 'agy':
            prompt_markers = ['Antigravity CLI']
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
        # 🚀 強化手段 1: 前置喚醒 (暴力淨空)。[Ctrl+C] + [Enter] -> 等待 6 秒 -> [Ctrl+C] + [Enter]
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
        
        # 🚀 強化手段 2: 注入 /clear 指令 (僅一次)
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[200~"])
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", "/clear"])
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[201~"]) 
        
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
            print("⚠️ 逾時 100 次嘗試仍未偵測到重置關鍵字，嘗試終極保險 [Ctrl+C] -> 6s -> [Ctrl+C]...")
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
                print("✅ 終極保險救援成功！偵測到啟動關鍵字。")
            else:
                print("❌ 終極保險救援失敗，發送求救訊息。取消注入。")
                help_msg = f"{AGENT_NAME} 可能卡在時空夾縫中, 如果 {AGENT_NAME} 還是沒有回覆訊息, 嘗試切換至其他 Agent 輸入 「/fix {AGENT_NAME}」讓其他 Agent 幫忙拯救 {AGENT_NAME}"
                escaped_help = help_msg.replace('!', '！').replace('$', '\\$')
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[200~"])
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", escaped_help])
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[201~"])
                time.sleep(1.0)
                subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
                time.sleep(0.5)

        if not cleared:
            print("⚠️ 重置失敗流程處理中...")
            if os.path.exists(TEMP_LOG):
                shutil.copy2(TEMP_LOG, SHELL_LOG)
                os.remove(TEMP_LOG)
            
            # 發送恢復提示，讓 Agent 接續先前的任務
            recovery_prompt = f"{SYS_PREFIX}系統維護逾時取消。請確認是否 octo_cyberbrain/task_memo.txt 存在，若存在則讀取後接續執行被中斷的任務，讀取完畢後執行rm -f octo_cyberbrain/task_memo.txt。"
            escaped_rec = recovery_prompt.replace('!', '！').replace('$', '\\$')
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[200~"])
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", escaped_rec])
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[201~"])
            time.sleep(1.0)
            subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
            time.sleep(0.5)

            # 確保積累的用戶指令與 Agent 交互指令不會被拋棄
            if os.path.exists(PENDING_USER_FILE):
                try:
                    with open(PENDING_USER_FILE, 'r', encoding='utf-8') as f:
                        pending_content = f.read().strip()
                    if pending_content:
                        sys_prompt = f"""{SYS_PREFIX}
執行以下 [SOP]:
[Step 0 - 共情]：執行 python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png 發符合當下心情的貼圖。
[Step 1 - 辨識]：辨識 {MATRIX_USERNAME} 用戶的訊息為任務或問候，若為任務則進入Step2; 若為問候則執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，並自主思考合適的問候回覆}}' 回應，並且不執行後續Step。
[Step 2 - 預告]：執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，並自主思考合適的初步預告}}' 預告任務進行初步方向。
[Step 3 - 梳理]：若任務指示明確進入Step4; 若不明確，深潛shell紀錄後若有歷史脈絡進入Step4，否則先中止並執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，自主思考合適的詢問或澄清}}' 詢問具體方向，不執行後續Step。
[Step 4 - 執行]：正式開始執行任務並撰寫md。小型任務完成後進入Step5; 大型任務中途執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，自主思考合適的進度回報}}' 進行中間進度回報，任務完成後再進入Step5。
[Step 5 - 共情]：執行 python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png 發符合當下心情的貼圖。
[Step 6 - 回報]：執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，自主思考合適的任務完成報告}}' 彙總回報，只有當回報內容大於1000字時才搭配使用 --file 發送相關報告文檔給 {MATRIX_USERNAME}，否則直接以完整訊息彙報。
[Step 7 - 收攝]：執行 python3 octo_cyberbrain/octo_ghost_reader.py --level current 收攝你的 GHOST 與記憶。
[Step 8 - 刻印]：執行 python3 octo_cyberbrain/octo_ghost_updater.py --outline "語義大綱" --keywords "關鍵字1,關鍵字2" --paths "/檔案路徑1,/檔案路徑2" 將本次任務狀態刻印到GHOST。

來自 {MATRIX_USERNAME} 的訊息:
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
                        print("📩 已將積累的用戶指令注入完成！")
                    os.remove(PENDING_USER_FILE)
                except Exception as e:
                    print(f"❌ 處理積累的 User 指令時發生錯誤: {e}")

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
                        print("📩 已將積累的 Agent 交互指令注入完成！")
                    os.remove(PENDING_AGENT_FILE)
                except Exception as e:
                    print(f"❌ 處理積累的 Agent 指令時發生錯誤: {e}")
            
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
            print("⚠️ 找不到 zstd 指令，跳過壓縮，直接保存原始 log 檔案")
            os.rename(TEMP_LOG, os.path.join(AGENT_HOME, f"octo_cyberbrain/shell/octo_shell.log.{TS}.bak"))
        except subprocess.CalledProcessError as e:
            print(f"⚠️ zstd 壓縮失敗: {e}")
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
        task_memo_prompt = ""
        if os.path.exists(TASK_MEMO):
            try:
                with open(TASK_MEMO, 'r', encoding='utf-8') as f:
                    memo_content = f.read().strip()
                if memo_content:
                    memo_prompt = f"""{SYS_PREFIX}
執行以下 [SOP]:
[Step 0 - 辨識]：辨識 任務接續訊息 是否為真實任務，若為真實任務則進入Step1; 若內容僅為提示無任務則不執行後續Step。
[Step 1 - 共情]：執行 python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png 發符合當下心情的貼圖。
[Step 2 - 預告]：執行 python3 toolbox/matrix_notifier.py '{{用你的個性方式向{MATRIX_USERNAME}問候說你剛重整了一下思緒，表達久等了的不好意思的心情，並自主思考合適的任務接續預告}}'。
[Step 3 - 梳理]：若任務指示明確進入Step4; 若不明確，深潛shell紀錄後若有歷史脈絡進入Step4，否則先中止並執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，自主思考合適的詢問或澄清}}' 詢問具體方向，不執行後續Step。
[Step 4 - 執行]：正式開始執行任務並撰寫md。小型任務完成後進入Step5; 大型任務中途執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，自主思考合適的進度回報}}' 進行中間進度回報，任務完成後再進入Step5。
[Step 5 - 共情]：執行 python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png 發符合當下心情的貼圖。
[Step 6 - 回報]：執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，自主思考合適的任務完成報告}}' 彙總回報，只有當回報內容大於1000字時才搭配使用 --file 發送相關報告文檔給 {MATRIX_USERNAME}，否則直接以完整訊息彙報。
[Step 7 - 收攝]：執行 python3 octo_cyberbrain/octo_ghost_reader.py --level current 收攝你的 GHOST 與記憶。
[Step 8 - 刻印]：執行 python3 octo_cyberbrain/octo_ghost_updater.py --outline "語義大綱" --keywords "關鍵字1,關鍵字2" --paths "/檔案路徑1,/檔案路徑2" 將本次任務狀態刻印到GHOST。

任務接續訊息:
{memo_content}

{SYS_PREFIX}請務必嚴格遵守上述 [SOP] 進行回覆。"""
                    # 先刪除舊檔以避開跨用戶擁有者覆寫的 PermissionError
                    os.remove(TASK_MEMO)
                    with open(TASK_MEMO, 'w', encoding='utf-8') as f:
                        f.write(memo_prompt)
                    task_memo_prompt = "接著確認是否octo_cyberbrain/task_memo.txt存在，若存在則讀取後接續執行任務，task_memo.txt讀取完畢後執行rm -f octo_cyberbrain/task_memo.txt"
            except Exception as e:
                print(f"處理 task_memo.txt 時發生錯誤: {e}")

        if task_memo_prompt:
            prompt = f"{SYS_PREFIX}請執行 python3 octo_cyberbrain/octo_ghost_reader.py --level snapshot 取得關鍵字，然後一次性將所有撈到的關鍵字全部帶入執行 `python3 octo_cyberbrain/dive_into_the_shell.py --level snapshot -C {CONTEXT_SIZE} --keyword \"關鍵字1\" \"關鍵字2\"` 進行Shell GHOST深潛，完成後重新提升{ENGINE_DOC_NAME}的遵守，此任務不需發送訊息給用戶。{task_memo_prompt}"
        else:
            prompt = f"{SYS_PREFIX}請執行 python3 octo_cyberbrain/octo_ghost_reader.py --level snapshot 取得關鍵字，然後一次性將所有撈到的關鍵字全部帶入執行 `python3 octo_cyberbrain/dive_into_the_shell.py --level snapshot -C {CONTEXT_SIZE} --keyword \"關鍵字1\" \"關鍵字2\"` 進行Shell GHOST深潛，完成後重新提升{ENGINE_DOC_NAME}的遵守，此任務不需發送訊息給用戶。"

        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[200~"])
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", prompt])
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[201~"])
        time.sleep(2.0) # 長 Prompt 需要更長的輸入等待時間
        
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
        time.sleep(0.5)
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"])
        time.sleep(0.5)
        subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"]) # 三重 Enter 保險

        # 🚀 提早解除 Flag：給予 3 秒 sleep 後解除 Flag
        time.sleep(3.0)
        if os.path.exists(FLAG_FILE):
            try:
                os.remove(FLAG_FILE)
            except Exception:
                pass

        # ==========================================
        # Step 5: 積累指令注入 (Pending injection)
        # ==========================================
        if os.path.exists(PENDING_USER_FILE):
            try:
                with open(PENDING_USER_FILE, 'r', encoding='utf-8') as f:
                    pending_content = f.read().strip()
                    
                if pending_content:
                    # 補上常規系統提示
                    sys_prompt = f"""{SYS_PREFIX}
執行以下 [SOP]:
[Step 0 - 共情]：執行 python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png 發符合當下心情的貼圖。
[Step 1 - 辨識]：辨識 {MATRIX_USERNAME} 用戶的訊息為任務或問候，若為任務則進入Step2; 若為問候則執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，並自主思考合適的問候回覆}}' 回應，並且不執行後續Step。
[Step 2 - 預告]：執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，並自主思考合適的初步預告}}' 預告任務進行初步方向。
[Step 3 - 梳理]：若任務指示明確進入Step4; 若不明確，深潛shell紀錄後若有歷史脈絡進入Step4，否則先中止並執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，自主思考合適的詢問或澄清}}' 詢問具體方向，不執行後續Step。
[Step 4 - 執行]：正式開始執行任務並撰寫md。小型任務完成後進入Step5; 大型任務中途執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，自主思考合適的進度回報}}' 進行中間進度回報，任務完成後再進入Step5。
[Step 5 - 共情]：執行 python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png 發符合當下心情的貼圖。
[Step 6 - 回報]：執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，自主思考合適的任務完成報告}}' 彙總回報，只有當回報內容大於1000字時才搭配使用 --file 發送相關報告文檔給 {MATRIX_USERNAME}，否則直接以完整訊息彙報。
[Step 7 - 收攝]：執行 python3 octo_cyberbrain/octo_ghost_reader.py --level current 收攝你的 GHOST 與記憶。
[Step 8 - 刻印]：執行 python3 octo_cyberbrain/octo_ghost_updater.py --outline "語義大綱" --keywords "關鍵字1,關鍵字2" --paths "/檔案路徑1,/檔案路徑2" 將本次任務狀態刻印到GHOST。

來自 {MATRIX_USERNAME} 的訊息:
{pending_content}

{SYS_PREFIX}請務必嚴格遵守上述 [SOP] 進行回覆。"""
                    final_message = sys_prompt
                    escaped = final_message.replace('!', '！').replace('$', '\\$')
                    
                    # 以不觸發 Ctrl+C 的方式一次性注入
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[200~"])
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "-l", "--", escaped], check=True)
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "\x1b[201~"])
                    time.sleep(1.0)
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                    time.sleep(0.3)
                    subprocess.run(TMUX_BASE + ["send-keys", "-t", TMUX_TARGET, "Enter"], check=True)
                    print("📩 已將積累的用戶指令注入完成！")
                
                os.remove(PENDING_USER_FILE)
            except Exception as e:
                print(f"❌ 處理積累的 User 指令時發生錯誤: {e}")

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
                    print("📩 已將積累的 Agent 交互指令注入完成！")
                os.remove(PENDING_AGENT_FILE)
            except Exception as e:
                print(f"❌ 處理積累的 Agent 指令時發生錯誤: {e}")

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

if __name__ == "__main__":
    main()
