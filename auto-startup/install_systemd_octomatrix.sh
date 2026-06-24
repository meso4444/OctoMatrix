#!/bin/bash

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

# setup_systemd.sh
# Automatically registers OctoMatrix as a Systemd service for autostart

# 1. Prepare paths and variables
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
START_SCRIPT="$SCRIPT_DIR/start_octo_services.sh"
STOP_SCRIPT="$SCRIPT_DIR/stop_octo_services.sh"
SERVICE_NAME="octomatrix-services"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

# Detect real user
REAL_USER=${SUDO_USER:-$(whoami)}
USER_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run this script using sudo"
  echo "   Example: sudo ./auto-startup/install_systemd_octomatrix.sh"
  exit 1
fi

echo "🔧 Configuring Systemd service..."
echo "   - Service Name: $SERVICE_NAME"
echo "   - User: $REAL_USER"
echo "   - Start Script: $START_SCRIPT"

# 2. Create Service file
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=OctoMatrix - AI Remote Commander
After=network.target

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$START_SCRIPT
ExecStop=$STOP_SCRIPT
Restart=always
RestartSec=10
RemainAfterExit=yes
Environment="HOME=$USER_HOME"
Environment="PATH=$PATH"
Environment="TERM=xterm-256color"

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Service file created: $SERVICE_FILE"

# 3. Enable service
echo "🔄 Enabling service..."
systemctl daemon-reload
systemctl enable $SERVICE_NAME

# 4. Check WSL Systemd support
if grep -qi "Microsoft" /proc/version; then
    echo "🔍 Detected WSL, checking systemd config..."
    WSL_CONF="/etc/wsl.conf"
    
    if [ ! -f "$WSL_CONF" ]; then
        echo "   Creating new $WSL_CONF..."
        touch "$WSL_CONF"
    fi

    if ! grep -q "systemd=true" "$WSL_CONF"; then
        echo "🔧 Enabling WSL Systemd support..."
        if ! grep -q "\[boot\]" "$WSL_CONF"; then
            echo -e "\n[boot]" | tee -a "$WSL_CONF" > /dev/null
        fi
        echo "systemd=true" | tee -a "$WSL_CONF" > /dev/null
        echo "✅ Updated $WSL_CONF"
        echo "⚠️  Important: You must completely restart WSL for this to take effect!"
        echo "   Run in Windows PowerShell: wsl --shutdown"
        echo "   Then re-enter Ubuntu."
    else
        echo "✅ WSL Systemd config already exists ($WSL_CONF)"
    fi
fi

echo "✅ Autostart enabled!"
echo ""
echo "👉 You can manage the service with:"
echo "   sudo systemctl start $SERVICE_NAME"
echo "   sudo systemctl stop $SERVICE_NAME"
echo "   sudo systemctl status $SERVICE_NAME"
echo ""
echo "📝 Next step (Windows users):"
echo "   Run ./auto-startup/setup_windows_scheduler.sh to configure wake-up task."