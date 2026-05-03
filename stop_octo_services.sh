#!/bin/bash
# stop_octo_services.sh (OctoMatrix version)

SCRIPT_DIR="$(dirname "$0")"
TMUX_SESSION_NAME=$(python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import TMUX_SESSION_NAME; print(TMUX_SESSION_NAME)")

echo "==========================================="
echo "🛑 Stopping OctoMatrix system"
echo "==========================================="

# 1. Kill the dedicated tmux session
# Note: This will close all windows and services beneath it (Python Gateways, Router, Ngrok, etc.)
# Ensures absolute isolation when running multiple instances (Dev/Prod), won't accidentally kill other instances' services
if tmux has-session -t "$TMUX_SESSION_NAME" 2>/dev/null; then
    tmux kill-session -t "$TMUX_SESSION_NAME"
    echo "✅ tmux session '$TMUX_SESSION_NAME' and all attached services terminated"
else
    echo "⚠️  tmux session '$TMUX_SESSION_NAME' does not exist or is already closed"
fi

echo "==========================================="
echo "🎉 OctoMatrix instance ($TMUX_SESSION_NAME) completely stopped"
echo "==========================================="