#!/bin/bash
# setup_mac_launchd.sh - Configure Mac Auto-Startup for OctoMatrix

echo "=========================================="
echo "🍏 OctoMatrix - Mac Auto-Startup Setup (Launchd)"
echo "=========================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OCTO_DIR="$(dirname "$SCRIPT_DIR")"
START_SCRIPT="$OCTO_DIR/start_octo_services.sh"

if [ ! -f "$START_SCRIPT" ]; then
    echo "❌ Error: Startup script not found at $START_SCRIPT"
    exit 1
fi

PLIST_NAME="com.octomatrix.agent.plist"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "📂 Project Root: $OCTO_DIR"
echo "📝 Generating config file: $PLIST_PATH"

mkdir -p "$HOME/Library/LaunchAgents"

cat <<EOF > "$PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.octomatrix.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$START_SCRIPT</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$OCTO_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$OCTO_DIR/mac_autostart.log</string>
    <key>StandardErrorPath</key>
    <string>$OCTO_DIR/mac_autostart_error.log</string>
</dict>
</plist>
EOF

echo "✅ Configuration file generated successfully."

echo "🔄 Registering to system Launchd..."
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "🎉 Setup complete! OctoMatrix will now start automatically when you log into your Mac."
echo "👉 To disable auto-startup, run: launchctl unload $PLIST_PATH"
echo "=========================================="