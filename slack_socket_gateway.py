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
Slack Socket Mode 監聽與消息轉發

職責：
1. 建立 Slack Socket Mode 連線（無需公網 Webhook）
2. 監聽指定頻道的消息
3. 轉換為統一格式並發送至 Router
4. 處理 Slack 特定的事件與授權

技術棧：
- slack_sdk.socket_mode: Socket Mode 連線
- requests: 同步 POST 請求轉發至 Router

優勢：
- 無需公網 Webhook，安全性更高
- 直接透過 WebSocket 內部隧道通訊
- 支援雙向消息流
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
# 配置與日誌
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

# Slack 配置
SLACK_APP_TOKEN = os.getenv('SLACK_APP_TOKEN')  # xapp-... 開頭
SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')   # xoxb-... 開頭
ROUTER_HOST = os.getenv('ROUTER_HOST', 'localhost')
ROUTER_PORT = int(os.getenv('ROUTER_PORT', 12210))

# ============================================================================
# 配置加載
# ============================================================================

def load_config() -> dict:
    """加載統一配置"""
    try:
        from config import _config
        logger.info(f"[Slack] 統一配置已加載")
        return _config
    except Exception as e:
        logger.error(f"[Slack] 配置加載失敗: {e}")
        return {}


# ============================================================================
# 多媒體管理
# ============================================================================

class ImageManager:
    """圖片管理員：負責從 Slack 下載檔案（需處理驗證）"""
    def __init__(self, base_dir):
        self.base_dir = base_dir

    def download_slack_file(self, file_info: dict, agent_name: str):
        try:
            agent_img_dir = os.path.join(self.base_dir, 'agent_home', agent_name, 'downloads_temp')
            os.makedirs(agent_img_dir, exist_ok=True)

            url = file_info.get('url_private')
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_info.get('name')}"
            local_path = os.path.join(agent_img_dir, filename)

            # 🔐 關鍵：下載 Slack 私有檔案需附上 Bot Token
            headers = {'Authorization': f'Bearer {SLACK_BOT_TOKEN}'}
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                with open(local_path, 'wb') as f:
                    f.write(resp.content)
                logger.info(f"📸 Slack 圖片已下載至 [{agent_name}]: {local_path}")
                return local_path
            else:
                logger.error(f"❌ Slack 下載失敗 (Status: {resp.status_code})")
                return None
        except Exception as e:
            logger.error(f"❌ Slack 圖片下載失敗: {e}")
            return None

image_manager = ImageManager(os.path.dirname(os.path.abspath(__file__)))

# ============================================================================
# Slack Socket Mode Gateway
# ============================================================================

