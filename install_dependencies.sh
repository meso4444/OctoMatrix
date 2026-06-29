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

# 安裝 Telegram → AI 遠端控制系統 (ngrok 版) 所需的依賴
# 自動偵測環境 (WSL/Linux/macOS) 並應用適當的安裝方法

set -e

# ==============================================================================
# 環境初始化：動態定位專案根目錄並掛載虛擬環境 (冪等且相容任意子目錄)
# ==============================================================================
if [ -z "$VIRTUAL_ENV" ]; then
    find_project_root() {
        local dir="$1"
        while [ "$dir" != "/" ]; do
            if [ -f "$dir/install_dependencies.sh" ]; then echo "$dir"; return 0; fi
            dir=$(dirname "$dir")
        done
        return 1
    }
    export PROJECT_ROOT=$(find_project_root "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")
    if [ -n "$PROJECT_ROOT" ] && [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
        source "$PROJECT_ROOT/.venv/bin/activate"
    fi
fi

echo "🔧 正在檢查系統環境..."

# ============================================================================
# 步驟 1：環境偵測
# ============================================================================

detect_environment() {
    local os_type=$(uname -s)
    local uname_release=$(uname -r)

    # 檢查 WSL
    if grep -qi "microsoft" /proc/version 2>/dev/null; then
        # 偵測 WSL 版本
        if grep -qi "WSL2" /proc/version 2>/dev/null; then
            echo "WSL2"
        else
            echo "WSL1"
        fi
    # 檢查 macOS
    elif [[ "$os_type" == "Darwin" ]]; then
        echo "macOS"
    # 檢查 Linux
    elif [[ "$os_type" == "Linux" ]]; then
        echo "Linux"
    else
        echo "Unknown"
    fi
}

ENVIRONMENT=$(detect_environment)
echo "✅ 偵測到的環境：$ENVIRONMENT"
echo ""

# ============================================================================
# 步驟 2：環境特定的依賴安裝
# ============================================================================

# ===== Homebrew 檢查 (macOS 專用) =====
install_homebrew_if_needed() {
    if [[ "$ENVIRONMENT" != "macOS" ]]; then
        return
    fi

    if ! command -v brew &> /dev/null; then
        echo "📦 正在安裝 Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

        # 針對 Apple Silicon Mac 的額外設定
        if [[ $(uname -m) == 'arm64' ]]; then
            echo "🍎 檢測到 Apple Silicon (M1/M2/M3)，配置 Homebrew..."
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
    else
        echo "✅ Homebrew 已安裝"
    fi
}

# ===== 基礎工具安裝 =====
install_basic_tools() {
    echo "📦 正在檢查並安裝基礎工具 (curl, wget, jq, tmux, zstd)..."

    if [[ "$ENVIRONMENT" == "macOS" ]]; then
        # macOS: 使用 brew
        TOOLS="curl wget jq tmux zstd"
        for tool in $TOOLS; do
            if ! command -v $tool &> /dev/null; then
                echo "   安裝 $tool..."
                brew install $tool
            else
                echo "   ✅ $tool 已安裝"
            fi
        done
    else
        # Linux/WSL: 使用 apt-get 或 yum
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y curl wget jq tmux zstd
        elif command -v yum &> /dev/null; then
            sudo yum install -y curl wget jq tmux zstd
        else
            echo "⚠️  無法自動安裝基礎工具，請手動確認已安裝: curl, wget, jq, tmux, zstd"
        fi
    fi
}

# ===== ngrok 安裝 =====
install_ngrok() {
    echo ""
    if command -v ngrok &> /dev/null; then
        echo "✅ ngrok 已安裝: $(ngrok --version)"
        return
    fi

    echo "📦 正在安裝 ngrok..."

    if [[ "$ENVIRONMENT" == "macOS" ]]; then
        # macOS: 使用 brew
        brew install ngrok
    elif [[ "$ENVIRONMENT" == "WSL2" || "$ENVIRONMENT" == "Linux" ]]; then
        # Linux/WSL: 優先使用 apt-get，否則直接下載
        if command -v apt-get &> /dev/null; then
            echo "   (使用 apt 安裝)"
            curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
            echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
            sudo apt-get update
            sudo apt-get install -y ngrok
        else
            echo "   (使用直接下載方式)"
            wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
            sudo tar xvzf ngrok-v3-stable-linux-amd64.tgz -C /usr/local/bin
            rm ngrok-v3-stable-linux-amd64.tgz
        fi
    fi

    if command -v ngrok &> /dev/null; then
        echo "✅ ngrok 安裝成功"
    else
        echo "❌ ngrok 安裝失敗，請參考官網手動安裝: https://ngrok.com/download"
        exit 1
    fi
}

# ===== Python 3 安裝 (macOS 可能需要) =====
install_python3_if_needed() {
    if command -v python3 &> /dev/null; then
        echo "✅ Python 3 已安裝: $(python3 --version)"
        return
    fi

    if [[ "$ENVIRONMENT" == "macOS" ]]; then
        echo "📦 正在安裝 Python 3..."
        brew install python3
    elif [[ "$ENVIRONMENT" == "Linux" || "$ENVIRONMENT" == "WSL2" ]]; then
        echo "📦 正在安裝 Python 3..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get install -y python3 python3-pip python3-venv
        elif command -v yum &> /dev/null; then
            sudo yum install -y python3 python3-pip
        fi
    fi
}

# ===== Python 依賴安裝 =====
install_python_packages() {
    echo ""
    echo "🐍 正在安裝 Python 依賴..."

    # 確保系統支援 venv 與 pip (Ubuntu/Debian 預設閹割了 ensurepip)
    if ! python3 -c "import ensurepip" 2>/dev/null; then
        echo "📦 偵測到系統缺少 python3-venv (ensurepip)，準備安裝..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y python3-venv python3-pip
        elif command -v yum &> /dev/null; then
            sudo yum install -y python3-pip
        fi
    fi

    # 檢查 pip3
    if ! command -v pip3 &> /dev/null; then
        echo "📦 安裝 pip3..."
        if [[ "$ENVIRONMENT" == "macOS" ]]; then
            python3 -m ensurepip --upgrade
        else
            if command -v apt-get &> /dev/null; then
                sudo apt-get update && sudo apt-get install -y python3-pip
            elif command -v yum &> /dev/null; then
                sudo yum install -y python3-pip
            fi
        fi
    fi

    # 安裝套件
    # 基礎依賴
    PACKAGES="flask requests pyyaml apscheduler pillow"

    # MC 多通道依賴（新增）
    MC_PACKAGES="discord.py slack-sdk websockets aiohttp"

    # 合併所有套件
    ALL_PACKAGES="$PACKAGES $MC_PACKAGES"

    echo "📦 正在建立 Python 虛擬環境..."
    # 確保虛擬環境在安裝腳本所在目錄 (專案根目錄) 建立
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    python3 -m venv "$SCRIPT_DIR/.venv"
    source "$SCRIPT_DIR/.venv/bin/activate"

    local pip_cmd="pip3 install --upgrade"

    echo "📦 正在虛擬環境內安裝 Python 套件: $ALL_PACKAGES"
    if $pip_cmd $ALL_PACKAGES; then
        echo "✅ Python 套件安裝成功"
    else
        echo "❌ Python 套件安裝失敗！請檢查錯誤訊息以排除網路或系統依賴問題。"
        exit 1
    fi
}

# ===== Node.js 安裝 =====
install_nodejs() {
    echo ""
    echo "🤖 正在檢查與安裝 Node.js..."

    local npm_prefix=""
    if [[ "$ENVIRONMENT" != "macOS" ]]; then
        npm_prefix="sudo"
    fi

    if $npm_prefix bash -c "command -v npm" &> /dev/null; then
        echo "✅ 系統級 Node.js 已安裝"
        return
    fi

    echo "📦 正在安裝系統級 Node.js (v22.x)..."

    if [[ "$ENVIRONMENT" == "macOS" ]]; then
        # macOS: 使用 brew
        brew install node
    else
        # Linux/WSL: 使用 deb.nodesource.com 或 rpm.nodesource.com
        if command -v apt-get &> /dev/null; then
            curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
            sudo apt-get install -y nodejs
        elif command -v yum &> /dev/null; then
            curl -fsSL https://rpm.nodesource.com/setup_22.x | sudo -E bash -
            sudo yum install -y nodejs
        else
            echo "⚠️  無法自動安裝 Node.js，請手動安裝後重試"
        fi
    fi
}

# ===== AI Agent CLI 安裝 =====
install_ai_cli_tools() {
    echo ""
    echo "🤖 正在檢查與安裝 AI Agent CLI..."

    # 確保先卸載可能存在於局部 (非 sudo) 或舊版的 CLI，避免路徑衝突或未更新
    if command -v npm &> /dev/null; then
        echo "🧹 正在清除可能衝突的局部 AI CLI..."
        npm uninstall -g @anthropic-ai/claude-code @google/gemini-cli @openai/codex 2>/dev/null || true
        # agy 是原生 binary 非 npm 套件，不需 npm uninstall
    fi

    # 是否需要 sudo (Linux/WSL 需要，macOS 通常不需要)
    local npm_prefix=""
    if [[ "$ENVIRONMENT" != "macOS" ]]; then
        npm_prefix="sudo"
    fi

    # 安裝 Claude Code
    if ! command -v claude &> /dev/null; then
        if command -v npm &> /dev/null; then
            echo "📦 正在透過 npm 安裝 Claude Code..."
            $npm_prefix npm install -g @anthropic-ai/claude-code || echo "⚠️  Claude Code 安裝失敗 (權限不足?)"
        else
            echo "❌ Node.js 未安裝，跳過 Claude Code 安裝"
        fi
    else
        echo "✅ Claude Code 已安裝: $(claude --version 2>/dev/null || echo 'Detected')"
    fi

    # 安裝 Gemini CLI
    if ! command -v gemini &> /dev/null; then
        if command -v npm &> /dev/null; then
            echo "📦 正在透過 npm 安裝 Gemini CLI..."
            $npm_prefix npm install -g @google/gemini-cli || echo "⚠️  Gemini CLI 安裝失敗 (權限不足?)"
        else
            echo "❌ Node.js 未安裝，跳過 Gemini CLI 安裝"
        fi
    else
        echo "✅ Gemini CLI 已安裝: $(gemini --version 2>/dev/null || echo 'Detected')"
    fi

    # 安裝 Codex CLI
    if ! command -v codex &> /dev/null; then
        if command -v npm &> /dev/null; then
            echo "📦 正在透過 npm 安裝 Codex CLI..."
            $npm_prefix npm install -g @openai/codex || echo "⚠️  Codex CLI 安裝失敗 (權限不足?)"
        else
            echo "❌ Node.js 未安裝，跳過 Codex CLI 安裝"
        fi
    else
        echo "✅ Codex CLI 已安裝: $(codex --version 2>/dev/null || echo 'Detected')"
    fi

    # 安裝 agy CLI (Antigravity - 原生 binary，非 npm 套件)
    # 檢查系統全域路徑而非任意 PATH，避免 kenzan 個人 ~/.local/bin/agy 造成誤判跳過
    if [ ! -f /usr/local/bin/agy ]; then
        echo "📦 正在透過 curl 安裝 agy CLI..."
        if curl -fsSL https://antigravity.google/cli/install.sh | bash; then
            echo "   🚚 複製 agy 至系統全域路徑..."
            if [[ "$ENVIRONMENT" != "macOS" ]]; then
                sudo cp "$HOME/.local/bin/agy" /usr/local/bin/agy && sudo chmod 755 /usr/local/bin/agy || echo "⚠️  agy CLI 全域安裝失敗 (sudo 失敗?)"
            else
                cp "$HOME/.local/bin/agy" /usr/local/bin/agy && chmod 755 /usr/local/bin/agy || echo "⚠️  agy CLI 全域安裝失敗"
            fi
        else
            echo "⚠️  agy CLI 安裝失敗"
        fi
    else
        echo "✅ agy CLI 已安裝至系統全域路徑 (/usr/local/bin/agy)"
    fi
}

# ===== 進入設定精靈 =====
start_setup_wizard() {
    echo ""
    echo "🚀 依賴安裝完成！正在啟動設定精靈..."
    sleep 1

    # 檢查設定腳本是否存在
    if [ -f "./setup_config.sh" ]; then
        chmod +x ./setup_config.sh
        ./setup_config.sh
    else
        echo "⚠️  找不到 setup_config.sh，請手動編輯 .env 檔案"
    fi
}

# ===== 總結 =====
print_summary() {
    echo ""
    echo "📋 系統依賴檢查 ($ENVIRONMENT):"
    echo "   • 環境:    $ENVIRONMENT"
    if [[ "$ENVIRONMENT" == "macOS" ]]; then
        echo "   • Homebrew: $(brew --version 2>/dev/null | head -1 || echo '未安裝')"
    fi
    echo "   • tmux:    $(tmux -V 2>/dev/null || echo '未安裝')"
    echo "   • jq:      $(jq --version 2>/dev/null || echo '未安裝')"
    echo "   • zstd:    $(zstd --version 2>/dev/null | head -n 1 || echo '未安裝')"
    echo "   • ngrok:   $(ngrok --version 2>/dev/null || echo '未安裝')"
    echo "   • Python:  $(python3 --version 2>/dev/null || echo '未安裝')"
    echo "   • Node.js: $(node --version 2>/dev/null || echo '未安裝')"
    echo ""
    echo "✅ 環境準備完成！"
    echo ""
}

# ============================================================================
# 主要執行流程
# ============================================================================

# 檢查未知環境
if [[ "$ENVIRONMENT" == "Unknown" ]]; then
    echo "❌ 無法識別的操作系統"
    exit 1
fi

# WSL1 警告
if [[ "$ENVIRONMENT" == "WSL1" ]]; then
    echo "⚠️  偵測到 WSL1，某些功能可能受限"
    echo "   建議升級至 WSL2：wsl --set-version <distro-name> 2"
    read -p "是否繼續? (y/N): " continue_install
    if [[ ! $continue_install =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 執行安裝步驟
install_homebrew_if_needed
install_basic_tools
install_ngrok
install_python3_if_needed
install_python_packages
install_nodejs
install_ai_cli_tools
print_summary
start_setup_wizard
