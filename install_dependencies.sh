#!/bin/bash
# Install dependencies required for Telegram → AI Remote Control System (ngrok version)
# Automatically detect environment (WSL/Linux/macOS) and apply appropriate installation method

set -e

echo "🔧 Checking system environment..."

# ============================================================================
# Step 1: Environment Detection
# ============================================================================

detect_environment() {
    local os_type=$(uname -s)
    local uname_release=$(uname -r)

    # Check for WSL
    if grep -qi "microsoft" /proc/version 2>/dev/null; then
        # Detect WSL version
        if grep -qi "WSL2" /proc/version 2>/dev/null; then
            echo "WSL2"
        else
            echo "WSL1"
        fi
    # Check for macOS
    elif [[ "$os_type" == "Darwin" ]]; then
        echo "macOS"
    # Check for Linux
    elif [[ "$os_type" == "Linux" ]]; then
        echo "Linux"
    else
        echo "Unknown"
    fi
}

ENVIRONMENT=$(detect_environment)
echo "✅ Detected environment: $ENVIRONMENT"
echo ""

# ============================================================================
# Step 2: Environment-specific dependency installation
# ============================================================================

# ===== Homebrew Check (macOS only) =====
install_homebrew_if_needed() {
    if [[ "$ENVIRONMENT" != "macOS" ]]; then
        return
    fi

    if ! command -v brew &> /dev/null; then
        echo "📦 Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

        # Additional configuration for Apple Silicon Mac
        if [[ $(uname -m) == 'arm64' ]]; then
            echo "🍎 Detected Apple Silicon (M1/M2/M3), configuring Homebrew..."
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
    else
        echo "✅ Homebrew already installed"
    fi
}

# ===== Basic tools installation =====
install_basic_tools() {
    echo "📦 Checking and installing basic tools (curl, wget, jq, tmux, zstd)..."

    if [[ "$ENVIRONMENT" == "macOS" ]]; then
        # macOS: Use brew
        TOOLS="curl wget jq tmux zstd"
        for tool in $TOOLS; do
            if ! command -v $tool &> /dev/null; then
                echo "   Installing $tool..."
                brew install $tool
            else
                echo "   ✅ $tool already installed"
            fi
        done
    else
        # Linux/WSL: Use apt-get or yum
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y curl wget jq tmux zstd
        elif command -v yum &> /dev/null; then
            sudo yum install -y curl wget jq tmux zstd
        else
            echo "⚠️  Unable to automatically install basic tools, please manually verify installed: curl, wget, jq, tmux, zstd"
        fi
    fi
}

# ===== ngrok installation =====
install_ngrok() {
    echo ""
    if command -v ngrok &> /dev/null; then
        echo "✅ ngrok already installed: $(ngrok --version)"
        return
    fi

    echo "📦 Installing ngrok..."

    if [[ "$ENVIRONMENT" == "macOS" ]]; then
        # macOS: Use brew
        brew install ngrok
    elif [[ "$ENVIRONMENT" == "WSL2" || "$ENVIRONMENT" == "Linux" ]]; then
        # Linux/WSL: Prefer apt-get, otherwise download directly
        if command -v apt-get &> /dev/null; then
            echo "   (Using apt installation)"
            curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
            echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
            sudo apt-get update
            sudo apt-get install -y ngrok
        else
            echo "   (Using direct download)"
            wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
            sudo tar xvzf ngrok-v3-stable-linux-amd64.tgz -C /usr/local/bin
            rm ngrok-v3-stable-linux-amd64.tgz
        fi
    fi

    if command -v ngrok &> /dev/null; then
        echo "✅ ngrok installed successfully"
    else
        echo "❌ ngrok installation failed, please manually install from: https://ngrok.com/download"
        exit 1
    fi
}

# ===== Python 3 installation (may be needed on macOS) =====
install_python3_if_needed() {
    if command -v python3 &> /dev/null; then
        echo "✅ Python 3 already installed: $(python3 --version)"
        return
    fi

    if [[ "$ENVIRONMENT" == "macOS" ]]; then
        echo "📦 Installing Python 3..."
        brew install python3
    elif [[ "$ENVIRONMENT" == "Linux" || "$ENVIRONMENT" == "WSL2" ]]; then
        echo "📦 Installing Python 3..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get install -y python3 python3-pip
        elif command -v yum &> /dev/null; then
            sudo yum install -y python3 python3-pip
        fi
    fi
}

