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

# status_octo_services.sh (Multi-Agent version)

# ==============================================================================
# Environment Initialization: Dynamically locate project root and mount virtual environment
# ==============================================================================
if [ -z "$VIRTUAL_ENV" ]; then
    find_project_root() {
        local dir="$1"
        while [ "$dir" != "/" ]; do
            if [ -f "$dir/install_dependencies.sh" ]; then echo "$dir"; return 0; fi
            dir=$(dirname "$dir")
        done
        return 1
    }
    export PROJECT_ROOT=$(find_project_root "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")
    if [ -n "$PROJECT_ROOT" ] && [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
        source "$PROJECT_ROOT/.venv/bin/activate"
    fi
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.py"

# Read configuration
# Read configuration
TMUX_SESSION_NAME=$(python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import TMUX_SESSION_NAME; print(TMUX_SESSION_NAME)")
ROUTER_PORT=$(python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import ROUTER_PORT; print(ROUTER_PORT)")
TELEGRAM_GATEWAY_PORT=$(python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import TELEGRAM_GATEWAY_PORT; print(TELEGRAM_GATEWAY_PORT)")

echo "📊 OctoMatrix system status (Multi-Agent)"
echo "⏰ Check time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "==========================================="

# 1. Check tmux session
echo "1️⃣  Core processes (tmux):"
if tmux has-session -t "$TMUX_SESSION_NAME" 2>/dev/null; then
    echo "   ✅ Running (Session: $TMUX_SESSION_NAME)"
    tmux list-windows -t "$TMUX_SESSION_NAME" | sed 's/^/      /'
else
    echo "   ❌ Not started"
fi
echo ""

# 2. Check Router and Agent active status
echo "2️⃣  API server status:"
API_DATA=$(curl -s "http://localhost:$ROUTER_PORT/status" || echo "failed")
if [ "$API_DATA" != "failed" ]; then
    echo "   ✅ Router normal (Port $ROUTER_PORT)"
    ACTIVE=$(echo "$API_DATA" | python3 -c "import sys, json; print(json.load(sys.stdin).get('current_agent', 'None'))")
    echo "   ⭐ Currently active Agent: $ACTIVE"
else
    echo "   ❌ Cannot connect to API service"
fi
echo ""

# 3. Check ngrok
echo "3️⃣  Tunnel status (ngrok):"
if pgrep -f "ngrok http $TELEGRAM_GATEWAY_PORT" > /dev/null; then
    echo "   ✅ Running"
    PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['tunnels'][0]['public_url'] if data['tunnels'] else 'N/A')" 2>/dev/null)
    echo "   🌍 Public address: $PUBLIC_URL"
else
    echo "   ❌ Not started"
fi
echo ""