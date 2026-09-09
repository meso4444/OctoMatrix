# 更新日誌 (Changelog)

本文件彙整 OctoMatrix 各版本間的重大變更，格式比照 [Keep a Changelog](https://keepachangelog.com/) 精神編寫，但依專案習慣以「重大升級摘要」呈現。完整逐項細節可參閱各版本對應的 GitHub Release。

## [v1.0.0-beta.9] - 2026-09-02

與 beta.8 相比的整合發布，涵蓋 Telegram 連線架構調整、Avatar 系統擴充、Docker/macOS 部署穩定性，以及 GHOST/Harness 底層可靠性修補。

- **Telegram Gateway 改用 Long Polling**：拔除 ngrok 依賴，不再需要對外開洞或維護通道。
- **Avatar 系統強化**：新增 `candle_lantern` 道具、`sumikko` 系列整併、`--help` 動態掃描產生說明文件、`avatar_instruction` 移入樣板並在地化。
- **Docker / macOS 部署穩定性**：修正 token 貼上視覺回饋、docker-compose `$` 跳脫、agy 認證改於臨時容器執行、`.env` shell 跳脫、多 Agent 啟動錯開 5 秒。
- **GHOST / Harness 可靠性**：修補重置緩衝期孤兒檔案問題、甦醒上下文深度統一為 20、新增 Harness Cooldown、`auto_permission_responder.py` 容錯強化。

詳見 [Release v1.0.0-beta.9-zh](https://github.com/meso4444/OctoMatrix/releases/tag/v1.0.0-beta.9-zh)。

## [v1.0.0-beta.8] - 2026-08-13

單一但重要的可靠性修復：GHOST/Cyberbrain 終端擷取層 scrollback 補強，解決 Agent 空閒問候誤觸發的根因。

- `cyberbrain_pipe_manager.py` 的 `tmux capture-pane` 加上 `-S -300`，改為連同最近 300 行 scrollback 一起擷取，避免忙碌 Agent 因終端擷取盲區被誤判為長時間無互動。

詳見 [Release v1.0.0-beta.8-zh](https://github.com/meso4444/OctoMatrix/releases/tag/v1.0.0-beta.8-zh)。

## [v1.0.0-beta.7] - 2026-08-11

累積近三週的修復與強化，涵蓋三通道網路安全複查、macOS 原生支援、通知系統與橫向通訊的強健性補強。

- **資安強化**：`router`/`telegram_gateway` 預設改綁 `127.0.0.1`；Telegram Webhook 新增 `secret_token` 驗證；三通道檔案下載補上檔名清洗（保留中日韓檔名）並修復路徑穿越風險。
- **macOS 原生支援**：`config_wizard.py` 新增 macOS 分支，不再僅限 Linux `useradd`。
- **通知系統強健性**：Router 失敗時回傳 HTTP 502；`matrix_notifier.py` 補上 JSON body 驗證與純文字回退。
- **GHOST 與橫向通訊**：快照關鍵字改依觸碰時間排序並支援分頁；`agent_intercom.py` 逾時時間分段拉高。
- **Telegram 訊息類型擴充**：新增語音、影片、圓形訊息、GIF 的接收與轉發。

詳見 [Release v1.0.0-beta.7-zh](https://github.com/meso4444/OctoMatrix/releases/tag/v1.0.0-beta.7-zh)。

## [v1.0.0-beta.6] - 2026-07-23

涵蓋 Agent 執行環境虛擬環境隔離架構、頭像系統全面轉為動畫 WebM、Ghost 重置與 /fix 救援機制深度重構，以及多引擎與容器隔離強化。

- **核心架構**：導入 Overlay 虛擬環境（自我修復 `.pth` 機制）、全域技能快取架構 v3、PEP 370 使用者套件重定向。
- **Ghost 重置與 /fix 重構**：訊息佇列整併進 `task_memo.txt` 主動拉取機制，統一 `.rotation_flag`/`.fix_flag` 鎖定，消除重啟死鎖風險。
- **Avatar Generator v2**：全面升級為動畫 WebM 格式，新增絕對鎖定機制、5 代歷史備份、`/avatar_renew list`/`restore`。
- **多引擎 CLI 支援**：新增 Antigravity CLI (agy) 引擎。
- **容器與權限隔離**：重構 Docker `entrypoint.sh` chown 邏輯改為非遞迴限縮範圍；Agent 目錄套用 Sticky Bit。

詳見 [Release v1.0.0-beta.6-zh](https://github.com/meso4444/OctoMatrix/releases/tag/v1.0.0-beta.6-zh)。

## [v1.0.0-beta.5] 及更早版本 - 2026-06-15 及之前

v1.0.0-beta.5 為本 CHANGELOG 開始追蹤前的既有基準版本，此前（beta 至 beta.5）的逐版異動未回溯整理，如需查閱請參考 GitHub Releases 頁面的既有版本說明或 commit 歷史。
