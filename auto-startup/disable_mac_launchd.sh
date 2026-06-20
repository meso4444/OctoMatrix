#!/bin/bash
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
