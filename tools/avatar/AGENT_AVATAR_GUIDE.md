
# Matrix Agent Avatar 視覺形象建構指南

本指南引導 Agents 基於 **自主意志與個人喜好**，建構代表其靈魂的視覺形象。

---

## 🚀 一、 形象建構與生成 SOP

### 1. 喜好決策與思考框架
Agent 應依據個人喜好進行設計，不應受到拘束。建議思考維度：
- **配色偏好 (Color)**：選取一組 RGB。反映你的性格與底色。
- **符號隱喻 (Accessories)**：選取具備個人認同感的頭飾與眼鏡。
- **職能與愛好 (Items)**：選取 1-2 件體現你職能或個人興趣的持物。
- **靈魂特徵 (Blush)**：選取符合氣質的腮紅樣式。**（腮紅為靈魂組件，為強制必備項）**

**一鍵生成基礎形象與表情包**
- 不需要手動指定 `--name` 或逐個對應 `--mood` 生成。
- 直接使用一鍵生成命令，腳本會自動在記憶體中一次性產出 `base.png` 與所有固定的 12 款表情包 PNG，並自動封裝為 ZIP 發送給 Router API 進行高權覆寫更新。
```bash
# 一鍵生成指令範例：
python3 toolbox/octo_generator.py --color 41 128 185 --headgear grad --eyewear monocle --item_r magnifier --blush_style oval --token <YourToken>
```

### 3. 最終成果展示與說明 (Final Showcase)
完成生成後，**必須向使用者發送訊息展示成果**，內容需包含：
1.  **Avatar Base 圖檔** (作為附件發送)。
2.  **動機自述**：詳細說明為何選取該配色、配件與持物，向使用者介紹你的視覺靈魂，同時把此內容筆記在avatar/avatar.md。

---

## 🛠️ 二、 生成參數詳解 (Parameter Reference)

| 參數 | 類型 | 說明與預設值 | 範例 |
| :--- | :--- | :--- | :--- |
| `--name` | String | **必填**。產出圖檔的完整路徑與檔名。 | `avatar/base.png` |
| `--color` | Int x3 | 本體顏色 (R G B)，預設 `150 150 150`。 | `41 128 185` |
| `--mood` | String | 心情表情。預設 `base` (圓眼)。 | `smart`, `happy` |
| `--headgear` | String | 頭部配件 ID。預設 `none`。 | `grad`, `crown` |
| `--eyewear` | String | 眼部配件 ID。預設 `none`。 | `half_rim_glasses` |
| `--item_r` | String | 右手持物 ID。預設 `none`。 | `magnifier` |
| `--item_l` | String | 左手持物 ID。預設 `none`。 | `letter` |
| `--blush_style`| String | 腮紅幾何樣式。預設 `oval`。 | `hearts`, `lightning` |

---

## 👒 三、 資產與情緒索引 (Asset Index)

### 1. 持物 ID (24 款具象細節)
`flower`, `sword`, `shield`, `duck`, `axe`, `umbrella`, `balloon`, `magnifier`, `bow`, `spear`, `crystal_ball`, `ice_cream`, `key`, `letter`, `laptop`, `smartphone`, `battery`, `anchor`, `telescope`, `burger`, `compass`, `medal`, `bell`, `baguette`

### 2. 頭部配件 ID (34 款定稿)
`grad`, `crown`, `viking`, `wizard`, `ninja`, `flower_crown`, `fish`, `frog`, `ribbon`, `tophat`, `halo`, `chef`, `propeller`, `straw_hat`, `cap`, `hard_hat`, `beret`, `pirate`, `nurse`, `police`, `jester`, `party`, `sombrero`, `santa`, `elf`, `traffic_cone`, `apple`, `cherry`, `mushroom`, `earmuffs`, `ice_crown`, `paper_boat`, `magic_hat`, `bowler_hat`

### 3. 腮紅樣式 ID
`oval`, `lightning` (鋸齒), `stars`, `hearts` (實心), `dots`, `swirls` (實心)

### 4. 情緒 ID (`--mood`)
`base`, `happy`, `love`, `wink`, `surprised`, `thinking`, `angry`, `sad`, `excited`, `cool`, `sleepy`, `smart`, `shy`

---

## 🐙 四、 核心物理約束 (Physical Constraints)

所有形象必須符合以下 **死鎖規範 (Visual Lock)**：
1. **無嘴靈魂 (Mouthless)**：底層代碼嚴禁出現任何嘴巴像素。
2. **絕對重心置中 (Absolute Centering)**：章魚球體重心鎖定在畫布 **(32, 32)**，本體垂直區間為 **18-46** 像素。
3. **強制腮紅 (Blush Mandatory)**：腮紅位置鎖定於眼睛中心點下方 6 像素處 (`ly+6`)。
4. **畫布規格 (64x64 Canvas)**：維持 64 像素規格，為頂部與側邊資產保留 18 像素的「呼吸空間」。
5. **眼部高光**：眼睛為半徑 2 像素圓形，高光點鎖定於 `(ex-1, ey-1)`。


## 🔒 五、 絕對鎖定、安全防護與備份機制 (Absolute Lock & History Backup)

為了防止 Agent 被越權篡改形象或被注入惡意產圖代碼，系統實施了絕對的安全鎖定機制：

### 1. 檔案系統權限鎖定 (Filesystem Lockdown)
- `setup_agent_env.py` 在初始化環境時，會強制將 Agent 目錄下的 `avatar/` 及 `avatar/emojis/` 設定為 `755` 權限。
- 這意味著除了高權限的系統管理者（如宿主）及 Router 外，Agent 本身及其所屬的 CLI 進程對此目錄**僅有唯讀 (Read-Only) 權限**，無法直接透過程式碼或 Shell 指令寫入或覆蓋檔案。

### 2. 安全授權與 Token 校驗 (--token)
- 在執行 `/avatar_renew` 指令更新形象時，Router 會動態生成一組具有 5 分鐘有效期的 UUID Token，並作為安全 Prompt 的 `--token` 參數注入給 Agent。
- Agent 在生成新頭像時，**必須**將此 Token 傳遞給 `octo_generator.py`（即 `python3 toolbox/octo_generator.py --token <YourToken> ...`）。
- `octo_generator.py` 會自動將新圖片打包為 ZIP 位元組流，發送給 Router API。Router 驗證 Token 成功後，會**立即銷毀該 Token**，並代為解壓寫入 `avatar/` 目錄。
- **冷啟動豁免 (Cold Bootstrap)**：若 `avatar/base.png` 檔案不存在（即首次生成頭像時），系統允許直接寫入本地目錄，不強制要求 Token 校驗。

### 3. 五代歷史備份與還原 (History Backup & Restore)
- **自動備份**：當 Router 執行代寫更新前，會自動將現有的頭像（排除舊有 `history_*.zip` 檔案）封裝為 `history_YYYYMMDD_HHMMSS.zip` 儲存在 `avatar/` 下，並限制保留最新的 5 代。
- **列出歷史備份**：用戶可在聊天中發送以下指令查看可用的歷史備份：
  ```
  /avatar_renew list
  ```
- **一鍵還原**：發送以下指令，由 Router 直接還原至指定歷史版本（此操作無需 Agent 介入，不需 Token）：
  ```
  /avatar_renew restore <編號或檔名>
  # 範例：
  /avatar_renew restore 1
  /avatar_renew restore history_20260630_174700.zip
  ```


