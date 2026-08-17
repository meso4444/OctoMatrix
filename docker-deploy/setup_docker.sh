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

# setup_docker.sh - OctoMatrix Docker Deployment Configuration Wizard
# Purpose: Setup Docker instance with credentials and configuration

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
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_GENERATOR="$SCRIPT_DIR/generate_config.py"

echo "=========================================="
echo "🐳 OctoMatrix - Docker 實例設置精靈"
echo "=========================================="
echo ""

# 實例名稱驗證函數
validate_instance_name() {
  local name="$1"
  if [[ ! "$name" =~ ^[a-zA-Z0-9_]+$ ]]; then
    echo "❌ 無效的實例名稱：'$name'"
    echo "   允許的字符：字母、數字、下劃線"
    return 1
  fi
  return 0
}

# 循環讀取直到有效
if [ -z "$INSTANCE_NAME" ]; then
    while true; do
        read -p "請輸入實例名稱 (例: dev, test, pro): " INSTANCE_NAME
        if validate_instance_name "$INSTANCE_NAME"; then
            break
        fi
    done
fi

ENV_FILE="$SCRIPT_DIR/.env.${INSTANCE_NAME}"

# 載入現有環境變數
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# 建立還原快照 (用於 Q 操作)
ORIG_MATRIX_USERNAME="${MATRIX_USERNAME:-User}"
ORIG_TZ="${TZ:-Asia/Taipei}"
ORIG_TELEGRAM_ENABLED="${TELEGRAM_ENABLED:-false}"
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

# 當前工作變數
MATRIX_USERNAME="$ORIG_MATRIX_USERNAME"
TZ="$ORIG_TZ"
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

write_env_file() {
    cat > "$ENV_FILE" << ENVEOF
# =========================================
# OctoMatrix - $INSTANCE_NAME 環境變數
# =========================================
MATRIX_USERNAME=$MATRIX_USERNAME
TZ=$TZ

# =========================================
# Telegram 配置
# =========================================
TELEGRAM_ENABLED=$TELEGRAM_ENABLED
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID

# =========================================
# Discord 配置
# =========================================
DISCORD_ENABLED=$DISCORD_ENABLED
DISCORD_TOKEN=$DISCORD_TOKEN
DISCORD_SERVER_ID=$DISCORD_SERVER_ID
DISCORD_CHANNEL_ID=$DISCORD_CHANNEL_ID

# =========================================
# Slack 配置
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
ENVEOF
}

# ============================================================================
# 主控台迴圈
# ============================================================================
# 記錄進入選單時的初始狀態 (供放棄變更還原使用)
[ -f "$ENV_FILE" ] && cp "$ENV_FILE" "${ENV_FILE}.session.bak"
CONFIG_YAML="$SCRIPT_DIR/container_home/$INSTANCE_NAME/config.yaml"
[ -f "$CONFIG_YAML" ] && cp "$CONFIG_YAML" "${CONFIG_YAML}.session.bak"

