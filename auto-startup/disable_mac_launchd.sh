#!/bin/bash
# disable_mac_launchd.sh - Remove Mac auto-startup for OctoMatrix

echo "=========================================="
echo "🍏 OctoMatrix - Remove Mac Auto-startup (Launchd)"
echo "=========================================="

PLIST_NAME="com.octomatrix.agent.plist"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME"

if [ -f "$PLIST_PATH" ]; then
    echo "🔄 Unloading service from Launchd..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    
    echo "🗑️  Removing configuration file: $PLIST_PATH"
    rm -f "$PLIST_PATH"
    echo "✅ Successfully removed! OctoMatrix auto-startup is disabled."
else
    echo "⚠️  Configuration file not found: $PLIST_PATH"
    echo "   (It may have been removed already, or was never installed)"
fi
echo "=========================================="
