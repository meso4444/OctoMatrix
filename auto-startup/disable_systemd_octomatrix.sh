#!/bin/bash
# disable_systemd_octomatrix.sh
# Removes Systemd autostart for OctoMatrix

SERVICE_NAME="octomatrix-services"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run this script using sudo"
  echo "   Example: sudo ./auto-startup/disable_systemd_octomatrix.sh"
  exit 1
fi

echo "🛑 Removing Systemd service: $SERVICE_NAME"

if systemctl is-active --quiet $SERVICE_NAME; then
    echo "   Stopping service..."
    systemctl stop $SERVICE_NAME
fi

if systemctl is-enabled --quiet $SERVICE_NAME 2>/dev/null; then
    echo "   Disabling autostart..."
    systemctl disable $SERVICE_NAME
fi

if [ -f "$SERVICE_FILE" ]; then
    echo "   Removing config: $SERVICE_FILE"
    rm "$SERVICE_FILE"
    systemctl daemon-reload
    echo "✅ Service fully removed"
else
    echo "⚠️  Config not found, might already be removed"
fi

echo ""
echo "💡 To re-enable, run install_systemd_octomatrix.sh"