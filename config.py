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
# Supports three-layer overlay: Base YAML -> Instance YAML -> Environment
import os
import sys
import yaml
import json
from copy import deepcopy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==========================================
# Layer 1: Load .env (universal)
# ==========================================
def _load_env_file(env_path):
    """Load .env file to environment variables (without overwriting existing ones)"""
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
        sys.stderr.write(f"⚠️  Unable to read {env_path}: {e}\n")

# Load universal .env
_load_env_file(os.path.join(BASE_DIR, '.env'))

# ==========================================
# Layer 2: Load Instance-specific .env (if present)
# ==========================================
INSTANCE_NAME = os.environ.get('INSTANCE_NAME', '')
if INSTANCE_NAME:
    _instance_env_path = os.path.join(BASE_DIR, f'.env.{INSTANCE_NAME}')
    _load_env_file(_instance_env_path)
    # Also check docker-deploy directory
    _docker_env_path = os.path.join(BASE_DIR, 'docker-deploy', '.env')
    _load_env_file(_docker_env_path)

# 3. Load YAML configuration (ISC: Instance-Specific Config)
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
INSTANCE_CONFIG_PATH = os.path.join(BASE_DIR, f"config.{INSTANCE_NAME}.yaml")
AWAKE_YAML_PATH = os.path.join(BASE_DIR, "awake.yaml")

def load_yaml(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

def _deep_merge(base, override):
    """Recursively merge dictionaries, supports nested configuration"""
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

# Merge configuration (instance config takes priority, supports recursive deep merge)
if _instance_config:
    _config = _deep_merge(_config, _instance_config)

# 4. Variable mapping and environment variable override (extension: three-channel credential support)

# ==========================================
# User Information
# ==========================================
MATRIX_USERNAME = os.environ.get("MATRIX_USERNAME", _config.get("matrix_username", "User"))

# ==========================================
# Telegram Platform Configuration
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ==========================================
# Discord Platform Configuration (new)
# ==========================================
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
DISCORD_SERVER_ID = os.environ.get("DISCORD_SERVER_ID", "")
DISCORD_CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "")

# ==========================================
# Slack Platform Configuration (new)
# ==========================================
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_WORKSPACE_ID = os.environ.get("SLACK_WORKSPACE_ID", "")
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID", "")

# ==========================================
# OctoMatrix Router Configuration (new)
# ==========================================
ROUTER_HOST = os.environ.get("ROUTER_HOST", _config.get("router", {}).get("host", "0.0.0.0"))
ROUTER_PORT = int(os.environ.get("ROUTER_PORT", _config.get("router", {}).get("port", 12210)))

_api_host = "127.0.0.1" if ROUTER_HOST == "0.0.0.0" else ROUTER_HOST
ROUTER_INJECT_ENDPOINT = f"http://{_api_host}:{ROUTER_PORT}/inject"
ROUTER_HEALTH_ENDPOINT = f"http://{_api_host}:{ROUTER_PORT}/health"
ROUTER_STATUS_ENDPOINT = f"http://{_api_host}:{ROUTER_PORT}/status"

# ngrok configuration
NGROK_AUTHTOKEN = os.environ.get("NGROK_AUTHTOKEN", "")

_registry_str = os.environ.get("BOT_REGISTRY", "{}")
try:
    BOT_REGISTRY = json.loads(_registry_str)
except Exception:
    BOT_REGISTRY = {}

# 【Port configuration unification】Ports are read from config.yaml; environment variables are reserved for emergency override
TELEGRAM_GATEWAY_PORT = int(os.environ.get("TELEGRAM_GATEWAY_PORT", _config.get("server", {}).get("telegram_gateway_port", 11440)))
NGROK_API_PORT = int(os.environ.get("NGROK_API_PORT", _config.get("server", {}).get("ngrok_api_port", 4040)))

AGENTS = _config.get("agents", [])
DEFAULT_ACTIVE_AGENT = _config.get("default_active_agent", "")
TMUX_SESSION_NAME = os.environ.get("TMUX_SESSION_NAME", _config.get("tmux", {}).get("session_name", "ai_octomatrix"))
CUSTOM_MENU = _config.get("menu", [])