while true; do
    clear
    echo "=========================================="
    echo "🐳 Docker 實例設置精靈: $INSTANCE_NAME"
    echo "=========================================="
    
    # 顯示當前狀態
    echo "📊 當前通道狀態:"
    [ "$TELEGRAM_ENABLED" = "true" ] && echo "  ✅ Telegram (啟用)" || echo "  ⭕ Telegram (停用)"
    [ "$DISCORD_ENABLED" = "true" ] && echo "  ✅ Discord  (啟用)" || echo "  ⭕ Discord  (停用)"
    [ "$SLACK_ENABLED" = "true" ] && echo "  ✅ Slack    (啟用)" || echo "  ⭕ Slack    (停用)"
    echo "  🌍 時區 (TZ): $TZ"
    echo "----------------------------------------"
    echo " [U] 👤 設定使用者名稱 (當前: $MATRIX_USERNAME)"
    echo " [1] 📱 設定 Telegram 與 Ngrok 隧道"
    echo " [2] 💻 設定 Discord"
    echo " [3] ⚡ 設定 Slack"
    echo " [4] 🌍 設定時區 (TZ)"
    echo " [5] 🤖 設定 AI Agent 軍團與進階參數"
    echo " [6] 🔐 AI Agent CLI 認證設定"
    echo " [7] 📦 執行全域技能建置 (Install Agent Skills)"
    echo "----------------------------------------"
    echo " [S] 💾 儲存並生成配置 (Start)"
    echo " [C] 🧹 清除設定與憑證 (Clear)"
    echo " [Q] ❌ 放棄變更退出 (Quit)"
    echo "=========================================="

    read -p "請選擇操作 [1-7, U, S, C, Q]: " choice
    
    case $choice in
        [Uu])
            echo ""
            read -p "請輸入您的稱呼 (預設: User) [目前: $MATRIX_USERNAME]: " TEMP_USER
            if [ -n "$TEMP_USER" ]; then
                MATRIX_USERNAME="$TEMP_USER"
            fi
            ;;
        1)
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
            echo "🌍 時區設定"
            read -p "  請輸入時區 (例如 Asia/Taipei) [目前: $TZ]: " INPUT_TZ
            TZ="${INPUT_TZ:-$TZ}"
            ;;
        5)
            echo ""
            echo "🤖 啟動設定精靈配置 Agent 與進階參數..."
            write_env_file
            if [ ! -f "$SCRIPT_DIR/config.${INSTANCE_NAME}.yaml" ]; then
                echo "⚙️  正在產生基礎設定檔..."
                python3 "$CONFIG_GENERATOR" "config" "$INSTANCE_NAME" "" "$SCRIPT_DIR" "11440" "4040" "$(whoami)" "12210"
            fi
            python3 "$SCRIPT_DIR/../config_wizard.py" "$SCRIPT_DIR/config.${INSTANCE_NAME}.yaml"
            ;;
        6)
            echo ""
            bash "$SCRIPT_DIR/../agent_credential_wizard.sh" --container "$INSTANCE_NAME"
            ;;
        7)
            echo ""
            if [ ! -f "$SCRIPT_DIR/config.${INSTANCE_NAME}.yaml" ]; then
                echo "❌ 錯誤：尚未產生 Agent 設定檔，請先執行 [5] 設定 AI Agent 軍團與進階參數。"
                read -p "按 Enter 鍵繼續..." dummy
                continue
            fi
            # 先建好每個 Agent 的 skillbox 目錄（可能尚未執行過 setup_agent_env.py），
            # 否則 install_agent_skills.py 找不到任何 Agent 目錄可以部署技能。
            python3 -c "
import yaml, os
config = yaml.safe_load(open('$SCRIPT_DIR/config.${INSTANCE_NAME}.yaml'))
for agent in config.get('agents', []):
    os.makedirs(os.path.join('$SCRIPT_DIR', '..', 'agent_home', agent['name'], 'skillbox'), exist_ok=True)
" 2>/dev/null
            echo "📦 啟動全域技能建置程序..."
            if python3 "$SCRIPT_DIR/../install_agent_skills.py"; then
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
            
            echo ""
            if [ ! -f "$SCRIPT_DIR/config.${INSTANCE_NAME}.yaml" ]; then
                echo "⚙️  正在調用生成器物理落地基礎配置..."
                python3 "$CONFIG_GENERATOR" "config" "$INSTANCE_NAME" "" "$SCRIPT_DIR" "11440" "4040" "$(whoami)" "12210"
                echo "🤖 啟動設定精靈配置 Agent 與進階參數..."
                python3 "$SCRIPT_DIR/../config_wizard.py" "$SCRIPT_DIR/config.${INSTANCE_NAME}.yaml"
            fi
            python3 "$CONFIG_GENERATOR" "compose" "$INSTANCE_NAME" "" "$SCRIPT_DIR" "11440" "4040" "$(whoami)" "12210"

            if [ ! -f "$SCRIPT_DIR/awake.${INSTANCE_NAME}.yaml" ]; then
                echo "awake:" > "$SCRIPT_DIR/awake.${INSTANCE_NAME}.yaml"
                echo "📄 已產生全新喚醒配置檔: awake.${INSTANCE_NAME}.yaml"
            fi

            # 建立容器憑證持久化目錄
            mkdir -p "$SCRIPT_DIR/container_home/$INSTANCE_NAME"
            chmod 750 "$SCRIPT_DIR/container_home/$INSTANCE_NAME"
            chown "$(whoami)" "$SCRIPT_DIR/container_home/$INSTANCE_NAME"
            
            TMUX_SESSION=$(python3 -c "import yaml; print(yaml.safe_load(open('$SCRIPT_DIR/config.${INSTANCE_NAME}.yaml'))['tmux']['session_name'])" 2>/dev/null || echo "ai_${INSTANCE_NAME}")
            CURRENT_USER=$(whoami)

            # 先建好每個 Agent 的 skillbox 目錄，再建置並部署技能包，讓 host 端
            # agent_home/{name}/skillbox 在使用者執行 docker build 之前就已就緒
            # （含 .global_skills_cache），確保 Dockerfile 的 COPY skills/ 能把
            # 已建置好的快取一併打包進映像檔。
            python3 -c "
