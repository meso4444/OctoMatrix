#!/usr/bin/env python3
# auto_permission_responder.py
# 【物理硬化版】：支援日誌監聽模式與環境自適應

import sys
import subprocess
import time
import re
import os
import threading

# 🎯 目標視窗 (例如 session:Gupa)
TARGET = sys.argv[1]
KEYWORDS = ["allow", "approve", "trust", "apply"]

MAX_RETRY = 9                     # 最多重試 9 次
INTERVAL = 5                      # 每次間隔 5 秒
ATTEMPT_TIMEOUT = 40              # 單次觸發的總超時時間

monitoring = False
DEBUG = os.getenv('DEBUG', '0') == '1'
log_file = f"/tmp/monitor_{TARGET.replace(':', '_')}.log"

# 🚀 增加：追蹤最後一次收到系統指令的時間
last_gateway_msg_time = 0
GATEWAY_MARKER = "【系統提示】"  # 精確定位來自網關的指令標記

def log(msg):
    if not DEBUG: return
    with open(log_file, 'a') as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        f.flush()

if DEBUG:
    with open(log_file, 'w') as f:
        f.write(f"--- Monitor Start at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")

ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

def get_tmux_base():
    """🚀 環境自適應：自動定位 Tmux Socket"""
    return ["tmux"]

TMUX_BASE = get_tmux_base()

def clean(text):
    text = ansi_escape.sub('', text)
    return text.lower()

def capture():
    """🚀 深度適配：捕獲最後 15 行，確保完整涵蓋多行授權請求與語意背景"""
    try:
        cmd = TMUX_BASE + ["capture-pane", "-pt", TARGET, "-S", "-15"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return clean(result.stdout)
    except: return ""

def send_enter():
    try:
        cmd = TMUX_BASE + ["send-keys", "-t", TARGET, "Enter"]
        subprocess.run(cmd)
    except: pass

def contains_keyword(text):
    for keyword in KEYWORDS:
        if re.search(r'\b' + re.escape(keyword) + r'\b', text.lower()):
            return True
    return False

def has_stuck_command_pattern(text):
    pattern = r'^\s*[*❯›]\s+\S'
    return bool(re.search(pattern, text, re.MULTILINE))

def stuck_monitor_thread():
    """異步監控卡住的指令，不阻塞主程序的 stdin 讀取"""
    global monitoring, last_gateway_msg_time
    last_screen_hash = None
    last_change_time = time.time()
    
    while True:
        time.sleep(5)
        if monitoring:
            last_change_time = time.time()
            continue
            
        screen = capture()
        current_hash = hash(screen)
        
        if current_hash != last_screen_hash:
            last_screen_hash = current_hash
            last_change_time = time.time()
        else:
            # 🚀 雙重驗證：
            # 1. 畫面超過 30 秒沒變，且符合卡住的指令特徵
            # 2. 必須是在最近 60 秒內有收到網關訊息的情況下 (避免 Claude 灰字幻覺)
            if time.time() - last_change_time >= 30:
                if time.time() - last_gateway_msg_time < 60:
                    if has_stuck_command_pattern(screen):
                        monitoring = True
                        try:
                            log("🔨 Intent confirmed by gateway log. Resolving missed Enter...")
                            send_enter()
                            time.sleep(5)
                        finally:
                            last_change_time = time.time()
                            monitoring = False
                else:
                    if has_stuck_command_pattern(screen):
                        log("ℹ️ Screen matches pattern but no recent gateway activity. Ignoring (likely Claude hint).")

# 啟動異步監控執行緒
stuck_thread = threading.Thread(target=stuck_monitor_thread, daemon=True)
stuck_thread.start()

try:
    log(f"🚀 Monitor started for {TARGET} (Waiting for input...)")
    for line in sys.stdin:
        clean_line = clean(line)
        
        # 🚀 只要看到網關標記，就更新最後活動時間
        if GATEWAY_MARKER in line:
            last_gateway_msg_time = time.time()
            log("📡 Gateway activity detected, arming auto-enter.")

        if monitoring: continue

        if contains_keyword(clean_line):
            log(f"🔔 Keyword detected! Starting recovery cycle...")
            monitoring = True
            start_time = time.time()

            try:
                for attempt in range(MAX_RETRY):
                    if time.time() - start_time > ATTEMPT_TIMEOUT: break
                    screen = capture()
                    if not contains_keyword(screen):
                        log(f"✅ Keyword disappeared, stopping.")
                        break
                    send_enter()
                    log(f"🎯 Sent Enter ({attempt+1}/{MAX_RETRY})")
                    time.sleep(INTERVAL)
            finally:
                monitoring = False

except (EOFError, KeyboardInterrupt, BrokenPipeError):
    sys.exit(0)
except Exception as e:
    log(f"❌ Error: {e}")
    sys.exit(1)
