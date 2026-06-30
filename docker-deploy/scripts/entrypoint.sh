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

# ============================================================================
# OctoMatrix - [Entrypoint] 精簡委派版 (使用 gosu 實現正確降權)
# ============================================================================
set -e

echo "🧬 [Entrypoint] 容器覺醒中..."

# 1. 環境變數準備
export SCRIPT_DIR="/app/octomatrix"
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# 如果 APP_USER 變數未設定，預設回退為 appuser 以防萬一
export APP_USER=${APP_USER:-appuser}
export APP_UID=$(id -u $APP_USER 2>/dev/null || echo 1000)
export APP_GID=$(id -g $APP_USER 2>/dev/null || echo 1000)

# 2. 以 root 身份修復掛載卷的權限（一次性初始化）
if [ "$(id -u)" = "0" ]; then
    echo "🔐 [Root] 修復掛載卷的所有權和權限..."

    # 修復 agent_home 目錄
    if [ -d "$SCRIPT_DIR/agent_home" ]; then
        chown $APP_UID:$APP_GID "$SCRIPT_DIR/agent_home" 2>/dev/null || true
    fi

    # 確保動態用戶的主目錄與 tmux 目錄存在且可寫
    if [ ! -d "/home/$APP_USER/.tmux" ]; then
        mkdir -p "/home/$APP_USER/.tmux"
        chown -R $APP_UID:$APP_GID "/home/$APP_USER/.tmux"
        chmod 700 "/home/$APP_USER/.tmux"
    fi

    echo "🔓 [Root] 解鎖核心腳本以允許覆寫更新..."
    if [ -f "$SCRIPT_DIR/agent_home/.system_distributed_files.txt" ]; then
        xargs -a "$SCRIPT_DIR/agent_home/.system_distributed_files.txt" chattr -i 2>/dev/null || true
    fi

    echo "✅ 權限修復與解鎖完成"
fi

# 3. 使用 gosu 切換到動態用戶並執行啟動腳本
# 這樣確保容器全程以非 root 身份運行
cd "$SCRIPT_DIR"

if [ -f "./start_octo_services.sh" ]; then
    echo "🚀 使用 gosu 切換到 $APP_USER 用戶並執行啟動腳本..."
    # 確保 HOME 變數指向容器內的家目錄 (掛載了憑證)
    export HOME="/home/$APP_USER"
    gosu $APP_USER bash ./start_octo_services.sh
else
    echo "❌ 致命錯誤: 找不到 /app/octomatrix/start_octo_services.sh"
    exit 1
fi

if [ "$(id -u)" = "0" ]; then
    echo "🔒 [Root] 服務啟動完畢，精準鎖定系統派發腳本以防止越權篡改..."
    if [ -f "$SCRIPT_DIR/agent_home/.system_distributed_files.txt" ]; then
        xargs -a "$SCRIPT_DIR/agent_home/.system_distributed_files.txt" chattr +i 2>/dev/null || true
    fi
fi

echo "🏁 [Entrypoint] 啟動序列執行完畢。容器進入守護模式。"
# 保持容器運行
tail -f /dev/null
