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

# auto_permission_responder.py

import sys
import subprocess
import time
import re
import os
import signal
import traceback
from config import SYS_PREFIX

import threading

# [DEBUG-TEMP] 暫時性除錯：stdout 會被下游的 tee/pipe_manager 吃掉、stderr 被導向 /dev/null，
# 一律改成明確寫入獨立檔案，才能真的被讀到。查完根因後請務必 git revert 本次 commit 移除這段。
def _debug_temp_log(msg):
    try:
        target = sys.argv[1] if len(sys.argv) > 1 else 'unknown'
        path = f"/tmp/octo_debug_responder_{target.replace(':', '_')}.log"
        with open(path, 'a', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def _debug_temp_signal_handler(signum, frame):
    sig_name = signal.Signals(signum).name
    _debug_temp_log(
        f"收到訊號 {sig_name}({signum})，PID={os.getpid()} PPID={os.getppid()}，即將終止"
    )
    sys.exit(0)

signal.signal(signal.SIGTERM, _debug_temp_signal_handler)
signal.signal(signal.SIGHUP, _debug_temp_signal_handler)

# 🎯 目標視窗 (例如 session:Gupa)
TARGET = sys.argv[1]
KEYWORDS = ["allow", "approve", "trust", "apply"]

MAX_RETRY = 9                     # 最多重試 9 次
INTERVAL = 5                      # 每次間隔 5 秒
ATTEMPT_TIMEOUT = 40              # 單次觸發的總超時時間

monitoring = False
DEBUG = os.getenv('DEBUG', '0') == '1'
log_file = f"/tmp/monitor_{TARGET.replace(':', '_')}.log"

# 🚀 精確定位來自網關的指令標記
GATEWAY_MARKER = f"{SYS_PREFIX}"

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

def is_remote_stuck_command(text, marker):
    # 尋找畫面上所有的提示字元
    matches = list(re.finditer(r'^\s*[*❯›]\s+', text, re.MULTILINE))
    if not matches:
        return False
    
    # 擷取「最後一個」提示字元到畫面結尾的所有文字（這代表當前卡住的指令區塊）
    last_prompt_idx = matches[-1].start()
    last_cmd_text = text[last_prompt_idx:]
    
    # 1. 確保提示字元後面確實有輸入文字（排除單純的空提示字元）
    if not re.search(r'^\s*[*❯›]\s+\S', last_cmd_text, re.MULTILINE):
        return False
        
    # 2. 確保「系統提示」標記存在於這最後一個指令區塊中
    return marker.lower() in last_cmd_text.lower()

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
            # 🚀 雙重驗證：
            # 1. 畫面超過 30 秒沒變
            # 2. 當前「最後一個輸入區塊」必須同時具備卡住的特徵與網關標記
            if time.time() - last_change_time >= 30:
                if is_remote_stuck_command(screen, GATEWAY_MARKER):
                    monitoring = True
                    try:
                        log("🔨 Intent confirmed by screen marker. Resolving missed Enter...")
                        send_enter()
                        time.sleep(5)
                    finally:
                        last_change_time = time.time()
                        monitoring = False
                elif re.search(r'^\s*[*❯›]\s+\S', screen, re.MULTILINE):
                    log("ℹ️ Screen matches pattern but no system prompt marker found in the current command block. Ignoring (likely local manual input or Claude hint).")

# 啟動異步監控執行緒
stuck_thread = threading.Thread(target=stuck_monitor_thread, daemon=True)
stuck_thread.start()

try:
    log(f"🚀 Monitor started for {TARGET} (Waiting for input...)")
    _debug_temp_log(f"主迴圈啟動，PID={os.getpid()} PPID={os.getppid()}")
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

    _debug_temp_log("for-loop正常結束(stdin EOF，非例外路徑)，即將自然結束程式")
except (EOFError, KeyboardInterrupt, BrokenPipeError) as e:
    _debug_temp_log(f"被判定為正常結束的例外: {type(e).__name__}: {e}")
    sys.exit(0)
except Exception as e:
    _debug_temp_log(f"未預期例外: {type(e).__name__}: {e}\n{traceback.format_exc()}")
    log(f"❌ Error: {e}")
    sys.exit(1)
