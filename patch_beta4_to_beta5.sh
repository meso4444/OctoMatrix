#!/bin/bash
# OctoMatrix Beta.4 to Beta.5 Environment Patch Script
# 解決 V4 隔離架構下的 Python 全域套件衝突、pip3 路徑問題，與缺失 pip 模組的防呆安裝。

set -e

echo "🐙 [OctoMatrix] 正在執行 Beta.4 -> Beta.5 升級環境修復 (V4)..."
echo "⚠️ [警告] 此腳本目前處於【測試中】狀態，請謹慎使用以避免誤用！"
echo "========================================================="
sleep 2

# 1. 環境與指令偵測 (嚴格 POSIX 相容)
os_type=$(uname -s)
if [ "$os_type" = "Darwin" ]; then
    ENVIRONMENT="macOS"
    pip_cmd="python3 -m pip"
else
    ENVIRONMENT="Linux"
    pip_cmd="sudo python3 -m pip"
fi

echo "✅ 偵測到的環境：$ENVIRONMENT"

# 1.5 檢查「全域」環境是否具備 pip (避開 Conda 誤判)
if ! $pip_cmd --version > /dev/null 2>&1; then
    echo "🔧 偵測到全域系統缺少 pip 模組，正在嘗試自動安裝 python3-pip..."
    if command -v apt-get > /dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y python3-pip
    elif command -v yum > /dev/null 2>&1; then
        sudo yum install -y python3-pip
    elif command -v pacman > /dev/null 2>&1; then
        sudo pacman -Sy --noconfirm python-pip
    else
        echo "❌ 無法自動安裝 pip，請手動執行系統的 pip 安裝指令 (如 sudo apt install python3-pip)"
        exit 1
    fi
fi

# 2. 移除舊版使用者本地 (User-Local) 套件，防止依賴衝突 (Shadowing)
echo "🗑 正在清理舊版本地 Python 依賴..."
PACKAGES="flask requests pyyaml apscheduler pillow discord.py slack-sdk websockets aiohttp"
python3 -m pip uninstall -y $PACKAGES > /dev/null 2>&1 || true

# 3. 全域安裝 Python 套件
echo "📦 正在全域重新安裝 Python 核心套件..."
if $pip_cmd install --upgrade $PACKAGES --break-system-packages > /dev/null 2>&1 || $pip_cmd install --upgrade $PACKAGES; then
    echo "✅ Python 套件全域安裝成功"
else
    echo "❌ Python 套件全域安裝失敗！"
    echo "💡 提示: 請嘗試手動執行: $pip_cmd install --upgrade $PACKAGES --break-system-packages"
fi

# 4. 補齊 CentOS/RHEL 的 Node.js 安裝
if [ "$ENVIRONMENT" != "macOS" ] && command -v yum > /dev/null 2>&1 && ! command -v node > /dev/null 2>&1; then
    echo "🤖 正在為 CentOS/RHEL 補裝 Node.js..."
    curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo -E bash -
    sudo yum install -y nodejs
fi

echo "✅ Beta.4 -> Beta.5 環境升級修復完成！請接續執行 ./start_octo_services.sh"