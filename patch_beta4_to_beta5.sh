#!/bin/bash
# OctoMatrix Beta.4 to Beta.5 Environment Patch Script
# Resolves global Python package conflicts, pip3 path issues, and missing pip module.

set -e

echo "🐙 [OctoMatrix] Executing Beta.4 -> Beta.5 environment upgrade patch (V9 Ultimate Debug Version)..."

# 1. Environment & Command Detection (Strict POSIX compliant)
os_type=$(uname -s)
if [ "$os_type" = "Darwin" ]; then
    ENVIRONMENT="macOS"
    pip_cmd="python3 -m pip"
else
    ENVIRONMENT="Linux"
    # Dynamic detection of Conda or Virtual Environment
    if [ -n "$CONDA_PREFIX" ] || [ -n "$VIRTUAL_ENV" ]; then
        pip_cmd="python3 -m pip"
        echo "✅ Detected virtual environment (Conda/Venv), using local environment..."
    else
        pip_cmd="sudo python3 -m pip"
    fi
fi

echo "✅ Detected system: $ENVIRONMENT"

# 1.5 Check if target environment has pip
if ! $pip_cmd --version > /dev/null 2>&1; then
    echo "🔧 Missing pip module. Attempting to auto-install python3-pip..."
    if command -v apt-get > /dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y python3-pip
    elif command -v yum > /dev/null 2>&1; then
        sudo yum install -y python3-pip
    elif command -v pacman > /dev/null 2>&1; then
        sudo pacman -Sy --noconfirm python-pip
    else
        echo "❌ Failed to auto-install pip. Please manually install python3-pip."
        exit 1
    fi
fi

PACKAGES="flask requests pyyaml apscheduler pillow discord.py slack-sdk websockets aiohttp"

# 2. Forcefully remove old packages to ensure a clean slate
echo "🗑 Forcefully cleaning up old Python dependencies..."
python3 -m pip uninstall -y $PACKAGES > /dev/null 2>&1 || true

# 3. Force reinstall Python packages (Ignoring conflicts to ensure OctoMatrix has the perfect environment)
echo "📦 Force reinstalling Python core packages..."
if $pip_cmd install --upgrade --force-reinstall $PACKAGES --break-system-packages > /dev/null 2>&1 || $pip_cmd install --upgrade --force-reinstall $PACKAGES; then
    echo "✅ Python packages installed successfully"
else
    echo "❌ Python package installation failed!"
    echo "💡 Hint: Please try running manually: $pip_cmd install --upgrade --force-reinstall $PACKAGES --break-system-packages"
fi

# 4. Install Node.js for CentOS/RHEL
if [ "$ENVIRONMENT" != "macOS" ] && command -v yum > /dev/null 2>&1 && ! command -v node > /dev/null 2>&1; then
    echo "🤖 Installing Node.js for CentOS/RHEL..."
    curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo -E bash -
    sudo yum install -y nodejs
fi

# 5. Force reinstall AI CLI Tools
echo "🤖 Reinstalling latest AI CLI Tools..."
npm_prefix=""
if [ "$ENVIRONMENT" != "macOS" ]; then
    if [ -n "$CONDA_PREFIX" ] || [ -n "$VIRTUAL_ENV" ] || [[ "$(which npm 2>/dev/null)" == *".nvm"* ]]; then
        npm_prefix=""
    else
        npm_prefix="sudo"
    fi
fi

if command -v npm > /dev/null 2>&1; then
    $npm_prefix npm install -g @anthropic-ai/claude-code @google/gemini-cli @openai/codex || echo "⚠️ AI CLI installation failed, please check Node.js environment or permissions."
    echo "✅ AI CLI Tools reinstallation complete!"
else
    echo "❌ npm not found, skipping AI CLI reinstallation. Please install Node.js manually!"
fi

echo "✅ Beta.4 -> Beta.5 environment patch complete! You may now run ./start_octo_services.sh"