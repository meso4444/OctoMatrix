# ⚡ 開機自動啟動 (Autostart) 指南

本模組提供 Systemd 與 Windows Task Scheduler 的整合腳本，實現 **「不死鳥模式」**：即使伺服器重啟，Agent 也會自動在背景復活。

---

## 🐧 Linux / WSL 內部設定 (Systemd)

首先，我們需要告訴 Linux 系統將 Agent 視為一個背景服務。

### 1. 執行註冊腳本
在 Ubuntu 視窗中執行對應指令：

```bash
# 回到專案根目錄
cd ~/ai-project/services/OctoMatrix/public-zh
sudo ./auto-startup/install_systemd_octomatrix.sh
```

---

## 🪟 Windows 宿主機設定 (Task Scheduler)

如果您是在 Windows WSL 上運行，為了避免 Windows 更新重啟後服務掛掉，請執行以下步驟。

### 1. 設定自動排程 (推薦方法)
您無需離開 Linux 終端機，直接執行以下指令即可呼叫 Windows 進行設定：

```bash
# 在專案目錄下
./auto-startup/setup_windows_scheduler.sh
```

這會自動彈出一個藍色的 PowerShell 視窗（若有權限詢問請按「是」），依照提示按 Enter 即可完成。

> **⚠️ 重要提示：關於 Session 0 隔離**
> 為了實現「不登入也能執行」的伺服器級能力，此任務會在 Windows 的 **Session 0** 運行。
> *   **看不到視窗**：當電腦重啟後，您**不會**在桌面上看到任何 Ubuntu 視窗，這是正常的。
> *   **背景運行**：雖然看不到，但 WSL 已經在背景啟動，且 Agent 已經上線。
> *   **如何管理**：請使用 `ssh` 連入，或透過 Telegram 傳送指令。若要手動叫出視窗，請執行 `start_octomatrix.bat`。

### 2. 備用方法 (手動執行)
如果上述方法失敗，您可以手動在 Windows PowerShell (管理員) 中執行：

1.  在 Windows 中打開 PowerShell (以系統管理員身分執行)。
2.  輸入以下指令 (請將路徑替換為您的實際路徑)：
    ```powershell
    powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\您的使用者名稱\...\setup_autostart.ps1"
    ```

---

## 🛠️ 常見問題

**Q: 我怎麼知道服務有沒有在跑？**
A: 打開 Telegram，傳送 `/status` 給您的 Bot。

**Q: 我想手動停止服務？**
A: 打開 Ubuntu，輸入 `sudo systemctl stop octomatrix-services`。

**Q: 我想移除開機自動啟動？**
A: 請執行移除腳本：
   `sudo ./auto-startup/disable_systemd_octomatrix.sh`

**Q: 腳本顯示 "WSL distro not found"？**
A: 我們的腳本預設使用 `Ubuntu`。如果您安裝的是其他版本，請編輯 `setup_autostart.ps1` 中的 `$WSLDistro` 變數。