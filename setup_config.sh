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

# setup_config.sh
# OctoMatrix 互動式設定精靈

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
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
CONFIG_YAML="$SCRIPT_DIR/config.yaml"

# 載入現有設定 (如果有的話)
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# 嘗試從 config.yaml 讀取當前 Port 與通道偏好
CUR_TELEGRAM_GATEWAY_PORT=11440
CUR_NGROK_PORT=4040
CUR_ROUTER_PORT=12210

if [ -f "$CONFIG_YAML" ]; then
    CUR_TELEGRAM_GATEWAY_PORT=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_YAML'))['server'].get('telegram_gateway_port', 11440))" 2>/dev/null || echo 11440)
    CUR_NGROK_PORT=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_YAML'))['server']['ngrok_api_port'])" 2>/dev/null || echo 4040)
    CUR_ROUTER_PORT=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_YAML'))['router']['port'])" 2>/dev/null || echo 12210)
fi

# 建立還原快照 (用於 Q 操作)
ORIG_MATRIX_USERNAME="${MATRIX_USERNAME:-User}"
ORIG_TELEGRAM_ENABLED="${TELEGRAM_ENABLED:-true}"
ORIG_TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
ORIG_TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"
ORIG_NGROK_AUTHTOKEN="${NGROK_AUTHTOKEN:-}"

ORIG_DISCORD_ENABLED="${DISCORD_ENABLED:-false}"
ORIG_DISCORD_TOKEN="${DISCORD_TOKEN:-}"
ORIG_DISCORD_SERVER_ID="${DISCORD_SERVER_ID:-}"
ORIG_DISCORD_CHANNEL_ID="${DISCORD_CHANNEL_ID:-}"

ORIG_SLACK_ENABLED="${SLACK_ENABLED:-false}"
ORIG_SLACK_APP_TOKEN="${SLACK_APP_TOKEN:-}"
ORIG_SLACK_BOT_TOKEN="${SLACK_BOT_TOKEN:-}"
ORIG_SLACK_WORKSPACE_ID="${SLACK_WORKSPACE_ID:-}"
ORIG_SLACK_CHANNEL_ID="${SLACK_CHANNEL_ID:-}"

ORIG_TELEGRAM_GATEWAY_PORT="$CUR_TELEGRAM_GATEWAY_PORT"
ORIG_NGROK_API_PORT="$CUR_NGROK_PORT"
ORIG_ROUTER_PORT="$CUR_ROUTER_PORT"

# 當前工作變數
MATRIX_USERNAME="$ORIG_MATRIX_USERNAME"
TELEGRAM_ENABLED="$ORIG_TELEGRAM_ENABLED"
TELEGRAM_BOT_TOKEN="$ORIG_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID="$ORIG_TELEGRAM_CHAT_ID"
NGROK_AUTHTOKEN="$ORIG_NGROK_AUTHTOKEN"

DISCORD_ENABLED="$ORIG_DISCORD_ENABLED"
DISCORD_TOKEN="$ORIG_DISCORD_TOKEN"
DISCORD_SERVER_ID="$ORIG_DISCORD_SERVER_ID"
DISCORD_CHANNEL_ID="$ORIG_DISCORD_CHANNEL_ID"

SLACK_ENABLED="$ORIG_SLACK_ENABLED"
SLACK_APP_TOKEN="$ORIG_SLACK_APP_TOKEN"
SLACK_BOT_TOKEN="$ORIG_SLACK_BOT_TOKEN"
SLACK_WORKSPACE_ID="$ORIG_SLACK_WORKSPACE_ID"
SLACK_CHANNEL_ID="$ORIG_SLACK_CHANNEL_ID"

TELEGRAM_GATEWAY_PORT="$ORIG_TELEGRAM_GATEWAY_PORT"
NGROK_API_PORT="$ORIG_NGROK_API_PORT"
ROUTER_PORT="$ORIG_ROUTER_PORT"

# --- 自動獲取 Chat ID 函數 ---
get_chat_id_from_api() {
    export PY_BOT_TOKEN="$1"
    python3 -c "
import requests, sys, time, os
try:
    token = os.environ['PY_BOT_TOKEN']
    requests.post(f'https://api.telegram.org/bot{token}/deleteWebhook')
    for i in range(10):
        url = f'https://api.telegram.org/bot{token}/getUpdates'
        res = requests.get(url, timeout=5).json()
        if res.get('ok') and res['result']:
            print(res['result'][-1]['message']['chat']['id'])
            sys.exit(0)
        time.sleep(3)
    sys.exit(1)
except: sys.exit(2)
"
}

