#!/bin/bash
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

# Start Telegram → AI Agent squad remote control system

set -e

# Parse as absolute path
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ----------------------------------------------------
# Intercept OS Stop signal (for macOS launchctl stop)
# ----------------------------------------------------
trap 'echo "Received OS stop signal (SIGTERM/SIGINT), stopping services..."; "$SCRIPT_DIR/stop_octo_services.sh"; exit 0' SIGTERM SIGINT

# ----------------------------------------------------
# Wait for network Ping loop (wait indefinitely to ensure offline boot support)
# ----------------------------------------------------
echo "Checking network connection..."
while ! python3 -c "import socket; socket.create_connection(('8.8.8.8', 53), timeout=2)" &>/dev/null; do
  # Use wait with sleep in the loop so trap can immediately respond to signals
  sleep 5 &
  wait $!
done
echo "Network connected!"

CONFIG_FILE="$SCRIPT_DIR/config.py"
ENV_FILE="$SCRIPT_DIR/.env"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Load environment variables
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
    echo "🔐 Loaded .env"
else
    echo "⚠️  Warning: .env file not found"
fi

# Read configuration
TMUX_SESSION_NAME=$(python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import TMUX_SESSION_NAME; print(TMUX_SESSION_NAME)")

echo "🚀 Starting OctoMatrix"
echo "==========================================="

# Generate dynamic Webhook Secret
SECRET_FILE="$SCRIPT_DIR/webhook_secret.token"
openssl rand -hex 32 > "$SECRET_FILE"
export WEBHOOK_SECRET_TOKEN=$(cat "$SECRET_FILE")

# Kill existing session
if tmux has-session -t "$TMUX_SESSION_NAME" 2>/dev/null; then
    echo "🔄 Killing existing session…"
    tmux kill-session -t "$TMUX_SESSION_NAME"
    sleep 1
fi

# Create main session (specify separate socket file for container isolation)
echo "🧬  Creating tmux session '$TMUX_SESSION_NAME'…"
# Use explicitly specified socket file path to create session (not dependent on TMUX_TMPDIR environment variable)
tmux new-session -d -s "$TMUX_SESSION_NAME" -n "init" -c "$SCRIPT_DIR"

# 1. Initialize Agent environment
echo "🧬  Initializing Agent ecosystem environment…"
python3 "$SCRIPT_DIR/setup_agent_env.py" --all

# 2. Dynamically start AI Agent squad
echo "🤖 Deploying AI Agent squad…"
export SCRIPT_DIR
export TMUX_SESSION_NAME


echo "   ✅ All Agents ready"

# Window: MC Router API
echo "🔀 Starting MC Router (message routing hub)…"
tmux new-window -t "$TMUX_SESSION_NAME" -n "router" -c "$SCRIPT_DIR"
tmux send-keys -t "$TMUX_SESSION_NAME:router" "python3 $SCRIPT_DIR/octo_router.py"
sleep 1
tmux send-keys -t "$TMUX_SESSION_NAME:router" Enter

# Wait for Router to start
sleep 2

# Check platform enabled status and start gateways
python3 << 'EOF'
import sys
import os
import subprocess
import time

script_dir = os.environ['SCRIPT_DIR']
session_name = os.environ['TMUX_SESSION_NAME']
sys.path.append(script_dir)

try:
    from config import PLATFORMS_ENABLED

    # 1. Telegram
    if PLATFORMS_ENABLED.get('telegram', True):
        print("   📱 Starting Telegram Gateway (Router forwarding)…")
        subprocess.run(['tmux', 'new-window', '-t', session_name, '-n', 'telegram', '-c', script_dir], check=True)
        subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:telegram', f'python3 {script_dir}/telegram_gateway.py', 'Enter'], check=True)
        time.sleep(2)
    else:
        print("   ⚪️ Telegram disabled, skipping startup")

    # 2. Discord
    if PLATFORMS_ENABLED.get('discord', True):
        print("   💻 Starting Discord Gateway (WebSocket mode)…")
        subprocess.run(['tmux', 'new-window', '-t', session_name, '-n', 'discord', '-c', script_dir], check=True)
        subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:discord', f'python3 {script_dir}/discord_gateway.py', 'Enter'], check=True)
        time.sleep(2)
    else:
        print("   ⚪️ Discord disabled, skipping startup")

    # 3. Slack
    if PLATFORMS_ENABLED.get('slack', True):
        print("   ⚡ Starting Slack Gateway (Socket Mode)…")
        subprocess.run(['tmux', 'new-window', '-t', session_name, '-n', 'slack', '-c', script_dir], check=True)
        subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:slack', f'python3 {script_dir}/slack_socket_gateway.py', 'Enter'], check=True)
        time.sleep(2)
    else:
        print("   ⚪️ Slack disabled, skipping startup")

except Exception as e:
    print(f"   ❌ Exception occurred while starting gateways: {e}")
EOF

# Wait for all Gateways to start
sleep 2

# Window: Octo Reaper (Cyberbrain GHOST reaper)
echo "🧠 Starting Cyberbrain GHOST reaper (octo_reaper.py)…"
tmux new-window -t "$TMUX_SESSION_NAME" -n "reaper" -c "$SCRIPT_DIR"
tmux send-keys -t "$TMUX_SESSION_NAME:reaper" "python3 $SCRIPT_DIR/octo_reaper.py"
sleep 1
tmux send-keys -t "$TMUX_SESSION_NAME:reaper" Enter

if python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import PLATFORMS_ENABLED; print(PLATFORMS_ENABLED.get('telegram', True))" | grep -q "True"; then
    # Window: ngrok Tunnel
    echo "☁️  Establishing secure connection tunnel (ngrok)…"
    tmux new-window -t "$TMUX_SESSION_NAME" -n "ngrok" -c "$SCRIPT_DIR"
    tmux send-keys -t "$TMUX_SESSION_NAME:ngrok" "$SCRIPT_DIR/start_ngrok.sh"
    sleep 1
    tmux send-keys -t "$TMUX_SESSION_NAME:ngrok" Enter

    echo "⏳ Synchronizing network address and Webhook…"
    sleep 5
else
    echo "⚪️ Telegram disabled, skipping Ngrok startup"
fi

# Back to first Agent window
tmux select-window -t "$TMUX_SESSION_NAME:0"

# Send test message
echo "📨 Sending test message to all Agents and requesting identification..."
python3 << 'EOF'
import os
import sys
import subprocess
import time
sys.path.append(os.environ['SCRIPT_DIR'])
try:
    from config import AGENTS, MATRIX_USERNAME, SYS_PREFIX
    session_name = os.environ['TMUX_SESSION_NAME']
    for agent in AGENTS:
        name = agent['name']
        test_msg = f"{SYS_PREFIX} Execute `python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png` to send a sticker matching your current mood, then execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME}}}'`"
        agent_dir = os.path.join(os.environ['SCRIPT_DIR'], 'agent_home', name)
        flag_file = os.path.join(agent_dir, 'octo_cyberbrain', '.rotation_flag')
        pending_file = os.path.join(agent_dir, 'octo_cyberbrain', 'pending_inject.txt')
        
        if os.path.exists(flag_file):
            with open(pending_file, 'a', encoding='utf-8') as f:
                if os.path.exists(pending_file) and os.path.getsize(pending_file) > 0:
                    f.write("\n\n")
                f.write(test_msg)
            print(f"   ✓ Queued test message for {name}")
        else:
            subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:{name}', test_msg], check=True)
            time.sleep(0.5)
            subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:{name}', 'Enter'], check=True)
            print(f"   ✓ Test message sent to: {name}")
except Exception as e:
    print(f"   ⚠️ Failed to send test message: {e}")
EOF

echo "==========================================="
echo "🎉 OctoMatrix fully deployed!"
echo ""
echo "📋 Execution summary:"
echo "   Session: $TMUX_SESSION_NAME"
echo "   Communication gateways started:"
python3 << 'EOF'
import os
import sys
sys.path.append(os.environ['SCRIPT_DIR'])
try:
    from config import PLATFORMS_ENABLED
    if PLATFORMS_ENABLED.get('telegram', True): print("      📱 Telegram Gateway (Router forwarding)")
    if PLATFORMS_ENABLED.get('discord', True): print("      💻 Discord Gateway (WebSocket + auto-reconnect)")
    if PLATFORMS_ENABLED.get('slack', True): print("      ⚡ Slack Gateway (Socket Mode + auto-reconnect)")
    if not any(PLATFORMS_ENABLED.values()): print("      ⚪️ No communication gateways enabled")
except Exception: pass
EOF
echo "   Hub services started:"
echo "      🔀 MC Router (message normalization + atomic injection)"
echo "      🧠 Octo Reaper (Cyberbrain GHOST reaper)"
if python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import PLATFORMS_ENABLED; print(PLATFORMS_ENABLED.get('telegram', True))" | grep -q "True"; then
    echo "      ☁️  ngrok (Webhook secure tunnel)"
fi
echo ""
echo "   All tmux windows:"
tmux list-windows -t "$TMUX_SESSION_NAME" -F "      • Window #{window_index}: #{window_name}"
echo ""
echo "🚀 Attach to session: tmux attach -t $TMUX_SESSION_NAME"
echo ""
echo "✅ Verification steps:"
echo "   1. tmux attach -t $TMUX_SESSION_NAME"
echo "   2. Check router window: curl http://localhost:12210/health"
echo "   3. Send message in Telegram/Discord/Slack and verify router logs"
