#!/bin/bash
# OctoMatrix Beta.4 to Beta.5 Environment Patch Script
# Resolves global Python package conflicts and sudo pip3 path issues under V4 Isolation, and adds CentOS Node.js support.

set -e

echo "🐙 [OctoMatrix] Executing Beta.4 -> Beta.5 environment upgrade patch..."

# 1. Environment Detection
os_type=$(uname -s)
if [[ "$os_type" == "Darwin" ]]; then
    ENVIRONMENT="macOS"
else
    ENVIRONMENT="Linux"
fi

echo "✅ Detected environment: $ENVIRONMENT"

# 1.5 Check and auto-install pip
if ! python3 -m pip --version > /dev/null 2>&1; then
    echo "🔧 Missing pip module detected. Attempting to auto-install python3-pip..."
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
# Use 'python3 -m pip' to bypass 'sudo pip3: command not found' error
# Force global installation to comply with V4 architecture
pip_cmd="sudo python3 -m pip install --upgrade"
if [[ "$ENVIRONMENT" == "macOS" ]]; then
    pip_cmd="python3 -m pip install --upgrade"
fi

echo "📦 Reinstalling Python core packages globally..."
if $pip_cmd $PACKAGES --break-system-packages 2>/dev/null || $pip_cmd $PACKAGES; then
    echo "✅ Python packages globally installed successfully"
else
    echo "❌ Python package global installation failed!"
    echo "💡 Hint: Please try running manually: $pip_cmd $PACKAGES --break-system-packages"
fi

# 4. Install Node.js for CentOS/RHEL (New in Beta.5)
if [[ "$ENVIRONMENT" != "macOS" ]] && command -v yum &> /dev/null && ! command -v node &> /dev/null; then
    echo "🤖 Installing Node.js for CentOS/RHEL..."
    curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo -E bash -
    sudo yum install -y nodejs
fi

echo "✅ Beta.4 -> Beta.5 environment patch complete! You may now run ./start_octo_services.sh"
