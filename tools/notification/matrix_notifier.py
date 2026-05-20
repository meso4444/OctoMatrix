#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📢 Unified Notifier (matrix_notifier.py)
Cross-platform notification center - Format translation and automatic fallback

Responsibilities:
1. Unified interface: notify(target_platform, template_id, context)
2. Cross-platform format rendering: compatible with legacy (icon/title/content) and new (platform-specific) templates
3. Automatic fallback: If primary channel fails, automatically switch to fallback channel
4. Multi-platform support: TG (HTML) / DS (Markdown) / SL (Plain Text)
"""

import os
import sys
import json
import logging
import argparse
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime

import requests
import yaml
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# ============================================================================
# Configuration and logging
# ============================================================================

# Dynamically load project root directory to sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = _current_dir
for _ in range(5):
    if os.path.exists(os.path.join(_root_dir, 'config.py')):
        if _root_dir not in sys.path:
            sys.path.insert(0, _root_dir)
        break
    _root_dir = os.path.dirname(_root_dir)

_log_handlers = [logging.StreamHandler()]
try:
    _log_handlers.append(logging.FileHandler('/tmp/matrix_notifier.log'))
except PermissionError:
    # Prevent multi-user permission conflicts in containers
    pass

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=_log_handlers
)
logger = logging.getLogger(__name__)

# Notification service configuration
try:
    from config import MESSAGE_TEMPLATES_PATH, TELEGRAM_BOT_TOKEN
    TEMPLATES_PATH = MESSAGE_TEMPLATES_PATH
except ImportError:
    from pathlib import Path
    _cur_dir = Path(__file__).resolve().parent
    TEMPLATES_PATH = str(_cur_dir / 'message_templates.yaml')
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

TELEGRAM_API_BASE_URL = "https://api.telegram.org/bot"

try:
    from config import CONFIG_PATH
except ImportError:
    from pathlib import Path
    _cur_dir = Path(__file__).resolve().parent
    CONFIG_PATH = os.getenv('CONFIG_PATH', str(_cur_dir / 'config.yaml'))
# Platform API endpoints
DISCORD_API_URL = "https://discord.com/api/v10"
SLACK_API_URL = "https://slack.com/api"


class PlatformEnum(str, Enum):
    """Communication platform enumeration"""
    TELEGRAM = 'telegram'
    DISCORD = 'discord'
    SLACK = 'slack'
    EMAIL = 'email'


# ============================================================================
# Template management
# ============================================================================

class TemplateManager:
    """
    Message template manager
    """

    def __init__(self, templates_path: str):
        self.templates = self._load_templates(templates_path)
        logger.info(f"[Notifier] Templates loaded: {templates_path}")

    def _load_templates(self, path: str) -> dict:
        """Load message template configuration"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"[Notifier] Template load failed: {e}")
            return {}

    def render(self, platform: str, template_id: str, context: Dict[str, Any]) -> str:
        """
        Render message template based on platform
        """
        software = context.get('software')
        all_templates = self.templates.get("templates", {})
        sw_templates = self.templates.get("software_templates", {})

        # 1. Priority lookup for software-specific templates
        template_entry = None
        if software and software in sw_templates:
            template_entry = sw_templates[software].get(template_id)

        # 2. Fallback to generic template
        if not template_entry:
            template_entry = all_templates.get(template_id, {})

        if not template_entry:
            return context.get('content', f"[Unknown template: {template_id}]")

        # 3. Get platform-specific content or perform legacy merge
        template = template_entry.get(platform)
        if not template:
            # Handle legacy icon + title + content structure
            icon = template_entry.get('icon', '')
            title = template_entry.get('title', '')
            body = template_entry.get('content', '')

            if icon or title or body:
                template = f"{icon} {title}\n\n{body}".strip()
            else:
                # Avoid converting entire dict to string causing format_map parsing failure
                template = f"[{template_id}] Notification: {context.get('content', '')}"

        # Prepare base context
        full_context = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'platform': platform
        }
        full_context.update(context)

        class SafeDict(dict):
            def __missing__(self, key):
                return '{' + key + '}'

        rendered_text = str(template)
        if isinstance(template, str):
            try:
                rendered_text = template.format_map(SafeDict(full_context))
            except Exception as e:
                logger.error(f"[Notifier] Rendering error: {e}")

        # --- Cross-platform tag auto-translation (HTML -> Markdown) ---
        if platform == 'discord':
            rendered_text = rendered_text.replace('<b>', '**').replace('</b>', '**')
            rendered_text = rendered_text.replace('<i>', '*').replace('</i>', '*')
            rendered_text = rendered_text.replace('<code>', '`').replace('</code>', '`')
            rendered_text = rendered_text.replace('<pre>', '```\n').replace('</pre>', '\n```')
        elif platform == 'slack':
            rendered_text = rendered_text.replace('<b>', '*').replace('</b>', '*')
            rendered_text = rendered_text.replace('<i>', '_').replace('</i>', '_')
            rendered_text = rendered_text.replace('<code>', '`').replace('</code>', '`')
            rendered_text = rendered_text.replace('<pre>', '```\n').replace('</pre>', '\n```')

        return rendered_text.strip()


