#!/usr/bin/env python3
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

# -*- coding: utf-8 -*-
"""
📲 Slack Socket Mode Gateway (slack_socket_gateway.py)
Slack Socket Mode listening and message forwarding

Responsibilities:
1. Establish Slack Socket Mode connection (no public webhook needed)
2. Listen to messages from specified channels
3. Convert to unified format and send to Router
4. Handle Slack-specific events and authorization

Tech Stack:
- slack_sdk.socket_mode: Socket Mode connection
- requests: Synchronous POST requests to Router

Advantages:
- No public webhook required, higher security
- Direct WebSocket internal tunnel communication
- Support for bidirectional message flow
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from typing import Optional, Set, Dict, Any

from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
import requests
import yaml

# ============================================================================
# Configuration and Logging
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/tmp/slack_gateway.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Slack Configuration
SLACK_APP_TOKEN = os.getenv('SLACK_APP_TOKEN')  # Starting with xapp-...
SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')   # Starting with xoxb-...
ROUTER_HOST = os.getenv('ROUTER_HOST', 'localhost')
ROUTER_PORT = int(os.getenv('ROUTER_PORT', 12210))

# ============================================================================
# Configuration Loading
# ============================================================================

def load_config() -> dict:
    """Load unified configuration"""
    try:
        from config import _config
        logger.info(f"[Slack] Unified configuration loaded")
        return _config
    except Exception as e:
        logger.error(f"[Slack] Configuration loading failed: {e}")
        return {}


# ============================================================================
# Media Management
# ============================================================================

class ImageManager:
    """Image Manager: Download files from Slack (with auth handling)"""
    def __init__(self, base_dir):
        self.base_dir = base_dir

    def download_slack_file(self, file_info: dict, agent_name: str):
        try:
            agent_img_dir = os.path.join(self.base_dir, 'agent_home', agent_name, 'downloads_temp')
            os.makedirs(agent_img_dir, exist_ok=True)

            url = file_info.get('url_private')
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_info.get('name')}"
            local_path = os.path.join(agent_img_dir, filename)

            # 🔐 Key: Downloading Slack private files requires Bot Token
            headers = {'Authorization': f'Bearer {SLACK_BOT_TOKEN}'}
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                with open(local_path, 'wb') as f:
                    f.write(resp.content)
                logger.info(f"📸 Slack image downloaded to [{agent_name}]: {local_path}")
                return local_path
            else:
                logger.error(f"❌ Slack download failed (Status: {resp.status_code})")
                return None
        except Exception as e:
            logger.error(f"❌ Slack image download failed: {e}")
            return None

image_manager = ImageManager(os.path.dirname(os.path.abspath(__file__)))

# ============================================================================
# Slack Socket Mode Gateway
# ============================================================================

class SlackSocketGateway:
    """
    Slack Socket Mode listening and forwarding

    Process:
    1. Establish Socket Mode connection
    2. Receive message events
    3. Verify authorization (channel + user)
    4. Convert to MCMessage format
    5. Synchronously POST to Router /inject endpoint
    """

    def __init__(self, config: dict):
        self.config = config
        self.router_url = f"http://{ROUTER_HOST}:{ROUTER_PORT}/inject"

        # Slack clients
        self.web_client = WebClient(token=SLACK_BOT_TOKEN)
        self.socket_client = SocketModeClient(
            app_token=SLACK_APP_TOKEN,
            trace_enabled=False
        )

        # Authorization settings
        self.authorized_channels: Set[str] = set()
        self.authorized_users: Set[str] = set()
        self._load_auth_from_config()

        # Event handler
        self.socket_client.socket_mode_request_listeners.append(self.handle_event)

        logger.info(f"[Slack] Gateway initialized")
        logger.info(f"[Slack] Authorized channels: {self.authorized_channels}")
        logger.info(f"[Slack] Authorized users: {self.authorized_users}")

    def _load_auth_from_config(self):
        """Load authorized channels and users from configuration file"""
        slack_config = self.config.get('CHANNELS', {}).get('slack', {})

        if 'authorized_channels' in slack_config:
            self.authorized_channels = set(slack_config['authorized_channels'])

        if 'authorized_users' in slack_config:
            self.authorized_users = set(slack_config['authorized_users'])

        # Get Bot's own info to prevent loops
        try:
            auth_test = self.web_client.auth_test()
            self.bot_user_id = auth_test.get("user_id")
            logger.info(f"[Slack] Bot User ID confirmed: {self.bot_user_id}")
        except Exception as e:
            logger.error(f"[Slack] Unable to get Bot info: {e}")
            self.bot_user_id = None

    def handle_event(self, client: SocketModeClient, req: SocketModeRequest):
        """
        Socket Mode event handler
        """
        try:
            # Immediately acknowledge event receipt
            response = SocketModeResponse(envelope_id=req.envelope_id)
            client.send_socket_mode_response(response)

            # 1. Handle standard events (like messages)
            if req.type == "events_api":
                event = req.payload.get("event", {})
                event_type = event.get("type")

                if event_type == "message":
                    self.handle_message(event)
                elif event_type == "app_mention":
                    self.handle_message(event)

            # 2. Handle interactive components (like button clicks)
            elif req.type == "interactive":
                payload = req.payload

                # Handle button clicks
                if payload.get("type") == "block_actions":
                    self.handle_interactive(payload)

                # Handle Modal submission
                elif payload.get("type") == "view_submission":
                    self.handle_modal_submission(payload)

        except Exception as e:
            logger.error(f"[Slack] Event handling error: {e}")

    def handle_modal_submission(self, payload: Dict[str, Any]):
        """Handle Slack Modal submission"""
        view = payload.get("view", {})
        private_metadata = view.get("private_metadata", "")
        if not private_metadata:
            return

        try:
            metadata = json.loads(private_metadata)
            command_template = metadata.get("command_template")
            label = metadata.get("label")
            channel_id = metadata.get("channel_id")

            # Get user input values
            state_values = view.get("state", {}).get("values", {})
            user_input = ""
            for block_id, actions in state_values.items():
                if "input_action" in actions:
                    user_input = actions["input_action"].get("value", "")
                    break

            if not user_input:
                return

            # Format command
            final_cmd = command_template.replace('{input}', user_input)
            user_id = payload.get("user", {}).get("id")
            username = payload.get("user", {}).get("name", user_id)

            logger.info(f"[Slack] Modal submitted: {final_cmd} (From: {username})")

            # Forward to Router
            self.forward_to_router(user_id, username, channel_id, final_cmd, payload)

        except Exception as e:
            logger.error(f"[Slack] Modal handling error: {e}")

    def handle_interactive(self, payload: Dict[str, Any]):
        """Handle interactive events like button clicks"""
        actions = payload.get("actions", [])
        if not actions:
            return

        action = actions[0]
        action_id = action.get("action_id", "")

        if action_id.startswith("mc_cmd_"):
            label = action_id.replace("mc_cmd_", "")
            cmd = action.get("value")
            user_id = payload.get("user", {}).get("id")
            username = payload.get("user", {}).get("name", user_id)
            channel_id = payload.get("channel", {}).get("id")
            trigger_id = payload.get("trigger_id")

            # Check if Modal needs to pop up
            if '{input}' in cmd:
                self.open_input_modal(trigger_id, label, cmd, channel_id)
                return

            logger.info(f"[Slack] Button clicked: {cmd} (From: {username})")

            # Forward to Router
            self.forward_to_router(user_id, username, channel_id, cmd, payload)

    def open_input_modal(self, trigger_id: str, label: str, command_template: str, channel_id: str):
        """Open Slack parameter input Modal"""
        try:
            view = {
                "type": "modal",
                "title": {"type": "plain_text", "text": f"Command Input: {label}"},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "input_block",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "input_action",
                            "placeholder": {"type": "plain_text", "text": "e.g.: Gupa"}
                        },
                        "label": {"type": "plain_text", "text": f"Please enter {label} parameter"}
                    }
                ],
                "submit": {"type": "plain_text", "text": "Execute"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "private_metadata": json.dumps({
                    "command_template": command_template,
                    "label": label,
                    "channel_id": channel_id
                })
            }

            self.web_client.views_open(trigger_id=trigger_id, view=view)
        except Exception as e:
            logger.error(f"[Slack] Failed to open Modal: {e}")

    def handle_message(self, event: Dict[str, Any]):
        """
        Handle Slack message events
        """
        # Ignore subtypes (bot messages, etc.)
        if event.get("subtype") in ["bot_message", "message_deleted"]:
            return

        # Extract basic info
        user_id = event.get("user")
        bot_id = event.get("bot_id")
        channel_id = event.get("channel")
        text = event.get("text", "")

        # 1. Thoroughly filter Bot's own messages
        if user_id == self.bot_user_id or bot_id is not None:
            return

        # 2. Handle menu commands and custom prefixes (Slack-specific: ! as command prefix)
        clean_text = text.strip()
        cmd_lower = clean_text.lower()

        # Detect ! prefix
        if clean_text.startswith('!'):
            cmd_name = clean_text[1:].strip().lower()

            # If menu command, directly trigger Block Kit menu (don't forward to Router)
            if cmd_name in ['menu', 'start', 'menu']:
                self.send_menu_blocks(channel_id)
                return

            command = "/" + clean_text[1:].strip()
            logger.info(f"[Slack] Detected ! prefix converted to: {command}")
            self.forward_to_router(user_id, "CommandExecutor", channel_id, command, event)
            return

        # 3. Handle specific shortcut commands (no prefix version)
        if cmd_lower in ['menu', 'menu']:
            self.send_menu_blocks(channel_id)
            return

        # Check user authorization
        if self.authorized_users and user_id not in self.authorized_users:
            logger.warning(f"[Slack] Intercepted unauthorized user message: {user_id}")
            return

        # Get username
        try:
            user_info = self.web_client.users_info(user=user_id)
            username = user_info.get("user", {}).get("real_name", user_id)
        except Exception as e:
            username = user_id

        logger.info(f"[Slack] Received message: {username} in #{channel_id}")

        # Forward to Router
        self.forward_to_router(user_id, username, channel_id, text, event)

    def send_menu_blocks(self, channel_id: str):
        """Send Slack Block Kit menu"""
        menu_config = self.config.get('menu', [])
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "🎮 *OctoMatrix System Control Menu*\nSelect buttons below to execute operations:"
                }
            }
        ]

        # Collect all command buttons
        action_elements = []
        for row in menu_config:
            for item in row:
                label = item.get('label') if isinstance(item, dict) else item
                command = item.get('command') if isinstance(item, dict) else label

                # Add all commands as buttons (including {input} type commands that will trigger Modal)
                action_elements.append({
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": str(label),
                        "emoji": True
                    },
                    "value": command,
                    "action_id": f"mc_cmd_{label}"
                })

        # Group into Actions Blocks (max 5 per group)
        for i in range(0, len(action_elements), 5):
            blocks.append({
                "type": "actions",
                "elements": action_elements[i:i+5]
            })

        try:
            self.web_client.chat_postMessage(
                channel=channel_id,
                text="🎮 OctoMatrix System Control Menu",
                blocks=blocks
            )
        except Exception as e:
            logger.error(f"[Slack] Failed to send menu: {e}")

    def get_current_agent(self) -> str:
        """Ask Router for current active Agent"""
        try:
            status_url = f"http://{ROUTER_HOST}:{ROUTER_PORT}/status"
            resp = requests.get(status_url, timeout=3)
            if resp.status_code == 200:
                return resp.json().get('current_agent', 'Aleister')
        except: pass
        return 'Aleister'

    def forward_to_router(self, user_id: str, username: str, channel_id: str,
                         text: str, event: Dict[str, Any]):
        """
        Synchronously forward messages to Router with multimedia attachment support
        """
        try:
            content = text
            metadata = {
                'channel_id': channel_id,
                'ts': event.get('ts'),
                'team_id': event.get('team'),
                'event_ts': event.get('event_ts'),
                'platform_timestamp': datetime.now().isoformat()
            }

            # 📸 Handle attachments (Slack files)
            files = event.get('files', [])
            if files:
                current_agent = self.get_current_agent()
                file_info = files[0] # Get first attachment
                local_path = image_manager.download_slack_file(file_info, current_agent)

                if local_path:
                    metadata['file_type'] = 'image' if 'image' in file_info.get('mimetype', '') else 'file'
                    metadata['local_path'] = local_path

                    if not content or content.strip() == "":
                        content = f"Please process this file, path: {local_path}"
                    else:
                        content = f"{content}\n\n[Attachment downloaded to: {local_path}]"

            payload = {
                'source': 'slack',
                'user_id': user_id,
                'username': username,
                'content': content,
                'metadata': metadata
            }

            resp = requests.post(
                self.router_url,
                json=payload,
                timeout=5
            )

            if resp.status_code == 200:
                logger.info(f"[Slack] ✅ Message (with attachment) forwarded to Router (From: {username})")
            else:
                logger.error(f"[Slack] ❌ Router response error (Status: {resp.status_code})")

        except requests.Timeout:
            logger.error("[Slack] Forwarding timeout (Router may not be ready)")
        except Exception as e:
            logger.error(f"[Slack] Forwarding error: {e}")

    def start(self):
        """Start Socket Mode listening"""
        logger.info("[Slack] Connecting to Slack...")
        self.socket_client.connect()
        # Keep listening (Keep alive)
        while True:
            time.sleep(1)


# ============================================================================
# Main Program
# ============================================================================

def main():
    """Main entry point"""

    # Check Tokens
    if not SLACK_APP_TOKEN:
        logger.error("[Slack] SLACK_APP_TOKEN not configured")
        sys.exit(1)
    if not SLACK_BOT_TOKEN:
        logger.error("[Slack] SLACK_BOT_TOKEN not configured")
        sys.exit(1)

    # Load configuration
    config = load_config()

    # Create Gateway instance
    gateway = SlackSocketGateway(config)

    logger.info("=" * 60)
    logger.info("📲 Slack Socket Mode Gateway Starting")
    logger.info("=" * 60)
    logger.info(f"[Slack] Connecting to Router: {ROUTER_HOST}:{ROUTER_PORT}")

    try:
        gateway.start()
    except KeyboardInterrupt:
        logger.info("[Slack] Received interrupt signal, shutting down...")
        gateway.socket_client.close()
    except Exception as e:
        logger.error(f"[Slack] Fatal exception: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
