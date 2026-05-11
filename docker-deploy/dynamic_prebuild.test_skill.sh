#!/bin/bash
set -e

echo "📦 處理技能包: /app/octomatrix/skills/travel-itinerary-toolkit.tar.gz"
if [ -f "/app/octomatrix/skills/travel-itinerary-toolkit.tar.gz" ]; then
    tmp_dir="/tmp/skill_build_travel-itinerary-toolkit"
    rm -rf "$tmp_dir" && mkdir -p "$tmp_dir"
    tar -xzf "/app/octomatrix/skills/travel-itinerary-toolkit.tar.gz" -C "$tmp_dir"

    setup_script=$(find "$tmp_dir" -name "setup.sh" | head -n 1)
    if [ -n "$setup_script" ]; then
        echo "🚀 執行安裝腳本: $setup_script"
        chmod +x "$setup_script"
        (cd "$(dirname "$setup_script")" && bash setup.sh)
    fi
    echo "📦 重新打包技能包 (包含依賴)..."
    (cd "$tmp_dir" && tar -czf "/app/octomatrix/skills/travel-itinerary-toolkit.tar.gz" *)
    rm -rf "$tmp_dir"
fi
