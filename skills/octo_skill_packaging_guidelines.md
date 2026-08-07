# 📜 Octo Skill 封裝規範指南 (Packaging Guidelines)

本指南旨在規範 OctoMatrix 生態系中擴充技能 (Skill) 的開發與封裝標準。所有欲整合至系統中的技能包，皆必須遵循以下結構與環境建置規範。

---

## 1. 命名與結構規範 (Naming & Structure)

技能必須被打包為 `.tar.gz` 或 `.zip` 壓縮檔，且其內部結構必須嚴格遵守以下約定：

### 1.1 命名一致性
解壓縮後的最外層目錄名稱，必須與壓縮包的檔名前綴完全一致，系統將以此名稱作為識別依據。
* **正確範例**：檔案名為 `draw_card_client_v2.tar.gz`（或 `draw_card_client_v2.zip`），其內部根目錄必須為 `draw_card_client_v2/`。

### 1.2 標準檔案結構
技能目錄內的組件規範如下：
* **`SKILL.md` (必備)**：Agent 讀取技能用法的唯一說明書。包含觸發指令、必要參數定義與預期產出。即使是純 Prompt 思維模型，也必須具備此檔案。
* **`setup.sh` (選配)**：技能初始化腳本。若技能需要額外下載二進位檔或提取動態函式庫，必須實作於此。
* **執行檔/源碼 (選配)**：如 `.py`, `.js` 等。若該技能僅為純提示詞 (Prompt) 注入，則不需程式碼。

### 1.3 貪婪打包陷阱 (防呆機制)
在封裝壓縮檔時，若直接執行 `tar -czf 技能包.tar.gz *`（或 `zip -r 技能包.zip *`），一旦目錄內已存在同名舊壓縮檔（例如重複打包時未先清除），會因 Shell 展開 `*` 而連帶將該壓縮檔本身一併包入，導致遞迴無限或產生幽靈壓縮檔。
* **強制規範**：打包時必須排除目標檔案本身：
  ```bash
  # tar.gz
  tar -czf 技能包.tar.gz --exclude="技能包.tar.gz" *

  # zip
  zip -r 技能包.zip * -x "技能包.zip"
  ```

---

## 2. 環境建置規範 (Environment & Setup)

Octo 系統底層安裝器 (`install_agent_skills`) 會為您的技能準備好安全的建置沙盒。若您的技能包含 `setup.sh`，請務必遵循以下實戰開發原則：

### 2.1 多作業系統相容性架構 (Multi-OS Branching)
OctoMatrix 支援廣泛的作業系統。宿主機的安裝器會在執行 `setup.sh` 前，將當前作業系統名稱注入到環境變數中（如 `OCTO_OS`，其值對應 `install_dependency` 的分支，例如 `ubuntu`, `debian`, `centos`, `macos` 等）。
開發者的 `setup.sh` 必須針對這些分支提供對應的安裝邏輯：

```bash
#!/bin/bash
# setup.sh 範例結構
case "$OCTO_OS" in
    ubuntu|debian)
        setup_debian
        ;;
    centos|rhel)
        setup_redhat
        ;;
    macos)
        setup_macos
        ;;
    *)
        echo "Unsupported OS: $OCTO_OS"
        exit 1
        ;;
esac
```

### 2.2 免 Sudo 沙盒提取原則 (Rootless Extraction)
**絕對禁止**在 `setup.sh` 中使用 `sudo` 索取系統最高權限。所有依賴必須被離線下載並「提取 (Extract)」至技能目錄內的 `local_libs` 中。

#### 2.2.1 靜默失敗防呆 (Silent Failure Masking)
使用 `apt-get download` 時，由於 apt 的「全有或全無 (all-or-nothing)」特性，若一次性傳入大量套件清單中包含 OS 不存在的套件，整個指令將靜默崩潰且不會下載任何檔案。若外層又加上 `2>/dev/null || true`，將導致無法排查的空目錄。
* **強制規範**：必須使用 `for` 迴圈逐一下載依賴，確保即使有單一套件缺失，其餘套件仍能成功提取。
  ```bash
  mkdir -p local_libs
  for pkg in dependency_a dependency_b dependency_c; do
      apt-get download $pkg 2>/dev/null || echo "警告: 無法下載 $pkg，忽略。"
  done
  dpkg -x *.deb ./local_libs
  rm *.deb
  ```

#### 2.2.2 跨平台安全複製 (GNU Portability)
在提取 `.so` 動態函式庫或搬移檔案時，應避免使用較新版本 GNU Coreutils 標示為不具移植性的 `cp -n` (no clobber) 參數，否則可能導致部分環境拋出警告。
* **推薦寫法**：對於本地暫存目錄的覆蓋，使用 `cp -f` 更為穩定安全。

### 2.3 執行期動態掛載與沙盒化 (Runtime Mounting & Sandboxing)

#### 2.3.1 函式庫動態掛載
若您在 `setup.sh` 中提取了動態函式庫至 `local_libs/usr/lib/...`，請務必在技能的入口程式中加入環境變數，讓 Agent 執行時能動態載入：
```bash
export LD_LIBRARY_PATH="$(pwd)/local_libs/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
```

#### 2.3.2 全域快取架構盲點消除 (Global Cache Relocation)
部分套件（例如具備龐大二進位檔的瀏覽器引擎、AI 模型權重等）預設會下載巨大的實體檔案至使用者的全域快取目錄（如 `~/.cache`）。這嚴重破壞了技能包的沙盒隔離性與可攜性。
* **強制規範**：必須透過環境變數或設定檔，強制將快取目錄指向技能自身的專屬目錄（如 `./.cache`），並在打包前清除或加入 `.gitignore`。
  ```bash
  # 以強制指定本地快取變數為例
  export HEAVY_DEPENDENCY_CACHE_DIR="$(pwd)/.cache"
  ```

### 2.4 日誌淨化 (Log Purification)
技能在執行期間，不應印出可能污染 Agent 思考決策的系統級錯誤雜訊。
* **強制規範**：在進行「非核心依賴」的環境驗證測試時（例如檢查某個選配的 CLI 工具是否存在），必須將錯誤流重新導向，確保純淨。
  ```bash
  # 錯誤寫法會污染日誌
  my_optional_tool --version
  
  # 正確的靜默驗證
  my_optional_tool --version 2>/dev/null || echo "提醒: 未安裝 my_optional_tool，附屬功能將跳過。"
  ```

---
**結語**：透過多 OS 分支控制、Rootless 沙盒提取、防呆迴圈機制與全域快取本地化技術，您的技能將具備最頂尖的安全性、跨平台可攜性與除錯透明度，成為 OctoMatrix 強大生態系的重要基石。