# ==========================================
# Cyberbrain Configuration (Cyberbrain GHOST)
# ==========================================
_octo_config = _config.get("octo_cyberbrain", {})
CYBERBRAIN_REAPER_POLLING_INTERVAL = int(_octo_config.get("ghost_check_interval_sec", 60))
CYBERBRAIN_ROTATION_THRESHOLD_KB = int(_octo_config.get("ghost_compression_threshold_kb", 70))
CYBERBRAIN_ROLLING_MERGE_LIMIT = int(_octo_config.get("ghost_long_term_compression_limit", 12))
CYBERBRAIN_DIVE_CONTEXT_SIZE = int(_octo_config.get("ghost_awake_context_depth", 50))

# ==========================================
# Message Template Loading (new)
# ==========================================
MESSAGE_TEMPLATES_PATH = os.path.join(BASE_DIR, "message_templates.yaml")
MESSAGE_TEMPLATES = load_yaml(MESSAGE_TEMPLATES_PATH)

# ==========================================
# Platform Adapter Configuration (new)
# ==========================================
PLATFORM_TOKENS_VALID = {
    "telegram": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
    "discord": bool(DISCORD_TOKEN and DISCORD_CHANNEL_ID),
    "slack": bool(SLACK_APP_TOKEN and SLACK_BOT_TOKEN),
}

# Channel control and preference settings (Channel Control)
CHANNEL_CONTROL = _config.get('channel_control', {})
DEFAULT_PRIMARY_CHANNEL = CHANNEL_CONTROL.get('default_primary_channel', 'telegram')

# Get channel status (must satisfy both: token exists AND setting is not disabled)
PLATFORMS_ENABLED = {
    "telegram": PLATFORM_TOKENS_VALID["telegram"] and str(os.environ.get('TELEGRAM_ENABLED', 'true')).lower() == 'true' and CHANNEL_CONTROL.get('telegram', {}).get('enabled', True),
    "discord": PLATFORM_TOKENS_VALID["discord"] and str(os.environ.get('DISCORD_ENABLED', 'true')).lower() == 'true' and CHANNEL_CONTROL.get('discord', {}).get('enabled', True),
    "slack": PLATFORM_TOKENS_VALID["slack"] and str(os.environ.get('SLACK_ENABLED', 'true')).lower() == 'true' and CHANNEL_CONTROL.get('slack', {}).get('enabled', True)
}

# --- Physical type correction: Read awake configuration from separate awake.yaml ---
_awake_config = load_yaml(AWAKE_YAML_PATH)
if isinstance(_awake_config, list):
    # Physical status: awake.yaml is a task list
    AWAKE_CONF = _awake_config
elif isinstance(_awake_config, dict):
    # Compatibility mode: awake.yaml contains labels
    AWAKE_CONF = _awake_config.get("awake", [])
else:
    # Exception handling
    AWAKE_CONF = []

COLLABORATION_GROUPS = _config.get("collaboration_groups", [])

# ==========================================
# Three-channel credential verification and status check functions (new)
# ==========================================
def get_platform_status():
    """Get three-platform credential status"""
    status = {}

    # Telegram status
    status["telegram"] = {
        "enabled": PLATFORMS_ENABLED["telegram"],
        "has_token": bool(TELEGRAM_BOT_TOKEN),
        "has_chat_id": bool(TELEGRAM_CHAT_ID),
    }

    # Discord status
    status["discord"] = {
        "enabled": PLATFORMS_ENABLED["discord"],
        "has_token": bool(DISCORD_TOKEN),
        "has_server_id": bool(DISCORD_SERVER_ID),
        "has_channel_id": bool(DISCORD_CHANNEL_ID),
    }

    # Slack status
    status["slack"] = {
        "enabled": PLATFORMS_ENABLED["slack"],
        "has_app_token": bool(SLACK_APP_TOKEN),
        "has_bot_token": bool(SLACK_BOT_TOKEN),
        "has_workspace_id": bool(SLACK_WORKSPACE_ID),
        "has_channel_id": bool(SLACK_CHANNEL_ID),
    }

    return status

def get_available_platforms():
    """Get list of enabled platforms"""
    return [p for p, enabled in PLATFORMS_ENABLED.items() if enabled]
def get_agent_info(name):
    """Get detailed information of specified Agent (case-insensitive)"""
    for agent in AGENTS:
        if agent['name'].lower() == name.lower():
            return agent
    return None

def get_active_agent():
    """Get current active Agent name"""
    return DEFAULT_ACTIVE_AGENT

# 系統提示前綴
SYS_PREFIX = "[System Prompt]"

# Agent 專屬 Linux 帳號密碼 (Local 雙軌隔離用)
AGENT_PASSWORD = str(os.environ.get("AGENT_PASSWORD", _config.get("agent_password", "octomatrix")))