# ===== Python dependency installation =====
install_python_packages() {
    echo ""
    echo "🐍 Installing Python dependencies..."

    # Check pip3
    if ! command -v pip3 &> /dev/null; then
        echo "📦 Installing pip3..."
        if [[ "$ENVIRONMENT" == "macOS" ]]; then
            python3 -m ensurepip --upgrade
        else
            if command -v apt-get &> /dev/null; then
                sudo apt-get install -y python3-pip
            elif command -v yum &> /dev/null; then
                sudo yum install -y python3-pip
            fi
        fi
    fi

    # Install packages
    # Basic dependencies
    PACKAGES="flask requests pyyaml apscheduler pillow"

    # MC multi-channel dependencies (new)
    MC_PACKAGES="discord.py slack-sdk websockets aiohttp"

    # Merge all packages
    ALL_PACKAGES="$PACKAGES $MC_PACKAGES"

    local pip_cmd="sudo pip3 install --upgrade"
    if [[ "$ENVIRONMENT" == "macOS" ]]; then
        pip_cmd="pip3 install --upgrade"
    fi

    echo "📦 Installing Python packages globally: $ALL_PACKAGES"
    if $pip_cmd $ALL_PACKAGES --break-system-packages 2>/dev/null || $pip_cmd $ALL_PACKAGES; then
        echo "✅ Python packages installed globally successfully"
    else
        echo "❌ Global Python package installation failed!"
        echo "💡 Tip: Try running manually: $pip_cmd $ALL_PACKAGES --break-system-packages"
    fi
    }

# ===== Node.js installation =====
install_nodejs() {
    echo ""
    echo "🤖 Checking and installing Node.js..."

    local npm_prefix=""
    if [[ "$ENVIRONMENT" != "macOS" ]]; then
        npm_prefix="sudo"
    fi

    if $npm_prefix bash -c "command -v npm" &> /dev/null; then
        echo "✅ System Node.js already installed"
        return
    fi

    echo "📦 Installing System Node.js (v22.x)..."

    if [[ "$ENVIRONMENT" == "macOS" ]]; then
        # macOS: Use brew
        brew install node
    else
        # Linux/WSL: Use deb.nodesource.com or rpm.nodesource.com
        if command -v apt-get &> /dev/null; then
            curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
            sudo apt-get install -y nodejs
        elif command -v yum &> /dev/null; then
            curl -fsSL https://rpm.nodesource.com/setup_22.x | sudo -E bash -
            sudo yum install -y nodejs
        else
            echo "⚠️  Unable to automatically install Node.js, please install manually and retry"
        fi
    fi
}

