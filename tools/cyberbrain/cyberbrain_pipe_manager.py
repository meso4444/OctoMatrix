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
from collections import deque

# ============================================================================
# Cyberbrain Pipe Manager (Environment-Adaptive & Multi-Layer Purge)
# ============================================================================
# 1. Environment adaptation: auto-detect tmux socket, compatible with containers and native environments.
# 2. Physical cutting enhancement: discard bottom 9 lines (volatile area).
# 3. Residual noise complete removal: physically suppress Thinking, bypass permissions and all TUI residue.
# 4. Typewriter incremental deduplication: prevent the same line from being repeatedly recorded during "growth" process.
# ============================================================================

LOG_PATH = sys.argv[1]
TARGET_WINDOW = sys.argv[2]
KEYWORDS = ["allow", "approve", "trust", "apply"]

# 🔍 Environment adaptation: auto-locate Tmux Socket
def get_tmux_cmd():
    return ["tmux"]

TMUX_BASE = get_tmux_cmd()

# 🚫 Residual noise blacklist (suppress even outside cutting area)
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

# ✅ Must-keep features
AGENT_MARKERS = ['✦', '│', '╭', '╰', '✓']

STABLE_HISTORY = deque(maxlen=1000)

def get_screen_snapshot():
    """Capture screen snapshot and trim bottom 9 lines"""
    try:
        cmd = TMUX_BASE + ["capture-pane", "-p", "-t", TARGET_WINDOW]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()

        # Physical cutting: discard bottom 9 lines (TUI volatile area)
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
    """Deep noise check"""
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
# Physical recording and snapshot sync (sync with Reaper 150KB system)
# ==========================================
last_sync_time = 0

try:
    with open(LOG_PATH, 'a', encoding='utf-8') as log_file:
        while True:
            chunk = os.read(sys.stdin.fileno(), 1024)
            if not chunk:
                break
            # 💡 Pure log recording, removed keyword detection and auto-send Enter logic
            # (independently handled by auto_permission_responder.py)

            # 2. Stable snapshot sync
            current_time = time.time()
            if current_time - last_sync_time > 1.2:
                time.sleep(0.3)
                snapshot = get_screen_snapshot()
                
                # Silent initialization on first startup
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
