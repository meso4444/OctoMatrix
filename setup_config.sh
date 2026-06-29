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
# OctoMatrix Interactive Configuration Wizard

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
ENV_FILE="$SCRIPT_DIR/.env"
CONFIG_YAML="$SCRIPT_DIR/config.yaml"

# Load existing configuration (if present)
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# Try to read current Port and channel preferences from config.yaml
CUR_TELEGRAM_GATEWAY_PORT=11440
CUR_NGROK_PORT=4040
CUR_ROUTER_PORT=12210

if [ -f "$CONFIG_YAML" ]; then
    CUR_TELEGRAM_GATEWAY_PORT=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_YAML'))['server'].get('telegram_gateway_port', 11440))" 2>/dev/null || echo 11440)
    CUR_NGROK_PORT=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_YAML'))['server']['ngrok_api_port'])" 2>/dev/null || echo 4040)
    CUR_ROUTER_PORT=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_YAML'))['router']['port'])" 2>/dev/null || echo 12210)
fi

# Create snapshot for restoration (for Q operation)
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

# Current working variables
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

# --- Auto-retrieve Chat ID function ---
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

# --- Write .env function ---
write_env_file() {
    cat > "$ENV_FILE" << EOF
# =========================================
# User Information
# =========================================
MATRIX_USERNAME=$MATRIX_USERNAME

# =========================================
# Telegram Configuration
# =========================================
TELEGRAM_ENABLED=$TELEGRAM_ENABLED
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID

# =========================================
# Discord Configuration (Optional)
# =========================================
DISCORD_ENABLED=$DISCORD_ENABLED
DISCORD_TOKEN=$DISCORD_TOKEN
DISCORD_SERVER_ID=$DISCORD_SERVER_ID
DISCORD_CHANNEL_ID=$DISCORD_CHANNEL_ID

# =========================================
# Slack Configuration (Optional)
# =========================================
SLACK_ENABLED=$SLACK_ENABLED
SLACK_APP_TOKEN=$SLACK_APP_TOKEN
SLACK_BOT_TOKEN=$SLACK_BOT_TOKEN
SLACK_WORKSPACE_ID=$SLACK_WORKSPACE_ID
SLACK_CHANNEL_ID=$SLACK_CHANNEL_ID

# =========================================
# ngrok Configuration
# =========================================
NGROK_AUTHTOKEN=$NGROK_AUTHTOKEN

# =========================================
# MC Router Configuration
# =========================================
ROUTER_HOST=127.0.0.1
ROUTER_PORT=$ROUTER_PORT
EOF
}

# --- Update config.yaml function ---
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

# 1. Server section
if 'server' not in config: config['server'] = {}
config['server']['telegram_gateway_port'] = int(os.environ['TELEGRAM_GATEWAY_PORT'])
config['server']['ngrok_api_port'] = int(os.environ['NGROK_API_PORT'])

# 2. Router section
if 'router' not in config: config['router'] = {}
config['router']['host'] = '127.0.0.1'
config['router']['port'] = int(os.environ['ROUTER_PORT'])

try:
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
except Exception as e:
    print(f"Failed to update config.yaml: {e}")
PYTHON_EOF
}

# ============================================================================
# Main console loop
# ============================================================================
# Record initial state when entering menu (for restoration if changes are abandoned)
[ -f "$ENV_FILE" ] && cp "$ENV_FILE" "${ENV_FILE}.session.bak"
[ -f "$CONFIG_YAML" ] && cp "$CONFIG_YAML" "${CONFIG_YAML}.session.bak"

