#!/bin/bash
# ============================================================================
# OctoMatrix - [Entrypoint] Lightweight Delegation Version (using gosu for proper privilege drop)
# ============================================================================
set -e

echo "🧬 [Entrypoint] Container awakening..."

# 1. Environment variable preparation
export SCRIPT_DIR="/app/octomatrix"
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# If APP_USER variable not set, default fallback to appuser just in case
export APP_USER=${APP_USER:-appuser}
export APP_UID=$(id -u $APP_USER 2>/dev/null || echo 1000)
export APP_GID=$(id -g $APP_USER 2>/dev/null || echo 1000)

# 2. Fix mounted volume permissions as root (one-time initialization)
if [ "$(id -u)" = "0" ]; then
    echo "🔐 [Root] Fixing mounted volume ownership and permissions..."

    # Fix agent_home directory
    if [ -d "$SCRIPT_DIR/agent_home" ]; then
        chown -R $APP_UID:$APP_GID "$SCRIPT_DIR/agent_home" 2>/dev/null || true
    fi

    # Ensure dynamic user's home directory and tmux directory exist and are writable
    if [ ! -d "/home/$APP_USER/.tmux" ]; then
        mkdir -p "/home/$APP_USER/.tmux"
        chown -R $APP_UID:$APP_GID "/home/$APP_USER/.tmux"
        chmod 700 "/home/$APP_USER/.tmux"
    fi

    echo "✅ Permission fixing complete"
fi

# 3. Use gosu to switch to dynamic user and execute startup script
# This ensures the container runs as non-root throughout
cd "$SCRIPT_DIR"

if [ -f "./start_octo_services.sh" ]; then
    echo "🚀 Using gosu to switch to $APP_USER user and execute startup script..."
    # Ensure HOME variable points to home directory in container (with mounted credentials)
    export HOME="/home/$APP_USER"
    gosu $APP_USER bash ./start_octo_services.sh
else
    echo "❌ Fatal error: /app/octomatrix/start_octo_services.sh not found"
    exit 1
fi

echo "🏁 [Entrypoint] Startup sequence complete. Container entering daemon mode."
# Keep container running
tail -f /dev/null
