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

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_GENERATOR="$SCRIPT_DIR/generate_config.py"

echo "=========================================="
echo "🐳 OctoMatrix - Docker Instance Setup Wizard"
echo "=========================================="
echo ""

# Instance name validation function
validate_instance_name() {
  local name="$1"
  if [[ ! "$name" =~ ^[a-zA-Z0-9_]+$ ]]; then
    echo "❌ Invalid instance name: '$name'"
    echo "   Allowed characters: letters, numbers, underscores"
    return 1
  fi
  return 0
}

# Loop until a valid name is provided
if [ -z "$INSTANCE_NAME" ]; then
    while true; do
        read -p "Enter instance name (e.g., dev, test, prod): " INSTANCE_NAME
        if validate_instance_name "$INSTANCE_NAME"; then
            break
        fi
    done
fi

ENV_FILE="$SCRIPT_DIR/.env.${INSTANCE_NAME}"

# Load existing environment variables
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# Create recovery snapshots (for Quit operation)
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

# Current working variables
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

# --- Auto-fetch Chat ID function ---
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
# OctoMatrix - $INSTANCE_NAME Environment Variables
# =========================================
MATRIX_USERNAME=$MATRIX_USERNAME
TZ=$TZ

# =========================================
# Telegram Configuration
# =========================================
TELEGRAM_ENABLED=$TELEGRAM_ENABLED
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID

# =========================================
# Discord Configuration
# =========================================
DISCORD_ENABLED=$DISCORD_ENABLED
DISCORD_TOKEN=$DISCORD_TOKEN
DISCORD_SERVER_ID=$DISCORD_SERVER_ID
DISCORD_CHANNEL_ID=$DISCORD_CHANNEL_ID

# =========================================
# Slack Configuration
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
ENVEOF
}

# ============================================================================
# Main Loop
# ============================================================================
# Record initial state when entering menu (for undo/quit)
[ -f "$ENV_FILE" ] && cp "$ENV_FILE" "${ENV_FILE}.session.bak"
CONFIG_YAML="$SCRIPT_DIR/container_home/$INSTANCE_NAME/config.yaml"
[ -f "$CONFIG_YAML" ] && cp "$CONFIG_YAML" "${CONFIG_YAML}.session.bak"