while true; do
    clear
    echo "=========================================="
    echo "☀️🌙 OctoMatrix Interactive Environment Configuration Wizard (Local)"
    echo "=========================================="

    # Display current status
    echo "📊 Current Status:"
    echo "  👤 User Nickname: $MATRIX_USERNAME"
    [ "$TELEGRAM_ENABLED" = "true" ] && echo "  ✅ Telegram (Enabled)" || echo "  ⭕ Telegram (Disabled)"
    [ "$DISCORD_ENABLED" = "true" ] && echo "  ✅ Discord  (Enabled)" || echo "  ⭕ Discord  (Disabled)"
    [ "$SLACK_ENABLED" = "true" ] && echo "  ✅ Slack    (Enabled)" || echo "  ⭕ Slack    (Disabled)"
    echo "----------------------------------------"
    echo " [1] 👤 Configure User Nickname (Username)"
    echo " [2] 📱 Configure Telegram and Ngrok Tunnel"
    echo " [3] 💻 Configure Discord"
    echo " [4] ⚡ Configure Slack"
    echo " [5] 🌍 Configure Network and Ports"
    echo " [6] 🤖 Configure AI Agent Squad and Advanced Parameters"
    echo " [7] 🔐 AI Agent CLI Authentication Settings"
    echo " [8] ⬆️ AI CLI Version Management (Upgrade/Rollback)"
    echo "----------------------------------------"
    echo " [S] 💾 Save Configuration and Start (Save)"
    echo " [C] 🧹 Clear Configuration and Credentials (Clear)"
    echo " [Q] ❌ Abandon Changes and Exit (Quit)"
    echo "=========================================="

    read -p "Please select an operation [1-8, S, C, Q]: " choice

    case $choice in
        1)
            echo ""
            echo "👤 User Nickname Configuration"
            read -p "  Please enter your nickname [current: $MATRIX_USERNAME]: " INPUT_USERNAME
            MATRIX_USERNAME="${INPUT_USERNAME:-$MATRIX_USERNAME}"
            ;;
        2)
            echo ""
            echo "📱 Telegram Configuration"
            read -p "  Enable Telegram? (y/N) [current: $TELEGRAM_ENABLED]: " INPUT_ENABLE
            if [[ "$INPUT_ENABLE" =~ ^[Yy]$ ]]; then
                TELEGRAM_ENABLED="true"
                read -p "  1. Bot Token [current: ${TELEGRAM_BOT_TOKEN:-Not set}]: " INPUT_BOT_TOKEN
                TELEGRAM_BOT_TOKEN="${INPUT_BOT_TOKEN:-$TELEGRAM_BOT_TOKEN}"

                # Auto-detect Chat ID
                DETECTED_CHAT_ID=""
                if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
                    echo "🔄 Attempting to auto-detect your Chat ID..."
                    DETECTED_CHAT_ID=$(get_chat_id_from_api "$TELEGRAM_BOT_TOKEN") || true
                fi
                read -p "  2. Chat ID [current/auto: ${DETECTED_CHAT_ID:-$TELEGRAM_CHAT_ID}]: " INPUT_CHAT_ID
                TELEGRAM_CHAT_ID="${INPUT_CHAT_ID:-${DETECTED_CHAT_ID:-$TELEGRAM_CHAT_ID}}"

                echo "  🌐 ngrok Configuration (Required for Telegram Webhook)"
                read -p "  3. ngrok Authtoken [current: ${NGROK_AUTHTOKEN:-Not set}]: " INPUT_NGROK
                NGROK_AUTHTOKEN="${INPUT_NGROK:-$NGROK_AUTHTOKEN}"
            else
                TELEGRAM_ENABLED="false"
            fi
            ;;
        3)
            echo ""
            echo "💻 Discord Configuration"
            read -p "  Enable Discord? (y/N) [current: $DISCORD_ENABLED]: " INPUT_ENABLE
            if [[ "$INPUT_ENABLE" =~ ^[Yy]$ ]]; then
                DISCORD_ENABLED="true"
                read -p "  1. Bot Token [current: ${DISCORD_TOKEN:-Not set}]: " INPUT_TOKEN
                DISCORD_TOKEN="${INPUT_TOKEN:-$DISCORD_TOKEN}"
                read -p "  2. Server ID [current: ${DISCORD_SERVER_ID:-Not set}]: " INPUT_SERVER
                DISCORD_SERVER_ID="${INPUT_SERVER:-$DISCORD_SERVER_ID}"
                read -p "  3. Channel ID [current: ${DISCORD_CHANNEL_ID:-Not set}]: " INPUT_CHANNEL
                DISCORD_CHANNEL_ID="${INPUT_CHANNEL:-$DISCORD_CHANNEL_ID}"
            else
                DISCORD_ENABLED="false"
            fi
            ;;
        4)
            echo ""
            echo "⚡ Slack Configuration"
            read -p "  Enable Slack? (y/N) [current: $SLACK_ENABLED]: " INPUT_ENABLE
            if [[ "$INPUT_ENABLE" =~ ^[Yy]$ ]]; then
                SLACK_ENABLED="true"
                read -p "  1. App Token (xapp-...) [current: ${SLACK_APP_TOKEN:-Not set}]: " INPUT_APP
                SLACK_APP_TOKEN="${INPUT_APP:-$SLACK_APP_TOKEN}"
                read -p "  2. Bot Token (xoxb-...) [current: ${SLACK_BOT_TOKEN:-Not set}]: " INPUT_BOT
                SLACK_BOT_TOKEN="${INPUT_BOT:-$SLACK_BOT_TOKEN}"
                read -p "  3. Workspace ID [current: ${SLACK_WORKSPACE_ID:-Not set}]: " INPUT_WORKSPACE
                SLACK_WORKSPACE_ID="${INPUT_WORKSPACE:-$SLACK_WORKSPACE_ID}"
                read -p "  4. Channel ID [current: ${SLACK_CHANNEL_ID:-Not set}]: " INPUT_CHANNEL
                SLACK_CHANNEL_ID="${INPUT_CHANNEL:-$SLACK_CHANNEL_ID}"
            else
                SLACK_ENABLED="false"
            fi
            ;;
        5)
            echo ""
            echo "🌍 Network and Port Configuration"
            read -p "  1. Telegram Gateway Port [current: $TELEGRAM_GATEWAY_PORT]: " INPUT_TG_PORT
            TELEGRAM_GATEWAY_PORT="${INPUT_TG_PORT:-$TELEGRAM_GATEWAY_PORT}"
            read -p "  2. Ngrok API Port [current: $NGROK_API_PORT]: " INPUT_NGROK_PORT
            NGROK_API_PORT="${INPUT_NGROK_PORT:-$NGROK_API_PORT}"
            read -p "  3. Octo Router Port [current: $ROUTER_PORT]: " INPUT_ROUTER_PORT
            ROUTER_PORT="${INPUT_ROUTER_PORT:-$ROUTER_PORT}"
            ;;
        6)
            echo ""
            echo "🤖 Starting configuration wizard to configure Agents and advanced parameters..."
            update_config_yaml
            if ! python3 "$SCRIPT_DIR/config_wizard.py" "$CONFIG_YAML"; then
                echo -e "\n⚠️ Agent Configuration Wizard encountered an error (possible missing dependency or corrupted environment)"
                read -p "Press Enter to return to menu..." dummy_key
            fi
            ;;
        7)
            echo ""
            bash "$SCRIPT_DIR/agent_credential_wizard.sh" --local
            ;;
        8)
            while true; do
                clear
                echo "=========================================="
                echo "⬆️  AI CLI Version Management (Manual Upgrade/Rollback)"
                echo "=========================================="
                echo " [1] 🆙 Upgrade Gemini CLI"
                echo " [2] 🆙 Upgrade Claude Code"
                echo " [3] 🆙 Upgrade Codex CLI"
                echo " [4] 🆙 Upgrade agy CLI (Antigravity)"
                echo " [5] 🚀 Upgrade all CLI tools at once"
                echo "----------------------------------------"
                echo " [6] ⏪ Rollback Gemini CLI (Restore from backup)"
                echo " [7] ⏪ Rollback Claude Code (Restore from backup)"
                echo " [8] ⏪ Rollback Codex CLI (Restore from backup)"
                echo " [9] 🛡️ Rollback all CLI tools at once"
                echo "----------------------------------------"
                echo " [R] 🔙 Return to Main Menu"
                echo "=========================================="
                read -p "Please select an operation [1-9, R]: " cli_choice

                do_update() {
                    local pkg="$1"
                    local name="$2"
                    echo "🔄 Backing up current version of $name..."
                    local current_ver=$(npm list -g --depth=0 --no-color "$pkg" | grep "$pkg" | awk -F@ '{print $NF}' | sed -r "s/\x1B\[[0-9;]*[mK]//g" | tr -d '\r\n')
                    if [ -n "$current_ver" ]; then
                        mkdir -p "$SCRIPT_DIR/.cli_versions_bak"
                        echo "$current_ver" > "$SCRIPT_DIR/.cli_versions_bak/${pkg//\//_}_version.bak"
                        echo "✅ Successfully backed up $name version: $current_ver"
                    fi
                    echo "🚀 Performing global upgrade for $name (requires sudo permission)..."
                    sudo npm update -g "$pkg"
                    echo "✅ $name upgrade complete!"
                    read -p "Press Enter to continue..." dummy_key
                }

                do_update_agy() {
                    echo "🔄 Reinstalling agy CLI (Antigravity) to the latest version..."
                    if curl -fsSL https://antigravity.google/cli/install.sh | bash; then
                        echo "   🚚 Copying agy to system-wide path..."
                        sudo cp ~/.local/bin/agy /usr/local/bin/agy
                        echo "✅ agy CLI upgrade complete!"
                    else
                        echo "⚠️ agy CLI upgrade failed"
                    fi
                    read -p "Press Enter to continue..." dummy_key
                }

                do_rollback() {
                    local pkg="$1"
                    local name="$2"
                    local bak_file="$SCRIPT_DIR/.cli_versions_bak/${pkg//\//_}_version.bak"
                    if [ -f "$bak_file" ]; then
                        local old_ver=$(cat "$bak_file")
                        echo "⏪ Preparing to rollback $name to version: $old_ver (requires sudo permission)..."
                        sudo npm install -g "${pkg}@${old_ver}"
                        echo "✅ $name rollback complete!"
                        rm -f "$bak_file"
                    else
                        echo "⚠️ Backup file for $name not found, automatic rollback is not possible!"
                    fi
                    read -p "Press Enter to continue..." dummy_key
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
                    *) echo "⚠️ Invalid selection"; sleep 1 ;;
                esac
            done
            ;;
        [Ss])
            echo ""
            # Check if at least one platform is enabled
            if [ "$TELEGRAM_ENABLED" != "true" ] && [ "$DISCORD_ENABLED" != "true" ] && [ "$SLACK_ENABLED" != "true" ]; then
                echo "❌ Error: At least one communication channel must be enabled!"
                read -p "Press Enter to continue..." dummy
                continue
            fi

            rm -f "${ENV_FILE}.session.bak" "${CONFIG_YAML}.session.bak" 2>/dev/null

            write_env_file
            update_config_yaml

            echo "🎉 Configuration complete! You can now run ./start_octo_services.sh to start the services."
            break
            ;;
        [Cc])
            echo ""
            echo "🧹 Clear Configuration and Credentials"
            echo "  [1] Clear only communication credentials (.env)"
            echo "  [2] Clear only Agent Squad and advanced settings (config.yaml)"
            echo "  [3] Clear all"
            echo "  [R] Return"
            read -p "  Please select clear scope [1-3, R]: " CLEAR_CHOICE
            
            if [[ "$CLEAR_CHOICE" =~ ^[1-3]$ ]]; then
                read -p "⚠️  Warning: This operation will clear the selected configuration. Are you sure? [y/N]: " CONFIRM_CLEAR
                if [[ "$CONFIRM_CLEAR" =~ ^[Yy]$ ]]; then
                    read -p "📂 Do you want to back up before clearing? (Y/n): " BACKUP_BEFORE_CLEAR
                    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

                    if [ "$CLEAR_CHOICE" == "1" ] || [ "$CLEAR_CHOICE" == "3" ]; then
                        if [[ ! "$BACKUP_BEFORE_CLEAR" =~ ^[Nn]$ ]]; then
                            [ -f "$ENV_FILE" ] && cp "$ENV_FILE" "${ENV_FILE}.${TIMESTAMP}.bak" && echo "✅ Backed up: $(basename "$ENV_FILE").${TIMESTAMP}.bak"
                        fi
                        # Reset variables
                        MATRIX_USERNAME="User"
                        TELEGRAM_ENABLED="false"; TELEGRAM_BOT_TOKEN=""; TELEGRAM_CHAT_ID=""; NGROK_AUTHTOKEN=""
                        DISCORD_ENABLED="false"; DISCORD_TOKEN=""; DISCORD_SERVER_ID=""; DISCORD_CHANNEL_ID=""
                        SLACK_ENABLED="false"; SLACK_APP_TOKEN=""; SLACK_BOT_TOKEN=""; SLACK_WORKSPACE_ID=""; SLACK_CHANNEL_ID=""
                        TELEGRAM_GATEWAY_PORT=11440; NGROK_API_PORT=4040; ROUTER_PORT=12210
                        write_env_file
                        echo "✅ All communication credentials (.env) have been cleared."
                    fi

                    if [ "$CLEAR_CHOICE" == "2" ] || [ "$CLEAR_CHOICE" == "3" ]; then
                        if [[ ! "$BACKUP_BEFORE_CLEAR" =~ ^[Nn]$ ]]; then
                            [ -f "$CONFIG_YAML" ] && cp "$CONFIG_YAML" "${CONFIG_YAML}.${TIMESTAMP}.bak" && echo "✅ Backed up: $(basename "$CONFIG_YAML").${TIMESTAMP}.bak"
                        fi
                        rm -f "$CONFIG_YAML"
                        echo "✅ Agent Squad configuration (config.yaml) has been cleared."
                    fi
                fi
            fi
            read -p "Press Enter to continue..." dummy
            ;;
        [Qq])
            echo "⚠️  Abandoning changes and exiting..."
            echo "🧹 Which settings would you like to restore to their state before entering the menu?"
            echo "  [1] Restore only communication credentials (.env)"
            echo "  [2] Restore only Agent Squad settings (config.yaml)"
            echo "  [3] Restore all"
            echo "  [N] Don't restore, exit directly"
            read -p "  Please select restore scope [1-3, N]: " RESTORE_CHOICE

            if [[ "$RESTORE_CHOICE" =~ ^[13]$ ]]; then
                if [ -f "${ENV_FILE}.session.bak" ]; then
                    mv "${ENV_FILE}.session.bak" "$ENV_FILE"
                    echo "✅ Communication credentials (.env) have been restored."
                else
                    rm -f "$ENV_FILE" 2>/dev/null
                fi
            else
                rm -f "${ENV_FILE}.session.bak" 2>/dev/null
            fi

            if [[ "$RESTORE_CHOICE" =~ ^[23]$ ]]; then
                if [ -f "${CONFIG_YAML}.session.bak" ]; then
                    mv "${CONFIG_YAML}.session.bak" "$CONFIG_YAML"
                    echo "✅ Agent Squad configuration (config.yaml) has been restored."
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
