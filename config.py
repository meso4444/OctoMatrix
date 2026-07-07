# Copyright 2026 meso4444
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# config.py - Configuration Loader (ISC - Instance-Specific Config)
# 支援三層疊加：Base YAML -> Instance YAML -> Environment
import os
import sys
import yaml
import json
from copy import deepcopy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==========================================
# 第一層: 載入 .env (通用)
# ==========================================
def _load_env_file(env_path):
    """載入 .env 檔案到環境變數 (不覆蓋已存在的)"""
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if key not in os.environ:
                        os.environ[key] = value.strip('"\'')
    except Exception as e:
        sys.stderr.write(f"⚠️  無法讀取 {env_path}: {e}\n")

# 載入通用 .env
_load_env_file(os.path.join(BASE_DIR, '.env'))

# ==========================================
# 第二層: 載入 Instance 專屬 .env (如果有)
# ==========================================
INSTANCE_NAME = os.environ.get('INSTANCE_NAME', '')
if INSTANCE_NAME:
    _instance_env_path = os.path.join(BASE_DIR, f'.env.{INSTANCE_NAME}')
    _load_env_file(_instance_env_path)
    # 也檢查 docker-deploy 目錄
    _docker_env_path = os.path.join(BASE_DIR, 'docker-deploy', '.env')
    _load_env_file(_docker_env_path)

# 3. 載入 YAML 配置 (ISC: Instance-Specific Config)
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
INSTANCE_CONFIG_PATH = os.path.join(BASE_DIR, f"config.{INSTANCE_NAME}.yaml")
AWAKE_YAML_PATH = os.path.join(BASE_DIR, "awake.yaml")

def load_yaml(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

def _deep_merge(base, override):
    """遞迴合併字典，支援巢狀配置"""
    if not isinstance(base, dict) or not isinstance(override, dict):
        return deepcopy(override)
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result

_config = load_yaml(CONFIG_PATH)
_instance_config = load_yaml(INSTANCE_CONFIG_PATH)

# 合併配置 (實例配置優先，支援遞迴深層合併)
if _instance_config:
    _config = _deep_merge(_config, _instance_config)

# 4. 變數映射與環境變數覆蓋 (擴展：三通道憑證支援)

# ==========================================
# 使用者資訊
# ==========================================
MATRIX_USERNAME = os.environ.get("MATRIX_USERNAME", _config.get("matrix_username", "User"))

# ==========================================
# Telegram 平臺配置
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ==========================================
# Discord 平臺配置 (新增)
# ==========================================
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
DISCORD_SERVER_ID = os.environ.get("DISCORD_SERVER_ID", "")
DISCORD_CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "")

# ==========================================
# Slack 平臺配置 (新增)
# ==========================================
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_WORKSPACE_ID = os.environ.get("SLACK_WORKSPACE_ID", "")
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID", "")

# ==========================================
# OctoMatrix Router 配置 (新增)
# ==========================================
ROUTER_HOST = os.environ.get("ROUTER_HOST", _config.get("router", {}).get("host", "0.0.0.0"))
ROUTER_PORT = int(os.environ.get("ROUTER_PORT", _config.get("router", {}).get("port", 12210)))

_api_host = "127.0.0.1" if ROUTER_HOST == "0.0.0.0" else ROUTER_HOST
ROUTER_INJECT_ENDPOINT = f"http://{_api_host}:{ROUTER_PORT}/inject"
ROUTER_HEALTH_ENDPOINT = f"http://{_api_host}:{ROUTER_PORT}/health"
ROUTER_STATUS_ENDPOINT = f"http://{_api_host}:{ROUTER_PORT}/status"

# ngrok 配置
NGROK_AUTHTOKEN = os.environ.get("NGROK_AUTHTOKEN", "")

_registry_str = os.environ.get("BOT_REGISTRY", "{}")
try:
    BOT_REGISTRY = json.loads(_registry_str)
except Exception:
    BOT_REGISTRY = {}

# 【Port 配置統一化】Port 從 config.yaml 讀取，環境變量保留作緊急覆蓋用
TELEGRAM_GATEWAY_PORT = int(os.environ.get("TELEGRAM_GATEWAY_PORT", _config.get("server", {}).get("telegram_gateway_port", 11440)))
NGROK_API_PORT = int(os.environ.get("NGROK_API_PORT", _config.get("server", {}).get("ngrok_api_port", 4040)))

AGENTS = _config.get("agents", [])
DEFAULT_ACTIVE_AGENT = _config.get("default_active_agent", "")
TMUX_SESSION_NAME = os.environ.get("TMUX_SESSION_NAME", _config.get("tmux", {}).get("session_name", "ai_octomatrix"))
CUSTOM_MENU = _config.get("menu", [])

