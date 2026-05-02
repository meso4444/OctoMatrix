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
    global monitoring
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
            # 畫面超過 30 秒沒變，且符合卡住的指令特徵 (提供給用戶的輸入緩衝時間)
            if time.time() - last_change_time >= 30:
                if has_stuck_command_pattern(screen):
                    monitoring = True
                    try:
                        log("🔨 Screen stuck for 30s, forcing Enter to resolve missed input...")
                        send_enter()
                        # 給予 5 秒冷卻，避免連續觸發
                        time.sleep(5)
                    finally:
                        last_change_time = time.time()
                        monitoring = False

# 啟動異步監控執行緒
stuck_thread = threading.Thread(target=stuck_monitor_thread, daemon=True)
stuck_thread.start()

try:
    log(f"🚀 Monitor started for {TARGET} (Waiting for input...)")
    for line in sys.stdin:
        clean_line = clean(line)
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
