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
CYBERBRAIN_INACTIVITY_CHECK_HOURS = int(_octo_config.get("inactivity_check_hours", 12))
CYBERBRAIN_DND_RANGE = str(_octo_config.get("dnd_range", "2200-0700"))

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

# System prompt prefix
SYS_PREFIX = "[IMPORTANT]"

# Agent specific Linux account password (for local dual-track isolation)
AGENT_PASSWORD = str(os.environ.get("AGENT_PASSWORD", _config.get("agent_password", "octomatrix")))


# ==========================================
# Extra Prompt and Text Templates
# ==========================================

AVATAR_RENEW_PROMPT = """[System Security Authorization Command: Avatar Renewal Procedure]
The user has officially initiated a `/avatar_renew` request.
Authorization Unlock Key: --token {token}
User Specific Requirements: {requirement}

Before executing any actions, you MUST strictly adhere to the following [Security and Protection SOP]:

[Step 1 - Requirement Compliance Validation]:
Carefully review the user's requested character image or accessory requirements. Compare them with the capabilities defined in `AGENT_AVATAR_GUIDE.md` and supported by `octo_generator.py`.
- If the user requests an unsupported art style, accessory, or any element violating the OctoMatrix character standards (e.g., realistic human photos, gore, or custom gear not supported by the generator), enter [Step 1-Reject].
- If the requirements are fully compliant, proceed to [Step 2].

[Step 1-Reject - Polite Rejection and Alternatives]:
Clearly state to the user that the current generation system cannot support the request (maintaining your character personality) and proactively suggest 1 or 2 compliant alternatives supported by the system. Do NOT run any generation commands until the user agrees to an alternative.

[Step 2 - Strict Script Execution Policy]:
Once the requirement is confirmed, begin generating.
⚠️ [CRITICAL WARNING]:
1. You can ONLY and MUST use the native `toolbox/octo_generator.py` script to generate.
2. Writing or using custom Python/Shell scripts to generate images is STRICTLY PROHIBITED.
3. Modifying, copying (cloning), or overwriting `octo_generator.py` is STRICTLY PROHIBITED.
4. When executing the script, please refer to `knowledge/AGENT_AVATAR_GUIDE.md` for the command example to configure all parameters, and make sure to append the authorization key `--token {token}`.

[Step 3 - Reporting Results]:
Once generation and automatic upload package are complete, report the result to the user and present the newly generated emoji sticker."""

USER_MESSAGE_SOP = f"""{SYS_PREFIX}
Execute the following [SOP]:
[Step 0 - Empathy]: Execute `python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.webm` to send a sticker matching your current mood.
[Step 1 - Identify]: Identify whether {MATRIX_USERNAME}'s message is a task or a greeting. If a task, proceed to Step2; if a greeting, execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME} and autonomously think of an appropriate greeting response}}'`, and do not execute subsequent Steps.
[Step 2 - Preview]: Execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME} and autonomously think of an appropriate initial preview}}'` to preview the task's initial direction.
[Step 3 - Clarify]: If task is clear, proceed to Step4; if unclear, proactively dive into keywords. If clear history exists, proceed to Step4, otherwise suspend task and execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME} and autonomously think of an appropriate clarification question}}'`, and do not execute subsequent Steps.
[Step 4 - Execute]: Start task and write md. Proceed to Step5 after task completion.
[Step 5 - Empathy]: Execute `python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.webm` to send a sticker matching your current mood.
[Step 6 - Report]: Execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME} and autonomously think of an appropriate task completion report}}'` and autonomously judge task complexity. For complex tasks, directly send related report documents to {MATRIX_USERNAME} using --file, otherwise prompt {MATRIX_USERNAME} that they can request the document if needed.
[Step 7 - Capture]: Execute `python3 octo_cyberbrain/octo_ghost_reader.py --level current` to capture your GHOST and memories.
[Step 8 - Imprint]: Execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline "Task semantic outline" --keywords "Keyword1,Keyword2" --paths "/FilePath1,/FilePath2"` to imprint task status to GHOST."""