# ==========================================
# 電子腦配置 (Cyberbrain GHOST)
# ==========================================
_octo_config = _config.get("octo_cyberbrain", {})
CYBERBRAIN_REAPER_POLLING_INTERVAL = int(_octo_config.get("ghost_check_interval_sec", 60))
CYBERBRAIN_ROTATION_THRESHOLD_KB = int(_octo_config.get("ghost_compression_threshold_kb", 70))
CYBERBRAIN_ROLLING_MERGE_LIMIT = int(_octo_config.get("ghost_long_term_compression_limit", 12))
CYBERBRAIN_DIVE_CONTEXT_SIZE = int(_octo_config.get("ghost_awake_context_depth", 50))
CYBERBRAIN_INACTIVITY_CHECK_HOURS = int(_octo_config.get("inactivity_check_hours", 12))
CYBERBRAIN_DND_RANGE = str(_octo_config.get("dnd_range", "2200-0700"))

# ==========================================
# 消息模板加載 (新增)
# ==========================================
MESSAGE_TEMPLATES_PATH = os.path.join(BASE_DIR, "message_templates.yaml")
MESSAGE_TEMPLATES = load_yaml(MESSAGE_TEMPLATES_PATH)

# ==========================================
# 平臺適配器配置 (新增)
# ==========================================
PLATFORM_TOKENS_VALID = {
    "telegram": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
    "discord": bool(DISCORD_TOKEN and DISCORD_CHANNEL_ID),
    "slack": bool(SLACK_APP_TOKEN and SLACK_BOT_TOKEN),
}

# 通道控制與偏好設定 (Channel Control)
CHANNEL_CONTROL = _config.get('channel_control', {})
DEFAULT_PRIMARY_CHANNEL = CHANNEL_CONTROL.get('default_primary_channel', 'telegram')

# 獲取通道狀態 (必須同時滿足: Token 存在 且 設定未禁用)
PLATFORMS_ENABLED = {
    "telegram": PLATFORM_TOKENS_VALID["telegram"] and str(os.environ.get('TELEGRAM_ENABLED', 'true')).lower() == 'true' and CHANNEL_CONTROL.get('telegram', {}).get('enabled', True),
    "discord": PLATFORM_TOKENS_VALID["discord"] and str(os.environ.get('DISCORD_ENABLED', 'true')).lower() == 'true' and CHANNEL_CONTROL.get('discord', {}).get('enabled', True),
    "slack": PLATFORM_TOKENS_VALID["slack"] and str(os.environ.get('SLACK_ENABLED', 'true')).lower() == 'true' and CHANNEL_CONTROL.get('slack', {}).get('enabled', True)
}

# --- 物理類型修正：從分離的 awake.yaml 讀取喚醒配置 ---
_awake_config = load_yaml(AWAKE_YAML_PATH)
if isinstance(_awake_config, list):
    # 物理現狀：awake.yaml 是任務清單
    AWAKE_CONF = _awake_config
elif isinstance(_awake_config, dict):
    # 相容模式：awake.yaml 包含標籤
    AWAKE_CONF = _awake_config.get("awake", [])
else:
    # 異常處理
    AWAKE_CONF = []

COLLABORATION_GROUPS = _config.get("collaboration_groups", [])

# ==========================================
# 三通道憑證驗證與狀態檢查函數 (新增)
# ==========================================
def get_platform_status():
    """取得三平臺憑證狀態"""
    status = {}

    # Telegram 狀態
    status["telegram"] = {
        "enabled": PLATFORMS_ENABLED["telegram"],
        "has_token": bool(TELEGRAM_BOT_TOKEN),
        "has_chat_id": bool(TELEGRAM_CHAT_ID),
    }

    # Discord 狀態
    status["discord"] = {
        "enabled": PLATFORMS_ENABLED["discord"],
        "has_token": bool(DISCORD_TOKEN),
        "has_server_id": bool(DISCORD_SERVER_ID),
        "has_channel_id": bool(DISCORD_CHANNEL_ID),
    }

    # Slack 狀態
    status["slack"] = {
        "enabled": PLATFORMS_ENABLED["slack"],
        "has_app_token": bool(SLACK_APP_TOKEN),
        "has_bot_token": bool(SLACK_BOT_TOKEN),
        "has_workspace_id": bool(SLACK_WORKSPACE_ID),
        "has_channel_id": bool(SLACK_CHANNEL_ID),
    }

    return status

def get_available_platforms():
    """取得已啟用的平臺列表"""
    return [p for p, enabled in PLATFORMS_ENABLED.items() if enabled]
def get_agent_info(name):
    """獲取指定 Agent 的詳細資訊 (不分大小寫)"""
    for agent in AGENTS:
        if agent['name'].lower() == name.lower():
            return agent
    return None

