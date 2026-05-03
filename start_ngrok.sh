#!/bin/bash
# start_ngrok.sh (Precise Process Management Version)
# Start ngrok and automatically configure Telegram Webhook (using dynamic secret + precise PID management)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.py"
ENV_FILE="$SCRIPT_DIR/.env"
SECRET_FILE="$SCRIPT_DIR/webhook_secret.token"
RUNTIME_STATE_FILE="$SCRIPT_DIR/.runtime_state"
NGROK_LOG="$SCRIPT_DIR/ngrok.log"
NGROK_PID_FILE="$SCRIPT_DIR/.ngrok.pid"

# Support for separate Ngrok Config path
#NGROK_CONFIG_PATH="${NGROK_CONFIG_PATH:-}"
#if [[ -z "$NGROK_CONFIG_PATH" ]]; then
#    # Check if ngrok_dev.yml exists (for Dev environment)
#    if [ -f "$SCRIPT_DIR/ngrok_dev.yml" ]; then
#        NGROK_CONFIG_PATH="$SCRIPT_DIR/ngrok_dev.yml"
#    else
#        # Default configuration (if exists)
#        NGROK_CONFIG_PATH=""
#    fi
#fi

cd "$SCRIPT_DIR"

# Load environment variables
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ Error: Environment variable TELEGRAM_BOT_TOKEN not set"
    exit 1
fi

BOT_TOKEN="$TELEGRAM_BOT_TOKEN"

# Read dynamic Secret
if [ ! -f "$SECRET_FILE" ]; then
    echo "❌ Error: Webhook Secret not found, please run start_octo_services.sh first"
    exit 1
fi
WEBHOOK_SECRET=$(cat "$SECRET_FILE")

# Read Port
TELEGRAM_GATEWAY_PORT=$(python3 -c "import sys; sys.path.append('.'); from config import TELEGRAM_GATEWAY_PORT; print(TELEGRAM_GATEWAY_PORT)")
NGROK_API_PORT=$(python3 -c "import sys; sys.path.append('.'); from config import NGROK_API_PORT; print(NGROK_API_PORT)" 2>/dev/null || echo "4040")
WEBHOOK_PATH="/telegram_webhook"

# ============================================================================
# Verify and set ngrok Authtoken
# ============================================================================
if [ -z "$NGROK_AUTHTOKEN" ]; then
    echo "❌ Error: Environment variable NGROK_AUTHTOKEN not set"
    exit 1
fi

# Ensure ngrok config directory exists (ngrok 3 uses ~/.config/ngrok)
mkdir -p ~/.config/ngrok

# Set ngrok config file (containing authtoken and web_addr)
NGROK_CONFIG_FILE="$HOME/.config/ngrok/ngrok.yml"
cat > "$NGROK_CONFIG_FILE" << EOF
version: "3"
agent:
    authtoken: $NGROK_AUTHTOKEN
    web_addr: 127.0.0.1:$NGROK_API_PORT
EOF

echo "🔐 ngrok configuration set:"
echo "   • Authtoken: ✅"
echo "   • Web API Port: 127.0.0.1:$NGROK_API_PORT"

echo "🚀 Starting ngrok (Port $TELEGRAM_GATEWAY_PORT)..."

# ============================================================================
# Precise cleanup: Use PID file instead of pkill pattern matching
# ============================================================================
if [ -f "$NGROK_PID_FILE" ]; then
    OLD_NGROK_PID=$(cat "$NGROK_PID_FILE")
    if kill -0 "$OLD_NGROK_PID" 2>/dev/null; then
        echo "🔄 Cleaning up old ngrok process (PID: $OLD_NGROK_PID)..."
        kill "$OLD_NGROK_PID" 2>/dev/null || true
        sleep 1
        # If process is still running, force kill
        if kill -0 "$OLD_NGROK_PID" 2>/dev/null; then
            kill -9 "$OLD_NGROK_PID" 2>/dev/null || true
        fi
    fi
    rm -f "$NGROK_PID_FILE"
fi

rm -f "$NGROK_LOG"

# Start ngrok
if [[ -n "$NGROK_CONFIG_PATH" && -f "$NGROK_CONFIG_PATH" ]]; then
    echo "📋 Using config file: $NGROK_CONFIG_PATH"
    nohup ngrok start --config "$NGROK_CONFIG_PATH" --all > "$NGROK_LOG" 2>&1 &
else
    echo "📋 Using default configuration (Telegram Gateway Port $TELEGRAM_GATEWAY_PORT)"
    # ngrok 3+ does not support --api parameter, use default ngrok http command
    # ngrok 3 API server defaults to listening on unix socket or other methods
    nohup ngrok http $TELEGRAM_GATEWAY_PORT > "$NGROK_LOG" 2>&1 &
fi

NGROK_PID=$!
echo "📝 ngrok PID: $NGROK_PID"
echo "$NGROK_PID" > "$NGROK_PID_FILE"

echo "⏳ Waiting for ngrok to establish connection and get URL..."

# Polling to get public URL
# ngrok 3 has web_addr configured, should listen on specified NGROK_API_PORT
PUBLIC_URL=""

for i in {1..10}; do
    echo "   ▸ Attempting to get URL ($i/10)..."

    if command -v jq &> /dev/null; then
        PUBLIC_URL=$(curl -s http://localhost:$NGROK_API_PORT/api/tunnels 2>/dev/null | jq -r '.tunnels[0].public_url' 2>/dev/null)
    else
        PUBLIC_URL=$(curl -s http://localhost:$NGROK_API_PORT/api/tunnels 2>/dev/null | grep -o '"public_url":"[^"]*"' | cut -d'"' -f4 | head -1)
    fi

    # Check if URL was successfully obtained
    if [[ -n "$PUBLIC_URL" && "$PUBLIC_URL" != "null" && "$PUBLIC_URL" == http* ]]; then
        echo "✅ Successfully obtained new URL: $PUBLIC_URL"
        break
    fi

    sleep 3
done

if [[ -z "$PUBLIC_URL" || "$PUBLIC_URL" == "null" ]]; then
    echo "❌ Failed to get ngrok URL (timeout 30 seconds)"
    echo "📋 Recent ngrok logs:"
    tail -n 5 "$NGROK_LOG"
    exit 1
fi

# Write runtime state file (for other programs to read)
echo "{\"ngrok_url\": \"$PUBLIC_URL\", \"ngrok_pid\": $NGROK_PID}" > "$RUNTIME_STATE_FILE"
echo "📝 Updated runtime state: $RUNTIME_STATE_FILE"

# Notify Telegram to update Webhook (with Secret Token)
WEBHOOK_URL="${PUBLIC_URL}${WEBHOOK_PATH}"
echo "🔄 Updating Telegram Webhook to: $WEBHOOK_URL"

RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/setWebhook" \
     -d "url=$WEBHOOK_URL" \
     -d "secret_token=$WEBHOOK_SECRET")

if echo "$RESPONSE" | grep -q '"ok":true'; then
    echo "✅ Webhook configuration successful (Secret Token verification enabled)"
else
    echo "❌ Webhook configuration failed"
    echo "   Response: $RESPONSE"
fi

echo ""
echo "🎉 ngrok startup and configuration complete!"
