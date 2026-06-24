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

# status_octo_services.sh (Multi-Agent 版)

# ==============================================================================
# 環境初始化：動態定位專案根目錄並掛載虛擬環境 (冪等且相容任意子目錄)
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
    PROJECT_ROOT=$(find_project_root "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")
    if [ -n "$PROJECT_ROOT" ] && [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
        source "$PROJECT_ROOT/.venv/bin/activate"
    fi
fi
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.py"

# 讀取配置
# 讀取配置
TMUX_SESSION_NAME=$(python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import TMUX_SESSION_NAME; print(TMUX_SESSION_NAME)")
ROUTER_PORT=$(python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import ROUTER_PORT; print(ROUTER_PORT)")
TELEGRAM_GATEWAY_PORT=$(python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import TELEGRAM_GATEWAY_PORT; print(TELEGRAM_GATEWAY_PORT)")

echo "📊 OctoMatrix 系統狀態 (Multi-Agent)"
echo "⏰ 檢查時間: $(date '+%Y-%m-%d %H:%M:%S')"
echo "==========================================="

# 1. 檢查 tmux session
echo "1️⃣  核心進程 (tmux):"
if tmux has-session -t "$TMUX_SESSION_NAME" 2>/dev/null; then
    echo "   ✅ 運行中 (Session: $TMUX_SESSION_NAME)"
    tmux list-windows -t "$TMUX_SESSION_NAME" | sed 's/^/      /'
else
    echo "   ❌ 未啟動"
fi
echo ""

# 2. 檢查 Router 與 Agent 活躍狀態
echo "2️⃣  API 伺服器狀態:"
API_DATA=$(curl -s "http://localhost:$ROUTER_PORT/status" || echo "failed")
if [ "$API_DATA" != "failed" ]; then
    echo "   ✅ Router 正常 (Port $ROUTER_PORT)"
    ACTIVE=$(echo "$API_DATA" | python3 -c "import sys, json; print(json.load(sys.stdin)['active_agent'])")
    echo "   ⭐ 當前活躍 Agent: $ACTIVE"
else
    echo "   ❌ 無法連接 API 服務"
fi
echo ""

# 3. 檢查 ngrok
echo "3️⃣  隧道狀態 (ngrok):"
if pgrep -f "ngrok http $TELEGRAM_GATEWAY_PORT" > /dev/null; then
    echo "   ✅ 運行中"
    PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['tunnels'][0]['public_url'] if data['tunnels'] else 'N/A')" 2>/dev/null)
    echo "   🌍 公網位址: $PUBLIC_URL"
else
    echo "   ❌ 未啟動"
fi
echo ""