# ===== AI Agent CLI installation =====
install_ai_cli_tools() {
    echo ""
    echo "🤖 Checking and installing AI Agent CLI..."

    # Ensure local (non-sudo) or old CLIs are uninstalled first to prevent path conflicts
    if command -v npm &> /dev/null; then
        echo "🧹 Clearing potentially conflicting local AI CLIs..."
        npm uninstall -g @anthropic-ai/claude-code @google/gemini-cli @openai/codex 2>/dev/null || true
        # agy is a native binary, not an npm package — no npm uninstall needed
    fi

    # Whether sudo is needed (Linux/WSL needs it, macOS usually doesn't)
    local npm_prefix=""
    if [[ "$ENVIRONMENT" != "macOS" ]]; then
        npm_prefix="sudo"
    fi

    # Install Claude Code
    if ! command -v claude &> /dev/null; then
        if command -v npm &> /dev/null; then
            echo "📦 Installing Claude Code via npm..."
            $npm_prefix npm install -g @anthropic-ai/claude-code || echo "⚠️  Claude Code installation failed (permission denied?)"
        else
            echo "❌ Node.js not installed, skipping Claude Code installation"
        fi
    else
        echo "✅ Claude Code already installed: $(claude --version 2>/dev/null || echo 'Detected')"
    fi

    # Install Gemini CLI
    if ! command -v gemini &> /dev/null; then
        if command -v npm &> /dev/null; then
            echo "📦 Installing Gemini CLI via npm..."
            $npm_prefix npm install -g @google/gemini-cli || echo "⚠️  Gemini CLI installation failed (permission denied?)"
        else
            echo "❌ Node.js not installed, skipping Gemini CLI installation"
        fi
    else
        echo "✅ Gemini CLI already installed: $(gemini --version 2>/dev/null || echo 'Detected')"
    fi

    # Install Codex CLI
    if ! command -v codex &> /dev/null; then
        if command -v npm &> /dev/null; then
            echo "📦 Installing Codex CLI via npm..."
            $npm_prefix npm install -g @openai/codex || echo "⚠️  Codex CLI installation failed (permission denied?)"
        else
            echo "❌ Node.js not installed, skipping Codex CLI installation"
        fi
    else
        echo "✅ Codex CLI already installed: $(codex --version 2>/dev/null || echo 'Detected')"
    fi

    # Install agy CLI (Antigravity - native binary, not npm package)
    # Check system-wide path, not arbitrary PATH — prevents skip if kenzan already has ~/.local/bin/agy
    if [ ! -f /usr/local/bin/agy ]; then
        echo "📦 Installing agy CLI via curl..."
        if curl -fsSL https://antigravity.google/cli/install.sh | bash; then
            echo "   🚚 Copying agy to system-wide path..."
            if [[ "$ENVIRONMENT" != "macOS" ]]; then
                sudo cp "$HOME/.local/bin/agy" /usr/local/bin/agy && sudo chmod 755 /usr/local/bin/agy || echo "⚠️  agy CLI system-wide installation failed (sudo failed?)"
            else
                cp "$HOME/.local/bin/agy" /usr/local/bin/agy && chmod 755 /usr/local/bin/agy || echo "⚠️  agy CLI system-wide installation failed"
            fi
        else
            echo "⚠️ agy CLI installation failed"
        fi
    else
        echo "✅ agy CLI already installed at system-wide path (/usr/local/bin/agy)"
    fi
}

# ===== Launch setup wizard =====
start_setup_wizard() {
    echo ""
    echo "🚀 Dependency installation complete! Launching setup wizard..."
    sleep 1

    # Check if setup script exists
    if [ -f "./setup_config.sh" ]; then
        chmod +x ./setup_config.sh
        ./setup_config.sh
    else
        echo "⚠️  setup_config.sh not found, please manually edit .env file"
    fi
}

# ===== Summary =====
print_summary() {
    echo ""
    echo "📋 System dependency check ($ENVIRONMENT):"
    echo "   • Environment:    $ENVIRONMENT"
    if [[ "$ENVIRONMENT" == "macOS" ]]; then
        echo "   • Homebrew: $(brew --version 2>/dev/null | head -1 || echo 'Not installed')"
    fi
    echo "   • tmux:    $(tmux -V 2>/dev/null || echo 'Not installed')"
    echo "   • jq:      $(jq --version 2>/dev/null || echo 'Not installed')"
    echo "   • zstd:    $(zstd --version 2>/dev/null | head -n 1 || echo 'Not installed')"
    echo "   • ngrok:   $(ngrok --version 2>/dev/null || echo 'Not installed')"
    echo "   • Python:  $(python3 --version 2>/dev/null || echo 'Not installed')"
    echo "   • Node.js: $(node --version 2>/dev/null || echo 'Not installed')"
    echo ""
    echo "✅ Environment preparation complete!"
    echo ""
}

# ============================================================================
# Main execution flow
# ============================================================================

# Check for unknown environment
if [[ "$ENVIRONMENT" == "Unknown" ]]; then
    echo "❌ Unrecognized operating system"
    exit 1
fi

# WSL1 warning
if [[ "$ENVIRONMENT" == "WSL1" ]]; then
    echo "⚠️  Detected WSL1, some features may be limited"
    echo "   Recommended upgrade to WSL2: wsl --set-version <distro-name> 2"
    read -p "Continue anyway? (y/N): " continue_install
    if [[ ! $continue_install =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Execute installation steps
install_homebrew_if_needed
install_basic_tools
install_ngrok
install_python3_if_needed
install_python_packages
install_nodejs
install_ai_cli_tools
print_summary
start_setup_wizard