# ============================================================================
# Platform Senders
# ============================================================================

class TelegramSender:
    def __init__(self, bot_token: str):
        self.api_url = f"https://api.telegram.org/bot{bot_token}"

    def send(self, chat_id: str, message: str, parse_mode: str = 'HTML', **kwargs) -> bool:
        try:
            chunks = [message[i:i+3800] for i in range(0, len(message), 3800)]
            success = True
            for chunk in chunks:
                data = {'chat_id': chat_id, 'text': chunk, 'parse_mode': parse_mode}
                # Telegram-specific keyboard support
                if 'reply_markup' in kwargs: data["reply_markup"] = kwargs["reply_markup"]
                resp = requests.post(f"{self.api_url}/sendMessage", json=data, timeout=5)
                if resp.status_code != 200: success = False
            return success
        except: return False

    def send_file(self, chat_id: str, file_path: str, file_type: str = 'document', caption: str = '', **kwargs) -> bool:
        try:
            method = {'photo': 'sendPhoto', 'video': 'sendVideo', 'audio': 'sendAudio'}.get(file_type, 'sendDocument')
            param = 'photo' if file_type == 'photo' else ('video' if file_type == 'video' else ('audio' if file_type == 'audio' else 'document'))
            with open(file_path, 'rb') as f:
                data = {'chat_id': chat_id, 'caption': caption[:1000], 'parse_mode': 'HTML'}
                resp = requests.post(f"{self.api_url}/{method}", files={param: f}, data=data, timeout=30)
                return resp.status_code == 200
        except: return False


class DiscordSender:
    def __init__(self, bot_token: str):
        self.headers = {'Authorization': f'Bot {bot_token}'}

    def send(self, channel_id: str, message: str, **kwargs) -> bool:
        try:
            chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
            success = True
            for chunk in chunks:
                resp = requests.post(f"{DISCORD_API_URL}/channels/{channel_id}/messages", json={'content': chunk}, headers=self.headers, timeout=5)
                if resp.status_code not in [200, 201]: success = False
            return success
        except: return False

    def send_file(self, channel_id: str, file_path: str, caption: str = '', **kwargs) -> bool:
        try:
            with open(file_path, 'rb') as f:
                data = {'content': caption[:1900]}
                resp = requests.post(f"{DISCORD_API_URL}/channels/{channel_id}/messages", files={'file': (os.path.basename(file_path), f)}, data=data, headers=self.headers, timeout=30)
                return resp.status_code in [200, 201]
        except: return False