class SlackSocketGateway:
    """
    Slack Socket Mode 監聽與轉發

    流程：
    1. 建立 Socket Mode 連線
    2. 接收 message 事件
    3. 驗證授權（頻道 + 用戶）
    4. 轉換為 MCMessage 格式
    5. 同步 POST 至 Router /inject 端點
    """

    def __init__(self, config: dict):
        self.config = config
        self.router_url = f"http://{ROUTER_HOST}:{ROUTER_PORT}/inject"

        # Slack 客戶端
        self.web_client = WebClient(token=SLACK_BOT_TOKEN)
        self.socket_client = SocketModeClient(
            app_token=SLACK_APP_TOKEN,
            trace_enabled=False
        )

        # 授權設定
        self.authorized_channels: Set[str] = set()
        self.authorized_users: Set[str] = set()
        self._load_auth_from_config()

        # 事件處理器
        self.socket_client.socket_mode_request_listeners.append(self.handle_event)

        logger.info(f"[Slack] Gateway 已初始化")
        logger.info(f"[Slack] 授權頻道: {self.authorized_channels}")
        logger.info(f"[Slack] 授權用戶: {self.authorized_users}")

    def _load_auth_from_config(self):
        """從配置文件加載授權頻道和用戶"""
        slack_config = self.config.get('CHANNELS', {}).get('slack', {})

        if 'authorized_channels' in slack_config:
            self.authorized_channels = set(slack_config['authorized_channels'])

        if 'authorized_users' in slack_config:
            self.authorized_users = set(slack_config['authorized_users'])

        # 獲取 Bot 自身信息以防止迴圈
        try:
            auth_test = self.web_client.auth_test()
            self.bot_user_id = auth_test.get("user_id")
            logger.info(f"[Slack] Bot User ID 已確認: {self.bot_user_id}")
        except Exception as e:
            logger.error(f"[Slack] 無法獲取 Bot 資訊: {e}")
            self.bot_user_id = None

    def handle_event(self, client: SocketModeClient, req: SocketModeRequest):
        """
        Socket Mode 事件處理器
        """
        try:
            # 立即確認事件接收
            response = SocketModeResponse(envelope_id=req.envelope_id)
            client.send_socket_mode_response(response)

            # 1. 處理標準事件 (如消息)
            if req.type == "events_api":
                event = req.payload.get("event", {})
                event_type = event.get("type")

                if event_type == "message":
                    self.handle_message(event)
                elif event_type == "app_mention":
                    self.handle_message(event)
            
            # 2. 處理交互式組件 (如按鈕點擊)
            elif req.type == "interactive":
                payload = req.payload
                
                # 處理按鈕點擊
                if payload.get("type") == "block_actions":
                    self.handle_interactive(payload)
                
                # 處理 Modal 提交
                elif payload.get("type") == "view_submission":
                    self.handle_modal_submission(payload)

        except Exception as e:
            logger.error(f"[Slack] 事件處理異常: {e}")

    def handle_modal_submission(self, payload: Dict[str, Any]):
        """處理 Slack Modal 提交"""
        view = payload.get("view", {})
        private_metadata = view.get("private_metadata", "")
        if not private_metadata:
            return
            
        try:
            metadata = json.loads(private_metadata)
            command_template = metadata.get("command_template")
            label = metadata.get("label")
            channel_id = metadata.get("channel_id")
            
            # 獲取用戶輸入的值
            state_values = view.get("state", {}).get("values", {})
            user_input = ""
            for block_id, actions in state_values.items():
                if "input_action" in actions:
                    user_input = actions["input_action"].get("value", "")
                    break
            
            if not user_input:
                return
                
            # 格式化指令
            final_cmd = command_template.replace('{input}', user_input)
            user_id = payload.get("user", {}).get("id")
            username = payload.get("user", {}).get("name", user_id)
            
            logger.info(f"[Slack] Modal 提交: {final_cmd} (From: {username})")
            
            # 轉發至 Router
            self.forward_to_router(user_id, username, channel_id, final_cmd, payload)
            
        except Exception as e:
            logger.error(f"[Slack] Modal 處理異常: {e}")

    def handle_interactive(self, payload: Dict[str, Any]):
        """處理按鈕點擊等交互事件"""
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
            
            # 判斷是否需要彈出 Modal
            if '{input}' in cmd:
                self.open_input_modal(trigger_id, label, cmd, channel_id)
                return
            
            logger.info(f"[Slack] 按鈕點擊: {cmd} (From: {username})")
            
            # 轉發至 Router
            self.forward_to_router(user_id, username, channel_id, cmd, payload)

    def open_input_modal(self, trigger_id: str, label: str, command_template: str, channel_id: str):
        """開啟 Slack 參數輸入 Modal"""
        try:
            view = {
                "type": "modal",
                "title": {"type": "plain_text", "text": f"指令輸入: {label}"},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "input_block",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "input_action",
                            "placeholder": {"type": "plain_text", "text": "例如: Gupa"}
                        },
                        "label": {"type": "plain_text", "text": f"請輸入 {label} 參數"}
                    }
                ],
                "submit": {"type": "plain_text", "text": "執行"},
                "close": {"type": "plain_text", "text": "取消"},
                "private_metadata": json.dumps({
                    "command_template": command_template,
                    "label": label,
                    "channel_id": channel_id
                })
            }
            
            self.web_client.views_open(trigger_id=trigger_id, view=view)
        except Exception as e:
            logger.error(f"[Slack] 開啟 Modal 失敗: {e}")

    def handle_message(self, event: Dict[str, Any]):
        """
        處理 Slack 消息事件
        """
        # 忽略子類型消息（bot 消息等）
        if event.get("subtype") in ["bot_message", "message_deleted"]:
            return

        # 提取基本信息
        user_id = event.get("user")
        bot_id = event.get("bot_id")
        channel_id = event.get("channel")
        text = event.get("text", "")

        # 1. 徹底過濾 Bot 自身消息
        if user_id == self.bot_user_id or bot_id is not None:
            return

        # 2. 處理選單指令與自定義前綴 (Slack 專用: ! 作為指令引導)
        clean_text = text.strip()
        cmd_lower = clean_text.lower()
        
        # 偵測 ! 前綴
        if clean_text.startswith('!'):
            cmd_name = clean_text[1:].strip().lower()
            
            # 若為選單類指令，直接觸發 Block Kit 選單 (不轉發給 Router)
            if cmd_name in ['menu', 'start', '菜單']:
                self.send_menu_blocks(channel_id)
                return
                
            command = "/" + clean_text[1:].strip()
            logger.info(f"[Slack] 偵測到指令前綴 ! 轉換為: {command}")
            self.forward_to_router(user_id, "CommandExecutor", channel_id, command, event)
            return

        # 3. 處理特定快捷指令 (無前綴版本)
        if cmd_lower in ['menu', '菜單']:
            self.send_menu_blocks(channel_id)
            return

        # 檢查用戶授權
        if self.authorized_users and user_id not in self.authorized_users:
            logger.warning(f"[Slack] 攔截未授權用戶消息: {user_id}")
            return

        # 獲取用戶名
        try:
            user_info = self.web_client.users_info(user=user_id)
            username = user_info.get("user", {}).get("real_name", user_id)
        except Exception as e:
            username = user_id

        logger.info(f"[Slack] 接收消息: {username} in #{channel_id}")

        # 轉發至 Router
        self.forward_to_router(user_id, username, channel_id, text, event)

    def send_menu_blocks(self, channel_id: str):
        """發送 Slack Block Kit 選單"""
        menu_config = self.config.get('menu', [])
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "🎮 *OctoMatrix  系統控制選單*\n請點選以下按鈕執行操作："
                }
            }
        ]
        
        # 收集所有指令按鈕
        action_elements = []
        for row in menu_config:
            for item in row:
                label = item.get('label') if isinstance(item, dict) else item
                command = item.get('command') if isinstance(item, dict) else label
                
                # 所有指令都加入按鈕 (含 {input} 類指令，將觸發 Modal)
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
        
        # 分組放入 Actions Block (每組最多 5 個)
        for i in range(0, len(action_elements), 5):
            blocks.append({
                "type": "actions",
                "elements": action_elements[i:i+5]
            })
            
        try:
            self.web_client.chat_postMessage(
                channel=channel_id,
                text="🎮 OctoMatrix  系統控制選單",
                blocks=blocks
            )
        except Exception as e:
            logger.error(f"[Slack] 發送選單失敗: {e}")

    def get_current_agent(self) -> str:
        """向 Router 詢問當前活躍 Agent"""
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
        同步轉發消息至 Router，支援多媒體附件處理
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

            # 📸 處理附件 (Slack files)
            files = event.get('files', [])
            if files:
                current_agent = self.get_current_agent()
                file_info = files[0] # 取第一個附件
                local_path = image_manager.download_slack_file(file_info, current_agent)
                
                if local_path:
                    metadata['file_type'] = 'image' if 'image' in file_info.get('mimetype', '') else 'file'
                    metadata['local_path'] = local_path
                    
                    if not content or content.strip() == "":
                        content = f"請處理這個檔案，路徑位於: {local_path}"
                    else:
                        content = f"{content}\n\n[附件已下載至: {local_path}]"

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
                logger.info(f"[Slack] ✅ 消息(含附件)已轉發至 Router (From: {username})")
            else:
                logger.error(f"[Slack] ❌ Router 回應異常 (Status: {resp.status_code})")

        except requests.Timeout:
            logger.error("[Slack] 轉發超時（Router 可能未就緒）")
        except Exception as e:
            logger.error(f"[Slack] 轉發異常: {e}")

    def start(self):
        """啟動 Socket Mode 監聽"""
        logger.info("[Slack] 正在連線至 Slack...")
        self.socket_client.connect()
        # 持續監聽 (Keep alive)
        while True:
            time.sleep(1)


# ============================================================================
# 主程序
# ============================================================================

def main():
    """主入口點"""

    # 檢查 Token
    if not SLACK_APP_TOKEN:
        logger.error("[Slack] SLACK_APP_TOKEN 未配置")
        sys.exit(1)
    if not SLACK_BOT_TOKEN:
        logger.error("[Slack] SLACK_BOT_TOKEN 未配置")
        sys.exit(1)

    # 加載配置
    config = load_config()

    # 建立 Gateway 實例
    gateway = SlackSocketGateway(config)

    logger.info("=" * 60)
    logger.info("📲 Slack Socket Mode Gateway 啟動")
    logger.info("=" * 60)
    logger.info(f"[Slack] 連接至 Router: {ROUTER_HOST}:{ROUTER_PORT}")

    try:
        gateway.start()
    except KeyboardInterrupt:
        logger.info("[Slack] 收到中斷信號，正在關閉...")
        gateway.socket_client.close()
    except Exception as e:
        logger.error(f"[Slack] 致命異常: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
