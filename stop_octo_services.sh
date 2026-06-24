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

# stop_octo_services.sh (OctoMatrix 版)

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

SCRIPT_DIR="$(dirname "$0")"
TMUX_SESSION_NAME=$(python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import TMUX_SESSION_NAME; print(TMUX_SESSION_NAME)")

echo "==========================================="
echo "🛑 正在停止 OctoMatrix 系統"
echo "==========================================="

# 1. 殺掉專屬的 tmux session
# 注意：這會連帶關閉其底下的所有視窗與服務 (Python Gateways, Router, Ngrok 等)
# 確保了多實例 (Dev/Prod) 運行時的絕對隔離，不會誤殺其他實例的服務
if tmux has-session -t "$TMUX_SESSION_NAME" 2>/dev/null; then
    tmux kill-session -t "$TMUX_SESSION_NAME"
    echo "✅ tmux session '$TMUX_SESSION_NAME' 與所有附屬服務已終止"
else
    echo "⚠️  tmux session '$TMUX_SESSION_NAME' 不存在或已關閉"
fi

echo "==========================================="
echo "🎉 OctoMatrix 實例 ($TMUX_SESSION_NAME) 已完全停止"
echo "==========================================="