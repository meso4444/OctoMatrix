#!/bin/bash

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

# disable_mac_launchd.sh - 移除 Mac 開機自動啟動 OctoMatrix

echo "=========================================="
echo "🍏 OctoMatrix - 移除 Mac 開機自啟動 (Launchd)"
echo "=========================================="

PLIST_NAME="com.octomatrix.agent.plist"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME"

if [ -f "$PLIST_PATH" ]; then
    echo "🔄 正在從系統 Launchd 卸載服務..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    
    echo "🗑️  正在移除設定檔: $PLIST_PATH"
    rm -f "$PLIST_PATH"
    echo "✅ 移除成功！OctoMatrix 已取消開機自啟動。"
else
    echo "⚠️  找不到設定檔: $PLIST_PATH"
    echo "   (可能已經被移除，或者從未安裝過)"
fi
echo "=========================================="
