#!/bin/bash
# OctoMatrix Beta.4 to Beta.5 Environment Patch Script
# Resolves global Python package conflicts, pip3 path issues, and missing pip module.

set -e

echo "🐙 [OctoMatrix] Executing Beta.4 -> Beta.5 environment upgrade patch (V6)..."

# 1. Environment & Command Detection (Strict POSIX compliant)
os_type=$(uname -s)
IS_VENV="false"
if [ "$os_type" = "Darwin" ]; then
    ENVIRONMENT="macOS"
    pip_cmd="python3 -m pip"
else
    ENVIRONMENT="Linux"
    # Dynamic detection of Conda or Virtual Environment
    if [ -n "$CONDA_PREFIX" ] || [ -n "$VIRTUAL_ENV" ]; then
        pip_cmd="python3 -m pip"
        IS_VENV="true"
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

# 2. Remove old user-local packages to prevent dependency shadowing
if [ "$IS_VENV" = "true" ]; then
    echo "⏭️ Detected virtual environment, skipping uninstall to protect existing dependencies..."
else
    echo "🗑 Cleaning up old local Python dependencies..."
    python3 -m pip uninstall -y $PACKAGES > /dev/null 2>&1 || true
fi

# 3. Install Python packages (no forced --upgrade to prevent breaking Conda dependencies)
echo "📦 Installing Python core packages..."
if $pip_cmd install $PACKAGES --break-system-packages > /dev/null 2>&1 || $pip_cmd install $PACKAGES; then
    echo "✅ Python packages installed successfully"
else
    echo "❌ Python package installation failed!"
    echo "💡 Hint: Please try running manually: $pip_cmd install $PACKAGES --break-system-packages"
fi

# 4. Install Node.js for CentOS/RHEL
if [ "$ENVIRONMENT" != "macOS" ] && command -v yum > /dev/null 2>&1 && ! command -v node > /dev/null 2>&1; then
    echo "🤖 Installing Node.js for CentOS/RHEL..."
    curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo -E bash -
    sudo yum install -y nodejs
fi

echo "✅ Beta.4 -> Beta.5 environment patch complete! You may now run ./start_octo_services.sh"