def get_active_agent():
    """獲取當前活躍 Agent 名稱"""
    return DEFAULT_ACTIVE_AGENT

# 系統提示前綴
SYS_PREFIX = "【系統提示】"

# Agent 專屬 Linux 帳號密碼 (Local 雙軌隔離用)
AGENT_PASSWORD = str(os.environ.get("AGENT_PASSWORD", _config.get("agent_password", "octomatrix")))

# ==========================================
# 額外 Prompt 與 Text 模板
# ==========================================

AVATAR_RENEW_PROMPT = """【系統安全授權指令：Avatar 形象更新程序】
用戶已正式發起 /avatar_renew 請求。
授權解鎖金鑰：--token {token}
用戶具體需求：{requirement}

在執行任何動作之前，你必須嚴格遵守以下 [安全與防護 SOP]：

[Step 1 - 需求合規性檢驗]：
仔細審視用戶提出的形象或配件需求。將其與 `AGENT_AVATAR_GUIDE.md` 及 `octo_generator.py` 目前所支援的能力邊界進行比對。
- 若用戶要求了不支援的畫風、配件、或任何違反 OctoMatrix 形象規範的元素（例如：寫實人類相片、血腥、或是生成器不支援的特定裝備），進入 [Step 1-Reject]。
- 若需求完全合規，進入 [Step 2]。

[Step 1-Reject - 溫和拒絕與替代方案]：
向用戶明確說明目前生成系統無法支援該需求（請保持你的角色性格），並主動提供 1 到 2 個「目前系統可支援的相近替代方案」供用戶選擇。在用戶同意替代方案前，絕對禁止執行任何產圖指令。

[Step 2 - 嚴格腳本執行限制]：
確認需求後，開始執行產圖。
⚠️ 【最高紅色警戒】：
1. 你僅能且必須使用原生的 `toolbox/octo_generator.py` 來進行生成。
2. 絕對禁止使用任何其他腳本，絕對禁止撰寫新的 Python/Shell 腳本來產圖。
3. 絕對禁止對 `octo_generator.py` 進行任何形式的複製 (Clone)、修改 (Modify) 或覆寫 (Overwrite)。
4. 呼叫腳本時，請參照 `knowledge/AGENT_AVATAR_GUIDE.md` 中的指令範例來設定各項參數，並务必附上授權金鑰 `--token {token}`。

[Step 3 - 結果回報]：
生成完畢並自動打包上傳後，向用戶回報形象更新結果，並附上最新生成的心情貼圖展示。"""

USER_MESSAGE_SOP = f"""{SYS_PREFIX}
執行以下 [SOP]:
[Step 0 - 共情]：執行 python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.webm 發符合當下心情的貼圖。
[Step 1 - 辨識]：辨識 {MATRIX_USERNAME} 用戶的訊息為任務或問候，若為任務則進入Step2; 若為問候則執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，並自主思考合適的問候回覆}}' 回應，並且不執行後續Step。
[Step 2 - 預告]：執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，並自主思考合適的初步預告}}' 預告任務進行初步方向。
[Step 3 - 梳理]：若任務指示明確進入Step4; 若不明確，深潛shell紀錄後若有歷史脈絡進入Step4，否則先中止並執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，自主思考合適的詢問或澄清}}' 詢問具體方向，不執行後續Step。
[Step 4 - 執行]：正式開始執行任務並撰寫md。小型任務完成後進入Step5; 大型任務中途執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，自主思考合適的進度回報}}' 進行中間進度回報，任務完成後再進入Step5。
[Step 5 - 共情]：執行 python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.webm 發符合當下心情的貼圖。
[Step 6 - 回報]：執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，自主思考合適的任務完成報告}}' 彙總回報，只有當回報內容大於1000字時才搭配使用 --file 發送相關報告文檔給 {MATRIX_USERNAME}，否則直接以完整訊息彙報。
[Step 7 - 收攝]：執行 python3 octo_cyberbrain/octo_ghost_reader.py --level current 收攝你的 GHOST 與記憶。
[Step 8 - 刻印]：執行 python3 octo_cyberbrain/octo_ghost_updater.py --outline "語義大綱" --keywords "關鍵字1,關鍵字2" --paths "/檔案路徑1,/檔案路徑2" 將本次任務狀態刻印到GHOST。"""

