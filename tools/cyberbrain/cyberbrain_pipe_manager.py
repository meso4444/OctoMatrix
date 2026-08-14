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

import sys
import subprocess
import re
import os
import time
import signal
from collections import deque

# [DEBUG-TEMP] 暫時性除錯：stdout/stderr 會被導向 /dev/null 或被下游吃掉，
# 一律改成明確寫入獨立檔案，才能真的被讀到。查完根因後請務必 git revert 本次 commit 移除這段。
def _debug_temp_log(msg):
    try:
        target = sys.argv[2] if len(sys.argv) > 2 else 'unknown'
        path = f"/tmp/octo_debug_pipe_manager_{target.replace(':', '_')}.log"
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

# ============================================================================
# Cyberbrain Pipe Manager (Environment-Adaptive & Multi-Layer Purge)
# ============================================================================
# 1. 環境自適應：自動檢測 tmux socket，兼容容器與原生環境。
# 2. 物理裁切強化：捨棄底部 9 行（揮發區）。
# 3. 殘留噪音全量清除：物理封殺 Thinking、bypass permissions 等所有 TUI 殘留。
# 4. 打字機增量去重：防止同一行文字在「增長」過程中被重複錄入。
# ============================================================================

LOG_PATH = sys.argv[1]
TARGET_WINDOW = sys.argv[2]
KEYWORDS = ["allow", "approve", "trust", "apply"]

# 🔍 環境自適應：自動定位 Tmux Socket
def get_tmux_cmd():
    return ["tmux"]

TMUX_BASE = get_tmux_cmd()

# 🚫 殘留噪音黑名單 (即便在裁切區之外也要封殺)
NOISE_PATTERNS = [
    r'Thinking\.\.\.',
    r'bypass permissions',
    r'shift\+tab to cycle',
    r'esc to cancel',
    r'for shortcuts',
    r'workspace \(/directory\)',
    r'sandbox',
    r'/model',
    r'Auto \(Gemini',
    r'Auto \(Claude',
    r'YOLO Ctrl\+Y',
    r'Type your message or @path/to/file',
    r'^[▀▄─\s]{5,}$',
    r'^\s*[\.⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]\s*$',
    r'^[✢✻✶·•✽⎿]',
    r'▸ Thought for',
    r'\(ctrl\+o to',
    r'^● \w+\(',
    r'^\* .*?… \(',
    r'^(●\s+)?(Reading|Searching|Read|Searched|Ran|Listed|Listing|Running)\b',
    r'\(\d+[ms](\s+\d+[ms])?(\s*·.*?)?\)\s*$',
]

# ✅ 必留特徵
AGENT_MARKERS = ['✦', '│', '╭', '╰', '✓']

STABLE_HISTORY = deque(maxlen=1000)

def get_screen_snapshot():
    """抓取螢幕快照並裁切底部 9 行"""
    try:
        # -S -300：連同最近 300 行 scrollback 一起抓，不再只看當下可視畫面，
        # 避免視窗較小(例如目前連線終端機只有29行)時忙碌畫面把真正內容擠出視窗導致完全漏抓
        cmd = TMUX_BASE + ["capture-pane", "-p", "-S", "-300", "-t", TARGET_WINDOW]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        
        # 物理裁切：捨棄底部 9 行 (TUI 揮發區)
        if len(lines) > 9:
            stable_content = lines[:-9]
        else:
            stable_content = []
            
        return [l.strip() for l in stable_content if l.strip()]
    except Exception:
        return []

def send_enter():
    cmd = TMUX_BASE + ["send-keys", "-t", TARGET_WINDOW, "Enter"]
    subprocess.run(cmd)

def should_ignore(line):
    """深度噪音檢查"""
    if len(line) < 3 and not any(m in line for m in AGENT_MARKERS):
        return True
    for pattern in NOISE_PATTERNS:
        if re.search(pattern, line):
            return True
    return False

def contains_keyword(text):
    for keyword in KEYWORDS:
        if re.search(r'\b' + re.escape(keyword) + r'\b', text.lower()):
            return True
    return False

# ==========================================
# 物理記錄與快照同步 (與 Reaper 150KB 體系同步)
# ==========================================
last_sync_time = 0

try:
    with open(LOG_PATH, 'a', encoding='utf-8') as log_file:
        while True:
            chunk = os.read(sys.stdin.fileno(), 1024)
            if not chunk:
                _debug_temp_log("stdin回傳空bytes(自然EOF)，正常結束迴圈")
                break
            # 💡 純粹記錄日誌，移除關鍵字偵測與自動發送 Enter 邏輯
            # (由 auto_permission_responder.py 獨立負責)
            
            # 2. 穩定快照同步
            current_time = time.time()
            if current_time - last_sync_time > 1.2:
                time.sleep(0.3)
                snapshot = get_screen_snapshot()
                
                # 首次啟動靜默填充
                first_run = len(STABLE_HISTORY) == 0
                
                for line in snapshot:
                    if line not in STABLE_HISTORY:
                        if not should_ignore(line):
                            if not first_run:
                                log_file.write(line + '\n')
                                log_file.flush()
                            STABLE_HISTORY.append(line)
                
                last_sync_time = time.time()

except (EOFError, KeyboardInterrupt, BrokenPipeError) as e:
    _debug_temp_log(f"被判定為正常結束的例外: {type(e).__name__}: {e}")
    sys.exit(0)
except Exception as e:
    import traceback
    _debug_temp_log(f"未預期例外: {type(e).__name__}: {e}\n{traceback.format_exc()}")
    sys.exit(1)
