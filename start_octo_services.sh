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

# 啟動 Telegram → AI Agent 軍團 遠端控制系統

set -e

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
    export PROJECT_ROOT=$(find_project_root "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")
    if [ -n "$PROJECT_ROOT" ] && [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
        source "$PROJECT_ROOT/.venv/bin/activate"
    fi
fi

# 動態判定 Python 執行檔路徑 (支援 Docker 的全域環境與 Local 的虛擬環境)
if [ -n "$PROJECT_ROOT" ] && [ -d "$PROJECT_ROOT/.venv" ]; then
    export PYTHON_CMD="$PROJECT_ROOT/.venv/bin/python3"
else
    export PYTHON_CMD="python3"
fi

# 解析為絕對路徑
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ----------------------------------------------------
# 攔截系統的 Stop 信號 (針對 macOS launchctl stop)
# ----------------------------------------------------
trap 'echo "收到系統停止信號 (SIGTERM/SIGINT)，正在關閉服務..."; "$SCRIPT_DIR/stop_octo_services.sh"; exit 0' SIGTERM SIGINT

# ----------------------------------------------------
# 等待網路的 Ping 迴圈 (無限期等待，確保離線開機時能接續)
# ----------------------------------------------------
echo "正在檢查網路連線..."
while ! python3 -c "import socket; socket.create_connection(('8.8.8.8', 53), timeout=2)" &>/dev/null; do
  # 在迴圈中使用 wait 來搭配 sleep，這樣 trap 才能即時響應信號
  sleep 5 &
  wait $!
done
echo "網路已連線！"

CONFIG_FILE="$SCRIPT_DIR/config.py"
ENV_FILE="$SCRIPT_DIR/.env"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 配置文件不存在: $CONFIG_FILE"
    exit 1
fi

# 載入環境變數
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
    echo "🔐 已載入 .env"
else
    echo "⚠️  警告: .env 檔案不存在"
fi

# 讀取配置
TMUX_SESSION_NAME=$(python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import TMUX_SESSION_NAME; print(TMUX_SESSION_NAME)")

echo "🚀 啟動 OctoMatrix"
echo "==========================================="

# 生成動態 Webhook Secret
SECRET_FILE="$SCRIPT_DIR/webhook_secret.token"
openssl rand -hex 32 > "$SECRET_FILE"
export WEBHOOK_SECRET_TOKEN=$(cat "$SECRET_FILE")

# 終止現有 session
if tmux has-session -t "$TMUX_SESSION_NAME" 2>/dev/null; then
    echo "🔄 終止現有 session…"
    tmux kill-session -t "$TMUX_SESSION_NAME"
    sleep 1
fi

# 建立主 session（指定獨立的 socket 文件，確保容器隔離）
echo "🧬  建立 tmux session '$TMUX_SESSION_NAME'…"
# 使用明確指定的 socket 檔案路徑建立 session（不依賴 TMUX_TMPDIR 環境變數）
tmux new-session -d -s "$TMUX_SESSION_NAME" -n "init" -c "$SCRIPT_DIR"

export SCRIPT_DIR
export TMUX_SESSION_NAME

# 1. 初始化 Agent 環境
echo "🧬  正在初始化 Agent 生態環境…"
python3 "$SCRIPT_DIR/setup_agent_env.py" --all

# 2. 動態啟動 AI Agent 軍團
echo "🤖 正在部署 AI Agent 軍團…"


echo "   ✅ 所有 Agent 已就緒"

# Window: MC Router API
echo "🔀 啟動 MC Router (消息路由中樞)…"
tmux new-window -t "$TMUX_SESSION_NAME" -n "router" -c "$SCRIPT_DIR"
tmux send-keys -t "$TMUX_SESSION_NAME:router" "$PYTHON_CMD $SCRIPT_DIR/octo_router.py" C-m
sleep 1
tmux send-keys -t "$TMUX_SESSION_NAME:router" Enter

# 等待 Router 啟動
sleep 2

# 檢查平臺啟用狀態並啟動網關
python3 << 'EOF'
import sys
import os
import subprocess
import time

script_dir = os.environ['SCRIPT_DIR']
session_name = os.environ['TMUX_SESSION_NAME']
python_exe = os.environ.get('PYTHON_CMD', 'python3')
sys.path.append(script_dir)

try:
    from config import PLATFORMS_ENABLED
    
    # 1. Telegram
    if PLATFORMS_ENABLED.get('telegram', True):
        print("   📱 啟動 Telegram Gateway (Router 轉發)…")
        subprocess.run(['tmux', 'new-window', '-t', session_name, '-n', 'telegram', '-c', script_dir], check=True)
        subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:telegram', f'{python_exe} {script_dir}/telegram_gateway.py', 'Enter'], check=True)
        time.sleep(2)
    else:
        print("   ⚪️ Telegram 已禁用，跳過啟動")

    # 2. Discord
    if PLATFORMS_ENABLED.get('discord', True):
        print("   💻 啟動 Discord Gateway (WebSocket 模式)…")
        subprocess.run(['tmux', 'new-window', '-t', session_name, '-n', 'discord', '-c', script_dir], check=True)
        subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:discord', f'{python_exe} {script_dir}/discord_gateway.py', 'Enter'], check=True)
        time.sleep(2)
    else:
        print("   ⚪️ Discord 已禁用，跳過啟動")

    # 3. Slack
    if PLATFORMS_ENABLED.get('slack', True):
        print("   ⚡ 啟動 Slack Gateway (Socket Mode)…")
        subprocess.run(['tmux', 'new-window', '-t', session_name, '-n', 'slack', '-c', script_dir], check=True)
        subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:slack', f'{python_exe} {script_dir}/slack_socket_gateway.py', 'Enter'], check=True)
        time.sleep(2)
    else:
        print("   ⚪️ Slack 已禁用，跳過啟動")

except Exception as e:
    print(f"   ❌ 啟動網關時發生異常: {e}")
EOF

# 等待所有 Gateway 啟動
sleep 2

# Window: Octo Reaper (Cyberbrain GHOST 收割者)
echo "🧠 啟動 Cyberbrain GHOST 收割者 (octo_reaper.py)…"
tmux new-window -t "$TMUX_SESSION_NAME" -n "reaper" -c "$SCRIPT_DIR"
tmux send-keys -t "$TMUX_SESSION_NAME:reaper" "$PYTHON_CMD $SCRIPT_DIR/octo_reaper.py" C-m
sleep 1
tmux send-keys -t "$TMUX_SESSION_NAME:reaper" Enter

if python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import PLATFORMS_ENABLED; print(PLATFORMS_ENABLED.get('telegram', True))" | grep -q "True"; then
    # Window: ngrok Tunnel
    echo "☁️  建立安全連線隧道 (ngrok)…"
    tmux new-window -t "$TMUX_SESSION_NAME" -n "ngrok" -c "$SCRIPT_DIR"
    tmux send-keys -t "$TMUX_SESSION_NAME:ngrok" "$SCRIPT_DIR/start_ngrok.sh"
    sleep 1
    tmux send-keys -t "$TMUX_SESSION_NAME:ngrok" Enter

    echo "⏳ 正在同步網路位址與 Webhook…"
    sleep 5
else
    echo "⚪️ Telegram 已禁用，跳過 Ngrok 啟動"
fi

# 回到第一個 Agent window
tmux select-window -t "$TMUX_SESSION_NAME:0"

# 測試發送訊息
echo "📨 向所有 Agent 發送測試訊息並報上名字..."
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
        test_msg = f"{SYS_PREFIX}執行 python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png 發符合當下心情的貼圖，接著執行 python3 toolbox/matrix_notifier.py '{{向 {MATRIX_USERNAME} 問候}}'"
        agent_dir = os.path.join(os.environ['SCRIPT_DIR'], 'agent_home', name)
        flag_file = os.path.join(agent_dir, 'octo_cyberbrain', '.rotation_flag')
        pending_file = os.path.join(agent_dir, 'octo_cyberbrain', 'pending_inject.txt')
        
        if os.path.exists(flag_file):
            with open(pending_file, 'a', encoding='utf-8') as f:
                if os.path.exists(pending_file) and os.path.getsize(pending_file) > 0:
                    f.write("\n\n")
                f.write(test_msg)
            print(f"   ✓ 已將測試訊息排入 {name} 的 pending 佇列")
        else:
            subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:{name}', test_msg], check=True)
            time.sleep(0.5)
            subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:{name}', 'Enter'], check=True)
            print(f"   ✓ 已發送測試訊息給: {name}")
except Exception as e:
    print(f"   ⚠️ 發送測試訊息失敗: {e}")
EOF

echo "==========================================="
echo "🎉 OctoMatrix 已全員部署！"
echo ""
echo "📋 運行摘要:"
echo "   Session: $TMUX_SESSION_NAME"
echo "   已啟動通訊網關:"
python3 << 'EOF'
import os
import sys
sys.path.append(os.environ['SCRIPT_DIR'])
try:
    from config import PLATFORMS_ENABLED
    if PLATFORMS_ENABLED.get('telegram', True): print("      📱 Telegram Gateway (Router 轉發)")
    if PLATFORMS_ENABLED.get('discord', True): print("      💻 Discord Gateway (WebSocket + 自動重連)")
    if PLATFORMS_ENABLED.get('slack', True): print("      ⚡ Slack Gateway (Socket Mode + 自動重連)")
    if not any(PLATFORMS_ENABLED.values()): print("      ⚪️ 無啟用任何通訊網關")
except Exception: pass
EOF
echo "   已啟動中樞服務:"
echo "      🔀 MC Router (消息標準化 + 原子注入)"
echo "      🧠 Octo Reaper (電子腦 GHOST 收割者)"
if python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import PLATFORMS_ENABLED; print(PLATFORMS_ENABLED.get('telegram', True))" | grep -q "True"; then
    echo "      ☁️  ngrok (Webhook 安全隧道)"
fi
echo ""
echo "   所有 tmux 視窗:"
tmux list-windows -t "$TMUX_SESSION_NAME" -F "      • Window #{window_index}: #{window_name}"
echo ""
echo "🚀 連接 Session: tmux attach -t $TMUX_SESSION_NAME"
echo ""
echo "✅ 驗證步驟:"
echo "   1. tmux attach -t $TMUX_SESSION_NAME"
echo "   2. 檢查 router 窗口: curl http://localhost:12210/health"
echo "   3. 在 Telegram/Discord/Slack 發送訊息並驗證 router 日誌"
