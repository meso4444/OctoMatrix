#!/usr/bin/env python3
# auto_permission_responder.py
# 【Physical Hardened Version】: Support log listening mode and environment adaptation

import sys
import subprocess
import time
import re
import os
import threading

# 🎯 Target window (e.g., session:Gupa)
TARGET = sys.argv[1]
KEYWORDS = ["allow", "approve", "trust", "apply"]

MAX_RETRY = 9                     # Maximum 9 retries
INTERVAL = 5                      # 5 second interval between each attempt
ATTEMPT_TIMEOUT = 40              # Total timeout for single trigger

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
    """🚀 Environment adaptation: Automatically locate Tmux Socket"""
    return ["tmux"]

TMUX_BASE = get_tmux_base()

def clean(text):
    text = ansi_escape.sub('', text)
    return text.lower()

def capture():
    """🚀 Deep adaptation: Capture last 15 lines to ensure complete coverage of multi-line authorization requests and semantic context"""
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
    """Asynchronously monitor stuck commands without blocking main program's stdin reading"""
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
            # Screen unchanged for over 30 seconds and matches stuck command pattern (provide input buffer time for user)
            if time.time() - last_change_time >= 30:
                if has_stuck_command_pattern(screen):
                    monitoring = True
                    try:
                        log("🔨 Screen stuck for 30s, forcing Enter to resolve missed input...")
                        send_enter()
                        # Provide 5 second cooldown to avoid continuous triggering
                        time.sleep(5)
                    finally:
                        last_change_time = time.time()
                        monitoring = False

# Start asynchronous monitoring thread
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
