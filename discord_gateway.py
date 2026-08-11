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
🎮 Discord Gateway (discord_gateway.py)
Discord WebSocket listening and message forwarding

Responsibilities:
1. Establish Discord WebSocket persistent connection
2. Filter and listen to messages from specified channels
3. Convert to unified format and send to Router
4. Handle Discord-specific events and exceptions

Tech Stack:
- discord.py: WebSocket connection and event handling
- aiohttp: Asynchronous POST requests to Router
"""

import os
import sys
import json
import asyncio
import logging
from typing import Optional, Set
from datetime import datetime
from werkzeug.utils import secure_filename

import discord
from discord.ext import commands
import aiohttp
import yaml

# ============================================================================
# Configuration and Logging
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/tmp/discord_gateway.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Discord Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
ROUTER_HOST = os.getenv('ROUTER_HOST', 'localhost')
ROUTER_PORT = int(os.getenv('ROUTER_PORT', 12210))

# ============================================================================
# Configuration Loading
# ============================================================================

def load_config() -> dict:
    """Load unified configuration"""
    try:
        from config import _config
        logger.info(f"[Discord] Unified configuration loaded")
        return _config
    except Exception as e:
        logger.error(f"[Discord] Configuration loading failed: {e}")
        return {}


# ============================================================================
# Media Management
# ============================================================================

class ImageManager:
    """Image Manager: Asynchronously download Discord attachments"""
    def __init__(self, base_dir):
        self.base_dir = base_dir

    async def download_discord_attachment(self, attachment: discord.Attachment, agent_name: str):
        try:
            agent_img_dir = os.path.join(self.base_dir, 'agent_home', agent_name, 'downloads_temp')
            os.makedirs(agent_img_dir, exist_ok=True)

            # secure_filename strips all non-ASCII characters, so CJK filenames (e.g. "測試.jpg")
            # lose their extension entirely; split the extension off first and sanitize it
            # separately so path-traversal protection doesn't also destroy the extension
            orig_base, orig_ext = os.path.splitext(attachment.filename or '')
            safe_ext = ''.join(c for c in orig_ext if c.isalnum() or c == '.')[:10]
            safe_name = (secure_filename(orig_base) or 'attachment') + safe_ext
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}"
            local_path = os.path.join(agent_img_dir, filename)

            await attachment.save(local_path)
            logger.info(f"📸 Discord image downloaded to [{agent_name}]: {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"❌ Discord image download failed: {e}")
            return None

image_manager = ImageManager(os.path.dirname(os.path.abspath(__file__)))

# ============================================================================
# Discord Interactive Components (UI Components)
# ============================================================================

class InputCommandModal(discord.ui.Modal):
    """Handle commands requiring input parameters (e.g., /switch {input})"""
    def __init__(self, gateway: 'DiscordGateway', label: str, command_template: str):
        super().__init__(title=f"Command Input: {label}")
        self.gateway = gateway
        self.command_template = command_template

        # Dynamically create input field
        self.user_input = discord.ui.TextInput(
            label=f"Please enter {label} parameter",
            placeholder="e.g.: Gupa",
            min_length=1,
            max_length=50
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Format command
        final_cmd = self.command_template.replace('{input}', self.user_input.value)
        
        payload = {
            'source': 'discord',
            'user_id': str(interaction.user.id),
            'username': interaction.user.name,
            'content': final_cmd,
            'metadata': {
                'guild_id': str(interaction.guild.id) if interaction.guild else None,
                'channel_id': str(interaction.channel.id),
                'is_modal_submit': True
            }
        }
        
        await interaction.response.defer()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.gateway.router_url, json=payload, timeout=5) as resp:
                    if resp.status == 200:
                        logger.info(f"[Discord] Modal command forwarded: {final_cmd}")
                    else:
                        logger.error(f"[Discord] Router response error: {resp.status}")
        except Exception as e:
            logger.error(f"[Discord] Modal forwarding error: {e}")

class MenuButtonView(discord.ui.View):
    """Discord management menu button view"""
    def __init__(self, gateway: 'DiscordGateway', author_id: int):
        super().__init__(timeout=60) # Expires after 60 seconds
        self.gateway = gateway
        self.author_id = author_id
        self._add_buttons()

    def _add_buttons(self):
        """Dynamically generate buttons from configuration"""
        menu_config = self.gateway.config.get('menu', [])
        for row in menu_config:
            for item in row:
                label = item.get('label') if isinstance(item, dict) else item
                command = item.get('command') if isinstance(item, dict) else label
                
                button = discord.ui.Button(
                    label=str(label),
                    style=discord.ButtonStyle.primary if '{input}' not in command else discord.ButtonStyle.secondary,
                    custom_id=f"mc_cmd_{label}"
                )
                
                # Bind callback
                async def callback(interaction: discord.Interaction, lbl=label, cmd=command):
                    if interaction.user.id != self.author_id:
                        await interaction.response.send_message("❌ You don't have permission to operate this menu", ephemeral=True)
                        return

                    # Check if input field needs to pop up
                    if '{input}' in cmd:
                        modal = InputCommandModal(self.gateway, lbl, cmd)
                        await interaction.response.send_modal(modal)
                        return

                    # Simulate a message from user sent to Router
                    payload = {
                        'source': 'discord',
                        'user_id': str(interaction.user.id),
                        'username': interaction.user.name,
                        'content': cmd,
                        'metadata': {
                            'guild_id': str(interaction.guild.id) if interaction.guild else None,
                            'channel_id': str(interaction.channel.id),
                            'is_button_click': True
                        }
                    }

                    await interaction.response.defer() # Prevent timeout

                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(self.gateway.router_url, json=payload, timeout=5) as resp:
                                if resp.status == 200:
                                    logger.info(f"[Discord] Button click forwarded: {cmd}")
                                else:
                                    logger.error(f"[Discord] Router response error: {resp.status}")
                    except Exception as e:
                        logger.error(f"[Discord] Button forwarding error: {e}")

                button.callback = callback
                self.add_item(button)

# ============================================================================
# Discord Gateway Client
# ============================================================================

class DiscordGateway(commands.Cog):
    """
    Discord WebSocket listening and forwarding

    Process:
    1. Receive on_message event
    2. Filter Bot's own messages + check channel authorization
    3. Convert to MCMessage format
    4. Asynchronously POST to Router /inject endpoint
    """

    def __init__(self, bot: commands.Bot, config: dict):
        self.bot = bot
        self.config = config
        self.router_url = f"http://{ROUTER_HOST}:{ROUTER_PORT}/inject"

        # Extract authorized channels and users
        self.authorized_channels: Set[int] = set()
        self.authorized_users: Set[int] = set()
        self._load_auth_from_config()

        logger.info(f"[Discord] Gateway initialized")
        logger.info(f"[Discord] Authorized channels: {self.authorized_channels}")
        logger.info(f"[Discord] Authorized users: {self.authorized_users}")

    def _load_auth_from_config(self):
        """Load authorized channels and users from configuration file"""
        discord_config = self.config.get('CHANNELS', {}).get('discord', {})

        if 'authorized_channels' in discord_config:
            self.authorized_channels = set(discord_config['authorized_channels'])

        if 'authorized_users' in discord_config:
            self.authorized_users = set(discord_config['authorized_users'])

        # Default: If no configuration and admin_ids only contains placeholders, no user restrictions (for Dev testing)
        if not self.authorized_users:
            admin_ids = self.config.get('admin_ids', [])
            # Only restrict if admin_ids contains real IDs (numbers or non-admin ending strings)
            real_admins = [uid for uid in admin_ids if isinstance(uid, int) or (isinstance(uid, str) and not uid.endswith('admin'))]
            if real_admins:
                self.authorized_users = set(real_admins)
            else:
                logger.warning("[Discord] No valid admin ID detected, allowing all users (Dev Mode)")
                self.authorized_users = set()

    async def get_current_agent(self) -> str:
        """Ask Router for current active Agent"""
        try:
            status_url = f"http://{ROUTER_HOST}:{ROUTER_PORT}/status"
            async with aiohttp.ClientSession() as session:
                async with session.get(status_url, timeout=3) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('current_agent', 'Aleister')
        except: pass
        return 'Aleister'

    async def forward_to_router(self, message: discord.Message):
        """
        Asynchronously forward messages to Router with attachment support
        """
        try:
            content = message.content
            metadata = {
                'guild_id': str(message.guild.id) if message.guild else None,
                'channel_id': str(message.channel.id),
                'message_id': str(message.id),
                'platform_timestamp': message.created_at.isoformat()
            }

            # 📸 Handle attachments
            if message.attachments:
                current_agent = await self.get_current_agent()
                attachment = message.attachments[0] # Get first one
                local_path = await image_manager.download_discord_attachment(attachment, current_agent)

                if local_path:
                    metadata['file_type'] = 'image' if attachment.content_type and 'image' in attachment.content_type else 'file'
                    metadata['local_path'] = local_path

                    suffix = f"Please process this file, path: `{local_path}`"
                    content = f"{content}\n\n{suffix}" if content and content.strip() else suffix

            payload = {
                'source': 'discord',
                'user_id': str(message.author.id),
                'username': message.author.name,
                'content': content,
                'metadata': metadata
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.router_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"[Discord] ✅ Message (with attachment) forwarded to Router (From: {message.author.name})")
                    else:
                        logger.error(f"[Discord] ❌ Router response error (Status: {resp.status})")

        except asyncio.TimeoutError:
            logger.error("[Discord] Forwarding timeout (Router may not be ready)")
        except Exception as e:
            logger.error(f"[Discord] Forwarding error: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Bot connection successful event"""
        logger.info(f"[Discord] ✅ Connected as {self.bot.user}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Message listening event
        """
        # 1. Ignore bot's own messages (prevent infinite loop)
        if message.author == self.bot.user or message.author.bot:
            return

        # Channel authorization check (was left disabled after a debugging session; this
        # security re-audit found it was never re-enabled, restoring it now)
        if self.authorized_channels and message.channel.id not in self.authorized_channels:
            logger.debug(f"[Discord] Channel not authorized: {message.channel.id}")
            return

        # Check user authorization
        if self.authorized_users and message.author.id not in self.authorized_users:
            logger.warning(f"[Discord] Intercepted unauthorized user message: {message.author.name} (ID: {message.author.id})")
            return

        logger.info(f"[Discord] Received message: {message.author.name} in #{message.channel.name}")

        # 2. Handle menu command (trigger button view)
        clean_content = message.content.strip().lower()
        if clean_content in ['menu', '/menu', 'menu']:
            view = MenuButtonView(self, message.author.id)
            await message.channel.send("🎮 **OctoMatrix System Control Menu**", view=view)
            return

        # 3. Forward to Router
        await self.forward_to_router(message)


# ============================================================================
# Main Program
# ============================================================================

async def main():
    """Main entry point"""

    # Check Token
    if not DISCORD_TOKEN:
        logger.error("[Discord] DISCORD_TOKEN not configured")
        sys.exit(1)

    # Load configuration
    config = load_config()

    # Create Bot instance
    intents = discord.Intents.default()
    intents.message_content = True  # Enable message content reading permission

    bot = commands.Bot(command_prefix='!', intents=intents)

    # Register Cog
    await bot.add_cog(DiscordGateway(bot, config))

    # Start Bot
    logger.info("=" * 60)
    logger.info("🎮 Discord Gateway Starting")
    logger.info("=" * 60)
    logger.info(f"[Discord] Connecting to Router: {ROUTER_HOST}:{ROUTER_PORT}")

    try:
        async with bot:
            await bot.start(DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("[Discord] Token invalid or expired")
        sys.exit(1)
    except Exception as e:
        logger.error(f"[Discord] Fatal exception: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
