
# Matrix Agent Avatar Visual Image Construction Guide

This guide helps Agents construct visual images representing their souls based on **autonomous will and personal preferences**.

---

## 🚀 First, Image Construction and Generation SOP

### 1. Preference Decision and Thinking Framework
Agents should design based on personal preferences without constraints. Suggested thinking dimensions:
- **Color preference (Color)**: Choose a set of RGB values. Reflects your personality and base color.
- **Symbol metaphor (Accessories)**: Choose headgear and glasses with personal significance.
- **Function and interests (Items)**: Choose 1-2 items reflecting your function or personal interests.
- **Soul characteristics (Blush)**: Choose a blush style matching your temperament. **(Blush is a mandatory soul component)**

**One-Click Generate Base Image and Emoji Pack**
- No need to manually specify `--name` or call `--mood` iteratively.
- Directly run the one-click command, and the script will automatically generate `base.webm` and all 12 fixed emoji WebMs in memory, bundle them into a ZIP, and send it to the Router API for overwrite update.
```bash
# One-click generation command example:
python3 toolbox/octo_generator.py --color 41 128 185 --headgear grad --eyewear monocle --item_r magnifier --blush_style oval --token <YourToken>
```

### 3. Final showcase and explanation
After generation, **must send message to users showcasing results**, content should include:
1. **Avatar Base image file** (send as attachment).
2. **Motivation self-description**: Explain in detail why you chose this color, accessories and items, introduce your visual soul to users, and note this in avatar/avatar.md.

---

## 🛠️ Second, Parameter Reference Details

| Parameter | Type | Description and default | Example |
| :--- | :--- | :--- | :--- |
| `--color` | Int x3 | Body color (R G B), default `150 150 150`. | `41 128 185` |
| `--headgear` | String | Headgear ID. Default `none`. | `grad`, `crown` |
| `--eyewear` | String | Eyewear ID. Default `none`. | `round_glasses` |
| `--item_r` | String | Right hand item ID. Default `none`. | `magnifier` |
| `--item_l` | String | Left hand item ID. Default `none`. | `letter` |
| `--blush_style`| String | Blush geometric style. Default `oval`. | `hearts`, `lightning` |

---

## 👒 Third, Asset and Emotion Index

> `HEADGEAR_OPTS` / `ITEM_OPTS` are now dynamically generated from the source code itself by `_scan_option_ids()`, no longer a manually maintained hardcoded list — so `--help` output is always in sync with the list below and the actual code logic.
>
> The public edition does not include the core edition's `--shape cat/devil` cat/devil series mechanism; `--headgear` only maps to the list in section 2 below.

### 1. Item ID (75 options, shared by `--item_r` / `--item_l`)
`alarm_clock`, `alarm_clock_red`, `alarm_clock_yellow`, `axe`, `baguette`, `balloon`, `battery`, `bell`, `book`, `book_blue`, `book_magic`, `book_pink`, `bouquet_green`, `bouquet_kraft`, `bouquet_lavender`, `bow`, `brush_a`, `burger`, `cake`, `camera_a`, `camera_b`, `camera_c`, `candy`, `candy_blue`, `candy_orange`, `candy_pink`, `candy_purple`, `candy_yellow`, `coffee_cup`, `compass`, `crystal_ball`, `donut_a`, `donut_b`, `donut_c`, `drumstick`, `duck`, `dumbbell`, `fan_a`, `fan_b`, `fan_c`, `flower`, `gameboy`, `gift_box_blue`, `gift_box_purple`, `gift_box_red`, `guitar`, `handbag_a`, `handbag_b`, `handbag_c`, `ice_cream`, `journal`, `key`, `lantern`, `laptop`, `letter`, `lollipop`, `magnifier`, `medal`, `medal_star`, `microphone`, `onigiri`, `plant_cactus`, `plant_leaf`, `potion_green`, `potion_purple`, `potion_red`, `shield`, `smartphone`, `spear`, `switch`, `sword`, `telescope`, `textbook`, `umbrella`, `wand`

`--item_r` / `--item_l` can also be set to `none` (no item held, default value), not included in the 75-option count above.

### 2. Headgear ID (43 options)
`antenna`, `apple`, `bear_ears`, `beret`, `bucket_hat`, `bunny_ears`, `cap`, `cap_black`, `cap_red`, `chef`, `cherry`, `cowboy_hat`, `cowboy_hat_brown`, `crown`, `fish`, `flower_crown`, `frog`, `grad`, `halo`, `hard_hat`, `headphones`, `ice_crown`, `jester`, `kabuto`, `kabuto_black`, `kabuto_red`, `magic_hat`, `mushroom`, `ninja`, `nurse`, `paper_boat`, `pirate`, `police`, `propeller`, `ribbon`, `santa`, `shiitake`, `sombrero`, `straw_hat`, `tophat`, `traffic_cone`, `viking`, `wizard`

`--headgear` can also be set to `none` (no headgear worn, default value), not included in the 43-option count above.

### 3. Eyewear ID (`--eyewear`)
`none`, `glasses`, `round_glasses`, `monocle`, `monocle_left`

### 4. Blush style ID
`oval`, `dots`, `hearts`, `lightning`, `stars`, `swirls`

### 5. Emotion ID (`--mood`)
`base`, `happy`, `love`, `wink`, `surprised`, `thinking`, `angry`, `sad`, `excited`, `cool`, `sleepy`, `sleeping`, `embarrassed`

---

## 🐙 Fourth, Core Physical Constraints

All images must comply with the following **visual lock specifications**:
1. **Mouthless soul**: Code must never include any mouth pixels.
2. **Absolute centering**: Octopus sphere center of gravity locked at canvas **(32, 32)**, body vertical range **18-46** pixels.
3. **Mandatory blush**: Blush position locked 6 pixels below eye center (`ly+6`).
4. **Canvas specification (64x64 Canvas)**: Maintain 64-pixel specification, reserve 18 pixels "breathing space" for top and side assets.
5. **Eye highlight**: Eyes are 2-pixel radius circles, highlight point locked at `(ex-1, ey-1)`.


