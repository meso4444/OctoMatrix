#!/bin/bash
# setup_mac_launchd.sh - 設定 Mac 開機自動啟動 OctoMatrix

echo "=========================================="
echo "🍏 OctoMatrix - Mac 開機自啟動設定 (Launchd)"
echo "=========================================="

# 取得 OctoMatrix 根目錄的絕對路徑
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OCTO_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
START_SCRIPT="$OCTO_DIR/start_octo_services.sh"

if [ ! -f "$START_SCRIPT" ]; then
    echo "❌ 錯誤：找不到啟動腳本 $START_SCRIPT"
    exit 1
fi

PLIST_NAME="com.octomatrix.agent.plist"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "📂 專案根目錄: $OCTO_DIR"
echo "📝 準備生成設定檔: $PLIST_PATH"

# 確保 LaunchAgents 目錄存在
mkdir -p "$HOME/Library/LaunchAgents"

# 生成 .plist 檔案
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

echo "✅ 設定檔生成成功。"

# 重新載入 plist
echo "🔄 正在註冊到系統 Launchd..."
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "🎉 設定完成！OctoMatrix 將會在您登入 Mac 時自動在背景啟動。"
echo "👉 若要取消開機自啟動，請執行: launchctl unload $PLIST_PATH"
echo "=========================================="