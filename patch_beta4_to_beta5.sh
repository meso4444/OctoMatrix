#!/bin/bash
# OctoMatrix Beta.4 to Beta.5 Environment Patch Script
# 解決 V4 隔離架構下的 Python 全域套件衝突、pip3 路徑問題，與缺失 pip 模組的防呆安裝。

set -e

echo "🐙 [OctoMatrix] 正在執行 Beta.4 -> Beta.5 升級環境修復 (V10 完美無瑕版)..."

# 1. 環境與指令偵測 (嚴格 POSIX 相容)
os_type=$(uname -s)
if [ "$os_type" = "Darwin" ]; then
    ENVIRONMENT="macOS"
    pip_cmd="python3 -m pip"
else
    ENVIRONMENT="Linux"
    # 動態偵測是否處於 Conda 或虛擬環境中
    if [ -n "$CONDA_PREFIX" ] || [ -n "$VIRTUAL_ENV" ]; then
        pip_cmd="python3 -m pip"
        echo "✅ 偵測到虛擬環境 (Conda/Venv)，將使用本地環境安裝..."
    else
        pip_cmd="sudo python3 -m pip"
    fi
fi

echo "✅ 偵測到的系統：$ENVIRONMENT"

# 1.5 檢查當前目標環境是否具備 pip
if ! $pip_cmd --version > /dev/null 2>&1; then
    echo "🔧 偵測到缺少 pip 模組，正在嘗試自動安裝 python3-pip..."
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

# 1.8 檢查並補齊缺失的系統基礎依賴 (jq, tmux, zstd 等)
echo "📦 正在檢查系統基礎依賴 (curl, wget, jq, tmux, zstd)..."
if [[ "$ENVIRONMENT" == "macOS" ]]; then
    TOOLS="curl wget jq tmux zstd"
    for tool in $TOOLS; do
        if ! command -v $tool &> /dev/null; then
            echo "   安裝 $tool..."
            brew install $tool
        fi
    done
else
    if command -v apt-get > /dev/null 2>&1; then
        sudo apt-get update > /dev/null 2>&1 || true
        sudo apt-get install -y curl wget jq tmux zstd
    elif command -v yum > /dev/null 2>&1; then
        sudo yum install -y curl wget jq tmux zstd
    fi
fi

PACKAGES="flask requests pyyaml apscheduler pillow discord.py slack-sdk websockets aiohttp"

# 2. 強制移除舊版套件，徹底淨化環境
echo "🗑 正在強制清理舊版 Python 依賴..."
python3 -m pip uninstall -y $PACKAGES > /dev/null 2>&1 || true

# 3. 強制全新安裝 Python 套件 (無畏衝突，確保 OctoMatrix 擁有最乾淨的依賴)
echo "📦 正在以最高優先級安裝 Python 核心套件..."
if $pip_cmd install --upgrade --force-reinstall $PACKAGES --break-system-packages > /dev/null 2>&1 || $pip_cmd install --upgrade --force-reinstall $PACKAGES; then
    echo "✅ Python 套件安裝成功"
else
    echo "❌ Python 套件安裝失敗！"
    echo "💡 提示: 請嘗試手動執行: $pip_cmd install --upgrade --force-reinstall $PACKAGES --break-system-packages"
fi

# 4. 補齊所有系統的 Node.js 安裝 (不僅限 CentOS)
if ! command -v node > /dev/null 2>&1 || ! command -v npm > /dev/null 2>&1; then
    echo "🤖 正在為系統補裝 Node.js..."
    if [[ "$ENVIRONMENT" == "macOS" ]]; then
        brew install node
    elif command -v apt-get > /dev/null 2>&1; then
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt-get install -y nodejs
    elif command -v yum > /dev/null 2>&1; then
        curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo -E bash -
        sudo yum install -y nodejs
    else
        echo "⚠️ 無法自動安裝 Node.js，後續 CLI 安裝可能失敗，請手動安裝"
    fi
fi

# 5. 強制重裝 AI CLI 工具
echo "🤖 正在重新安裝最新版 AI CLI 工具..."
npm_prefix=""
if [ "$ENVIRONMENT" != "macOS" ]; then
    if [ -n "$CONDA_PREFIX" ] || [ -n "$VIRTUAL_ENV" ] || [[ "$(which npm 2>/dev/null)" == *".nvm"* ]]; then
        npm_prefix=""
    else
        npm_prefix="sudo"
    fi
fi

if command -v npm > /dev/null 2>&1; then
    $npm_prefix npm install -g @anthropic-ai/claude-code @google/gemini-cli @openai/codex || echo "⚠️ AI CLI 安裝失敗，請手動檢查 Node.js 環境或權限。"
    echo "✅ AI CLI 工具重裝完成！"
else
    echo "❌ 偵測不到 npm，跳過 AI CLI 重裝，請手動安裝 Node.js！"
fi

echo "✅ Beta.4 -> Beta.5 環境升級修復完成！請接續執行 ./start_octo_services.sh"