# --- 寫入 .env 函數 ---
write_env_file() {
    cat > "$ENV_FILE" << EOF
# =========================================
# 使用者資訊
# =========================================
MATRIX_USERNAME=$MATRIX_USERNAME

# =========================================
# Telegram 配置
# =========================================
TELEGRAM_ENABLED=$TELEGRAM_ENABLED
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID

# =========================================
# Discord 配置 (可選)
# =========================================
DISCORD_ENABLED=$DISCORD_ENABLED
DISCORD_TOKEN=$DISCORD_TOKEN
DISCORD_SERVER_ID=$DISCORD_SERVER_ID
DISCORD_CHANNEL_ID=$DISCORD_CHANNEL_ID

# =========================================
# Slack 配置 (可選)
# =========================================
SLACK_ENABLED=$SLACK_ENABLED
SLACK_APP_TOKEN=$SLACK_APP_TOKEN
SLACK_BOT_TOKEN=$SLACK_BOT_TOKEN
SLACK_WORKSPACE_ID=$SLACK_WORKSPACE_ID
SLACK_CHANNEL_ID=$SLACK_CHANNEL_ID

# =========================================
# ngrok 配置
# =========================================
NGROK_AUTHTOKEN=$NGROK_AUTHTOKEN

# =========================================
# MC Router 配置
# =========================================
ROUTER_HOST=127.0.0.1
ROUTER_PORT=$ROUTER_PORT
EOF
}

# --- 更新 config.yaml 函數 ---
update_config_yaml() {
    export TELEGRAM_GATEWAY_PORT NGROK_API_PORT ROUTER_PORT
    export TELEGRAM_ENABLED DISCORD_ENABLED SLACK_ENABLED
    python3 << 'PYTHON_EOF'
import os
import yaml

config_path = 'config.yaml'
try:
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) or {}
except FileNotFoundError:
    config = {}

# 1. Server 區塊
if 'server' not in config: config['server'] = {}
config['server']['telegram_gateway_port'] = int(os.environ['TELEGRAM_GATEWAY_PORT'])
config['server']['ngrok_api_port'] = int(os.environ['NGROK_API_PORT'])

# 2. Router 區塊
if 'router' not in config: config['router'] = {}
config['router']['host'] = '127.0.0.1'
config['router']['port'] = int(os.environ['ROUTER_PORT'])

try:
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
except Exception as e:
    print(f"更新 config.yaml 失敗: {e}")
PYTHON_EOF
}

# ============================================================================
# 主控台迴圈
# ============================================================================
# 記錄進入選單時的初始狀態 (供放棄變更還原使用)
[ -f "$ENV_FILE" ] && cp "$ENV_FILE" "${ENV_FILE}.session.bak"
[ -f "$CONFIG_YAML" ] && cp "$CONFIG_YAML" "${CONFIG_YAML}.session.bak"