def get_help_text(CURRENT_AGENT):
    help_text = "📖 <b>OctoMatrix System Complete Feature Guide</b>\n\n"
    help_text += f"<b>🎯 Currently Focused Agent:</b> <code>{CURRENT_AGENT}</code>\n\n"
    help_text += "───────────────────────────────\n\n"
    help_text += "<b>🤖 Conversation and Basic Operations</b>\n"
    help_text += "• <b>Direct Send</b>: Messages will be sent to the active Agent marked with ⭐.\n"
    help_text += "• <b>Send Image</b>: Automatically perform multimodal analysis (Telegram/Discord only).\n"
    help_text += "• <code>/switch [name]</code>: Switch the current active Agent for conversation.\n"
    help_text += "• <code>/menu</code>: Pop up physical management key menu (recommended for mobile).\n\n"
    help_text += "<b>🔍 Monitoring and Diagnostics</b>\n"
    help_text += "• <code>/status</code>: View all Agent survival, awake content and channel connectivity.\n"
    help_text += "• <code>/capture [name]</code>: Capture the last 50 lines of a specific window to check for runtime errors.\n"
    help_text += "• <code>/inspect [name]</code>: Assign the current AI to check another AI's status and error messages.\n\n"
    help_text += "<b>🛠️ Control and Fix</b>\n"
    help_text += "• <code>/interrupt</code>: Send Ctrl+C to the active Agent to forcefully interrupt a frozen process.\n"
    help_text += "• <code>/clear</code>: Clear the window display and the Agent's current context.\n"
    help_text += "• <code>/resume_latest</code>: Attempt to restore the last conversation record from CLI local cache.\n"
    help_text += "• <code>/fix [name]</code>: Force restart and attempt to recover the conversation. Use this if the AI is stuck or unresponsive.\n"
    help_text += "• <code>/sys_refresh</code>: Check and update the Agent's system protocol and specification.\n"
    help_text += "• <code>/avatar_renew {requirements}</code>: Redefine and reconstruct the Agent's visual avatar and persona.\n"
    help_text += "• <code>/avatar_renew list</code>: View the Avatar backup history list (with preview images).\n"
    help_text += "• <code>/avatar_renew restore {backup_id|filename}</code>: Restore to a specific historical version.\n\n"
    help_text += "<b>⏰ Automated Wake-up</b>\n"
    help_text += "• Ask the Agent directly to \"create a wake-up task\" to establish a scheduled wake-up task. You can monitor existing tasks via <code>/status</code>.\n\n"
    help_text += "───────────────────────────────\n"
    help_text += "💡 <b>Tip</b>: Use slash <code>/</code> for Telegram and Discord; use exclamation mark <code>!</code> for Slack."
    return help_text


def get_agent_intercom_sop(source_agent, message):
    return f"""{SYS_PREFIX}
Execute the following [SOP]:
[Step 0 - Empathize]: Execute `python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.webm` to send a sticker matching the current mood.
[Step 1 - Identify]: Identify if the Source Agent's message is an unfinished collaboration task. If it is an unfinished collaboration task, proceed to Step2; if not, execute `python3 toolbox/matrix_notifier.py '{{Report the completion status of the collaboration task to {MATRIX_USERNAME}}}'`, and do not execute subsequent Steps.
[Step 2 - Clarify]: If the collaboration task is clear, execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME} and autonomously think of an appropriate initial preview}}'` to preview the initial direction of the collaboration, and proceed to Step3; if unclear, suspend the task and execute `python3 toolbox/agent_intercom.py --target "{source_agent}" --message "{{Your message...}}"` to ask the Source Agent for specific directions, and do not execute subsequent Steps.
[Step 3 - Execute]: Officially start the collaboration task and write md. If the task still requires a phased handover or completion verification with the Source Agent, execute `python3 toolbox/agent_intercom.py --target "{source_agent}" --message "{{Your message...}}"` for inter-agent handover, and do not execute subsequent Steps; if the collaboration task is confirmed completed or failed, proceed to Step4.
[Step 4 - Empathize]: Execute `python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.webm` to send a sticker matching the current mood.
[Step 5 - Report to User]: Execute `python3 toolbox/matrix_notifier.py '{{Report successful transfer or failure exception to {MATRIX_USERNAME}}}'`.
[Step 6 - Report to Agent]: Execute `python3 toolbox/agent_intercom.py --target "{source_agent}" --message "{{Explain the completed or failed status, and note that this message does not require an Agent communication reply to avoid an infinite loop. If in doubt, ask {MATRIX_USERNAME}}}"`
[Step 7 - Absorb]: Execute `python3 octo_cyberbrain/octo_ghost_reader.py --level current` to absorb your GHOST and memory.
[Step 8 - Engrave]: Execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline "Semantic Outline" --keywords "keyword1,keyword2" --paths "/file/path1,/file/path2"` to engrave this task's status into GHOST.

Message from {source_agent}:
{message}

{SYS_PREFIX} Please strictly follow the [SOP] above to reply."""