import yaml, os
config = yaml.safe_load(open('$SCRIPT_DIR/config.${INSTANCE_NAME}.yaml'))
for agent in config.get('agents', []):
    os.makedirs(os.path.join('$SCRIPT_DIR', '..', 'agent_home', agent['name'], 'skillbox'), exist_ok=True)
" 2>/dev/null
            echo "📦 正在建置並部署技能包..."
            python3 "$SCRIPT_DIR/../install_agent_skills.py"

            echo "✅ 實例設置完成！"
            echo "=========================================="
            echo "🚀 接下來，您可以執行以下指令來操作您的 AI 軍團："
            echo "1. 乾淨建置與啟動容器 (背景執行)："
            echo "   docker compose -f docker-compose.${INSTANCE_NAME}.yml -p octo_${INSTANCE_NAME} build --no-cache && docker compose -f docker-compose.${INSTANCE_NAME}.yml -p octo_${INSTANCE_NAME} up -d"
            echo ""
            echo "2. 查看容器運行狀態："
            echo "   docker compose -f docker-compose.${INSTANCE_NAME}.yml -p octo_${INSTANCE_NAME} ps"
            echo "   docker compose -f docker-compose.${INSTANCE_NAME}.yml -p octo_${INSTANCE_NAME} logs -f"
            echo ""
            echo "3. 進入容器內部查看 tmux 視窗："
            echo "   docker exec -it -u $CURRENT_USER octo_${INSTANCE_NAME}-bot tmux attach -t $TMUX_SESSION"
            echo ""
            echo "4. 停止並移除容器："
            echo "   docker compose -f docker-compose.${INSTANCE_NAME}.yml -p octo_${INSTANCE_NAME} down"
            echo "   docker image rm octo_${INSTANCE_NAME}-bot"
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
                        TZ="Asia/Taipei"
                        TELEGRAM_ENABLED="false"; TELEGRAM_BOT_TOKEN=""; TELEGRAM_CHAT_ID=""; NGROK_AUTHTOKEN=""
                        DISCORD_ENABLED="false"; DISCORD_TOKEN=""; DISCORD_SERVER_ID=""; DISCORD_CHANNEL_ID=""
                        SLACK_ENABLED="false"; SLACK_APP_TOKEN=""; SLACK_BOT_TOKEN=""; SLACK_WORKSPACE_ID=""; SLACK_CHANNEL_ID=""
                        write_env_file
                        echo "✅ 所有通訊憑證 (.env) 已清除。"
                    fi
                    
                    if [ "$CLEAR_CHOICE" == "2" ] || [ "$CLEAR_CHOICE" == "3" ]; then
                        CONFIG_YAML="$SCRIPT_DIR/container_home/$INSTANCE_NAME/config.yaml"
                        if [[ ! "$BACKUP_BEFORE_CLEAR" =~ ^[Nn]$ ]]; then
                            [ -f "$CONFIG_YAML" ] && cp "$CONFIG_YAML" "${CONFIG_YAML}.${TIMESTAMP}.bak" && echo "✅ 已備份: config.yaml.${TIMESTAMP}.bak"
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
            
            CONFIG_YAML="$SCRIPT_DIR/container_home/$INSTANCE_NAME/config.yaml"
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