while true; do
    clear
    echo "=========================================="
    echo "☀️🌙 OctoMatrix 互動式環境設定精靈 (Local)"
    echo "=========================================="
    
    # 顯示當前狀態
    echo "📊 當前狀態:"
    echo "  👤 使用者暱稱: $MATRIX_USERNAME"
    [ "$TELEGRAM_ENABLED" = "true" ] && echo "  ✅ Telegram (啟用)" || echo "  ⭕ Telegram (停用)"
    [ "$DISCORD_ENABLED" = "true" ] && echo "  ✅ Discord  (啟用)" || echo "  ⭕ Discord  (停用)"
    [ "$SLACK_ENABLED" = "true" ] && echo "  ✅ Slack    (啟用)" || echo "  ⭕ Slack    (停用)"
    echo "----------------------------------------"
    echo " [1] 👤 設定使用者暱稱 (Username)"
    echo " [2] 📱 設定 Telegram 與 Ngrok 隧道"
    echo " [3] 💻 設定 Discord"
    echo " [4] ⚡ 設定 Slack"
    echo " [5] 🌍 設定網路與連接埠 (Ports)"
    echo " [6] 🤖 設定 AI Agent 軍團與進階參數"
    echo " [7] 🔐 AI Agent CLI 認證設定"
    echo " [8] ⬆️ AI CLI 版本管理 (升級/退版)"
    echo " [9] 📦 執行全域技能建置 (Install Agent Skills)"
    echo "----------------------------------------"
    echo " [S] 💾 儲存設定並啟動 (Save)"
    echo " [C] 🧹 清除設定與憑證 (Clear)"
    echo " [Q] ❌ 放棄變更退出 (Quit)"
    echo "=========================================="

    read -p "請選擇操作 [1-8, S, C, Q]: " choice

    case $choice in
        1)
            echo ""
            echo "👤 使用者暱稱設定"
            read -p "  請輸入您的暱稱 [目前: $MATRIX_USERNAME]: " INPUT_USERNAME
            MATRIX_USERNAME="${INPUT_USERNAME:-$MATRIX_USERNAME}"
            ;;
        2)
            echo ""
            echo "📱 Telegram 設定"
            read -p "  啟用 Telegram? (y/N) [目前: $TELEGRAM_ENABLED]: " INPUT_ENABLE
            if [[ "$INPUT_ENABLE" =~ ^[Yy]$ ]]; then
                TELEGRAM_ENABLED="true"
                read -p "  1. Bot Token [目前: ${TELEGRAM_BOT_TOKEN:-未設定}]: " INPUT_BOT_TOKEN
                TELEGRAM_BOT_TOKEN="${INPUT_BOT_TOKEN:-$TELEGRAM_BOT_TOKEN}"

                # 自動獲取 Chat ID
                DETECTED_CHAT_ID=""
                if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
                    echo "🔄 正在嘗試自動獲取您的 Chat ID..."
                    DETECTED_CHAT_ID=$(get_chat_id_from_api "$TELEGRAM_BOT_TOKEN") || true
                fi
                read -p "  2. Chat ID [目前/自動: ${DETECTED_CHAT_ID:-$TELEGRAM_CHAT_ID}]: " INPUT_CHAT_ID
                TELEGRAM_CHAT_ID="${INPUT_CHAT_ID:-${DETECTED_CHAT_ID:-$TELEGRAM_CHAT_ID}}"

                echo "  🌐 ngrok 配置 (Telegram Webhook 必要項目)"
                read -p "  3. ngrok Authtoken [目前: ${NGROK_AUTHTOKEN:-未設定}]: " INPUT_NGROK
                NGROK_AUTHTOKEN="${INPUT_NGROK:-$NGROK_AUTHTOKEN}"
            else
                TELEGRAM_ENABLED="false"
            fi
            ;;
        3)
            echo ""
            echo "💻 Discord 設定"
            read -p "  啟用 Discord? (y/N) [目前: $DISCORD_ENABLED]: " INPUT_ENABLE
            if [[ "$INPUT_ENABLE" =~ ^[Yy]$ ]]; then
                DISCORD_ENABLED="true"
                read -p "  1. Bot Token [目前: ${DISCORD_TOKEN:-未設定}]: " INPUT_TOKEN
                DISCORD_TOKEN="${INPUT_TOKEN:-$DISCORD_TOKEN}"
                read -p "  2. Server ID [目前: ${DISCORD_SERVER_ID:-未設定}]: " INPUT_SERVER
                DISCORD_SERVER_ID="${INPUT_SERVER:-$DISCORD_SERVER_ID}"
                read -p "  3. Channel ID [目前: ${DISCORD_CHANNEL_ID:-未設定}]: " INPUT_CHANNEL
                DISCORD_CHANNEL_ID="${INPUT_CHANNEL:-$DISCORD_CHANNEL_ID}"
            else
                DISCORD_ENABLED="false"
            fi
            ;;
        4)
            echo ""
            echo "⚡ Slack 設定"
            read -p "  啟用 Slack? (y/N) [目前: $SLACK_ENABLED]: " INPUT_ENABLE
            if [[ "$INPUT_ENABLE" =~ ^[Yy]$ ]]; then
                SLACK_ENABLED="true"
                read -p "  1. App Token (xapp-...) [目前: ${SLACK_APP_TOKEN:-未設定}]: " INPUT_APP
                SLACK_APP_TOKEN="${INPUT_APP:-$SLACK_APP_TOKEN}"
                read -p "  2. Bot Token (xoxb-...) [目前: ${SLACK_BOT_TOKEN:-未設定}]: " INPUT_BOT
                SLACK_BOT_TOKEN="${INPUT_BOT:-$SLACK_BOT_TOKEN}"
                read -p "  3. Workspace ID [目前: ${SLACK_WORKSPACE_ID:-未設定}]: " INPUT_WORKSPACE
                SLACK_WORKSPACE_ID="${INPUT_WORKSPACE:-$SLACK_WORKSPACE_ID}"
                read -p "  4. Channel ID [目前: ${SLACK_CHANNEL_ID:-未設定}]: " INPUT_CHANNEL
                SLACK_CHANNEL_ID="${INPUT_CHANNEL:-$SLACK_CHANNEL_ID}"
            else
                SLACK_ENABLED="false"
            fi
            ;;
        5)
            echo ""
            echo "🌍 網路與連接埠設定"
            read -p "  1. Telegram Gateway Port [目前: $TELEGRAM_GATEWAY_PORT]: " INPUT_TG_PORT
            TELEGRAM_GATEWAY_PORT="${INPUT_TG_PORT:-$TELEGRAM_GATEWAY_PORT}"
            read -p "  2. Ngrok API Port [目前: $NGROK_API_PORT]: " INPUT_NGROK_PORT
            NGROK_API_PORT="${INPUT_NGROK_PORT:-$NGROK_API_PORT}"
            read -p "  3. Octo Router Port [目前: $ROUTER_PORT]: " INPUT_ROUTER_PORT
            ROUTER_PORT="${INPUT_ROUTER_PORT:-$ROUTER_PORT}"
            ;;
        6)
            echo ""
            echo "🤖 啟動設定精靈配置 Agent 與進階參數..."
            update_config_yaml
            if ! python3 "$SCRIPT_DIR/config_wizard.py" "$CONFIG_YAML"; then
                echo -e "\n⚠️ Agent 配置精靈發生錯誤 (可能是依賴套件缺失或環境損毀)"
                echo "腳本已中斷，請往上捲動查看 Python 報錯資訊。"
                exit 1
            fi
            ;;
        7)
            echo ""
            bash "$SCRIPT_DIR/agent_credential_wizard.sh" --local
            echo ""
            read -p "請按 Enter 鍵繼續..." dummy_key
            ;;
        8)
            while true; do
                clear
                echo "=========================================="
                echo "⬆️  AI CLI 版本管理 (手動升級/退版)"
                echo "=========================================="
                echo " [1] 🆙 升級 Gemini CLI"
                echo " [2] 🆙 升級 Claude Code"
                echo " [3] 🆙 升級 Codex CLI"
                echo " [4] 🆙 升級 agy CLI (Antigravity)"
                echo " [5] 🚀 一併升級所有 CLI 工具"
                echo "----------------------------------------"
                echo " [6] ⏪ 退版 Gemini CLI (還原至備份版本)"
                echo " [7] ⏪ 退版 Claude Code (還原至備份版本)"
                echo " [8] ⏪ 退版 Codex CLI (還原至備份版本)"
                echo " [9] 🛡️ 一併退版所有 CLI 工具"
                echo "----------------------------------------"
                echo " [R] 🔙 返回主選單"
                echo "=========================================="
                read -p "請選擇操作 [1-9, R]: " cli_choice

                do_update() {
                    local pkg="$1"
                    local name="$2"
                    echo "🔄 正在備份 $name 當前版本..."
                    local current_ver=$(npm list -g --depth=0 --no-color "$pkg" | grep "$pkg" | awk -F@ '{print $NF}' | sed -r "s/\x1B\[[0-9;]*[mK]//g" | tr -d '\r\n')
                    if [ -n "$current_ver" ]; then
                        mkdir -p "$SCRIPT_DIR/.cli_versions_bak"
                        echo "$current_ver" > "$SCRIPT_DIR/.cli_versions_bak/${pkg//\//_}_version.bak"
                        echo "✅ 已備份 $name 版本: $current_ver"
                    fi
                    echo "🚀 正在全域升級 $name (需要 sudo 權限)..."
                    sudo npm update -g "$pkg"
                    echo "✅ $name 升級完成！"
                    read -p "請按 Enter 鍵繼續..." dummy_key
                }

                do_update_agy() {
                    echo "🔄 正在重新安裝 agy CLI (Antigravity) 至最新版本..."
                    if curl -fsSL https://antigravity.google/cli/install.sh | bash; then
                        echo "   🚚 複製 agy 至系統全域路徑..."
                        sudo cp ~/.local/bin/agy /usr/local/bin/agy
                        echo "✅ agy CLI 升級完成！"
                    else
                        echo "⚠️ agy CLI 升級失敗"
                    fi
                    read -p "請按 Enter 鍵繼續..." dummy_key
                }

                do_rollback() {
                    local pkg="$1"
                    local name="$2"
                    local bak_file="$SCRIPT_DIR/.cli_versions_bak/${pkg//\//_}_version.bak"
                    if [ -f "$bak_file" ]; then
                        local old_ver=$(cat "$bak_file")
                        echo "⏪ 準備將 $name 退回版本: $old_ver (需要 sudo 權限)..."
                        sudo npm install -g "${pkg}@${old_ver}"
                        echo "✅ $name 退版完成！"
                        rm -f "$bak_file"
                    else
                        echo "⚠️ 找不到 $name 的版本備份檔，無法自動退版！"
                    fi
                    read -p "請按 Enter 鍵繼續..." dummy_key
                }

                case $cli_choice in
                    1) do_update "@google/gemini-cli" "Gemini CLI" ;;
                    2) do_update "@anthropic-ai/claude-code" "Claude Code" ;;
                    3) do_update "@openai/codex" "Codex CLI" ;;
                    4) do_update_agy ;;
                    5)
                        do_update "@google/gemini-cli" "Gemini CLI"
                        do_update "@anthropic-ai/claude-code" "Claude Code"
                        do_update "@openai/codex" "Codex CLI"
                        do_update_agy
                        ;;
                    6) do_rollback "@google/gemini-cli" "Gemini CLI" ;;
                    7) do_rollback "@anthropic-ai/claude-code" "Claude Code" ;;
                    8) do_rollback "@openai/codex" "Codex CLI" ;;
                    9)
                        do_rollback "@google/gemini-cli" "Gemini CLI"
                        do_rollback "@anthropic-ai/claude-code" "Claude Code"
                        do_rollback "@openai/codex" "Codex CLI"
                        ;;
                    [Rr]) break ;;
                    *) echo "⚠️ 無效的選擇"; sleep 1 ;;
                esac
            done
            ;;
        9)
            echo ""
            # 先建好每個 Agent 的 skillbox 目錄（可能尚未執行過 setup_agent_env.py），
            # 否則 install_agent_skills.py 找不到任何 Agent 目錄可以部署技能。
            python3 -c "
