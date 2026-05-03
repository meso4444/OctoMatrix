#!/bin/bash
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

# Loop until valid input
if [ -z "$INSTANCE_NAME" ]; then
    while true; do
        read -p "Enter instance name (e.g., dev, test, pro): " INSTANCE_NAME
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

# Create restore snapshot (for Q operation)
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

# --- Function to auto-detect Chat ID ---
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
# OctoMatrix - $INSTANCE_NAME Environment variables
# =========================================
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
# Main console loop
# ============================================================================
# Record initial state when entering menu (for restore on abandon)
[ -f "$ENV_FILE" ] && cp "$ENV_FILE" "${ENV_FILE}.session.bak"
CONFIG_YAML="$SCRIPT_DIR/container_home/$INSTANCE_NAME/config.yaml"
[ -f "$CONFIG_YAML" ] && cp "$CONFIG_YAML" "${CONFIG_YAML}.session.bak"

while true; do
    clear
    echo "=========================================="
    echo "🐳 Docker Instance Setup Wizard: $INSTANCE_NAME"
    echo "=========================================="

    # Display current status
    echo "📊 Current channel status:"
    [ "$TELEGRAM_ENABLED" = "true" ] && echo "  ✅ Telegram (enabled)" || echo "  ⭕ Telegram (disabled)"
    [ "$DISCORD_ENABLED" = "true" ] && echo "  ✅ Discord  (enabled)" || echo "  ⭕ Discord  (disabled)"
    [ "$SLACK_ENABLED" = "true" ] && echo "  ✅ Slack    (enabled)" || echo "  ⭕ Slack    (disabled)"
    echo "  🌍 Timezone (TZ): $TZ"
    echo "----------------------------------------"
    echo " [1] 📱 Configure Telegram and Ngrok Tunnel"
    echo " [2] 💻 Configure Discord"
    echo " [3] ⚡ Configure Slack"
    echo " [4] 🌍 Configure Timezone (TZ)"
    echo " [5] 🤖 Configure AI Agent Squad and Advanced Parameters"
    echo " [6] 🔐 AI Agent CLI Authentication Configuration"
    echo "----------------------------------------"
    echo " [S] 💾 Save and Generate Configuration (Start)"
    echo " [C] 🧹 Clear Configuration and Credentials (Clear)"
    echo " [Q] ❌ Discard Changes and Exit (Quit)"
    echo "=========================================="

    read -p "Select operation [1-6, S, C, Q]: " choice
    
    case $choice in
        1)
            echo ""
            echo "📱 Telegram Configuration"
            read -p "  Enable Telegram? (y/N) [current: $TELEGRAM_ENABLED]: " INPUT_ENABLE
            if [[ "$INPUT_ENABLE" =~ ^[Yy]$ ]]; then
                TELEGRAM_ENABLED="true"
                read -p "  1. Bot Token [current: ${TELEGRAM_BOT_TOKEN:-not configured}]: " INPUT_BOT_TOKEN
                TELEGRAM_BOT_TOKEN="${INPUT_BOT_TOKEN:-$TELEGRAM_BOT_TOKEN}"

                # Auto-detect Chat ID
                DETECTED_CHAT_ID=""
                if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
                    echo "🔄 Attempting to auto-detect your Chat ID..."
                    DETECTED_CHAT_ID=$(get_chat_id_from_api "$TELEGRAM_BOT_TOKEN") || true
                fi
                read -p "  2. Chat ID [current/auto-detected: ${DETECTED_CHAT_ID:-$TELEGRAM_CHAT_ID}]: " INPUT_CHAT_ID
                TELEGRAM_CHAT_ID="${INPUT_CHAT_ID:-${DETECTED_CHAT_ID:-$TELEGRAM_CHAT_ID}}"

                echo "  🌐 ngrok Configuration (Required for Telegram Webhook)"
                read -p "  3. ngrok Authtoken [current: ${NGROK_AUTHTOKEN:-not configured}]: " INPUT_NGROK
                NGROK_AUTHTOKEN="${INPUT_NGROK:-$NGROK_AUTHTOKEN}"
            else
                TELEGRAM_ENABLED="false"
            fi
            ;;
        2)
            echo ""
            echo "💻 Discord Configuration"
            read -p "  Enable Discord? (y/N) [current: $DISCORD_ENABLED]: " INPUT_ENABLE
            if [[ "$INPUT_ENABLE" =~ ^[Yy]$ ]]; then
                DISCORD_ENABLED="true"
                read -p "  1. Bot Token [current: ${DISCORD_TOKEN:-not configured}]: " INPUT_TOKEN
                DISCORD_TOKEN="${INPUT_TOKEN:-$DISCORD_TOKEN}"
                read -p "  2. Server ID [current: ${DISCORD_SERVER_ID:-not configured}]: " INPUT_SERVER
                DISCORD_SERVER_ID="${INPUT_SERVER:-$DISCORD_SERVER_ID}"
                read -p "  3. Channel ID [current: ${DISCORD_CHANNEL_ID:-not configured}]: " INPUT_CHANNEL
                DISCORD_CHANNEL_ID="${INPUT_CHANNEL:-$DISCORD_CHANNEL_ID}"
            else
                DISCORD_ENABLED="false"
            fi
            ;;
        3)
            echo ""
            echo "⚡ Slack Configuration"
            read -p "  Enable Slack? (y/N) [current: $SLACK_ENABLED]: " INPUT_ENABLE
            if [[ "$INPUT_ENABLE" =~ ^[Yy]$ ]]; then
                SLACK_ENABLED="true"
                read -p "  1. App Token (xapp-...) [current: ${SLACK_APP_TOKEN:-not configured}]: " INPUT_APP
                SLACK_APP_TOKEN="${INPUT_APP:-$SLACK_APP_TOKEN}"
                read -p "  2. Bot Token (xoxb-...) [current: ${SLACK_BOT_TOKEN:-not configured}]: " INPUT_BOT
                SLACK_BOT_TOKEN="${INPUT_BOT:-$SLACK_BOT_TOKEN}"
                read -p "  3. Workspace ID [current: ${SLACK_WORKSPACE_ID:-not configured}]: " INPUT_WORKSPACE
                SLACK_WORKSPACE_ID="${INPUT_WORKSPACE:-$SLACK_WORKSPACE_ID}"
                read -p "  4. Channel ID [current: ${SLACK_CHANNEL_ID:-not configured}]: " INPUT_CHANNEL
                SLACK_CHANNEL_ID="${INPUT_CHANNEL:-$SLACK_CHANNEL_ID}"
            else
                SLACK_ENABLED="false"
            fi
            ;;
        4)
            echo ""
            echo "🌍 Timezone Configuration"
            read -p "  Enter timezone (e.g., Asia/Taipei) [current: $TZ]: " INPUT_TZ
            TZ="${INPUT_TZ:-$TZ}"
            ;;
        5)
            echo ""
            echo "🤖 Starting configuration wizard to configure Agent and advanced parameters..."
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
                echo "⚙️  Generating base configuration..."
                python3 "$CONFIG_GENERATOR" "config" "$INSTANCE_NAME" "" "$SCRIPT_DIR" "11440" "4040" "$(whoami)" "12210"
                echo "🤖 Starting configuration wizard to configure Agent and advanced parameters..."
                python3 "$SCRIPT_DIR/../config_wizard.py" "$SCRIPT_DIR/config.${INSTANCE_NAME}.yaml"
            fi
            python3 "$CONFIG_GENERATOR" "compose" "$INSTANCE_NAME" "" "$SCRIPT_DIR" "11440" "4040" "$(whoami)" "12210"

            if [ ! -f "$SCRIPT_DIR/awake.${INSTANCE_NAME}.yaml" ]; then
                echo "awake:" > "$SCRIPT_DIR/awake.${INSTANCE_NAME}.yaml"
                echo "📄 Generated new wake-up configuration: awake.${INSTANCE_NAME}.yaml"
            fi

            # Create container credential persistence directory            mkdir -p "$SCRIPT_DIR/container_home/$INSTANCE_NAME"
            chmod 750 "$SCRIPT_DIR/container_home/$INSTANCE_NAME"
            chown $(whoami):$(whoami) "$SCRIPT_DIR/container_home/$INSTANCE_NAME"
            
            TMUX_SESSION=$(python3 -c "import yaml; print(yaml.safe_load(open('$SCRIPT_DIR/config.${INSTANCE_NAME}.yaml'))['tmux']['session_name'])" 2>/dev/null || echo "ai_${INSTANCE_NAME}")
            CURRENT_USER=$(whoami)

            echo "✅ Instance setup completed!"
            echo "=========================================="
            echo "🚀 Next, you can execute the following commands to operate your AI squad:"
            echo "1. Build and start containers (in background):"
            echo "   docker compose -f docker-compose.${INSTANCE_NAME}.yml -p octo_${INSTANCE_NAME} up -d --build"
            echo ""
            echo "2. View container running status:"
            echo "   docker compose -f docker-compose.${INSTANCE_NAME}.yml -p octo_${INSTANCE_NAME} ps"
            echo "   docker compose -f docker-compose.${INSTANCE_NAME}.yml -p octo_${INSTANCE_NAME} logs -f"
            echo ""
            echo "3. Enter container and view tmux windows:"
            echo "   docker exec -it -u $CURRENT_USER chat-agent-${INSTANCE_NAME} tmux attach -t $TMUX_SESSION"
            echo ""
            echo "4. Stop and remove containers:"
            echo "   docker compose -f docker-compose.${INSTANCE_NAME}.yml -p octo_${INSTANCE_NAME} down"
            echo "=========================================="
            break
            ;;
        [Cc])
            echo ""
            echo "🧹 Clear Configuration and Credentials"
            echo "  [1] Only clear communication credentials (.env)"
            echo "  [2] Only clear Agent Squad and advanced configuration (config.yaml)"
            echo "  [3] Clear all"
            echo "  [R] Return"
            read -p "  Select clear scope [1-3, R]: " CLEAR_CHOICE

            if [[ "$CLEAR_CHOICE" =~ ^[1-3]$ ]]; then
                read -p "⚠️  Warning: This will delete the selected configuration. Are you sure? [y/N]: " CONFIRM_CLEAR
                if [[ "$CONFIRM_CLEAR" =~ ^[Yy]$ ]]; then
                    read -p "📂 Backup before clearing? (Y/n): " BACKUP_BEFORE_CLEAR
                    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

                    if [ "$CLEAR_CHOICE" == "1" ] || [ "$CLEAR_CHOICE" == "3" ]; then
                        if [[ ! "$BACKUP_BEFORE_CLEAR" =~ ^[Nn]$ ]]; then
                            [ -f "$ENV_FILE" ] && cp "$ENV_FILE" "${ENV_FILE}.${TIMESTAMP}.bak" && echo "✅ Backed up: $(basename "$ENV_FILE").${TIMESTAMP}.bak"
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
                            [ -f "$CONFIG_YAML" ] && cp "$CONFIG_YAML" "${CONFIG_YAML}.${TIMESTAMP}.bak" && echo "✅ Backed up: config.yaml.${TIMESTAMP}.bak"
                        fi
                        rm -f "$CONFIG_YAML"
                        echo "✅ Agent Squad configuration (config.yaml) cleared."
                    fi
                fi
            fi
            read -p "Press Enter to continue..." dummy
            ;;
        [Qq])
            echo "⚠️  Discarding changes and exiting..."
            echo "🧹 Which settings would you like to restore to the state before entering the menu?"
            echo "  [1] Only restore communication credentials (.env)"
            echo "  [2] Only restore Agent Squad configuration (config.yaml)"
            echo "  [3] Restore all"
            echo "  [N] Do not restore, exit directly"
            read -p "  Select restore scope [1-3, N]: " RESTORE_CHOICE

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
                    echo "✅ Agent Squad configuration (config.yaml) restored."
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