while true; do
    clear
    echo "=========================================="
    echo "🐳 Docker Instance Setup Wizard: $INSTANCE_NAME"
    echo "=========================================="
    
    # Display current status
    echo "📊 Current Channel Status:"
    [ "$TELEGRAM_ENABLED" = "true" ] && echo "  ✅ Telegram (Enabled)" || echo "  ⭕ Telegram (Disabled)"
    [ "$DISCORD_ENABLED" = "true" ] && echo "  ✅ Discord  (Enabled)" || echo "  ⭕ Discord  (Disabled)"
    [ "$SLACK_ENABLED" = "true" ] && echo "  ✅ Slack    (Enabled)" || echo "  ⭕ Slack    (Disabled)"
    echo "  🌍 Timezone (TZ): $TZ"
    echo "----------------------------------------"
    echo " [U] 👤 Configure Username (Current: $MATRIX_USERNAME)"
    echo " [1] 📱 Configure Telegram & Ngrok Tunnel"
    echo " [2] 💻 Configure Discord"
    echo " [3] ⚡ Configure Slack"
    echo " [4] 🌍 Configure Timezone (TZ)"
    echo " [5] 🤖 Configure AI Agent Army & Advanced Parameters"
    echo " [6] 🔐 AI Agent CLI Credential Settings"
    echo "----------------------------------------"
    echo " [S] 💾 Save & Generate Configuration (Start)"
    echo " [C] 🧹 Clear Settings & Credentials (Clear)"
    echo " [Q] ❌ Quit without saving (Quit)"
    echo "=========================================="
    
    read -p "Select option [1-6, U, S, C, Q]: " choice
    
    case $choice in
        [Uu])
            echo ""
            read -p "Enter your name (Default: User) [Current: $MATRIX_USERNAME]: " TEMP_USER
            if [ -n "$TEMP_USER" ]; then
                MATRIX_USERNAME="$TEMP_USER"
            fi
            ;;
        1)
            echo ""
            echo "📱 Telegram Settings"
            read -p "  Enable Telegram? (y/N) [Current: $TELEGRAM_ENABLED]: " INPUT_ENABLE
            if [[ "$INPUT_ENABLE" =~ ^[Yy]$ ]]; then
                TELEGRAM_ENABLED="true"
                read -p "  1. Bot Token [Current: ${TELEGRAM_BOT_TOKEN:-Not Set}]: " INPUT_BOT_TOKEN
                TELEGRAM_BOT_TOKEN="${INPUT_BOT_TOKEN:-$TELEGRAM_BOT_TOKEN}"
                
                # Auto-fetch Chat ID
                DETECTED_CHAT_ID=""
                if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
                    echo "🔄 Attempting to automatically fetch your Chat ID..."
                    DETECTED_CHAT_ID=$(get_chat_id_from_api "$TELEGRAM_BOT_TOKEN") || true
                fi
                read -p "  2. Chat ID [Current/Auto: ${DETECTED_CHAT_ID:-$TELEGRAM_CHAT_ID}]: " INPUT_CHAT_ID
                TELEGRAM_CHAT_ID="${INPUT_CHAT_ID:-${DETECTED_CHAT_ID:-$TELEGRAM_CHAT_ID}}"
                
                echo "  🌐 ngrok Configuration (Required for Telegram Webhook)"
                read -p "  3. ngrok Authtoken [Current: ${NGROK_AUTHTOKEN:-Not Set}]: " INPUT_NGROK
                NGROK_AUTHTOKEN="${INPUT_NGROK:-$NGROK_AUTHTOKEN}"
            else
                TELEGRAM_ENABLED="false"
            fi
            ;;
        2)
            echo ""
            echo "💻 Discord Settings"
            read -p "  Enable Discord? (y/N) [Current: $DISCORD_ENABLED]: " INPUT_ENABLE
            if [[ "$INPUT_ENABLE" =~ ^[Yy]$ ]]; then
                DISCORD_ENABLED="true"
                read -p "  1. Bot Token [Current: ${DISCORD_TOKEN:-Not Set}]: " INPUT_TOKEN
                DISCORD_TOKEN="${INPUT_TOKEN:-$DISCORD_TOKEN}"
                read -p "  2. Server ID [Current: ${DISCORD_SERVER_ID:-Not Set}]: " INPUT_SERVER
                DISCORD_SERVER_ID="${INPUT_SERVER:-$DISCORD_SERVER_ID}"
                read -p "  3. Channel ID [Current: ${DISCORD_CHANNEL_ID:-Not Set}]: " INPUT_CHANNEL
                DISCORD_CHANNEL_ID="${INPUT_CHANNEL:-$DISCORD_CHANNEL_ID}"
            else
                DISCORD_ENABLED="false"
            fi
            ;;
        3)
            echo ""
            echo "⚡ Slack Settings"
            read -p "  Enable Slack? (y/N) [Current: $SLACK_ENABLED]: " INPUT_ENABLE
            if [[ "$INPUT_ENABLE" =~ ^[Yy]$ ]]; then
                SLACK_ENABLED="true"
                read -p "  1. App Token (xapp-...) [Current: ${SLACK_APP_TOKEN:-Not Set}]: " INPUT_APP
                SLACK_APP_TOKEN="${INPUT_APP:-$SLACK_APP_TOKEN}"
                read -p "  2. Bot Token (xoxb-...) [Current: ${SLACK_BOT_TOKEN:-Not Set}]: " INPUT_BOT
                SLACK_BOT_TOKEN="${INPUT_BOT:-$SLACK_BOT_TOKEN}"
                read -p "  3. Workspace ID [Current: ${SLACK_WORKSPACE_ID:-Not Set}]: " INPUT_WORKSPACE
                SLACK_WORKSPACE_ID="${INPUT_WORKSPACE:-$SLACK_WORKSPACE_ID}"
                read -p "  4. Channel ID [Current: ${SLACK_CHANNEL_ID:-Not Set}]: " INPUT_CHANNEL
                SLACK_CHANNEL_ID="${INPUT_CHANNEL:-$SLACK_CHANNEL_ID}"
            else
                SLACK_ENABLED="false"
            fi
            ;;
        4)
            echo ""
            echo "🌍 Timezone Settings"
            read -p "  Enter Timezone (e.g., Asia/Taipei) [Current: $TZ]: " INPUT_TZ
            TZ="${INPUT_TZ:-$TZ}"
            ;;
        5)
            echo ""
            echo "🤖 Launching Wizard to configure Agents and advanced parameters..."
            write_env_file
            if [ ! -f "$SCRIPT_DIR/config.${INSTANCE_NAME}.yaml" ]; then
                echo "⚙️  Generating base configuration file..."
                python3 "$CONFIG_GENERATOR" "config" "$INSTANCE_NAME" "" "$SCRIPT_DIR" "11440" "4040" "$(whoami)" "12210"
            fi
            python3 "$SCRIPT_DIR/../config_wizard.py" "$SCRIPT_DIR/config.${INSTANCE_NAME}.yaml"
            ;;
        6)
            echo ""
            bash "$SCRIPT_DIR/../agent_credential_wizard.sh" --container "$INSTANCE_NAME"
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
            
            echo ""
            if [ ! -f "$SCRIPT_DIR/config.${INSTANCE_NAME}.yaml" ]; then
                echo "⚙️  Invoking generator for base configuration..."
                python3 "$CONFIG_GENERATOR" "config" "$INSTANCE_NAME" "" "$SCRIPT_DIR" "11440" "4040" "$(whoami)" "12210"
                echo "🤖 Launching Wizard to configure Agents and advanced parameters..."
                python3 "$SCRIPT_DIR/../config_wizard.py" "$SCRIPT_DIR/config.${INSTANCE_NAME}.yaml"
            fi
            python3 "$CONFIG_GENERATOR" "compose" "$INSTANCE_NAME" "" "$SCRIPT_DIR" "11440" "4040" "$(whoami)" "12210"

            if [ ! -f "$SCRIPT_DIR/awake.${INSTANCE_NAME}.yaml" ]; then
                echo "awake:" > "$SCRIPT_DIR/awake.${INSTANCE_NAME}.yaml"
                echo "📄 Generated new awake configuration file: awake.${INSTANCE_NAME}.yaml"
            fi

            # Create container credentials persistence directory
            mkdir -p "$SCRIPT_DIR/container_home/$INSTANCE_NAME"
            chmod 750 "$SCRIPT_DIR/container_home/$INSTANCE_NAME"
            chown $(whoami):$(whoami) "$SCRIPT_DIR/container_home/$INSTANCE_NAME"
            
            TMUX_SESSION=$(python3 -c "import yaml; print(yaml.safe_load(open('$SCRIPT_DIR/config.${INSTANCE_NAME}.yaml'))['tmux']['session_name'])" 2>/dev/null || echo "ai_${INSTANCE_NAME}")
            CURRENT_USER=$(whoami)
            
            echo "✅ Instance setup complete!"
            echo "=========================================="
            echo "🚀 Next steps, you can use the following commands to operate your AI Army:"
            echo "1. Clean build and start containers (background):"
            echo "   docker compose -f docker-compose.${INSTANCE_NAME}.yml -p octo_${INSTANCE_NAME} build --no-cache && docker compose -f docker-compose.${INSTANCE_NAME}.yml -p octo_${INSTANCE_NAME} up -d"
            echo ""
            echo "2. Check container status and logs:"
            echo "   docker compose -f docker-compose.${INSTANCE_NAME}.yml -p octo_${INSTANCE_NAME} ps"
            echo "   docker compose -f docker-compose.${INSTANCE_NAME}.yml -p octo_${INSTANCE_NAME} logs -f"
            echo ""
            echo "3. Attach to tmux session inside the container:"
            echo "   docker exec -it -u $CURRENT_USER octo_${INSTANCE_NAME}-bot tmux attach -t $TMUX_SESSION"
            echo ""
            echo "4. Stop and remove containers:"
            echo "   docker compose -f docker-compose.${INSTANCE_NAME}.yml -p octo_${INSTANCE_NAME} down"
            echo "   docker image rm octo_${INSTANCE_NAME}-bot"
            break
            ;;
        [Cc])
            echo ""
            echo "🧹 Clear Settings & Credentials"
            echo "  [1] Clear communication credentials only (.env)"
            echo "  [2] Clear Agent Army & advanced settings only (config.yaml)"
            echo "  [3] Clear everything"
            echo "  [R] Return"
            read -p "  Select clearing scope [1-3, R]: " CLEAR_CHOICE
            
            if [[ "$CLEAR_CHOICE" =~ ^[1-3]$ ]]; then
                read -p "⚠️  Warning: This will wipe the selected settings. Are you sure? [y/N]: " CONFIRM_CLEAR
                if [[ "$CONFIRM_CLEAR" =~ ^[Yy]$ ]]; then
                    read -p "📂 Backup before clearing? (Y/n): " BACKUP_BEFORE_CLEAR
                    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
                    
                    if [ "$CLEAR_CHOICE" == "1" ] || [ "$CLEAR_CHOICE" == "3" ]; then
                        if [[ ! "$BACKUP_BEFORE_CLEAR" =~ ^[Nn]$ ]]; then
                            [ -f "$ENV_FILE" ] && cp "$ENV_FILE" "${ENV_FILE}.${TIMESTAMP}.bak" && echo "✅ Backup created: $(basename "$ENV_FILE").${TIMESTAMP}.bak"
                        fi
                        # Reset variables
                        TZ="Asia/Taipei"
                        TELEGRAM_ENABLED="false"; TELEGRAM_BOT_TOKEN=""; TELEGRAM_CHAT_ID=""; NGROK_AUTHTOKEN=""
                        DISCORD_ENABLED="false"; DISCORD_TOKEN=""; DISCORD_SERVER_ID=""; DISCORD_CHANNEL_ID=""
                        SLACK_ENABLED="false"; SLACK_APP_TOKEN=""; SLACK_BOT_TOKEN=""; SLACK_WORKSPACE_ID=""; SLACK_CHANNEL_ID=""
                        write_env_file
                        echo "✅ All communication credentials (.env) cleared."
                    fi
                    
                    if [ "$CLEAR_CHOICE" == "2" ] || [ "$CLEAR_CHOICE" == "3" ]; then
                        CONFIG_YAML="$SCRIPT_DIR/container_home/$INSTANCE_NAME/config.yaml"
                        if [[ ! "$BACKUP_BEFORE_CLEAR" =~ ^[Nn]$ ]]; then
                            [ -f "$CONFIG_YAML" ] && cp "$CONFIG_YAML" "${CONFIG_YAML}.${TIMESTAMP}.bak" && echo "✅ Backup created: config.yaml.${TIMESTAMP}.bak"
                        fi
                        rm -f "$CONFIG_YAML"
                        echo "✅ Agent Army settings (config.yaml) cleared."
                    fi
                fi
            fi
            read -p "Press Enter to continue..." dummy
            ;;
        [Qq])
            echo "⚠️  Discarding changes and quitting..."
            echo "🧹 Which settings would you like to restore to their state before entering the menu?"
            echo "  [1] Restore communication credentials only (.env)"
            echo "  [2] Restore Agent Army settings only (config.yaml)"
            echo "  [3] Restore everything"
            echo "  [N] Don't restore, just exit"
            read -p "  Select restoration scope [1-3, N]: " RESTORE_CHOICE
            
            if [[ "$RESTORE_CHOICE" =~ ^[13]$ ]]; then
                if [ -f "${ENV_FILE}.session.bak" ]; then
                    mv "${ENV_FILE}.session.bak" "$ENV_FILE"
                    echo "✅ Communication credentials (.env) restored."
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
                    echo "✅ Agent Army settings (config.yaml) restored."
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
