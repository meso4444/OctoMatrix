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
Discord WebSocket 監聽與消息轉發

職責：
1. 建立 Discord WebSocket 持續連線
2. 過濾並監聽指定頻道的消息
3. 轉換為統一格式並發送至 Router
4. 處理 Discord 特定的事件與異常

技術棧：
- discord.py: WebSocket 連線與事件處理
- aiohttp: 非同步 POST 請求轉發至 Router
"""

import os
import sys
import json
import asyncio
import logging
from typing import Optional, Set
from datetime import datetime

import discord
from discord.ext import commands
import aiohttp
import yaml

# ============================================================================
# 配置與日誌
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

# Discord 配置
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
ROUTER_HOST = os.getenv('ROUTER_HOST', 'localhost')
ROUTER_PORT = int(os.getenv('ROUTER_PORT', 12210))

# ============================================================================
# 配置加載
# ============================================================================

def load_config() -> dict:
    """加載統一配置"""
    try:
        from config import _config
        logger.info(f"[Discord] 統一配置已加載")
        return _config
    except Exception as e:
        logger.error(f"[Discord] 配置加載失敗: {e}")
        return {}


# ============================================================================
# 多媒體管理
# ============================================================================

class ImageManager:
    """圖片管理員：非同步下載 Discord 附件"""
    def __init__(self, base_dir):
        self.base_dir = base_dir

    async def download_discord_attachment(self, attachment: discord.Attachment, agent_name: str):
        try:
            agent_img_dir = os.path.join(self.base_dir, 'agent_home', agent_name, 'downloads_temp')
            os.makedirs(agent_img_dir, exist_ok=True)

            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{attachment.filename}"
            local_path = os.path.join(agent_img_dir, filename)

            await attachment.save(local_path)
            logger.info(f"📸 Discord 圖片已下載至 [{agent_name}]: {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"❌ Discord 圖片下載失敗: {e}")
            return None

image_manager = ImageManager(os.path.dirname(os.path.abspath(__file__)))

# ============================================================================
# Discord 交互式組件 (UI Components)
# ============================================================================

class InputCommandModal(discord.ui.Modal):
    """處理需要輸入參數的指令 (如 /switch {input})"""
    def __init__(self, gateway: 'DiscordGateway', label: str, command_template: str):
        super().__init__(title=f"指令輸入: {label}")
        self.gateway = gateway
        self.command_template = command_template
        
        # 動態建立輸入框
        self.user_input = discord.ui.TextInput(
            label=f"請輸入 {label} 參數",
            placeholder="例如: Gupa",
            min_length=1,
            max_length=50
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        # 格式化指令
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
                        logger.info(f"[Discord] Modal 指令已轉發: {final_cmd}")
                    else:
                        logger.error(f"[Discord] Router 回應異常: {resp.status}")
        except Exception as e:
            logger.error(f"[Discord] Modal 轉發異常: {e}")

class MenuButtonView(discord.ui.View):
    """Discord 管理選單按鈕視圖"""
    def __init__(self, gateway: 'DiscordGateway', author_id: int):
        super().__init__(timeout=60) # 60秒後失效
        self.gateway = gateway
        self.author_id = author_id
        self._add_buttons()

    def _add_buttons(self):
        """從配置動態生成按鈕"""
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
                
                # 綁定回調
                async def callback(interaction: discord.Interaction, lbl=label, cmd=command):
                    if interaction.user.id != self.author_id:
                        await interaction.response.send_message("❌ 您無權操作此選單", ephemeral=True)
                        return
                    
                    # 判斷是否需要彈出輸入框
                    if '{input}' in cmd:
                        modal = InputCommandModal(self.gateway, lbl, cmd)
                        await interaction.response.send_modal(modal)
                        return

                    # 模擬一條來自用戶的消息發送給 Router
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
                    
                    await interaction.response.defer() # 防止超時
                    
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(self.gateway.router_url, json=payload, timeout=5) as resp:
                                if resp.status == 200:
                                    logger.info(f"[Discord] 按鈕點擊已轉發: {cmd}")
                                else:
                                    logger.error(f"[Discord] Router 回應異常: {resp.status}")
                    except Exception as e:
                        logger.error(f"[Discord] 按鈕轉發異常: {e}")

                button.callback = callback
                self.add_item(button)

# ============================================================================
# Discord Gateway Client
# ============================================================================

class DiscordGateway(commands.Cog):
    """
    Discord WebSocket 監聽與轉發

    流程：
    1. 接收 on_message 事件
    2. 過濾 Bot 自身消息 + 檢查頻道授權
    3. 轉換為 MCMessage 格式
    4. 非同步 POST 至 Router /inject 端點
    """

    def __init__(self, bot: commands.Bot, config: dict):
        self.bot = bot
        self.config = config
        self.router_url = f"http://{ROUTER_HOST}:{ROUTER_PORT}/inject"

        # 提取授權頻道和用戶
        self.authorized_channels: Set[int] = set()
        self.authorized_users: Set[int] = set()
        self._load_auth_from_config()

        logger.info(f"[Discord] Gateway 已初始化")
        logger.info(f"[Discord] 授權頻道: {self.authorized_channels}")
        logger.info(f"[Discord] 授權用戶: {self.authorized_users}")

    def _load_auth_from_config(self):
        """從配置文件加載授權頻道和用戶"""
        discord_config = self.config.get('CHANNELS', {}).get('discord', {})

        if 'authorized_channels' in discord_config:
            self.authorized_channels = set(discord_config['authorized_channels'])

        if 'authorized_users' in discord_config:
            self.authorized_users = set(discord_config['authorized_users'])

        # 默認值：若無配置，且 admin_ids 僅包含佔位符，則不限制用戶 (便於 Dev 測試)
        if not self.authorized_users:
            admin_ids = self.config.get('admin_ids', [])
            # 只有當 admin_ids 包含真正的 ID (數字或非 admin 結尾字串) 時才限制
            real_admins = [uid for uid in admin_ids if isinstance(uid, int) or (isinstance(uid, str) and not uid.endswith('admin'))]
            if real_admins:
                self.authorized_users = set(real_admins)
            else:
                logger.warning("[Discord] 未偵測到有效管理員 ID，將允許所有用戶訪問 (Dev 模式模式)")
                self.authorized_users = set()

    async def get_current_agent(self) -> str:
        """向 Router 詢問當前活躍 Agent"""
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
        非同步轉發消息至 Router，支援附件處理
        """
        try:
            content = message.content
            metadata = {
                'guild_id': str(message.guild.id) if message.guild else None,
                'channel_id': str(message.channel.id),
                'message_id': str(message.id),
                'platform_timestamp': message.created_at.isoformat()
            }

            # 📸 處理附件
            if message.attachments:
                current_agent = await self.get_current_agent()
                attachment = message.attachments[0] # 取第一個
                local_path = await image_manager.download_discord_attachment(attachment, current_agent)
                
                if local_path:
                    metadata['file_type'] = 'image' if attachment.content_type and 'image' in attachment.content_type else 'file'
                    metadata['local_path'] = local_path
                    
                    if not content: # 如果只有圖片沒有文字
                        content = f"請處理這個檔案，路徑位於: {local_path}"
                    else:
                        content = f"{content}\n\n[附件已下載至: {local_path}]"

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
                        logger.info(f"[Discord] ✅ 消息(含附件)已轉發至 Router (From: {message.author.name})")
                    else:
                        logger.error(f"[Discord] ❌ Router 回應異常 (Status: {resp.status})")

        except asyncio.TimeoutError:
            logger.error("[Discord] 轉發超時（Router 可能未就緒）")
        except Exception as e:
            logger.error(f"[Discord] 轉發異常: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Bot 連線成功事件"""
        logger.info(f"[Discord] ✅ 已連線為 {self.bot.user}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        消息監聽事件
        """
        # 1. 忽略機器人自身的訊息 (防止無限迴圈)
        if message.author == self.bot.user or message.author.bot:
            return

        # 檢查頻道授權 (暫時停用以便 Debug)
        # if self.authorized_channels and message.channel.id not in self.authorized_channels:
        #     logger.debug(f"[Discord] 頻道未授權: {message.channel.id}")
        #     return

        # 檢查用戶授權
        if self.authorized_users and message.author.id not in self.authorized_users:
            logger.warning(f"[Discord] 攔截未授權用戶消息: {message.author.name} (ID: {message.author.id})")
            return

        logger.info(f"[Discord] 接收消息: {message.author.name} in #{message.channel.name}")

        # 2. 處理選單指令 (觸發按鈕視圖)
        clean_content = message.content.strip().lower()
        if clean_content in ['menu', '/menu', '菜單']:
            view = MenuButtonView(self, message.author.id)
            await message.channel.send("🎮 **OctoMatrix  系統控制選單**", view=view)
            return

        # 3. 轉發至 Router
        await self.forward_to_router(message)


# ============================================================================
# 主程序
# ============================================================================

async def main():
    """主入口點"""

    # 檢查 Token
    if not DISCORD_TOKEN:
        logger.error("[Discord] DISCORD_TOKEN 未配置")
        sys.exit(1)

    # 加載配置
    config = load_config()

    # 建立 Bot 實例
    intents = discord.Intents.default()
    intents.message_content = True  # 啟用消息內容讀取權限

    bot = commands.Bot(command_prefix='!', intents=intents)

    # 註冊 Cog
    await bot.add_cog(DiscordGateway(bot, config))

    # 啟動 Bot
    logger.info("=" * 60)
    logger.info("🎮 Discord Gateway 啟動")
    logger.info("=" * 60)
    logger.info(f"[Discord] 連接至 Router: {ROUTER_HOST}:{ROUTER_PORT}")

    try:
        async with bot:
            await bot.start(DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("[Discord] Token 無效或已過期")
        sys.exit(1)
    except Exception as e:
        logger.error(f"[Discord] 致命異常: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