import yaml, os
config = yaml.safe_load(open('$CONFIG_YAML'))
for agent in config.get('agents', []):
    os.makedirs(os.path.join('$SCRIPT_DIR', 'agent_home', agent['name'], 'skillbox'), exist_ok=True)
" 2>/dev/null
            echo "📦 啟動全域技能建置程序..."
            if python3 "$SCRIPT_DIR/install_agent_skills.py"; then
                echo -e "\n✅ 全域技能建置成功！"
            else
                echo -e "\n⚠️ 全域技能建置發生錯誤，請查看上方輸出。"
            fi
            read -p "請按 Enter 鍵繼續..." dummy_key
            ;;
        [Ss])
            echo ""
            # 檢查是否有至少一個平台啟用
            if [ "$TELEGRAM_ENABLED" != "true" ] && [ "$DISCORD_ENABLED" != "true" ] && [ "$SLACK_ENABLED" != "true" ]; then
                echo "❌ 錯誤：至少需要啟用一個通訊通道！"
                read -p "按 Enter 鍵繼續..." dummy
                continue
            fi
            
            rm -f "${ENV_FILE}.session.bak" "${CONFIG_YAML}.session.bak" 2>/dev/null
            
            write_env_file
            update_config_yaml
            
            echo "🎉 設定完成！您可以執行 ./start_octo_services.sh 啟動服務了。"
            break
            ;;
        [Cc])
            echo ""
            echo "🧹 清除設定與憑證"
            echo "  [1] 僅清除通訊憑證 (.env)"
            echo "  [2] 僅清除 Agent 軍團與進階設定 (config.yaml)"
            echo "  [3] 全部清除"
            echo "  [R] 返回"
            read -p "  請選擇清除範圍 [1-3, R]: " CLEAR_CHOICE
            
            if [[ "$CLEAR_CHOICE" =~ ^[1-3]$ ]]; then
                read -p "⚠️  警告：此操作將清空選定的設定，確定要清除嗎? [y/N]: " CONFIRM_CLEAR
                if [[ "$CONFIRM_CLEAR" =~ ^[Yy]$ ]]; then
                    read -p "📂 是否在清除前進行備份? (Y/n): " BACKUP_BEFORE_CLEAR
                    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
                    
                    if [ "$CLEAR_CHOICE" == "1" ] || [ "$CLEAR_CHOICE" == "3" ]; then
                        if [[ ! "$BACKUP_BEFORE_CLEAR" =~ ^[Nn]$ ]]; then
                            [ -f "$ENV_FILE" ] && cp "$ENV_FILE" "${ENV_FILE}.${TIMESTAMP}.bak" && echo "✅ 已備份: $(basename "$ENV_FILE").${TIMESTAMP}.bak"
                        fi
                        # 重置變數
                        MATRIX_USERNAME="User"
                        TELEGRAM_ENABLED="false"; TELEGRAM_BOT_TOKEN=""; TELEGRAM_CHAT_ID=""; NGROK_AUTHTOKEN=""
                        DISCORD_ENABLED="false"; DISCORD_TOKEN=""; DISCORD_SERVER_ID=""; DISCORD_CHANNEL_ID=""
                        SLACK_ENABLED="false"; SLACK_APP_TOKEN=""; SLACK_BOT_TOKEN=""; SLACK_WORKSPACE_ID=""; SLACK_CHANNEL_ID=""
                        TELEGRAM_GATEWAY_PORT=11440; NGROK_API_PORT=4040; ROUTER_PORT=12210
                        write_env_file
                        echo "✅ 所有通訊憑證 (.env) 已清除。"
                    fi
                    
                    if [ "$CLEAR_CHOICE" == "2" ] || [ "$CLEAR_CHOICE" == "3" ]; then
                        if [[ ! "$BACKUP_BEFORE_CLEAR" =~ ^[Nn]$ ]]; then
                            [ -f "$CONFIG_YAML" ] && cp "$CONFIG_YAML" "${CONFIG_YAML}.${TIMESTAMP}.bak" && echo "✅ 已備份: $(basename "$CONFIG_YAML").${TIMESTAMP}.bak"
                        fi
                        rm -f "$CONFIG_YAML"
                        echo "✅ Agent 軍團設定 (config.yaml) 已清除。"
                    fi
                fi
            fi
            read -p "按 Enter 鍵繼續..." dummy
            ;;
        [Qq])
            echo "⚠️  放棄變更並退出..."
            echo "🧹 請問要還原哪些設定至進入選單前的狀態？"
            echo "  [1] 僅還原通訊憑證 (.env)"
            echo "  [2] 僅還原 Agent 軍團設定 (config.yaml)"
            echo "  [3] 全部還原"
            echo "  [N] 不還原，直接退出"
            read -p "  請選擇還原範圍 [1-3, N]: " RESTORE_CHOICE
            
            if [[ "$RESTORE_CHOICE" =~ ^[13]$ ]]; then
                if [ -f "${ENV_FILE}.session.bak" ]; then
                    mv "${ENV_FILE}.session.bak" "$ENV_FILE"
                    echo "✅ 通訊憑證 (.env) 已還原。"
                else
                    rm -f "$ENV_FILE" 2>/dev/null
                fi
            else
                rm -f "${ENV_FILE}.session.bak" 2>/dev/null
            fi
            
            if [[ "$RESTORE_CHOICE" =~ ^[23]$ ]]; then
                if [ -f "${CONFIG_YAML}.session.bak" ]; then
                    mv "${CONFIG_YAML}.session.bak" "$CONFIG_YAML"
                    echo "✅ Agent 軍團設定 (config.yaml) 已還原。"
                else
                    rm -f "$CONFIG_YAML" 2>/dev/null
                fi
            else
                rm -f "${CONFIG_YAML}.session.bak" 2>/dev/null
            fi
            exit 0
            ;;
    esac
done
