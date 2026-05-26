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
