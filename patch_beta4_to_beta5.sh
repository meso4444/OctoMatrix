#!/bin/bash
# OctoMatrix Beta.4 to Beta.5 Environment Patch Script
# Resolves global Python package conflicts, pip3 path issues, and missing pip module.

set -e

echo "🐙 [OctoMatrix] Executing Beta.4 -> Beta.5 environment upgrade patch (V4)..."

# 1. Environment & Command Detection (Strict POSIX compliant)
os_type=$(uname -s)
if [ "$os_type" = "Darwin" ]; then
    ENVIRONMENT="macOS"
    pip_cmd="python3 -m pip"
else
    ENVIRONMENT="Linux"
    pip_cmd="sudo python3 -m pip"
fi

echo "✅ Detected environment: $ENVIRONMENT"

# 1.5 Check if "global" environment has pip (Bypass Conda false positive)
if ! $pip_cmd --version > /dev/null 2>&1; then
    echo "🔧 Missing pip module in global system. Attempting to auto-install python3-pip..."
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

# 2. Remove old user-local packages to prevent dependency shadowing
echo "🗑 Cleaning up old local Python dependencies..."
PACKAGES="flask requests pyyaml apscheduler pillow discord.py slack-sdk websockets aiohttp"
python3 -m pip uninstall -y $PACKAGES > /dev/null 2>&1 || true

# 3. Reinstall Python packages globally
echo "📦 Reinstalling Python core packages globally..."
if $pip_cmd install --upgrade $PACKAGES --break-system-packages > /dev/null 2>&1 || $pip_cmd install --upgrade $PACKAGES; then
    echo "✅ Python packages globally installed successfully"
else
    echo "❌ Python package global installation failed!"
    echo "💡 Hint: Please try running manually: $pip_cmd install --upgrade $PACKAGES --break-system-packages"
fi

# 4. Install Node.js for CentOS/RHEL
if [ "$ENVIRONMENT" != "macOS" ] && command -v yum > /dev/null 2>&1 && ! command -v node > /dev/null 2>&1; then
    echo "🤖 Installing Node.js for CentOS/RHEL..."
    curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo -E bash -
    sudo yum install -y nodejs
fi

echo "✅ Beta.4 -> Beta.5 environment patch complete! You may now run ./start_octo_services.sh"