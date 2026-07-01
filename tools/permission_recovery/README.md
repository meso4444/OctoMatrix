# OctoMatrix 本地 Agent 權限精度修復工具

本工具用於在 OctoMatrix 實例遭遇 Docker 容器與宿主機檔案擁有權衝突、或者權限踩踏（例如日誌破裂、`.cyberbrain_env` 寫入被拒等 Permission Error）時，進行全自動的實例安全性與權限精密重組。

## 📂 目錄結構

```
tools/permission_recovery/
├── restore_local_permissions.sh  # 核心修復腳本 (須以 sudo 執行)
└── README.md                     # 本說明文件
```

---

## 🛠️ 修復腳本運作原理

`restore_local_permissions.sh` 會精準識別執行命令的「宿主機管理員帳戶」（例如 `kenzan`），並根據系統的安全防線規範，對 `agent_home` 下的所有 Agent 目錄進行權限收歸與修正：

### 🔒 權限與擁有者規範對照表

| 目錄/檔案路徑 | 推薦擁有者 (Owner:Group) | 推薦權限 | 說明與安全防線設計 |
| :--- | :--- | :--- | :--- |
| `agent_home/` 實例主目錄 | `kenzan:kenzan` (系統管理員) | `1777` | 具備 Sticky Bit，任何人均可在內建立檔案，但僅能刪除自己擁有的檔案，防止跨實例惡意刪除。 |
| `octo_cyberbrain/` | `kenzan:kenzan` (系統管理員) | `1777` | 主控防線，確保系統能夠重寫變數與管道。 |
| `.cyberbrain_env` | `kenzan:kenzan` (系統管理員) | `644` | 唯讀環境變數檔，防止 CLI 執行期被竄改。 |
| `octo_shell.log` | `kenzan:kenzan` (系統管理員) | `644` | 活動日誌，僅限系統使用者與 Tmux 管道寫入，其他帳戶唯讀，防止日誌被 Agent 惡意抹除。 |
| `octo_ghost.json` | `kenzan:kenzan` (系統管理員) | `646` | 活動 Ghost 記錄檔，Others 可寫，利於 Agent 在降權環境下調用 `ghost_updater` 記錄任務。 |
| `toolbox/` / `knowledge/` | `kenzan:kenzan` (系統管理員) | `644` (檔案)<br>`755` (目錄) | 工具與知識庫，對 Agent 唯讀，禁止運行中竄改。 |
| `skillbox/` | `kenzan:kenzan` (系統管理員) | `a-w,a+rX` | 技能沙盒，強制鎖定為唯讀狀態。 |
| 各協作軟連結 `*_shared_space` | - | `777` (Symbolic Link) | 確保 Mesh 協作網絡互通。 |

---

## 🚀 執行指南

### 1. 一鍵自動尋找並修復
直接在腳本目錄下執行：
```bash
sudo ./restore_local_permissions.sh
```
*腳本將會自動探測 `agent_home` 的物理位置並進行重組。*

### 2. 指定特定的 `agent_home` 目錄
若您的實例部署在非預設目錄，可以手動傳入路徑參數：
```bash
sudo ./restore_local_permissions.sh /path/to/custom/agent_home
```

---

## ⚠️ 注意事項
1. 本腳本涉及跨帳戶 `chown` 與安全敏感的權限操作，**必須以 `sudo` 身份運行**。
2. 執行完成後，建議使用 `ls -la` 抽樣檢查 `octo_shell.log` 的 Owners 是否已恢復為宿主機用戶（如 `kenzan`），權限是否為 `644`。
