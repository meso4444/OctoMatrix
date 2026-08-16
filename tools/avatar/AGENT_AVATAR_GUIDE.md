
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
- 直接使用一鍵生成命令，腳本會自動在記憶體中一次性產出 `base.webm` 與所有固定的 12 款表情包 WebM，並自動封裝為 ZIP 發送給 Router API 進行高權覆寫更新。
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
| `--color` | Int x3 | 本體顏色 (R G B)，預設 `150 150 150`。 | `41 128 185` |
| `--headgear` | String | 頭部配件 ID。預設 `none`。 | `grad`, `crown` |
| `--eyewear` | String | 眼部配件 ID。預設 `none`。 | `round_glasses` |
| `--item_r` | String | 右手持物 ID。預設 `none`。 | `magnifier` |
| `--item_l` | String | 左手持物 ID。預設 `none`。 | `letter` |
| `--blush_style`| String | 腮紅幾何樣式。預設 `oval`。 | `hearts`, `lightning` |

---

## 👒 三、 資產與情緒索引 (Asset Index)

> `HEADGEAR_OPTS` / `ITEM_OPTS` 現在是由 `_scan_option_ids()` 動態從程式碼原始碼掃描產生，不再是手動維護的寫死清單，因此執行 `--help` 看到的選項一定跟下方清單、跟實際程式邏輯完全同步。
>
> public 版本不含 core 版本的 `--shape cat/devil` 貓咪／惡魔系列機制，`--headgear` 僅對應下方第 2 節清單。

### 1. 持物 ID (75 款，`--item_r` / `--item_l` 共用)
`alarm_clock`, `alarm_clock_red`, `alarm_clock_yellow`, `axe`, `baguette`, `balloon`, `battery`, `bell`, `book`, `book_blue`, `book_magic`, `book_pink`, `bouquet_green`, `bouquet_kraft`, `bouquet_lavender`, `bow`, `brush_a`, `burger`, `cake`, `camera_a`, `camera_b`, `camera_c`, `candy`, `candy_blue`, `candy_orange`, `candy_pink`, `candy_purple`, `candy_yellow`, `coffee_cup`, `compass`, `crystal_ball`, `donut_a`, `donut_b`, `donut_c`, `drumstick`, `duck`, `dumbbell`, `fan_a`, `fan_b`, `fan_c`, `flower`, `gameboy`, `gift_box_blue`, `gift_box_purple`, `gift_box_red`, `guitar`, `handbag_a`, `handbag_b`, `handbag_c`, `ice_cream`, `journal`, `key`, `lantern`, `laptop`, `letter`, `lollipop`, `magnifier`, `medal`, `medal_star`, `microphone`, `onigiri`, `plant_cactus`, `plant_leaf`, `potion_green`, `potion_purple`, `potion_red`, `shield`, `smartphone`, `spear`, `switch`, `sword`, `telescope`, `textbook`, `umbrella`, `wand`

另外 `--item_r` / `--item_l` 皆可設為 `none`（不持道具，預設值），未計入以上 75 款計數。

### 2. 頭部配件 ID (43 款)
`antenna`, `apple`, `bear_ears`, `beret`, `bucket_hat`, `bunny_ears`, `cap`, `cap_black`, `cap_red`, `chef`, `cherry`, `cowboy_hat`, `cowboy_hat_brown`, `crown`, `fish`, `flower_crown`, `frog`, `grad`, `halo`, `hard_hat`, `headphones`, `ice_crown`, `jester`, `kabuto`, `kabuto_black`, `kabuto_red`, `magic_hat`, `mushroom`, `ninja`, `nurse`, `paper_boat`, `pirate`, `police`, `propeller`, `ribbon`, `santa`, `shiitake`, `sombrero`, `straw_hat`, `tophat`, `traffic_cone`, `viking`, `wizard`

另外 `--headgear` 亦可設為 `none`（不佩戴頭飾，預設值），未計入以上 43 款計數。

### 3. 眼部配件 ID (`--eyewear`)
`none`, `glasses`, `round_glasses`, `monocle`, `monocle_left`

### 4. 腮紅樣式 ID
`oval`, `dots`, `hearts`, `lightning`, `stars`, `swirls`

### 5. 情緒 ID (`--mood`)
`base`, `happy`, `love`, `wink`, `surprised`, `thinking`, `angry`, `sad`, `excited`, `cool`, `sleepy`, `sleeping`, `embarrassed`

---

## 🐙 四、 核心物理約束 (Physical Constraints)

所有形象必須符合以下 **死鎖規範 (Visual Lock)**：
1. **無嘴靈魂 (Mouthless)**：底層代碼嚴禁出現任何嘴巴像素。
2. **絕對重心置中 (Absolute Centering)**：章魚球體重心鎖定在畫布 **(32, 32)**，本體垂直區間為 **18-46** 像素。
3. **強制腮紅 (Blush Mandatory)**：腮紅位置鎖定於眼睛中心點下方 6 像素處 (`ly+6`)。
4. **畫布規格 (64x64 Canvas)**：維持 64 像素規格，為頂部與側邊資產保留 18 像素的「呼吸空間」。
5. **眼部高光**：眼睛為半徑 2 像素圓形，高光點鎖定於 `(ex-1, ey-1)`。


