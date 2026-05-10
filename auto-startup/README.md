# ⚡ Autostart Guide

This module provides integration scripts for Systemd and Windows Task Scheduler, enabling the **"Phoenix Mode"**: the Agent will automatically revive in the background even if the server reboots.

---

## 🐧 Linux / WSL Internal Setup (Systemd)

First, we need to register the Agent as a background service in the Linux system.

### 1. Run Registration Script
Execute the following commands in the Ubuntu terminal:

```bash
# Go to the project root directory
cd ~/ai-project/services/OctoMatrix/public-en
sudo ./auto-startup/install_systemd_octomatrix.sh
```

---

## 🪟 Windows Host Setup (Task Scheduler)

If you are running on Windows WSL, follow these steps to prevent the service from dying after Windows update reboots.

### 1. Configure Automatic Schedule (Recommended)
You do not need to leave the Linux terminal. Simply run the following command to invoke Windows configuration:

```bash
# From the project directory
./auto-startup/setup_windows_scheduler.sh
```

This will automatically pop up a blue PowerShell window (click "Yes" if UAC asks for permission), and press Enter as prompted to complete.

> **⚠️ Important Note: Session 0 Isolation**
> To achieve server-grade capability without requiring a user login, this task runs in Windows **Session 0**.
> *   **No visible window**: You will **NOT** see any Ubuntu windows on your desktop after reboot. This is normal.
> *   **Background operation**: WSL has started in the background, and the Agent is online.
> *   **How to manage**: Connect via `ssh` or send commands via Telegram. If you need to manually spawn the window, run `start_octomatrix.bat`.

### 2. Alternative Method (Manual)
If the above method fails, you can manually run this in Windows PowerShell (Administrator):

1.  Open PowerShell as Administrator in Windows.
2.  Enter the following command (replace the path with your actual path):
    ```powershell
    powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\YourUsername\...\setup_autostart.ps1"
    ```

---

## 🛠️ FAQ

**Q: How do I know if the service is running?**
A: Open Telegram and send `/status` to your Bot.

**Q: How do I manually stop the service?**
A: Open Ubuntu and enter `sudo systemctl stop octomatrix-services`.

**Q: How do I remove autostart?**
A: Run the uninstallation script:
   `sudo ./auto-startup/disable_systemd_octomatrix.sh`

**Q: The script says "WSL distro not found"?**
A: Our script defaults to using `Ubuntu`. If you installed a different distribution, please edit the `$WSLDistro` variable in `setup_autostart.ps1`.