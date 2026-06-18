#!/bin/bash
# disable_mac_launchd.sh - 移除 Mac 開機自動啟動 OctoMatrix

echo "=========================================="
echo "🍏 OctoMatrix - 移除 Mac 開機自啟動 (Launchd)"
echo "=========================================="

PLIST_NAME="com.octomatrix.agent.plist"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME"

if [ -f "$PLIST_PATH" ]; then
    echo "🔄 正在從系統 Launchd 卸載服務..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    
    echo "🗑️  正在移除設定檔: $PLIST_PATH"
    rm -f "$PLIST_PATH"
    echo "✅ 移除成功！OctoMatrix 已取消開機自啟動。"
else
    echo "⚠️  找不到設定檔: $PLIST_PATH"
    echo "   (可能已經被移除，或者從未安裝過)"
fi
echo "=========================================="