class SlackSender:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.client = WebClient(token=bot_token)
        self.headers = {'Authorization': f'Bearer {bot_token}'}

    def send(self, channel_id: str, message: str, **kwargs) -> bool:
        try:
            chunks = [message[i:i+3800] for i in range(0, len(message), 3800)]
            success = True
            for chunk in chunks:
                resp = self.client.chat_postMessage(channel=channel_id, text=chunk)
                if not resp.get('ok'):
                    logger.error(f"[Notifier] Slack send failed: {resp.get('error')}")
                    success = False
            return success
        except SlackApiError as e:
            logger.error(f"[Notifier] Slack API error: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"[Notifier] Slack send unknown error: {e}")
            return False

    def send_file(self, channel_id: str, file_path: str, caption: str = '', **kwargs) -> bool:
        try:
            # Use files_upload_v2 to auto-handle new three-stage upload flow (2025+ standard)
            resp = self.client.files_upload_v2(
                channel=channel_id,
                file=file_path,
                initial_comment=caption[:1900],
                title=os.path.basename(file_path)
            )
            if resp.get('ok'):
                return True
            else:
                logger.error(f"[Notifier] Slack file upload failed (v2): {resp.get('error')}")
                return False
        except SlackApiError as e:
            logger.error(f"[Notifier] Slack API upload error: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"[Notifier] Slack file upload unknown error: {e}")
            return False


# ============================================================================
# Unified Notifier
# ============================================================================

class MatrixNotifier:
    def __init__(self, config_path: str = CONFIG_PATH, templates_path: str = TEMPLATES_PATH):
        self.template_manager = TemplateManager(templates_path)
        self.senders = self._initialize_senders()

    def _initialize_senders(self) -> Dict[str, Any]:
        senders = {}
        tg = os.getenv('TELEGRAM_BOT_TOKEN')
        if tg: senders['telegram'] = TelegramSender(tg)
        ds = os.getenv('DISCORD_TOKEN')
        if ds: senders['discord'] = DiscordSender(ds)
        sl = os.getenv('SLACK_BOT_TOKEN')
        if sl: senders['slack'] = SlackSender(sl)
        return senders

    def _get_target_id(self, platform):
        from config import TELEGRAM_CHAT_ID, DISCORD_CHANNEL_ID, SLACK_CHANNEL_ID
        env_id = os.environ.get(f"{platform.upper()}_CHAT_ID") or os.environ.get(f"{platform.upper()}_CHANNEL_ID")
        if env_id: return env_id
        return {'telegram': TELEGRAM_CHAT_ID, 'discord': DISCORD_CHANNEL_ID, 'slack': SLACK_CHANNEL_ID}.get(platform)

    def notify(self, target_platform: str, template_id: str, context: Dict[str, Any], target_id: Optional[str] = None) -> bool:
        # Check if platform is enabled
        try:
            from config import PLATFORMS_ENABLED
            if not PLATFORMS_ENABLED.get(target_platform, True):
                logger.warning(f"[Notifier] Platform {target_platform} disabled, skipping notification")
                return False
        except ImportError:
            pass

        message = self.template_manager.render(target_platform, template_id, context)
        sender = self.senders.get(target_platform)
        if not sender: return False
        if not target_id: target_id = self._get_target_id(target_platform)
        if not target_id: return False

        # Pass all platform-specific parameters
        return sender.send(target_id, message, **context.get('_platform_kwargs', {}))

    def notify_file(self, target_platform: str, file_path: str, file_type: str = 'document', caption: str = '', target_id: Optional[str] = None) -> bool:
        # Check if platform is enabled
        try:
            from config import PLATFORMS_ENABLED
            if not PLATFORMS_ENABLED.get(target_platform, True):
                logger.warning(f"[Notifier] Platform {target_platform} disabled, skipping file send")
                return False
        except ImportError:
            pass

        sender = self.senders.get(target_platform)
        if not sender: return False
        if not target_id: target_id = self._get_target_id(target_platform)
        if not target_id: return False

        if target_platform == 'telegram': return sender.send_file(target_id, file_path, file_type, caption)
        return sender.send_file(target_id, file_path, caption)


def get_router_url() -> str:
    curr = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        port_file = os.path.join(curr, '.router_port')
        if os.path.exists(port_file):
            try:
                with open(port_file, 'r') as f:
                    p = f.read().strip()
                    if p: return f"http://localhost:{p}"
            except: pass
        curr = os.path.dirname(curr)
    return f"http://localhost:{os.getenv('ROUTER_PORT', 12210)}"

def get_source_info():
    curr = os.path.dirname(os.path.abspath(__file__))
    enabled_platforms = {}
    default_platform = 'telegram'

    # Try to get default primary channel and enabled status from config
    try:
        from config import DEFAULT_PRIMARY_CHANNEL, PLATFORMS_ENABLED
        default_platform = DEFAULT_PRIMARY_CHANNEL
        enabled_platforms = PLATFORMS_ENABLED

        # If default channel is disabled, auto-select first enabled channel
        if not enabled_platforms.get(default_platform, False):
            active = [k for k, v in enabled_platforms.items() if v]
            if active: default_platform = active[0]
    except ImportError:
        pass

    for _ in range(4):
        path = os.path.join(curr, '.last_source')
        if os.path.exists(path):
            try:
                import json
                with open(path, 'r') as f:
                    source = json.load(f)
                    p = source.get('platform')
                    # If source platform is disabled, force downgrade to default platform
                    if enabled_platforms and p and not enabled_platforms.get(p, False):
                        source['platform'] = default_platform
                    return source
            except: pass
        curr = os.path.dirname(curr)
    return {'platform': default_platform}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='OctoMatrix Matrix Notifier CLI (Multi-Channel)')
    parser.add_argument('message', nargs='*', help='Message content')
    parser.add_argument('--file', nargs=2, metavar=('TYPE', 'PATH'), help='Send a file (type: photo, video, audio, document)')
    parser.add_argument('--caption', help='Caption for the file')
    parser.add_argument('--template', default='custom', help='Template ID to use')
    parser.add_argument('--software', help='Software name for template lookup')
    parser.add_argument('--keyboard', help='JSON string for TG custom keyboard')
    parser.add_argument('--get-id', action='store_true', help='Helper to find Telegram Chat ID')

    # Intercept sys.argv to safely handle dash-prefixed messages
    import sys
    known_flags = {'--file': 2, '--caption': 1, '--template': 1, '--software': 1, '--keyboard': 1, '--get-id': 0, '-h': 0, '--help': 0}
    new_argv = []
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in known_flags:
            new_argv.append(arg)
            n = known_flags[arg]
            for _ in range(n):
                i += 1
                if i < len(sys.argv):
                    new_argv.append(sys.argv[i])
        else:
            new_argv.append('--')
            new_argv.extend(sys.argv[i:])
            break
        i += 1

    args = parser.parse_args(new_argv)

    if args.get_id:
        if not TELEGRAM_BOT_TOKEN: print("❌ Missing TELEGRAM_BOT_TOKEN"); sys.exit(1)
        resp = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates").json()
        if resp.get('result'):
            print(f"✅ Latest Chat ID: {resp['result'][-1]['message']['chat']['id']}")
        else:
            print("⚠️ No updates found. Send a message to your bot first.")
        sys.exit(0)

    source = get_source_info()
    platform = source.get('platform', 'telegram')

    target_id = source.get('channel_id')
    if not target_id and platform == 'telegram': target_id = source.get('user_id')

    context = {'software': args.software} if args.software else {}
    if args.keyboard:
        # Only Telegram supports this parameter
        try: context['_platform_kwargs'] = {'reply_markup': json.loads(args.keyboard)}
        except: print("❌ Invalid keyboard JSON")

    router_url = get_router_url()

    if args.file:
        f_type, f_path = args.file
        caption = (args.caption or " ".join(args.message)).replace('\\n', '\n')
        if not os.path.exists(f_path): print(f"❌ File not found: {f_path}"); sys.exit(1)
        try:
            with open(f_path, 'rb') as f:
                # [Optimization] Only send if target_id is valid, avoid passing invalid strings
                payload = {'platform': platform, 'file_type': f_type, 'caption': caption}
                if target_id and str(target_id).lower() not in ['none', 'null', 'undefined']:
                    payload['target_id'] = target_id

                resp = requests.post(f"{router_url}/notify_file", files={'file': f}, data=payload, timeout=30)
                if resp.status_code == 200: print(f"✅ File sent via Router to {platform}"); sys.exit(0)
                else: print(f"❌ Router Error: {resp.status_code}"); sys.exit(1)
        except Exception as e: print(f"❌ Error: {e}"); sys.exit(1)

    elif args.message or args.template != 'custom':
        msg_content = " ".join(args.message).replace('\\n', '\n')
        context['content'] = msg_content
        payload = {'platform': platform, 'template_id': args.template, 'context': context, 'target_id': target_id}
        try:
            resp = requests.post(f"{router_url}/notify", json=payload, timeout=10)
            if resp.status_code == 200: print(f"✅ Message sent via Router to {platform}"); sys.exit(0)
            else: print(f"❌ Router Error: {resp.status_code}"); sys.exit(1)
        except Exception as e: print(f"❌ Error: {e}"); sys.exit(1)
    else:
        parser.print_help()
