#!/usr/bin/env python3
import sys
import subprocess
import re
import os
import time
from collections import deque

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
    r'\* Doodling',
    r'\* Elucidating',
]

# ✅ 必留特徵
AGENT_MARKERS = ['✦', '│', '╭', '╰', '✓']

STABLE_HISTORY = deque(maxlen=1000)

def get_screen_snapshot():
    """抓取螢幕快照並裁切底部 9 行"""
    try:
        cmd = TMUX_BASE + ["capture-pane", "-p", "-t", TARGET_WINDOW]
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
        for raw_line in sys.stdin:
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

except (EOFError, KeyboardInterrupt, BrokenPipeError):
    sys.exit(0)
except Exception:
    sys.exit(1)
