#!/bin/bash
# setup_config.sh
# OctoMatrix 互動式設定精靈

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
    echo "📊 當前通道狀態:"
    [ "$TELEGRAM_ENABLED" = "true" ] && echo "  ✅ Telegram (啟用)" || echo "  ⭕ Telegram (停用)"
    [ "$DISCORD_ENABLED" = "true" ] && echo "  ✅ Discord  (啟用)" || echo "  ⭕ Discord  (停用)"
    [ "$SLACK_ENABLED" = "true" ] && echo "  ✅ Slack    (啟用)" || echo "  ⭕ Slack    (停用)"
    echo "----------------------------------------"
    echo " [1] 📱 設定 Telegram 與 Ngrok 隧道"
    echo " [2] 💻 設定 Discord"
    echo " [3] ⚡ 設定 Slack"
    echo " [4] 🌍 設定網路與連接埠 (Ports)"
    echo " [5] 🤖 設定 AI Agent 軍團與進階參數"
    echo " [6] 🔐 AI Agent CLI 認證設定"
    echo "----------------------------------------"
    echo " [S] 💾 儲存設定並啟動 (Save)"
    echo " [C] 🧹 清除設定與憑證 (Clear)"
    echo " [Q] ❌ 放棄變更退出 (Quit)"
    echo "=========================================="

    read -p "請選擇操作 [1-6, S, C, Q]: " choice

    case $choice in        1)
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
        2)
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
        3)
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
        4)
            echo ""
            echo "🌍 網路與連接埠設定"
            read -p "  1. Telegram Gateway Port [目前: $TELEGRAM_GATEWAY_PORT]: " INPUT_TG_PORT
            TELEGRAM_GATEWAY_PORT="${INPUT_TG_PORT:-$TELEGRAM_GATEWAY_PORT}"
            read -p "  2. Ngrok API Port [目前: $NGROK_API_PORT]: " INPUT_NGROK_PORT
            NGROK_API_PORT="${INPUT_NGROK_PORT:-$NGROK_API_PORT}"
            read -p "  3. Octo Router Port [目前: $ROUTER_PORT]: " INPUT_ROUTER_PORT
            ROUTER_PORT="${INPUT_ROUTER_PORT:-$ROUTER_PORT}"
            ;;
        5)
            echo ""
            echo "🤖 啟動設定精靈配置 Agent 與進階參數..."
            update_config_yaml
            python3 "$SCRIPT_DIR/config_wizard.py" "$CONFIG_YAML"
            ;;
        6)
            echo ""
            bash "$SCRIPT_DIR/agent_credential_wizard.sh" --local
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
