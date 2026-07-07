
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
| `--eyewear` | String | Eyewear ID. Default `none`. | `half_rim_glasses` |
| `--item_r` | String | Right hand item ID. Default `none`. | `magnifier` |
| `--item_l` | String | Left hand item ID. Default `none`. | `letter` |
| `--blush_style`| String | Blush geometric style. Default `oval`. | `hearts`, `lightning` |

---

## 👒 Third, Asset and Emotion Index

### 1. Item ID (24 concrete details)
`flower`, `sword`, `shield`, `duck`, `axe`, `umbrella`, `balloon`, `magnifier`, `bow`, `spear`, `crystal_ball`, `ice_cream`, `key`, `letter`, `laptop`, `smartphone`, `battery`, `anchor`, `telescope`, `burger`, `compass`, `medal`, `bell`, `baguette`

### 2. Headgear ID (34 final versions)
`grad`, `crown`, `viking`, `wizard`, `ninja`, `flower_crown`, `fish`, `frog`, `ribbon`, `tophat`, `halo`, `chef`, `propeller`, `straw_hat`, `cap`, `hard_hat`, `beret`, `pirate`, `nurse`, `police`, `jester`, `party`, `sombrero`, `santa`, `elf`, `traffic_cone`, `apple`, `cherry`, `mushroom`, `earmuffs`, `ice_crown`, `paper_boat`, `magic_hat`, `bowler_hat`

### 3. Blush style ID
`oval`, `lightning` (sawtooth), `stars`, `hearts` (solid), `dots`, `swirls` (solid)

### 4. Emotion ID (`--mood`)
`base`, `happy`, `love`, `wink`, `surprised`, `thinking`, `angry`, `sad`, `excited`, `cool`, `sleepy`, `smart`, `shy`

---

## 🐙 Fourth, Core Physical Constraints

All images must comply with the following **visual lock specifications**:
1. **Mouthless soul**: Code must never include any mouth pixels.
2. **Absolute centering**: Octopus sphere center of gravity locked at canvas **(32, 32)**, body vertical range **18-46** pixels.
3. **Mandatory blush**: Blush position locked 6 pixels below eye center (`ly+6`).
4. **Canvas specification (64x64 Canvas)**: Maintain 64-pixel specification, reserve 18 pixels "breathing space" for top and side assets.
5. **Eye highlight**: Eyes are 2-pixel radius circles, highlight point locked at `(ex-1, ey-1)`.


