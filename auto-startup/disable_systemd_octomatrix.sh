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

# disable_systemd_octomatrix.sh
# 移除 OctoMatrix 的 Systemd 開機自啟設定

SERVICE_NAME="octomatrix-services"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

# 檢查 root 權限
if [ "$EUID" -ne 0 ]; then
  echo "❌ 請使用 sudo 執行此腳本"
  echo "   範例: sudo ./auto-startup/disable_systemd_octomatrix.sh"
  exit 1
fi

echo "🛑 正在移除 Systemd 服務: $SERVICE_NAME"

# 1. 停止並停用服務
if systemctl is-active --quiet $SERVICE_NAME; then
    echo "   停止服務..."
    systemctl stop $SERVICE_NAME
fi

if systemctl is-enabled --quiet $SERVICE_NAME 2>/dev/null; then
    echo "   停用開機自啟..."
    systemctl disable $SERVICE_NAME
fi

# 2. 刪除設定檔
if [ -f "$SERVICE_FILE" ]; then
    echo "   刪除設定檔: $SERVICE_FILE"
    rm "$SERVICE_FILE"
    systemctl daemon-reload
    echo "✅ 服務已完全移除"
else
    echo "⚠️  設定檔不存在，可能已經移除"
fi

echo ""
echo "💡 若要重新啟用，請執行 install_systemd_octomatrix.sh"