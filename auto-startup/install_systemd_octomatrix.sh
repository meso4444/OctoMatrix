#!/bin/bash
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