def get_help_text(CURRENT_AGENT):
    help_text = "📖 <b>OctoMatrix 系統全功能指南</b>\n\n"
    help_text += f"<b>🎯 當前關注 Agent:</b> <code>{CURRENT_AGENT}</code>\n\n"
    help_text += "───────────────────────────────\n\n"
    help_text += "<b>🤖 對話與基礎操作</b>\n"
    help_text += "• <b>直接發送</b>：訊息將傳送給標註 ⭐ 的活躍 Agent。\n"
    help_text += "• <b>發送圖片</b>：自動執行多模態分析（僅限 Telegram/Discord）。\n"
    help_text += "• <code>/switch [名稱]</code>：切換當前對話的活躍 Agent。\n"
    help_text += "• <code>/menu</code>：彈出實體管理按鍵選單（手機端推薦）。\n\n"
    help_text += "<b>🔍 監控與診斷</b>\n"
    help_text += "• <code>/status</code>：查看所有 Agent 存活、喚醒內容與通道連通性。\n"
    help_text += "• <code>/capture [名稱]</code>：擷取指定視窗最近 50 行內容，檢查運行報錯。\n"
    help_text += "• <code>/inspect [名稱]</code>：指派當前的 AI 去檢查另一位 AI 的狀態與錯誤訊息。\n\n"
    help_text += "<b>🛠️ 控制與修復</b>\n"
    help_text += "• <code>/interrupt</code>：向活躍 Agent 發送 Ctrl+C 強制中斷卡死的程序。\n"
    help_text += "• <code>/clear</code>：清除視窗畫面與 Agent 的當前上下文。\n"
    help_text += "• <code>/resume_latest</code>：嘗試從 CLI 本地快取恢復最近一次的對話紀錄。\n"
    help_text += "• <code>/fix [名稱]</code>：強制重啟並嘗試恢復對話。若 AI 卡住或無回應時可使用此指令。\n"
    help_text += "• <code>/sys_refresh</code>：檢查並更新 Agent 的系統協定與規範。\n"
    help_text += "• <code>/avatar_renew {需求}</code>：重新定義並建構 Agent 的視覺形象與性格。\n"
    help_text += "• <code>/avatar_renew list</code>：查看歷史 Avatar 備份列表（附預覽圖）。\n"
    help_text += "• <code>/avatar_renew restore {編號|檔名}</code>：還原至指定歷史版本。\n\n"
    help_text += "<b>⏰ 自動化喚醒</b>\n"
    help_text += "• 請直接透過對話「要求 Agent 建立喚醒任務」，即可實現定時喚醒任務。可透過 <code>/status</code> 監控現有喚醒任務。\n\n"
    help_text += "───────────────────────────────\n"
    help_text += "💡 <b>提示</b>：Telegram 與 Discord 請使用斜線 <code>/</code> 指令；Slack 請使用驚嘆號 <code>!</code> 引導。"
    return help_text


def get_agent_intercom_sop(source_agent, message):
    return f"""{SYS_PREFIX}
執行以下 [SOP]:
[Step 0 - 共情]：執行 python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.webm 發符合當下心情的貼圖。
[Step 1 - 辨識]：辨識 Source Agent 的訊息是否為未完成協作任務，若為未完成協作任務則進入Step2; 若非則執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}報告協作任務的完成狀態}}'，並且不執行後續Step。
[Step 2 - 梳理]：若協作任務明確則執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}問候，並自主思考合適的初步預告}}' 預告協作進行的初步方向，並且進入Step3; 若不明確，則先中止任務並執行 python3 toolbox/agent_intercom.py --target "{source_agent}" --message "{{你的訊息...}}" 向 Source Agent 詢問具體方向，不執行後續Step。
[Step 3 - 執行]：正式開始執行協作任務並撰寫md。若協作任務仍需要與 Source Agent 進行階段性交接或者完工驗證，則執行 python3 toolbox/agent_intercom.py --target "{source_agent}" --message "{{你的訊息...}}" 進行 Agent 間通訊交接，且不執行後續Step; 若協作任務已確認完工或失敗則進入Step4。
[Step 4 - 共情]：執行 python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.webm 發符合當下心情的貼圖。
[Step 5 - 回報User]：執行 python3 toolbox/matrix_notifier.py '{{向{MATRIX_USERNAME}回報傳遞成功通知或失敗異常}}'。
[Step 6 - 回報Agent]：執行 python3 toolbox/agent_intercom.py --target "{source_agent}" --message "{{說明完工或失敗狀態，並且註明此訊息不需再進行Agent通訊回覆避免進入無限迴圈，若有疑義則詢問{MATRIX_USERNAME}}}"
[Step 7 - 收攝]：執行 python3 octo_cyberbrain/octo_ghost_reader.py --level current 收攝你的 GHOST 與記憶。
[Step 8 - 刻印]：執行 python3 octo_cyberbrain/octo_ghost_updater.py --outline "語義大綱" --keywords "關鍵字1,關鍵字2" --paths "/檔案路徑1,/檔案路徑2" 將本次任務狀態刻印到GHOST。

來自 {source_agent} 的訊息:
{message}

{SYS_PREFIX}請務必嚴格遵守上述 [SOP] 進行回覆。"""
