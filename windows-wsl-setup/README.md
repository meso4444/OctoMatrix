# OctoMatrix - WSL Installation Guide

## Overview

This installer will automatically:
- ✅ Install WSL (if not installed)
- ✅ Auto-enable Virtual Machine Platform (Hyper-V)
- ✅ Configure all necessary settings
- ✅ Prompt you to restart your computer

**Users just need to double-click and restart!**

## Steps to Use

### Step 1: Double-Click to Run

1. Find the **install_wsl.bat** file
2. **Double-click this file**
3. Click "Yes" if asked "Do you want to allow this app to make changes to your device?"

### Step 2: Wait for Installation

The installer will automatically:

1. **Check WSL Status** - Check if WSL is already installed
2. **Check VM Platform** - Check if Hyper-V is enabled
3. **Auto-enable Features** - Enable VM platform if needed
4. **Prompt Restart** - Ask if you want to restart your PC immediately

### Step 3: Choose Restart Option

After installation finishes, you will be asked:

**Restart your computer now? (Y/N)**

- Type **Y** → Restart immediately (Recommended)
- Type **N** → Restart manually later

#### ⚠️ Important Reminder

**Virtual Machine Platform settings only take effect after a restart!**

Without restarting, WSL2 will not work properly.

### Step 4: Post-Restart Setup

After restarting:

1. Open the "Start" menu
2. Search for and open the **Ubuntu** application
3. On first run, it will ask you to create a username and password. Follow the instructions.

### Step 5: Install Git Tool

Once set up, install Git in the Ubuntu window:

```bash
sudo apt update
sudo apt install git -y
```

The system will prompt for the password you just created. Enter it and press Enter (it won't show as you type).

## Troubleshooting

### Issue 1: Nothing happens when double-clicked

**Solution:**
1. Ensure `install_wsl.bat` and `install_wsl.ps1` are in the same folder
2. Try right-clicking `install_wsl.bat`
3. Select "Run as administrator"

### Issue 2: "User Account Control" prompt appears

**Solution:**
This is normal. Click "Yes" to allow the installer to make necessary system changes.